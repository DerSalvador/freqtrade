import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Type, Union
from uuid import uuid4

from freqtrade.rpc.api_server.ws.proxy import WebSocketProxy
from freqtrade.rpc.api_server.ws.serializer import (HybridJSONWebSocketSerializer,
                                                    WebSocketSerializer)
from freqtrade.rpc.api_server.ws.types import WebSocketType
from freqtrade.rpc.api_server.ws_schemas import WSMessageSchemaType


logger = logging.getLogger(__name__)


class WebSocketChannel:
    """
    Object to help facilitate managing a websocket connection
    """
    def __init__(
        self,
        websocket: WebSocketType,
        channel_id: Optional[str] = None,
        serializer_cls: Type[WebSocketSerializer] = HybridJSONWebSocketSerializer
    ):
        self.channel_id = channel_id if channel_id else uuid4().hex[:8]
        self._websocket = WebSocketProxy(websocket)

        # Internal event to signify a closed websocket
        self._closed = asyncio.Event()
        self._send_timeout_high_limit = 2

        # The subscribed message types
        self._subscriptions: List[str] = []

        # Wrap the WebSocket in the Serializing class
        self._wrapped_ws = serializer_cls(self._websocket)

        # The async tasks created for the channel
        self._channel_tasks: List[asyncio.Task] = []

    def __repr__(self):
        return f"WebSocketChannel({self.channel_id}, {self.remote_addr})"

    @property
    def raw_websocket(self):
        return self._websocket.raw_websocket

    @property
    def remote_addr(self):
        return self._websocket.remote_addr

    async def send(self, message: Union[WSMessageSchemaType, Dict[str, Any]]):
        """
        Send a message on the wrapped websocket
        """
        await self._wrapped_ws.send(message)

        # Without this sleep, messages would send to one channel
        # first then another after the first one finished and prevent
        # any normal Rest API calls from processing at the same time.
        # With the sleep call, it gives control to the event
        # loop to schedule other channel send methods, and helps
        # throttle how fast we send.
        # 0.01 = 100 messages/second max throughput
        await asyncio.sleep(0.01)

    async def recv(self):
        """
        Receive a message on the wrapped websocket
        """
        return await self._wrapped_ws.recv()

    async def ping(self):
        """
        Ping the websocket
        """
        return await self._websocket.ping()

    async def accept(self):
        """
        Accept the underlying websocket connection
        """
        return await self._websocket.accept()

    async def close(self):
        """
        Close the WebSocketChannel
        """

        self._closed.set()

        try:
            await self._websocket.close()
        except Exception:
            pass

    def is_closed(self) -> bool:
        """
        Closed flag
        """
        return self._closed.is_set()

    def set_subscriptions(self, subscriptions: List[str] = []) -> None:
        """
        Set which subscriptions this channel is subscribed to

        :param subscriptions: List of subscriptions, List[str]
        """
        self._subscriptions = subscriptions

    def subscribed_to(self, message_type: str) -> bool:
        """
        Check if this channel is subscribed to the message_type

        :param message_type: The message type to check
        """
        return message_type in self._subscriptions

    async def run_channel_tasks(self, *tasks, **kwargs):
        """
        Create and await on the channel tasks unless an exception
        was raised, then cancel them all.

        :params *tasks: All coros or tasks to be run concurrently
        :param **kwargs: Any extra kwargs to pass to gather
        """

        # Wrap the coros into tasks if they aren't already
        self._channel_tasks = [
            task if isinstance(task, asyncio.Task) else asyncio.create_task(task)
            for task in tasks
        ]

        try:
            return await asyncio.gather(*self._channel_tasks, **kwargs)
        except Exception:
            # If an exception occurred, cancel the rest of the tasks
            await self.cancel_channel_tasks()

    async def cancel_channel_tasks(self):
        """
        Cancel and wait on all channel tasks
        """
        for task in self._channel_tasks:
            task.cancel()

        # Wait for tasks to finish cancelling
        try:
            await asyncio.wait(self._channel_tasks)
        except asyncio.CancelledError:
            pass

        self._channel_tasks = []

    async def __aiter__(self):
        """
        Generator for received messages
        """
        # We can not catch any errors here as websocket.recv is
        # the first to catch any disconnects and bubble it up
        # so the connection is garbage collected right away
        while not self.is_closed():
            yield await self.recv()


@asynccontextmanager
async def create_channel(websocket: WebSocketType, **kwargs):
    """
    Context manager for safely opening and closing a WebSocketChannel
    """
    channel = WebSocketChannel(websocket, **kwargs)
    try:
        await channel.accept()
        logger.info(f"Connected to channel - {channel}")

        yield channel
    finally:
        await channel.close()
        logger.info(f"Disconnected from channel - {channel}")
