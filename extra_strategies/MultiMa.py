# MultiMa Strategy
# Author: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/
# (First Hyperopt it.A hyperopt file is available)
#
# --- Do not remove these libs ---
from freqtrade.strategy import IntParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from functools import reduce

class MultiMa(IStrategy):
    INTERFACE_VERSION = 3
    entry_ma_count = IntParameter(0, 10, default=10, space='entry')
    entry_ma_gap = IntParameter(2, 10, default=2, space='entry')
    entry_ma_shift = IntParameter(0, 10, default=0, space='entry')
    # entry_ma_rolling = IntParameter(0, 10, default=0, space='entry')
    exit_ma_count = IntParameter(0, 10, default=10, space='exit')
    exit_ma_gap = IntParameter(2, 10, default=2, space='exit')
    exit_ma_shift = IntParameter(0, 10, default=0, space='exit')
    # exit_ma_rolling = IntParameter(0, 10, default=0, space='exit')
    # ROI table:
    minimal_roi = {'0': 0.30873, '569': 0.16689, '3211': 0.06473, '7617': 0}
    # Stoploss:
    stoploss = -0.1
    # Buy hypers
    timeframe = '4h'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # We will dinamicly generate the indicators
        # cuz this method just run one time in hyperopts
        # if you have static timeframes you can move first loop of entry and exit trends populators inside this method
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for i in self.entry_ma_count.range:
            dataframe[f'entry-ma-{i + 1}'] = ta.SMA(dataframe, timeperiod=int((i + 1) * self.entry_ma_gap.value))
        conditions = []
        for i in self.entry_ma_count.range:
            if i > 1:
                shift = self.entry_ma_shift.value
                for shift in self.entry_ma_shift.range:
                    conditions.append(dataframe[f'entry-ma-{i}'].shift(shift) > dataframe[f'entry-ma-{i - 1}'].shift(shift))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for i in self.exit_ma_count.range:
            dataframe[f'exit-ma-{i + 1}'] = ta.SMA(dataframe, timeperiod=int((i + 1) * self.exit_ma_gap.value))
        conditions = []
        for i in self.exit_ma_count.range:
            if i > 1:
                shift = self.exit_ma_shift.value
                for shift in self.exit_ma_shift.range:
                    conditions.append(dataframe[f'exit-ma-{i}'].shift(shift) < dataframe[f'exit-ma-{i - 1}'].shift(shift))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'exit_long'] = 1
        return dataframe