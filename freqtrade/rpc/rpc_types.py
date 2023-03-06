from datetime import datetime
from typing import List, Literal, Optional, TypedDict, Union

from freqtrade.enums import RPCMessageType


class RPCSendMsgBase(TypedDict):
    pass
    # ty1pe: Literal[RPCMessageType]


class RPCStatusMsg(RPCSendMsgBase):
    """Used for Status, Startup and Warning messages"""
    type: Literal[RPCMessageType.STATUS]
    status: str


class RPCProtectionMsg(RPCSendMsgBase):
    type: Literal[RPCMessageType.PROTECTION_TRIGGER, RPCMessageType.PROTECTION_TRIGGER_GLOBAL]
    id: int
    pair: str
    base_currency: Optional[str]
    lock_time: str
    lock_timestamp: int
    lock_end_time: str
    lock_end_timestamp: int
    reason: str
    side: str
    active: bool


class RPCWhitelistMsg(RPCSendMsgBase):
    type: Literal[RPCMessageType.WHITELIST]
    data: List[str]


class RPCBuyMsg(RPCSendMsgBase):
    type: Literal[RPCMessageType.ENTRY, RPCMessageType.ENTRY_FILL]
    trade_id: int
    buy_tag: Optional[str]
    enter_tag: Optional[str]
    exchange: str
    pair: str
    leverage: Optional[float]
    direction: str
    limit: float
    open_rate: float
    order_type: Optional[str]  # TODO: why optional??
    stake_amount: float
    stake_currency: str
    fiat_currency: Optional[str]
    amount: float
    open_date: datetime
    current_rate: Optional[float]
    sub_trade: bool


class RPCCancelMsg(RPCBuyMsg):
    type: Literal[RPCMessageType.ENTRY_CANCEL]
    reason: str


class RPCSellMsg(RPCBuyMsg):
    type: Literal[RPCMessageType.EXIT, RPCMessageType.EXIT_FILL]
    cumulative_profit: float
    gain: str  # Literal["profit", "loss"]
    close_rate: float
    profit_amount: float
    profit_ratio: float
    sell_reason: Optional[str]
    exit_reason: Optional[str]
    close_date: datetime
    # current_rate: Optional[float]
    order_rate: Optional[float]


class RPCSellCancelMsg(RPCBuyMsg):
    type: Literal[RPCMessageType.EXIT_CANCEL]
    reason: str
    gain: str  # Literal["profit", "loss"]
    profit_amount: float
    profit_ratio: float
    sell_reason: Optional[str]
    exit_reason: Optional[str]
    close_date: datetime


RPCSendMsg = Union[
    RPCStatusMsg,
    RPCProtectionMsg,
    RPCWhitelistMsg,
    RPCBuyMsg,
    RPCCancelMsg,
    RPCSellMsg,
    RPCSellCancelMsg
    ]
