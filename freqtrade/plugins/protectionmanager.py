"""
Protection manager class
"""
import logging
from datetime import datetime
from typing import Dict, List

from freqtrade.exceptions import OperationalException
from freqtrade.plugins.protections import IProtection
from freqtrade.resolvers import ProtectionResolver


logger = logging.getLogger(__name__)


class ProtectionManager():

    def __init__(self, config: dict) -> None:
        self._config = config

        self._protection_handlers: List[IProtection] = []
        for protection_handler_config in self._config.get('protections', []):
            if 'method' not in protection_handler_config:
                logger.warning(f"No method found in {protection_handler_config}, ignoring.")
                continue
            protection_handler = ProtectionResolver.load_protection(
                protection_handler_config['method'],
                config=config,
                protection_config=protection_handler_config,
            )
            self._protection_handlers.append(protection_handler)

        if not self._protection_handlers:
            logger.info("No protection Handlers defined.")

    @property
    def name_list(self) -> List[str]:
        """
        Get list of loaded Protection Handler names
        """
        return [p.name for p in self._protection_handlers]

    def short_desc(self) -> List[Dict]:
        """
        List of short_desc for each Pairlist Handler
        """
        return [{p.name: p.short_desc()} for p in self._protection_handlers]

    def global_stop(self) -> bool:
        now = datetime.utcnow()

        for protection_handler in self._protection_handlers:
            result = protection_handler.global_stop(now)

            # Early stopping - first positive result stops the application
            if result:
                return True
        return False
