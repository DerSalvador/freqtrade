import talib.abstract as ta
import numpy as np  # noqa
import pandas as pd
from functools import reduce
from pandas import DataFrame
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, CategoricalParameter, DecimalParameter, IntParameter, RealParameter
__author__ = 'Robert Roman'
__copyright__ = 'Free For Use'
__license__ = 'MIT'
__version__ = '1.0'
__maintainer__ = 'Robert Roman'
__email__ = 'robertroman7@gmail.com'
__BTC_donation__ = '3FgFaG15yntZYSUzfEpxr5mDt1RArvcQrK'
# Optimized With Sharpe Ratio and 1 year data
# 199/40000:  30918 trades. 18982/3408/8528 Wins/Draws/Losses. Avg profit   0.39%. Median profit   0.65%. Total profit  119934.26007495 USDT ( 119.93%). Avg duration 8:12:00 min. Objective: -127.60220

class Bandtastic(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '15m'
    # ROI table:
    minimal_roi = {'0': 0.162, '69': 0.097, '229': 0.061, '566': 0}
    # Stoploss:
    stoploss = -0.345
    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.058
    trailing_only_offset_is_reached = False
    # Hyperopt Buy Parameters
    entry_fastema = IntParameter(low=1, high=236, default=211, space='entry', optimize=True, load=True)
    entry_slowema = IntParameter(low=1, high=126, default=364, space='entry', optimize=True, load=True)
    entry_rsi = IntParameter(low=15, high=70, default=52, space='entry', optimize=True, load=True)
    entry_mfi = IntParameter(low=15, high=70, default=30, space='entry', optimize=True, load=True)
    entry_rsi_enabled = CategoricalParameter([True, False], space='entry', optimize=True, default=False)
    entry_mfi_enabled = CategoricalParameter([True, False], space='entry', optimize=True, default=False)
    entry_ema_enabled = CategoricalParameter([True, False], space='entry', optimize=True, default=False)
    entry_trigger = CategoricalParameter(['bb_lower1', 'bb_lower2', 'bb_lower3', 'bb_lower4'], default='bb_lower1', space='entry')
    # Hyperopt Sell Parameters
    exit_fastema = IntParameter(low=1, high=365, default=7, space='exit', optimize=True, load=True)
    exit_slowema = IntParameter(low=1, high=365, default=6, space='exit', optimize=True, load=True)
    exit_rsi = IntParameter(low=30, high=100, default=57, space='exit', optimize=True, load=True)
    exit_mfi = IntParameter(low=30, high=100, default=46, space='exit', optimize=True, load=True)
    exit_rsi_enabled = CategoricalParameter([True, False], space='exit', optimize=True, default=False)
    exit_mfi_enabled = CategoricalParameter([True, False], space='exit', optimize=True, default=True)
    exit_ema_enabled = CategoricalParameter([True, False], space='exit', optimize=True, default=False)
    exit_trigger = CategoricalParameter(['exit-bb_upper1', 'exit-bb_upper2', 'exit-bb_upper3', 'exit-bb_upper4'], default='exit-bb_upper2', space='exit')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe)
        dataframe['mfi'] = ta.MFI(dataframe)
        # Bollinger Bands 1,2,3 and 4
        bollinger1 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=1)
        dataframe['bb_lowerband1'] = bollinger1['lower']
        dataframe['bb_middleband1'] = bollinger1['mid']
        dataframe['bb_upperband1'] = bollinger1['upper']
        bollinger2 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband2'] = bollinger2['lower']
        dataframe['bb_middleband2'] = bollinger2['mid']
        dataframe['bb_upperband2'] = bollinger2['upper']
        bollinger3 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=3)
        dataframe['bb_lowerband3'] = bollinger3['lower']
        dataframe['bb_middleband3'] = bollinger3['mid']
        dataframe['bb_upperband3'] = bollinger3['upper']
        bollinger4 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=4)
        dataframe['bb_lowerband4'] = bollinger4['lower']
        dataframe['bb_middleband4'] = bollinger4['mid']
        dataframe['bb_upperband4'] = bollinger4['upper']
        # Build EMA rows - combine all ranges to a single set to avoid duplicate calculations.
        for period in set(list(self.entry_fastema.range) + list(self.entry_slowema.range) + list(self.exit_fastema.range) + list(self.exit_slowema.range)):
            dataframe[f'EMA_{period}'] = ta.EMA(dataframe, timeperiod=period)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # GUARDS
        if self.entry_rsi_enabled.value:
            conditions.append(dataframe['rsi'] < self.entry_rsi.value)
        if self.entry_mfi_enabled.value:
            conditions.append(dataframe['mfi'] < self.entry_mfi.value)
        if self.entry_ema_enabled.value:
            conditions.append(dataframe[f'EMA_{self.entry_fastema.value}'] > dataframe[f'EMA_{self.entry_slowema.value}'])
        # TRIGGERS
        if self.entry_trigger.value == 'bb_lower1':
            conditions.append(dataframe['close'] < dataframe['bb_lowerband1'])
        if self.entry_trigger.value == 'bb_lower2':
            conditions.append(dataframe['close'] < dataframe['bb_lowerband2'])
        if self.entry_trigger.value == 'bb_lower3':
            conditions.append(dataframe['close'] < dataframe['bb_lowerband3'])
        if self.entry_trigger.value == 'bb_lower4':
            conditions.append(dataframe['close'] < dataframe['bb_lowerband4'])
        # Check that volume is not 0
        conditions.append(dataframe['volume'] > 0)
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # GUARDS
        if self.exit_rsi_enabled.value:
            conditions.append(dataframe['rsi'] > self.exit_rsi.value)
        if self.exit_mfi_enabled.value:
            conditions.append(dataframe['mfi'] > self.exit_mfi.value)
        if self.exit_ema_enabled.value:
            conditions.append(dataframe[f'EMA_{self.exit_fastema.value}'] < dataframe[f'EMA_{self.exit_slowema.value}'])
        # TRIGGERS
        if self.exit_trigger.value == 'exit-bb_upper1':
            conditions.append(dataframe['close'] > dataframe['bb_upperband1'])
        if self.exit_trigger.value == 'exit-bb_upper2':
            conditions.append(dataframe['close'] > dataframe['bb_upperband2'])
        if self.exit_trigger.value == 'exit-bb_upper3':
            conditions.append(dataframe['close'] > dataframe['bb_upperband3'])
        if self.exit_trigger.value == 'exit-bb_upper4':
            conditions.append(dataframe['close'] > dataframe['bb_upperband4'])
        # Check that volume is not 0
        conditions.append(dataframe['volume'] > 0)
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'exit_long'] = 1
        return dataframe