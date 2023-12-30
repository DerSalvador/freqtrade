from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta

class JustROCR3(IStrategy):
    INTERFACE_VERSION = 3
    minimal_roi = {'0': 0.5}
    stoploss = -0.01
    trailing_stop = True
    timeframe = '5m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rocr'] = ta.ROCR(dataframe, period=499)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe['rocr'] > 1.1, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(), 'exit_long'] = 1
        return dataframe