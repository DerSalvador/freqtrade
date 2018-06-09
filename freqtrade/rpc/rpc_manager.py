"""
This module contains class to manage RPC communications (Telegram, Slack, ...)
"""
import logging
from typing import List

from freqtrade.rpc.rpc import RPC

logger = logging.getLogger(__name__)


class RPCManager(object):
    """
    Class to manage RPC objects (Telegram, Slack, ...)
    """
    def __init__(self, freqtrade) -> None:
        """ Initializes all enabled rpc modules """
        self.registered_modules: List[RPC] = []

        # Enable telegram
        if freqtrade.config['telegram'].get('enabled', False):
            logger.info('Enabling rpc.telegram ...')
            from freqtrade.rpc.telegram import Telegram
            self.registered_modules.append(Telegram(freqtrade))

    def cleanup(self) -> None:
        """ Stops all enabled rpc modules """
        logger.info('Cleaning up rpc modules ...')
        while self.registered_modules:
            mod = self.registered_modules.pop()
            logger.debug('Cleaning up rpc.%s ...', mod.name)
            mod.cleanup()
            del mod

    def send_msg(self, msg: str) -> None:
        """
        Send given markdown message to all registered rpc modules
        :param msg: message
        :return: None
        """
        logger.info('Sending rpc message: %s', msg)
        for mod in self.registered_modules:
            logger.debug('Forwarding message to rpc.%s', mod.name)
            mod.send_msg(msg)
