# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
# --------------------------------

class ADX_15M_USDT(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '15m'
    # ROI table:
    minimal_roi = {'0': 0.26552, '30': 0.10255, '210': 0.03545, '540': 0}
    # Stoploss:
    stoploss = -0.1255

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['plus_di'] = ta.PLUS_DI(dataframe, timeperiod=25)
        dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=25)
        dataframe['sar'] = ta.SAR(dataframe)
        dataframe['mom'] = ta.MOM(dataframe, timeperiod=14)
        dataframe['exit-adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['exit-plus_di'] = ta.PLUS_DI(dataframe, timeperiod=25)
        dataframe['exit-minus_di'] = ta.MINUS_DI(dataframe, timeperiod=25)
        dataframe['exit-sar'] = ta.SAR(dataframe)
        dataframe['exit-mom'] = ta.MOM(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['adx'] > 16) & (dataframe['minus_di'] > 4) & (dataframe['plus_di'] > 20) & qtpylib.crossed_above(dataframe['plus_di'], dataframe['minus_di']), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['adx'] > 43) & (dataframe['minus_di'] > 22) & (dataframe['plus_di'] > 20) & qtpylib.crossed_above(dataframe['exit-minus_di'], dataframe['exit-plus_di']), 'exit_long'] = 1
        return dataframe