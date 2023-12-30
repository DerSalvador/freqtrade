# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class ASDTSRockwellTrading(IStrategy):
    INTERFACE_VERSION = 3
    "\n    trading strategy based on the concept explained at https://www.youtube.com/watch?v=mmAWVmKN4J0\n    author@: Gert Wohlgemuth\n\n    idea:\n\n        uptrend definition:\n            MACD above 0 line AND above MACD signal\n\n\n        downtrend definition:\n            MACD below 0 line and below MACD signal\n\n        exit definition:\n            MACD below MACD signal\n\n    it's basically a very simple MACD based strategy and we ignore the definition of the entry and exit points in this case, since the trading bot, will take of this already\n\n    "
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {'60': 0.01, '30': 0.03, '20': 0.04, '0': 0.05}
    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.3
    # Optimal timeframe for the strategy
    timeframe = '5m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """
        dataframe.loc[(dataframe['macd'] > 0) & (dataframe['macd'] > dataframe['macdsignal']), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """
        dataframe.loc[dataframe['macd'] < dataframe['macdsignal'], 'exit_long'] = 1
        return dataframe