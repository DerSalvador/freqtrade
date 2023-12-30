from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta

class JustROCR5(IStrategy):
    INTERFACE_VERSION = 3
    minimal_roi = {'0': 0.05}
    stoploss = -0.01
    trailing_stop = True
    timeframe = '1m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rocr'] = ta.ROCR(dataframe, timeperiod=5)
        dataframe['rocr_2'] = ta.ROCR(dataframe, timeperiod=2)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['rocr'] > 1.1) & (dataframe['rocr_2'] > 1.01), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(), 'exit_long'] = 1
        return dataframe