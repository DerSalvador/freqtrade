# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------
import talib.abstract as ta
import numpy as np
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.exchange import timeframe_to_prev_date, timeframe_to_seconds
import datetime
from technical.util import resample_to_interval, resampled_merge
from datetime import datetime, timedelta
from freqtrade.persistence import Trade
from freqtrade.strategy import stoploss_from_open, merge_informative_pair, DecimalParameter, IntParameter, CategoricalParameter
import technical.indicators as ftt
# @Rallipanos
# Buy hyperspace params:
# entry_params = {
#     "base_nb_candles_entry": 7,
#     "ewo_high": 3.004,
#     "ewo_low": -9.551,
#     "low_offset": 0.984,
#     "rsi_entry": 56,
# }
# # Sell hyperspace params:
# exit_params = {
#     "base_nb_candles_exit": 19,
#     "high_offset": 1.0,
#     "high_offset_2": 0.998,
# }
# # Buy hyperspace params:
# entry_params = {
#     "base_nb_candles_entry": 12,
#     "ewo_high": 2.38,
#     "ewo_low": -9.496,
#     "low_offset": 0.986,
#     "rsi_entry": 65,
# }
# Sell hyperspace params:
# exit_params = {
#     "base_nb_candles_exit": 11,
#     "high_offset": 1.0,
#     "high_offset_2": 0.995,
# }
# Buy hyperspace params:
# entry_params = {
#     "base_nb_candles_entry": 12,
#     "ewo_high": 2.303,
#     "ewo_low": -8.114,
#     "low_offset": 0.986,
#     "rsi_entry": 68,
# }
# Buy hyperspace params:
# entry_params = {
#     "base_nb_candles_entry": 10,
#     "ewo_high": 3.751,
#     "ewo_low": -9.735,
#     "low_offset": 0.984,
#     "rsi_entry": 68,
# }
# Buy hyperspace params:
# entry_params = {
#     "base_nb_candles_entry": 10,
#     "ewo_high": 3.734,
#     "ewo_low": -9.551,
#     "low_offset": 0.984,
#     "rsi_entry": 65,
# }
# Buy hyperspace params:
entry_params = {'base_nb_candles_entry': 10, 'ewo_high': 3.206, 'ewo_low': -10.69, 'low_offset': 0.984, 'rsi_entry': 63}
# Sell hyperspace params:
exit_params = {'base_nb_candles_exit': 6, 'high_offset': 1.002, 'high_offset_2': 1.0}

def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['low'] * 100
    return emadif

class NotAnotherSMAOffsetStrategyModHO(IStrategy):
    INTERFACE_VERSION = 3
    # ROI table:
    # "20": 0.09,
    # "40": 0.029,
    # "90": 0
    minimal_roi = {'0': 0.214}
    # minimal_roi = {
    #     "0": 0.99,
    # }
    # Stoploss:
    stoploss = -0.32
    # SMAOffset
    base_nb_candles_entry = IntParameter(5, 80, default=entry_params['base_nb_candles_entry'], space='entry', optimize=True)
    base_nb_candles_exit = IntParameter(5, 80, default=exit_params['base_nb_candles_exit'], space='exit', optimize=True)
    low_offset = DecimalParameter(0.9, 0.99, default=entry_params['low_offset'], space='entry', optimize=True)
    high_offset = DecimalParameter(0.95, 1.1, default=exit_params['high_offset'], space='exit', optimize=True)
    high_offset_2 = DecimalParameter(0.99, 1.5, default=exit_params['high_offset_2'], space='exit', optimize=True)
    # Protection
    fast_ewo = 50
    slow_ewo = 200
    ewo_low = DecimalParameter(-20.0, -8.0, default=entry_params['ewo_low'], space='entry', optimize=True)
    ewo_high = DecimalParameter(2.0, 12.0, default=entry_params['ewo_high'], space='entry', optimize=True)
    rsi_entry = IntParameter(30, 70, default=entry_params['rsi_entry'], space='entry', optimize=True)
    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.0075
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True
    use_custom_stoploss = True
    # Sell signal
    use_exit_signal = True
    exit_profit_only = False
    exit_profit_offset = 0.01
    ignore_roi_if_entry_signal = True
    # Optional order time in force.
    order_time_in_force = {'entry': 'gtc', 'exit': 'ioc'}
    # Optimal timeframe for the strategy
    timeframe = '5m'
    inf_1h = '1h'
    process_only_new_candles = True
    startup_candle_count = 200
    plot_config = {'main_plot': {'ma_entry': {'color': 'orange'}, 'ma_exit': {'color': 'orange'}}}
    slippage_protection = {'retries': 3, 'max_slippage': -0.02}

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float, rate: float, time_in_force: str, exit_reason: str, current_time: datetime, **kwargs) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        previous_candle_1 = dataframe.iloc[-2]
        if last_candle is not None:
            #            if (exit_reason in ['roi','exit_signal','trailing_stop_loss']):
            if exit_reason in ['exit_signal']:
                if last_candle['block_trade_exit']:
                    return False
                if last_candle['di_up'] and last_candle['adx'] > previous_candle_1['adx']:
                    return False
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

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> float:
        stoploss = self.stoploss
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        if last_candle is None:
            return stoploss
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc - timedelta(seconds=timeframe_to_seconds(self.timeframe)))
        trade_candle = dataframe.loc[dataframe['date'] == trade_date]
        if trade_candle.empty:
            return stoploss
        trade_candle = trade_candle.squeeze()
        dur_minutes = (current_time - trade.open_date_utc).seconds // 60
        slippage_ratio = trade.open_rate / trade_candle['close'] - 1
        slippage_ratio = slippage_ratio if slippage_ratio > 0 else 0
        current_profit_comp = current_profit + slippage_ratio
        if current_profit_comp >= self.trailing_stop_positive_offset:
            return self.trailing_stop_positive
        for x in self.minimal_roi:
            dur = int(x)
            roi = self.minimal_roi[x]
            if dur_minutes >= dur and current_profit_comp >= roi:
                return 0.001
        return stoploss

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Calculate all ma_entry values
        for val in self.base_nb_candles_entry.range:
            dataframe[f'ma_entry_{val}'] = ta.EMA(dataframe, timeperiod=val)
        # Calculate all ma_exit values
        for val in self.base_nb_candles_exit.range:
            dataframe[f'ma_exit_{val}'] = ta.EMA(dataframe, timeperiod=val)
        dataframe['hma_50'] = qtpylib.hull_moving_average(dataframe['close'], window=50)
        dataframe['sma_9'] = ta.SMA(dataframe, timeperiod=9)
        # Elliot
        dataframe['EWO'] = EWO(dataframe, self.fast_ewo, self.slow_ewo)
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_slow'] = ta.RSI(dataframe, timeperiod=20)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        # confirm_trade_exit
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=2)
        dataframe['di_up'] = ta.PLUS_DI(dataframe, timeperiod=2) > ta.MINUS_DI(dataframe, timeperiod=2)
        rsi2 = ta.RSI(dataframe, timeperiod=2)
        rsi4 = ta.RSI(dataframe, timeperiod=4)
        dataframe['block_trade_exit'] = rsi2 > rsi4
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append((dataframe['rsi_fast'] < 35) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] > self.ewo_high.value) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value))
        conditions.append((dataframe['rsi_fast'] < 35) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] < self.ewo_low.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append((dataframe['close'] > dataframe['sma_9']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset_2.value) & (dataframe['rsi'] > 50) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']) | (dataframe['close'] < dataframe['hma_50']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'exit_long'] = 1
        return dataframe