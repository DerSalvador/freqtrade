# --- Do not remove these libs ---
from logging import FATAL
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
#import technical.indicators as ftt
# @Rallipanos
# @pluxury
# @volk (antipump)
# with help from @stash86 and @Perkmeister
# Buy hyperspace params:
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
entry_params = {'low_offset': 0.981, 'base_nb_candles_entry': 8, 'ewo_high': 3.553, 'ewo_high_2': -5.585, 'ewo_low': -14.378, 'lookback_candles': 32, 'low_offset_2': 0.942, 'profit_threshold': 1.037, 'rsi_entry': 78, 'rsi_fast_entry': 37}
# Sell hyperspace params:
# value loaded from strategy
# value loaded from strategy
# value loaded from strategy
exit_params = {'base_nb_candles_exit': 16, 'high_offset': 1.097, 'high_offset_2': 1.472}

def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['low'] * 100
    return emadif

class NASOSv5(IStrategy):
    INTERFACE_VERSION = 3
    # ROI table:
    # "0": 0.283,
    # "40": 0.086,
    # "99": 0.036,
    minimal_roi = {'360': 0}
    # Stoploss:
    stoploss = -0.15
    # SMAOffset
    base_nb_candles_entry = IntParameter(2, 20, default=entry_params['base_nb_candles_entry'], space='entry', optimize=False)
    base_nb_candles_exit = IntParameter(2, 25, default=exit_params['base_nb_candles_exit'], space='exit', optimize=False)
    low_offset = DecimalParameter(0.9, 0.99, default=entry_params['low_offset'], space='entry', optimize=True)
    low_offset_2 = DecimalParameter(0.9, 0.99, default=entry_params['low_offset_2'], space='entry', optimize=False)
    high_offset = DecimalParameter(0.95, 1.1, default=exit_params['high_offset'], space='exit', optimize=True)
    high_offset_2 = DecimalParameter(0.99, 1.5, default=exit_params['high_offset_2'], space='exit', optimize=False)
    # Protection
    fast_ewo = 50
    slow_ewo = 200
    lookback_candles = IntParameter(1, 36, default=entry_params['lookback_candles'], space='entry', optimize=False)
    profit_threshold = DecimalParameter(0.99, 1.05, default=entry_params['profit_threshold'], space='entry', optimize=False)
    ewo_low = DecimalParameter(-20.0, -8.0, default=entry_params['ewo_low'], space='entry', optimize=False)
    ewo_high = DecimalParameter(2.0, 12.0, default=entry_params['ewo_high'], space='entry', optimize=False)
    ewo_high_2 = DecimalParameter(-6.0, 12.0, default=entry_params['ewo_high_2'], space='entry', optimize=False)
    rsi_entry = IntParameter(10, 80, default=entry_params['rsi_entry'], space='entry', optimize=False)
    rsi_fast_entry = IntParameter(10, 50, default=entry_params['rsi_fast_entry'], space='entry', optimize=False)
    # Trailing stop:
    trailing_stop = False
    trailing_stop_positive = 0.001
    trailing_stop_positive_offset = 0.016
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
    inf_15m = '15m'
    inf_1h = '1h'
    process_only_new_candles = True
    startup_candle_count = 200
    use_custom_stoploss = True
    #                'mfi': {'color': 'blue'},
    plot_config = {'main_plot': {'ma_entry_8': {'color': 'orange'}, 'ma_exit_16': {'color': 'orange'}}, 'subplots': {'rsi': {'rsi': {'color': 'orange'}, 'rsi_fast': {'color': 'red'}, 'rsi_slow': {'color': 'green'}}, 'ewo': {'EWO': {'color': 'blue'}}, 'ps': {'pump_strength': {'color': 'yellow'}}}}
    slippage_protection = {'retries': 3, 'max_slippage': -0.02}

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> float:
        if current_profit > 0.3:
            return 0.05
        elif current_profit > 0.1:
            return 0.03
        elif current_profit > 0.06:
            return 0.02
        elif current_profit > 0.04:
            return 0.01
        elif current_profit > 0.025:
            return 0.005
        elif current_profit > 0.018:
            return 0.005
        return self.stoploss

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

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, '15m') for pair in pairs]
        return informative_pairs

    def informative_1h_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        assert self.dp, 'DataProvider is required for multiple timeframes.'
        # Get the informative pair
        informative_1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=self.inf_1h)
        # EMA
        # informative_1h['ema_50'] = ta.EMA(informative_1h, timeperiod=50)
        # informative_1h['ema_200'] = ta.EMA(informative_1h, timeperiod=200)
        # # RSI
        # informative_1h['rsi'] = ta.RSI(informative_1h, timeperiod=14)
        # bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        # informative_1h['bb_lowerband'] = bollinger['lower']
        # informative_1h['bb_middleband'] = bollinger['mid']
        # informative_1h['bb_upperband'] = bollinger['upper']
        return informative_1h

    def informative_15m_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        assert self.dp, 'DataProvider is required for multiple timeframes.'
        # Get the informative pair
        informative_15m = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=self.inf_15m)
        # EMA
        # informative_1h['ema_50'] = ta.EMA(informative_1h, timeperiod=50)
        # informative_1h['ema_200'] = ta.EMA(informative_1h, timeperiod=200)
        # # RSI
        # informative_1h['rsi'] = ta.RSI(informative_1h, timeperiod=14)
        # bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        # informative_1h['bb_lowerband'] = bollinger['lower']
        # informative_1h['bb_middleband'] = bollinger['mid']
        # informative_1h['bb_upperband'] = bollinger['upper']
        return informative_15m

    def normal_tf_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
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
        #pump stregth
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['pump_strength'] = (dataframe['ema_50'] - dataframe['ema_200']) / dataframe['ema_50']
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_slow'] = ta.RSI(dataframe, timeperiod=20)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # informative_1h = self.informative_1h_indicators(dataframe, metadata)
        informative_15m = self.informative_15m_indicators(dataframe, metadata)
        dataframe = merge_informative_pair(dataframe, informative_15m, self.timeframe, self.inf_15m, ffill=True)
        # The indicators for the normal (5m) timeframe
        dataframe = self.normal_tf_indicators(dataframe, metadata)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dont_entry_conditions = []
        # don't entry if there isn't 3% profit to be made
        dont_entry_conditions.append(dataframe['close_15m'].rolling(self.lookback_candles.value).max() < dataframe['close'] * self.profit_threshold.value)
        dataframe.loc[(dataframe['rsi_fast'] < self.rsi_fast_entry.value) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] > self.ewo_high.value) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value), ['enter_long', 'enter_tag']] = (1, 'ewo1')
        dataframe.loc[(dataframe['rsi_fast'] < self.rsi_fast_entry.value) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset_2.value) & (dataframe['EWO'] > self.ewo_high_2.value) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['rsi'] < 25), ['enter_long', 'enter_tag']] = (1, 'ewo2')
        dataframe.loc[(dataframe['rsi_fast'] < self.rsi_fast_entry.value) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] < self.ewo_low.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value), ['enter_long', 'enter_tag']] = (1, 'ewolow')
        if dont_entry_conditions:
            for condition in dont_entry_conditions:
                dataframe.loc[condition, 'enter_long'] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append((dataframe['close'] > dataframe['sma_9']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset_2.value) & (dataframe['rsi'] > 50) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']) | (dataframe['close'] < dataframe['hma_50']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'exit_long'] = 1
        return dataframe

class NASOSv5_antipump(NASOSv5):
    antipump_threshold = DecimalParameter(0, 0.4, default=0.113, space='entry', optimize=True)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dont_entry_conditions = []
        # don't entry if there isn't 3% profit to be made
        dont_entry_conditions.append(dataframe['close_15m'].rolling(self.lookback_candles.value).max() < dataframe['close'] * self.profit_threshold.value)
        dataframe.loc[(dataframe['pump_strength'] < self.antipump_threshold.value) & (dataframe['rsi_fast'] < self.rsi_fast_entry.value) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] > self.ewo_high.value) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value), ['enter_long', 'enter_tag']] = (1, 'ewo1')
        dataframe.loc[(dataframe['rsi_fast'] < self.rsi_fast_entry.value) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset_2.value) & (dataframe['EWO'] > self.ewo_high_2.value) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['rsi'] < 25), ['enter_long', 'enter_tag']] = (1, 'ewo2')
        dataframe.loc[(dataframe['rsi_fast'] < self.rsi_fast_entry.value) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] < self.ewo_low.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value), ['enter_long', 'enter_tag']] = (1, 'ewolow')
        if dont_entry_conditions:
            for condition in dont_entry_conditions:
                dataframe.loc[condition, 'enter_long'] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []  # 4 consecutive equal highs, a whale gets rid off a fortune, go away before is too late
        conditions.append((dataframe['high'] == dataframe['high'].shift(1)) & (dataframe['high'].shift(1) == dataframe['high'].shift(2)) & (dataframe['high'].shift(2) == dataframe['high'].shift(3)))
        conditions.append((dataframe['close'] > dataframe['sma_9']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset_2.value) & (dataframe['rsi'] > 50) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']) | (dataframe['close'] < dataframe['hma_50']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'exit_long'] = 1
        return dataframe