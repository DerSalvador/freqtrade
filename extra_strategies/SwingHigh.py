# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from freqtrade.strategy.interface import IStrategy
# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class SwingHigh(IStrategy):
    INTERFACE_VERSION = 3
    # Disable ROI
    # Could be replaced with new ROI from hyperopt.
    minimal_roi = {'0': 0.16035, '23': 0.03218, '54': 0.01182, '173': 0}
    stoploss = -0.22274
    ### Do extra hyperopt for trailing seperat. Use "--spaces default" and then "--spaces trailing".
    ### See here for more information: https://www.freqtrade.io/en/latest/hyperopt
    trailing_stop = True
    trailing_stop_positive = 0.08
    trailing_stop_positive_offset = 0.1
    trailing_only_offset_is_reached = True
    timeframe = '30m'

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        ### Add timeperiod from hyperopt (replace xx with value):
        ### "xx" must be replaced even before the first hyperopt is run,
        ### else "xx" would be a syntax error because it must be a Integer value.
        dataframe['cci-entry'] = ta.CCI(dataframe, timeperiod=13)
        dataframe['cci-exit'] = ta.CCI(dataframe, timeperiod=76)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['macd'] > dataframe['macdsignal']) & (dataframe['cci-entry'] <= -188.0) & (dataframe['volume'] > 0), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['macd'] < dataframe['macdsignal']) & (dataframe['cci-exit'] >= 231.0) & (dataframe['volume'] > 0), 'exit_long'] = 1
        return dataframe