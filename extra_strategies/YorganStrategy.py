# --- Do not remove these libs ---
# --- Do not remove these libs ---
import datetime
from datetime import datetime, timedelta
from functools import reduce
from typing import Dict, List
import numpy as np
# --------------------------------
import talib.abstract as ta
import technical.indicators as ftt
from pandas import DataFrame
from technical.util import resample_to_interval, resampled_merge
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.persistence import Trade
from freqtrade.strategy import CategoricalParameter, DecimalParameter, IntParameter, merge_informative_pair, stoploss_from_open
from freqtrade.strategy.interface import IStrategy
# @Rallipanos
# # Buy hyperspace params:
entry_params = {'base_nb_candles_entry': 14, 'ewo_high': 2.327, 'ewo_high_2': -2.327, 'ewo_low': -20.988, 'low_offset': 0.975, 'low_offset_2': 0.955, 'rsi_entry': 69}
# # Buy hyperspace params:
entry_params = {'base_nb_candles_entry': 18, 'ewo_high': 3.422, 'ewo_high_2': -3.436, 'ewo_low': -8.562, 'low_offset': 0.966, 'low_offset_2': 0.959, 'rsi_entry': 66}
# # # Sell hyperspace params:
exit_params = {'base_nb_candles_exit': 17, 'high_offset': 0.997, 'high_offset_2': 1.01}
# # Sell hyperspace params:
exit_params = {'base_nb_candles_exit': 7, 'high_offset': 1.014, 'high_offset_2': 0.995}
# # Buy hyperspace params:
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
entry_params = {'ewo_high_2': -5.642, 'low_offset_2': 0.951, 'rsi_entry': 54, 'base_nb_candles_entry': 16, 'ewo_high': 3.422, 'ewo_low': -8.562, 'low_offset': 0.966}
# # Sell hyperspace params:
# value loaded from strategy
exit_params = {'base_nb_candles_exit': 8, 'high_offset_2': 1.002, 'high_offset': 1.014}
# Buy hyperspace params:
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
entry_params = {'base_nb_candles_entry': 8, 'ewo_high': 4.179, 'ewo_low': -16.917, 'ewo_high_2': -2.609, 'low_offset': 0.986, 'low_offset_2': 0.944, 'rsi_entry': 58}
# Sell hyperspace params:
# value loaded from strategy
exit_params = {'base_nb_candles_exit': 16, 'high_offset': 1.054, 'high_offset_2': 1.018}

def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['low'] * 100
    return emadif

class YorganStrategy(IStrategy):
    INTERFACE_VERSION = 3
    # ROI table:
    minimal_roi = {'0': 0.283, '40': 0.086, '99': 0.036, '0': 10}
    # Stoploss:
    stoploss = -0.1
    # SMAOffset
    base_nb_candles_entry = IntParameter(2, 20, default=entry_params['base_nb_candles_entry'], space='entry', optimize=True)
    base_nb_candles_exit = IntParameter(10, 40, default=exit_params['base_nb_candles_exit'], space='exit', optimize=True)
    low_offset = DecimalParameter(0.9, 0.99, default=entry_params['low_offset'], space='entry', optimize=True)
    low_offset_2 = DecimalParameter(0.9, 0.99, default=entry_params['low_offset_2'], space='entry', optimize=True)
    high_offset = DecimalParameter(0.95, 1.1, default=exit_params['high_offset'], space='exit', optimize=True)
    high_offset_2 = DecimalParameter(0.99, 1.5, default=exit_params['high_offset_2'], space='exit', optimize=True)
    # Protection
    fast_ewo = 50
    slow_ewo = 200
    ewo_low = DecimalParameter(-20.0, -8.0, default=entry_params['ewo_low'], space='entry', optimize=True)
    ewo_high = DecimalParameter(2.0, 12.0, default=entry_params['ewo_high'], space='entry', optimize=True)
    ewo_high_2 = DecimalParameter(-6.0, 12.0, default=entry_params['ewo_high_2'], space='entry', optimize=True)
    rsi_entry = IntParameter(30, 70, default=entry_params['rsi_entry'], space='entry', optimize=True)
    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.0033
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True
    # Sell signal
    use_exit_signal = True
    exit_profit_only = False
    exit_profit_offset = 0.01
    ignore_roi_if_entry_signal = False
    # Optional order time in force.
    order_time_in_force = {'entry': 'gtc', 'exit': 'gtc'}
    # Optimal timeframe for the strategy
    timeframe = '5m'
    inf_1h = '1h'
    process_only_new_candles = True
    startup_candle_count = 200
    use_custom_stoploss = False
    slippage_protection = {'retries': 3, 'max_slippage': -0.02}

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float, rate: float, time_in_force: str, exit_reason: str, current_time: datetime, **kwargs) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        if last_candle is not None:
            if exit_reason in ['exit_signal']:
                if last_candle['hma_50'] * 1.149 > last_candle['ema_100'] and last_candle['close'] < last_candle['ema_100'] * 0.951:  # *1.2
                    return False
        # slippage
        try:
            state = self.slippage_protection['__pair_retries']
        except KeyError:
            state = self.slippage_protection['__pair_retries'] = {}
        candle = dataframe.iloc[-1].squeeze()
        slippage = rate / candle['close'] - 1
        if slippage < self.slippage_protection['max_slippage']:
            pair_retries = state.get(pair, 0)
            if pair_retries < self.slippage_protection['retries']:
                state[pair] = pair_retries + 1
                return False
        state[pair] = 0
        return True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Calculate all ma_entry values
        for val in self.base_nb_candles_entry.range:
            dataframe[f'ma_entry_{val}'] = ta.EMA(dataframe, timeperiod=val)
        # Calculate all ma_exit values
        for val in self.base_nb_candles_exit.range:
            dataframe[f'ma_exit_{val}'] = ta.EMA(dataframe, timeperiod=val)
        dataframe['hma_50'] = qtpylib.hull_moving_average(dataframe['close'], window=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        dataframe['sma_9'] = ta.SMA(dataframe, timeperiod=9)
        # Elliot
        dataframe['EWO'] = EWO(dataframe, self.fast_ewo, self.slow_ewo)
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_slow'] = ta.RSI(dataframe, timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['rsi_fast'] < 35) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] > self.ewo_high.value) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value), ['enter_long', 'enter_tag']] = (1, 'ewo1')
        dataframe.loc[(dataframe['rsi_fast'] < 35) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset_2.value) & (dataframe['EWO'] > self.ewo_high_2.value) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['rsi'] < 25), ['enter_long', 'enter_tag']] = (1, 'ewo2')
        dataframe.loc[(dataframe['rsi_fast'] < 35) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] < self.ewo_low.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value), ['enter_long', 'enter_tag']] = (1, 'ewolow')
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append((dataframe['close'] > dataframe['sma_9']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset_2.value) & (dataframe['rsi'] > 50) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']) | (dataframe['close'] < dataframe['hma_50']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'exit_long'] = 1
        return dataframe