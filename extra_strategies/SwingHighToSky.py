"""
author      = "Kevin Ossenbrück"
copyright   = "Free For Use"
credits     = ["Bloom Trading, Mohsen Hassan"]
license     = "MIT"
version     = "1.0"
maintainer  = "Kevin Ossenbrück"
email       = "kevin.ossenbrueck@pm.de"
status      = "Live"
"""
from freqtrade.strategy import IStrategy
from freqtrade.strategy import IntParameter
from functools import reduce
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy
# CCI timerperiods and values
cciBuyTP = 72
cciBuyVal = -175
cciSellTP = 66
cciSellVal = -106
# RSI timeperiods and values
rsiBuyTP = 36
rsiBuyVal = 90
rsiSellTP = 45
rsiSellVal = 88

class SwingHighToSky(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '15m'
    stoploss = -0.34338
    minimal_roi = {'0': 0.27058, '33': 0.0853, '64': 0.04093, '244': 0}
    entry_cci = IntParameter(low=-200, high=200, default=100, space='entry', optimize=True)
    entry_cciTime = IntParameter(low=10, high=80, default=20, space='entry', optimize=True)
    entry_rsi = IntParameter(low=10, high=90, default=30, space='entry', optimize=True)
    entry_rsiTime = IntParameter(low=10, high=80, default=26, space='entry', optimize=True)
    exit_cci = IntParameter(low=-200, high=200, default=100, space='exit', optimize=True)
    exit_cciTime = IntParameter(low=10, high=80, default=20, space='exit', optimize=True)
    exit_rsi = IntParameter(low=10, high=90, default=30, space='exit', optimize=True)
    exit_rsiTime = IntParameter(low=10, high=80, default=26, space='exit', optimize=True)
    # Buy hyperspace params:
    entry_params = {'entry_cci': -175, 'entry_cciTime': 72, 'entry_rsi': 90, 'entry_rsiTime': 36}
    # Sell hyperspace params:
    exit_params = {'exit_cci': -106, 'exit_cciTime': 66, 'exit_rsi': 88, 'exit_rsiTime': 45}

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for val in self.entry_cciTime.range:
            dataframe[f'cci-{val}'] = ta.CCI(dataframe, timeperiod=val)
        for val in self.exit_cciTime.range:
            dataframe[f'cci-exit-{val}'] = ta.CCI(dataframe, timeperiod=val)
        for val in self.entry_rsiTime.range:
            dataframe[f'rsi-{val}'] = ta.RSI(dataframe, timeperiod=val)
        for val in self.exit_rsiTime.range:
            dataframe[f'rsi-exit-{val}'] = ta.RSI(dataframe, timeperiod=val)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe[f'cci-{self.entry_cciTime.value}'] < self.entry_cci.value) & (dataframe[f'rsi-{self.entry_rsiTime.value}'] < self.entry_rsi.value), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe[f'cci-exit-{self.exit_cciTime.value}'] > self.exit_cci.value) & (dataframe[f'rsi-exit-{self.exit_rsiTime.value}'] > self.exit_rsi.value), 'exit_long'] = 1
        return dataframe