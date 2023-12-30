from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta

class JustROCR4(IStrategy):
    INTERFACE_VERSION = 3
    minimal_roi = {'0': 0.15}
    stoploss = -0.15
    trailing_stop = False
    timeframe = '5m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rocr'] = ta.ROCR(dataframe, period=499)
        dataframe['rocr_200'] = ta.ROCR(dataframe, period=200)
        dataframe['rocr_100'] = ta.ROCR(dataframe, period=100)
        dataframe['rocr_20'] = ta.ROCR(dataframe, period=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['rocr'] > 1.2) & (dataframe['rocr_200'] > 1.15) & (dataframe['rocr_100'] > 1.1) & (dataframe['rocr_20'] > 1.05), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(), 'exit_long'] = 1
        return dataframe