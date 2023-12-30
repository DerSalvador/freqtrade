# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class EMAVolume(IStrategy):
    INTERFACE_VERSION = 3
    "\n\n    author@: Gert Wohlgemuth\n\n    idea:\n        entrys and exits on crossovers - doesn't really perfom that well and its just a proof of concept\n    "
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {'0': 0.5}
    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.2
    # Optimal ticker interval for the strategy
    timeframe = '15m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema13'] = ta.EMA(dataframe, timeperiod=13)
        dataframe['ema34'] = ta.EMA(dataframe, timeperiod=34)
        dataframe['ema7'] = ta.EMA(dataframe, timeperiod=7)
        dataframe['ema21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=10).mean()
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """
        dataframe.loc[qtpylib.crossed_above(dataframe['ema13'], dataframe['ema34']) & (dataframe['volume'] > dataframe['volume'].rolling(window=10).mean()), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """
        dataframe.loc[qtpylib.crossed_below(dataframe['ema13'], dataframe['ema34']), 'exit_long'] = 1
        return dataframe