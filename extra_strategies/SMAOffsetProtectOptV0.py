# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------
import talib.abstract as ta
import numpy as np
import freqtrade.vendor.qtpylib.indicators as qtpylib
import datetime
from technical.util import resample_to_interval, resampled_merge
from datetime import datetime, timedelta
from freqtrade.persistence import Trade
from freqtrade.strategy import stoploss_from_open, merge_informative_pair, DecimalParameter, IntParameter, CategoricalParameter
import technical.indicators as ftt
SMA = 'SMA'
EMA = 'EMA'
# Buy hyperspace params:
#entry_params = {
#    "base_nb_candles_entry": 20,
#    "ewo_high": 6,
#    "fast_ewo": 50,
#    "slow_ewo": 200,
#    "low_offset": 0.958,
#    "entry_trigger": "EMA",
#    "ewo_high": 2.0,
#    "ewo_low": -16.062,
#    "rsi_entry": 51,
#}
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
entry_params = {'base_nb_candles_entry': 20, 'ewo_high': 5.499, 'ewo_low': -19.881, 'low_offset': 0.975, 'rsi_entry': 67, 'entry_trigger': 'EMA', 'fast_ewo': 50, 'slow_ewo': 200, 'entry_trigger': 'EMA'}
# Sell hyperspace params:
#exit_params = {
#    "base_nb_candles_exit": 20,
#    "high_offset": 1.012,
#    "exit_trigger": "EMA",
#}
# Sell hyperspace params:
exit_params = {'base_nb_candles_exit': 24, 'high_offset': 1.012, 'exit_trigger': 'EMA'}

def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['close'] * 100
    return emadif

class SMAOffsetProtectOptV0(IStrategy):
    INTERFACE_VERSION = 3
    # ROI table:
    minimal_roi = {'0': 0.01}
    # Stoploss:
    stoploss = -0.5
    # SMAOffset
    base_nb_candles_entry = IntParameter(5, 80, default=entry_params['base_nb_candles_entry'], space='entry', optimize=True)
    base_nb_candles_exit = IntParameter(5, 80, default=exit_params['base_nb_candles_exit'], space='exit', optimize=True)
    low_offset = DecimalParameter(0.9, 0.99, default=entry_params['low_offset'], space='entry', optimize=True)
    high_offset = DecimalParameter(0.99, 1.1, default=exit_params['high_offset'], space='exit', optimize=True)
    entry_trigger = CategoricalParameter([SMA, EMA], default=entry_params['entry_trigger'], space='entry', optimize=False)
    exit_trigger = CategoricalParameter([SMA, EMA], default=exit_params['exit_trigger'], space='exit', optimize=False)
    # Protection
    ewo_low = DecimalParameter(-20.0, -8.0, default=entry_params['ewo_low'], space='entry', optimize=True)
    ewo_high = DecimalParameter(2.0, 12.0, default=entry_params['ewo_high'], space='entry', optimize=True)
    fast_ewo = IntParameter(10, 50, default=entry_params['fast_ewo'], space='entry', optimize=False)
    slow_ewo = IntParameter(100, 200, default=entry_params['slow_ewo'], space='entry', optimize=False)
    rsi_entry = IntParameter(30, 70, default=entry_params['rsi_entry'], space='entry', optimize=True)
    # slow_ema = IntParameter(
    #     10, 50, default=entry_params['fast_ewo'], space='entry', optimize=True)
    # fast_ema = IntParameter(
    #     100, 200, default=entry_params['slow_ewo'], space='entry', optimize=True)
    # Trailing stop:
    trailing_stop = False
    trailing_stop_positive = 0.001
    trailing_stop_positive_offset = 0.01
    trailing_only_offset_is_reached = True
    # Sell signal
    use_exit_signal = True
    exit_profit_only = True
    exit_profit_offset = 0.01
    ignore_roi_if_entry_signal = True
    # Optimal timeframe for the strategy
    timeframe = '5m'
    informative_timeframe = '1h'
    use_exit_signal = True
    exit_profit_only = False
    process_only_new_candles = True
    startup_candle_count = 30
    plot_config = {'main_plot': {'ma_offset_entry': {'color': 'orange'}, 'ma_offset_exit': {'color': 'orange'}}}
    use_custom_stoploss = False

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, self.informative_timeframe) for pair in pairs]
        # EMA
        informative_pairs['ema_50'] = ta.EMA(informative_pairs, timeperiod=50)
        informative_pairs['ema_100'] = ta.EMA(informative_pairs, timeperiod=100)
        informative_pairs['ema_200'] = ta.EMA(informative_pairs, timeperiod=200)
        # SMA
        informative_pairs['sma_200'] = ta.SMA(informative_pairs, timeperiod=200)
        informative_pairs['sma_200_dec'] = informative_pairs['sma_200'] < informative_pairs['sma_200'].shift(20)
        # RSI
        informative_pairs['rsi'] = ta.RSI(informative_pairs, timeperiod=14)
        return informative_pairs

    def get_informative_indicators(self, metadata: dict):
        dataframe = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=self.informative_timeframe)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # informative = self.get_informative_indicators(metadata)
        # dataframe = merge_informative_pair(dataframe, informative, self.timeframe, self.informative_timeframe,
        #                                    ffill=True)
        # Calculate all base_nb_candles_entry values
        for val in self.base_nb_candles_entry.range:
            dataframe[f'ma_entry_{val}'] = ta.EMA(dataframe, timeperiod=val)
        # Calculate all base_nb_candles_entry values
        for val in self.base_nb_candles_exit.range:
            dataframe[f'ma_exit_{val}'] = ta.EMA(dataframe, timeperiod=val)
        # ---------------- original code -------------------
        ##SMAOffset
        #if self.entry_trigger.value == 'EMA':
        #    dataframe['ma_entry'] = ta.EMA(dataframe, timeperiod=self.base_nb_candles_entry.value)
        #else:
        #    dataframe['ma_entry'] = ta.SMA(dataframe, timeperiod=self.base_nb_candles_entry.value)
        #
        #if self.exit_trigger.value == 'EMA':
        #    dataframe['ma_exit'] = ta.EMA(dataframe, timeperiod=self.base_nb_candles_exit.value)
        #else:
        #    dataframe['ma_exit'] = ta.SMA(dataframe, timeperiod=self.base_nb_candles_exit.value)
        #
        #dataframe['ma_offset_entry'] = dataframe['ma_entry'] * self.low_offset.value
        #dataframe['ma_offset_exit'] = dataframe['ma_exit'] * self.high_offset.value
        # ------------ end original code --------------------
        # Elliot
        dataframe['EWO'] = EWO(dataframe, self.fast_ewo.value, self.slow_ewo.value)
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append((dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] > self.ewo_high.value) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0))
        conditions.append((dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] < self.ewo_low.value) & (dataframe['volume'] > 0))
        # ---------------- original code -------------------
        #conditions.append(
        #    (
        #        (dataframe['close'] < dataframe['ma_offset_entry']) &
        #        (dataframe['EWO'] > self.ewo_high.value) &
        #        (dataframe['rsi'] < self.rsi_entry.value) &
        #        (dataframe['volume'] > 0)
        #    )
        #)
        #conditions.append(
        #    (
        #        (dataframe['close'] < dataframe['ma_offset_entry']) &
        #        (dataframe['EWO'] < self.ewo_low.value) &
        #        (dataframe['volume'] > 0)
        #    )
        #)
        # ------------ end original code --------------------
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append((dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['volume'] > 0))
        # ---------------- original code -------------------
        #conditions.append(
        #    (
        #        (dataframe['close'] > dataframe['ma_offset_exit']) &
        #        (dataframe['volume'] > 0)
        #    )
        #)
        # ------------ end original code --------------------
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'exit_long'] = 1
        return dataframe