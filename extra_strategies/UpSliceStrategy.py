# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa

class UpSliceStrategy(IStrategy):
    INTERFACE_VERSION = 3
    '\n    Strategy 002\n    author@: Gerald Lonlas\n    github@: https://github.com/freqtrade/freqtrade-strategies\n\n    How to use it?\n    > python3 ./freqtrade/main.py -s Strategy002\n    '
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    # 5% after 240 min
    # 8% imidietly
    minimal_roi = {'240': 0.05, '300': 0.03, '360': 0.0, '0': 0.08}
    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.1
    # Optimal timeframe for the strategy
    timeframe = '5m'
    # trailing stoploss
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.03
    # run "populate_indicators" only for new candle
    process_only_new_candles = False
    # Experimental settings (configuration will overide these if set)
    # use_exit_signal = True
    # exit_profit_only = True
    # ignore_roi_if_entry_signal = False
    # Optional order type mapping
    order_types = {'entry': 'market', 'exit': 'market', 'stoploss': 'market', 'stoploss_on_exchange': True}

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        """
        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """  # Guard: tema is raising
        # Make sure Volume is not 0
        dataframe.loc[(dataframe['close'] > dataframe['close'].shift(1)) & (dataframe['close'].shift > dataframe['close'].shift(2)) & (dataframe['tema'] > dataframe['tema'].shift(1)) & (dataframe['volume'] > 0), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """
        dataframe.loc[False, 'exit_long'] = 1
        return dataframe