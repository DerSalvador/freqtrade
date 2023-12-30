# Author: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/
# IMPORTANT: DO NOT USE IT WITHOUT HYPEROPT:
# freqtrade hyperopt --hyperopt-loss SharpeHyperOptLoss --spaces all --strategy mabStra --config config.json -e 100
# --- Do not remove these libs ---
from freqtrade.strategy import IntParameter, DecimalParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
# --------------------------------
# Add your lib to import here
import talib.abstract as ta

class MabStra(IStrategy):
    INTERFACE_VERSION = 3
    # #################### RESULTS PASTE PLACE ####################
    # ROI table:
    minimal_roi = {'0': 0.598, '644': 0.166, '3269': 0.115, '7289': 0}
    # Stoploss:
    stoploss = -0.128
    # Buy hypers
    timeframe = '4h'
    # #################### END OF RESULT PLACE ####################
    # entry params
    entry_mojo_ma_timeframe = IntParameter(2, 100, default=7, space='entry')
    entry_fast_ma_timeframe = IntParameter(2, 100, default=14, space='entry')
    entry_slow_ma_timeframe = IntParameter(2, 100, default=28, space='entry')
    entry_div_max = DecimalParameter(0, 2, decimals=4, default=2.25446, space='entry')
    entry_div_min = DecimalParameter(0, 2, decimals=4, default=0.29497, space='entry')
    # exit params
    exit_mojo_ma_timeframe = IntParameter(2, 100, default=7, space='exit')
    exit_fast_ma_timeframe = IntParameter(2, 100, default=14, space='exit')
    exit_slow_ma_timeframe = IntParameter(2, 100, default=28, space='exit')
    exit_div_max = DecimalParameter(0, 2, decimals=4, default=1.54593, space='exit')
    exit_div_min = DecimalParameter(0, 2, decimals=4, default=2.81436, space='exit')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # SMA - ex Moving Average
        dataframe['entry-mojoMA'] = ta.SMA(dataframe, timeperiod=self.entry_mojo_ma_timeframe.value)
        dataframe['entry-fastMA'] = ta.SMA(dataframe, timeperiod=self.entry_fast_ma_timeframe.value)
        dataframe['entry-slowMA'] = ta.SMA(dataframe, timeperiod=self.entry_slow_ma_timeframe.value)
        dataframe['exit-mojoMA'] = ta.SMA(dataframe, timeperiod=self.exit_mojo_ma_timeframe.value)
        dataframe['exit-fastMA'] = ta.SMA(dataframe, timeperiod=self.exit_fast_ma_timeframe.value)
        dataframe['exit-slowMA'] = ta.SMA(dataframe, timeperiod=self.exit_slow_ma_timeframe.value)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['entry-mojoMA'].div(dataframe['entry-fastMA']) > self.entry_div_min.value) & (dataframe['entry-mojoMA'].div(dataframe['entry-fastMA']) < self.entry_div_max.value) & (dataframe['entry-fastMA'].div(dataframe['entry-slowMA']) > self.entry_div_min.value) & (dataframe['entry-fastMA'].div(dataframe['entry-slowMA']) < self.entry_div_max.value), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['exit-fastMA'].div(dataframe['exit-mojoMA']) > self.exit_div_min.value) & (dataframe['exit-fastMA'].div(dataframe['exit-mojoMA']) < self.exit_div_max.value) & (dataframe['exit-slowMA'].div(dataframe['exit-fastMA']) > self.exit_div_min.value) & (dataframe['exit-slowMA'].div(dataframe['exit-fastMA']) < self.exit_div_max.value), 'exit_long'] = 1
        return dataframe