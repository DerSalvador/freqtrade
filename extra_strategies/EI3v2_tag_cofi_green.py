# --- Do not remove these libs ---
import datetime
import logging
import math
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
logger = logging.getLogger(__name__)
# @Rallipanos # changes by IcHiAT

def EWO(dataframe, ema_length=5, ema2_length=3):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['close'] * 100
    return emadif

class EI3v2_tag_cofi_green(IStrategy):
    INTERFACE_VERSION = 3
    '\n    # ROI table:\n    minimal_roi = {\n        "0": 0.08,\n        "20": 0.04,\n        "40": 0.032,\n        "87": 0.016,\n        "201": 0,\n        "202": -1\n    }\n    '
    # Buy hyperspace params:
    entry_params = {'base_nb_candles_entry': 12, 'rsi_entry': 58, 'ewo_high': 3.001, 'ewo_low': -10.289, 'low_offset': 0.987, 'lambo2_ema_14_factor': 0.981, 'lambo2_enabled': True, 'lambo2_rsi_14_limit': 39, 'lambo2_rsi_4_limit': 44, 'entry_adx': 20, 'entry_fastd': 20, 'entry_fastk': 22, 'entry_ema_cofi': 0.98, 'entry_ewo_high': 4.179}
    # Sell hyperspace params:
    exit_params = {'base_nb_candles_exit': 22, 'high_offset': 1.014, 'high_offset_2': 1.01}

    @property
    def protections(self):
        return [{'method': 'CooldownPeriod', 'stop_duration_candles': 5}, {'method': 'MaxDrawdown', 'lookback_period_candles': 48, 'trade_limit': 20, 'stop_duration_candles': 4, 'max_allowed_drawdown': 0.2}, {'method': 'StoplossGuard', 'lookback_period_candles': 24, 'trade_limit': 4, 'stop_duration_candles': 2, 'only_per_pair': False}, {'method': 'LowProfitPairs', 'lookback_period_candles': 6, 'trade_limit': 2, 'stop_duration_candles': 60, 'required_profit': 0.02}, {'method': 'LowProfitPairs', 'lookback_period_candles': 24, 'trade_limit': 4, 'stop_duration_candles': 2, 'required_profit': 0.01}]
    # ROI table:
    minimal_roi = {'0': 0.99}
    # Stoploss:
    stoploss = -0.99
    # SMAOffset
    base_nb_candles_entry = IntParameter(8, 20, default=entry_params['base_nb_candles_entry'], space='entry', optimize=False)
    base_nb_candles_exit = IntParameter(8, 20, default=exit_params['base_nb_candles_exit'], space='exit', optimize=False)
    low_offset = DecimalParameter(0.985, 0.995, default=entry_params['low_offset'], space='entry', optimize=True)
    high_offset = DecimalParameter(1.005, 1.015, default=exit_params['high_offset'], space='exit', optimize=True)
    high_offset_2 = DecimalParameter(1.01, 1.02, default=exit_params['high_offset_2'], space='exit', optimize=True)
    # lambo2
    lambo2_ema_14_factor = DecimalParameter(0.8, 1.2, decimals=3, default=entry_params['lambo2_ema_14_factor'], space='entry', optimize=True)
    lambo2_rsi_4_limit = IntParameter(5, 60, default=entry_params['lambo2_rsi_4_limit'], space='entry', optimize=True)
    lambo2_rsi_14_limit = IntParameter(5, 60, default=entry_params['lambo2_rsi_14_limit'], space='entry', optimize=True)
    # Protection
    fast_ewo = 50
    slow_ewo = 200
    ewo_low = DecimalParameter(-20.0, -8.0, default=entry_params['ewo_low'], space='entry', optimize=True)
    ewo_high = DecimalParameter(3.0, 3.4, default=entry_params['ewo_high'], space='entry', optimize=True)
    rsi_entry = IntParameter(30, 70, default=entry_params['rsi_entry'], space='entry', optimize=False)
    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.001
    trailing_stop_positive_offset = 0.012
    trailing_only_offset_is_reached = True
    #cofi
    is_optimize_cofi = False
    entry_ema_cofi = DecimalParameter(0.96, 0.98, default=0.97, optimize=is_optimize_cofi)
    entry_fastk = IntParameter(20, 30, default=20, optimize=is_optimize_cofi)
    entry_fastd = IntParameter(20, 30, default=20, optimize=is_optimize_cofi)
    entry_adx = IntParameter(20, 30, default=30, optimize=is_optimize_cofi)
    entry_ewo_high = DecimalParameter(2, 12, default=3.553, optimize=is_optimize_cofi)
    # Sell signal
    use_exit_signal = True
    exit_profit_only = True
    exit_profit_offset = 0.01
    ignore_roi_if_entry_signal = False
    ## Optional order time in force.
    order_time_in_force = {'entry': 'gtc', 'exit': 'gtc'}
    # Optimal timeframe for the strategy
    timeframe = '5m'
    inf_1h = '1h'
    process_only_new_candles = True
    startup_candle_count = 400
    plot_config = {'main_plot': {'ma_entry': {'color': 'orange'}, 'ma_exit': {'color': 'orange'}}}

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float, current_profit: float, **kwargs):
        # Sell any positions at a loss if they are held for more than 7 days.
        if current_profit < -0.04 and (current_time - trade.open_date_utc).days >= 4:
            return 'unclog'

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, '1h') for pair in pairs]
        if self.config['stake_currency'] in ['USDT', 'BUSD', 'USDC', 'DAI', 'TUSD', 'PAX', 'USD', 'EUR', 'GBP']:
            btc_info_pair = f"BTC/{self.config['stake_currency']}"
        else:
            btc_info_pair = 'BTC/USDT'
        informative_pairs.append((btc_info_pair, self.timeframe))
        informative_pairs.append((btc_info_pair, self.inf_1h))
        return informative_pairs

    def pump_dump_protection(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df36h = dataframe.copy().shift(432)  # TODO FIXME: This assumes 5m timeframe
        df24h = dataframe.copy().shift(288)  # TODO FIXME: This assumes 5m timeframe
        dataframe['volume_mean_short'] = dataframe['volume'].rolling(4).mean()
        dataframe['volume_mean_long'] = df24h['volume'].rolling(48).mean()
        dataframe['volume_mean_base'] = df36h['volume'].rolling(288).mean()
        dataframe['volume_change_percentage'] = dataframe['volume_mean_long'] / dataframe['volume_mean_base']
        dataframe['rsi_mean'] = dataframe['rsi'].rolling(48).mean()
        dataframe['pnd_volume_warn'] = np.where(dataframe['volume_mean_short'] / dataframe['volume_mean_long'] > 5.0, -1, 0)
        return dataframe

    def base_tf_btc_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Indicators
        # -----------------------------------------------------------------------------------------
        dataframe['price_trend_long'] = dataframe['close'].rolling(8).mean() / dataframe['close'].shift(8).rolling(144).mean()
        # Add prefix
        # -----------------------------------------------------------------------------------------
        ignore_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        dataframe.rename(columns=lambda s: f'btc_{s}' if s not in ignore_columns else s, inplace=True)
        return dataframe

    def info_tf_btc_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Indicators
        # -----------------------------------------------------------------------------------------
        dataframe['rsi_8'] = ta.RSI(dataframe, timeperiod=8)
        # Add prefix
        # -----------------------------------------------------------------------------------------
        ignore_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        dataframe.rename(columns=lambda s: f'btc_{s}' if s not in ignore_columns else s, inplace=True)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if self.config['stake_currency'] in ['USDT', 'BUSD']:
            btc_info_pair = f"BTC/{self.config['stake_currency']}"
        else:
            btc_info_pair = 'BTC/USDT'
        btc_info_tf = self.dp.get_pair_dataframe(btc_info_pair, self.inf_1h)
        btc_info_tf = self.info_tf_btc_indicators(btc_info_tf, metadata)
        dataframe = merge_informative_pair(dataframe, btc_info_tf, self.timeframe, self.inf_1h, ffill=True)
        drop_columns = [f'{s}_{self.inf_1h}' for s in ['date', 'open', 'high', 'low', 'close', 'volume']]
        dataframe.drop(columns=dataframe.columns.intersection(drop_columns), inplace=True)
        btc_base_tf = self.dp.get_pair_dataframe(btc_info_pair, self.timeframe)
        btc_base_tf = self.base_tf_btc_indicators(btc_base_tf, metadata)
        dataframe = merge_informative_pair(dataframe, btc_base_tf, self.timeframe, self.timeframe, ffill=True)
        drop_columns = [f'{s}_{self.timeframe}' for s in ['date', 'open', 'high', 'low', 'close', 'volume']]
        dataframe.drop(columns=dataframe.columns.intersection(drop_columns), inplace=True)
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
        #lambo2
        dataframe['ema_14'] = ta.EMA(dataframe, timeperiod=14)
        dataframe['rsi_4'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_14'] = ta.RSI(dataframe, timeperiod=14)
        # Pump strength
        dataframe['zema_30'] = ftt.zema(dataframe, period=30)
        dataframe['zema_200'] = ftt.zema(dataframe, period=200)
        dataframe['pump_strength'] = (dataframe['zema_30'] - dataframe['zema_200']) / dataframe['zema_30']
        # Cofi
        stoch_fast = ta.STOCHF(dataframe, 5, 3, 0, 3, 0)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']
        dataframe['adx'] = ta.ADX(dataframe)
        dataframe['ema_8'] = ta.EMA(dataframe, timeperiod=8)
        dataframe = self.pump_dump_protection(dataframe, metadata)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        dataframe.loc[:, 'enter_tag'] = ''
        #bool(self.lambo2_enabled.value) &
        #(dataframe['pump_warning'] == 0) &
        lambo2 = (dataframe['close'] < dataframe['ema_14'] * self.lambo2_ema_14_factor.value) & (dataframe['rsi_4'] < int(self.lambo2_rsi_4_limit.value)) & (dataframe['rsi_14'] < int(self.lambo2_rsi_14_limit.value))
        dataframe.loc[lambo2, 'enter_tag'] += 'lambo2_'
        conditions.append(lambo2)
        entry1ewo = (dataframe['rsi_fast'] < 35) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] > self.ewo_high.value) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value)
        dataframe.loc[entry1ewo, 'enter_tag'] += 'entry1eworsi_'
        conditions.append(entry1ewo)
        entry2ewo = (dataframe['rsi_fast'] < 35) & (dataframe['close'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}'] * self.low_offset.value) & (dataframe['EWO'] < self.ewo_low.value) & (dataframe['volume'] > 0) & (dataframe['close'] < dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value)
        dataframe.loc[entry2ewo, 'enter_tag'] += 'entry2ewo_'
        conditions.append(entry2ewo)
        is_cofi = (dataframe['open'] < dataframe['ema_8'] * self.entry_ema_cofi.value) & qtpylib.crossed_above(dataframe['fastk'], dataframe['fastd']) & (dataframe['fastk'] < self.entry_fastk.value) & (dataframe['fastd'] < self.entry_fastd.value) & (dataframe['adx'] > self.entry_adx.value) & (dataframe['EWO'] > self.entry_ewo_high.value)
        dataframe.loc[is_cofi, 'enter_tag'] += 'cofi_'
        conditions.append(is_cofi)
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'enter_long'] = 1
        dont_entry_conditions = []
        # don't entry if there seems to be a Pump and Dump event.
        dont_entry_conditions.append(dataframe['pnd_volume_warn'] < 0.0)
        # BTC price protection
        dont_entry_conditions.append(dataframe['btc_rsi_8_1h'] < 35.0)
        if dont_entry_conditions:
            for condition in dont_entry_conditions:
                dataframe.loc[condition, 'enter_long'] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append((dataframe['close'] > dataframe['hma_50']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset_2.value) & (dataframe['rsi'] > 50) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']) | (dataframe['close'] < dataframe['hma_50']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'exit_long'] = 1
        return dataframe

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float, rate: float, time_in_force: str, exit_reason: str, current_time: datetime, **kwargs) -> bool:
        trade.exit_reason = exit_reason + '_' + trade.entry_tag
        return True

def pct_change(a, b):
    return (b - a) / a

class EI3v2_tag_cofi_dca_green(EI3v2_tag_cofi_green):
    initial_safety_order_trigger = -0.018
    max_safety_orders = 8
    safety_order_step_scale = 1.2
    safety_order_volume_scale = 1.4
    entry_params = {'dca_min_rsi': 35}
    # append entry_params of parent class
    entry_params.update(EI3v2_tag_cofi_green.entry_params)
    dca_min_rsi = IntParameter(35, 75, default=entry_params['dca_min_rsi'], space='entry', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def adjust_trade_position(self, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, min_stake: float, max_stake: float, **kwargs):
        if current_profit > self.initial_safety_order_trigger:
            return None
        # credits to reinuvader for not blindly executing safety orders
        # Obtain pair dataframe.
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        # Only entry when it seems it's climbing back up
        last_candle = dataframe.iloc[-1].squeeze()
        previous_candle = dataframe.iloc[-2].squeeze()
        if last_candle['close'] < previous_candle['close']:
            return None
        count_of_entrys = 0
        for order in trade.orders:
            if order.ft_is_open or order.ft_order_side != 'entry':
                continue
            if order.status == 'closed':
                count_of_entrys += 1
        if 1 <= count_of_entrys <= self.max_safety_orders:
            safety_order_trigger = abs(self.initial_safety_order_trigger) + abs(self.initial_safety_order_trigger) * self.safety_order_step_scale * (math.pow(self.safety_order_step_scale, count_of_entrys - 1) - 1) / (self.safety_order_step_scale - 1)
            if current_profit <= -1 * abs(safety_order_trigger):
                try:
                    stake_amount = self.wallets.get_trade_stake_amount(trade.pair, None)
                    stake_amount = stake_amount * math.pow(self.safety_order_volume_scale, count_of_entrys - 1)
                    amount = stake_amount / current_rate
                    logger.info(f'Initiating safety order entry #{count_of_entrys} for {trade.pair} with stake amount of {stake_amount} which equals {amount}')
                    return stake_amount
                except Exception as exception:
                    logger.info(f'Error occured while trying to get stake amount for {trade.pair}: {str(exception)}')
                    return None
        return None