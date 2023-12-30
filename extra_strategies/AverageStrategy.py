# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class AverageStrategy(IStrategy):
    INTERFACE_VERSION = 3
    "\n\n    author@: Gert Wohlgemuth\n\n    idea:\n        entrys and exits on crossovers - doesn't really perfom that well and its just a proof of concept\n    "
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {'0': 0.5}
    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.2
    # Optimal timeframe for the strategy
    timeframe = '4h'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['maShort'] = ta.EMA(dataframe, timeperiod=8)
        dataframe['maMedium'] = ta.EMA(dataframe, timeperiod=21)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """
        dataframe.loc[qtpylib.crossed_above(dataframe['maShort'], dataframe['maMedium']), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """
        dataframe.loc[qtpylib.crossed_above(dataframe['maMedium'], dataframe['maShort']), 'exit_long'] = 1
        return dataframe