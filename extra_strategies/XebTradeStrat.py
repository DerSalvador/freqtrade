# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
import numpy as np
# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

def bollinger_bands(stock_price, window_size, num_of_std):
    rolling_mean = stock_price.rolling(window=window_size).mean()
    rolling_std = stock_price.rolling(window=window_size).std()
    lower_band = rolling_mean - rolling_std * num_of_std
    return (rolling_mean, lower_band)

class XebTradeStrat(IStrategy):
    INTERFACE_VERSION = 3
    #    "0": 0.0125
    minimal_roi = {'0': 0.99}
    stoploss = -0.05
    timeframe = '1m'
    trailing_stop = True
    trailing_only_offset_is_reached = True
    trailing_stop_positive_offset = 0.0015  # Trigger positive stoploss once crosses above this percentage
    trailing_stop_positive = 0.001  # Sell asset if it dips down this much

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema5'] = ta.EMA(dataframe, timeperiod=5)
        dataframe['ema10'] = ta.EMA(dataframe, timeperiod=10)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['ema5'] > dataframe['ema10']) & (dataframe['ema5'].shift(1) < dataframe['ema10'].shift(1)) & (dataframe['volume'] > 0), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        no exit signal
        """
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe