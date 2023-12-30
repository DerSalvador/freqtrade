# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa

class FiveMinCrossAbove(IStrategy):
    INTERFACE_VERSION = 3
    '\n    Strategy 005\n    author@: Gerald Lonlas\n    github@: https://github.com/freqtrade/freqtrade-strategies\n\n    How to use it?\n    > python3 ./freqtrade/main.py -s Strategy005\n    '
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {'0': 0.015, '25': 0.01, '100': 0.005}
    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.99
    # Optimal timeframe for the strategy
    timeframe = '5m'
    # trailing stoploss
    # trailing_stop = True
    # trailing_stop_positive = 0.005
    # trailing_stop_positive_offset = 0.02
    # trailing_only_offset_is_reached = True
    # run "populate_indicators" only for new candle
    process_only_new_candles = False
    # Experimental settings (configuration will overide these if set)
    use_exit_signal = False
    exit_profit_only = True
    ignore_roi_if_entry_signal = False
    # Optional order type mapping
    order_types = {'entry': 'market', 'exit': 'market', 'stoploss': 'market', 'stoploss_on_exchange': False}

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
        # bollinger dataframe
        #bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        #dataframe['bb_lowerband'] = bollinger['lower']
        # RSI for last 8 candle
        dataframe['rsi8'] = ta.RSI(dataframe, timeperiod=8)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param metadata:
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """
        # Prod
        dataframe.loc[qtpylib.crossed_above(dataframe['rsi8'], 30) & (dataframe['rsi8'] < 41), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param metadata:
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """
        # Prod
        dataframe.loc[dataframe['close'] > 9999999999, 'exit_long'] = 1
        return dataframe