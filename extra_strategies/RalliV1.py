# --- Do not remove these libs ---
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
# @Rallipanos
# Buy hyperspace params:
entry_params = {'base_nb_candles_entry': 14, 'ewo_high': 2.327, 'ewo_high_2': -2.327, 'ewo_low': -20.988, 'low_offset': 0.975, 'low_offset_2': 0.955, 'rsi_entry': 60, 'rsi_entry_2': 45}
# Sell hyperspace params:
exit_params = {'base_nb_candles_exit': 24, 'high_offset': 0.991, 'high_offset_2': 0.997}

def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['low'] * 100
    return emadif

class RalliV1(IStrategy):
    INTERFACE_VERSION = 3
    # ROI table:
    minimal_roi = {'0': 0.04, '40': 0.032, '87': 0.018, '201': 0}
    # Stoploss:
    stoploss = -0.3
    # SMAOffset
    base_nb_candles_entry = IntParameter(5, 80, default=entry_params['base_nb_candles_entry'], space='entry', optimize=True)
    base_nb_candles_exit = IntParameter(5, 80, default=exit_params['base_nb_candles_exit'], space='exit', optimize=True)
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
    rsi_entry_2 = IntParameter(30, 70, default=entry_params['rsi_entry_2'], space='entry', optimize=True)
    # Trailing stop:
    trailing_stop = False
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True
    # Sell signal
    use_exit_signal = True
    exit_profit_only = False
    exit_profit_offset = 0.01
    ignore_roi_if_entry_signal = False
    ## Optional order time in force.
    order_time_in_force = {'entry': 'gtc', 'exit': 'gtc'}
    # Optimal timeframe for the strategy
    timeframe = '5m'
    inf_1h = '1h'
    process_only_new_candles = True
    startup_candle_count = 200
    plot_config = {'main_plot': {'ma_entry': {'color': 'orange'}, 'ma_exit': {'color': 'orange'}}}

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float, rate: float, time_in_force: str, exit_reason: str, current_time: datetime, **kwargs) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        if last_candle is not None:
            if exit_reason in ['exit_signal']:
                if last_candle['rsi'] < 45 and last_candle['hma_50'] > last_candle['ema_100']:  #*1.2
                    return False
        return True
    use_custom_stoploss = True

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> float:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        candle = df.iloc[-1].squeeze()
        if current_profit < 0.001 and current_time - timedelta(minutes=140) > trade.open_date_utc:
            return -0.005
        return 1

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Calculate all ma_entry values
        for val in self.base_nb_candles_entry.range:
            dataframe[f'ma_entry_{val}'] = ta.EMA(dataframe, timeperiod=val)
        # Calculate all ma_exit values
        for val in self.base_nb_candles_exit.range:
            dataframe[f'ma_exit_{val}'] = ta.EMA(dataframe, timeperiod=val)
        dataframe['hma_50'] = qtpylib.hull_moving_average(dataframe['close'], window=50)
        dataframe['hma_9'] = qtpylib.hull_moving_average(dataframe['close'], window=9)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        dataframe['ema_14'] = ta.EMA(dataframe, timeperiod=14)
        dataframe['sma_9'] = ta.SMA(dataframe, timeperiod=9)
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        # Elliot
        dataframe['EWO'] = EWO(dataframe, self.fast_ewo, self.slow_ewo)
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_slow'] = ta.RSI(dataframe, timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append((dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] < dataframe['ema_100']) & (dataframe['sma_9'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}']) & (dataframe['rsi_fast'] < 35) & (dataframe['rsi_fast'] > 4) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] > self.ewo_high.value) & (dataframe['rsi'] < self.rsi_entry_2.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value))
        conditions.append((dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] < dataframe['ema_100']) & (dataframe['sma_9'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}']) & (dataframe['rsi_fast'] < 35) & (dataframe['rsi_fast'] > 4) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset_2.value) & (dataframe['EWO'] > self.ewo_high_2.value) & (dataframe['rsi'] < self.rsi_entry_2.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['rsi'] < 25))
        conditions.append((dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] < dataframe['ema_100']) & (dataframe['sma_9'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}']) & (dataframe['rsi_fast'] < 35) & (dataframe['rsi_fast'] > 4) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] < self.ewo_low.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value))
        conditions.append((dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] > dataframe['ema_100']) & (dataframe['rsi_fast'] < 35) & (dataframe['rsi_fast'] > 4) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] > self.ewo_high.value) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value))
        conditions.append((dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] > dataframe['ema_100']) & (dataframe['rsi_fast'] < 35) & (dataframe['rsi_fast'] > 4) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset_2.value) & (dataframe['EWO'] > self.ewo_high_2.value) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['rsi'] < 25))
        conditions.append((dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] > dataframe['ema_100']) & (dataframe['rsi_fast'] < 35) & (dataframe['rsi_fast'] > 4) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] < self.ewo_low.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append((dataframe['hma_50'] > dataframe['ema_100']) & (dataframe['close'] > dataframe['sma_9']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset_2.value) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']) | (dataframe['close'] < dataframe['ema_100']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'exit_long'] = 1
        return dataframe