from datetime import datetime, timedelta, timezone
from functools import reduce
from typing import List
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import pandas as pd
import pandas_ta as pta
import talib.abstract as ta
import technical.indicators as ftt
from freqtrade.persistence import Trade, PairLocks
from freqtrade.strategy import BooleanParameter, DecimalParameter, IntParameter, stoploss_from_open, merge_informative_pair
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame, Series
from skopt.space import Dimension, Integer

def bollinger_bands(stock_price, window_size, num_of_std):
    rolling_mean = stock_price.rolling(window=window_size).mean()
    rolling_std = stock_price.rolling(window=window_size).std()
    lower_band = rolling_mean - rolling_std * num_of_std
    return (np.nan_to_num(rolling_mean), np.nan_to_num(lower_band))

def ha_typical_price(bars):
    res = (bars['ha_high'] + bars['ha_low'] + bars['ha_close']) / 3.0
    return Series(index=bars.index, data=res)

class ClucHAnix_BB_RPB_MOD(IStrategy):
    INTERFACE_VERSION = 3
    # Buy hyperspace params:
    entry_params = {'antipump_threshold': 0.133, 'entry_btc_safe_1d': -0.311, 'clucha_bbdelta_close': 0.04796, 'clucha_bbdelta_tail': 0.93112, 'clucha_close_bblower': 0.01645, 'clucha_closedelta_close': 0.00931, 'clucha_enabled': False, 'clucha_rocr_1h': 0.41663, 'cofi_adx': 8, 'cofi_ema': 0.639, 'cofi_enabled': False, 'cofi_ewo_high': 5.6, 'cofi_fastd': 40, 'cofi_fastk': 13, 'ewo_1_enabled': False, 'ewo_1_rsi_14': 45, 'ewo_1_rsi_4': 7, 'ewo_candles_entry': 13, 'ewo_candles_exit': 19, 'ewo_high': 5.249, 'ewo_high_offset': 1.04116, 'ewo_low': -11.424, 'ewo_low_enabled': True, 'ewo_low_offset': 0.97463, 'ewo_low_rsi_4': 35, 'lambo1_ema_14_factor': 1.054, 'lambo1_enabled': False, 'lambo1_rsi_14_limit': 26, 'lambo1_rsi_4_limit': 18, 'lambo2_ema_14_factor': 0.981, 'lambo2_enabled': True, 'lambo2_rsi_14_limit': 39, 'lambo2_rsi_4_limit': 44, 'local_trend_bb_factor': 0.823, 'local_trend_closedelta': 19.253, 'local_trend_ema_diff': 0.125, 'local_trend_enabled': True, 'nfi32_cti_limit': -1.09639, 'nfi32_enabled': True, 'nfi32_rsi_14': 15, 'nfi32_rsi_4': 49, 'nfi32_sma_factor': 0.93391}
    # Sell hyperspace params:
    # custom stoploss params, come from BB_RPB_TSL
    exit_params = {'pHSL': -0.32, 'pPF_1': 0.02, 'pPF_2': 0.047, 'pSL_1': 0.02, 'pSL_2': 0.046, 'exit-fisher': 0.38414, 'exit-bbmiddle-close': 1.07634}
    # ROI table:
    minimal_roi = {'0': 0.05, '15': 0.04, '51': 0.03, '81': 0.02, '112': 0.01, '154': 0.0001, '240': -10}
    # Stoploss:
    stoploss = -0.99  # use custom stoploss
    # Trailing stop:
    trailing_stop = False
    trailing_stop_positive = 0.001
    trailing_stop_positive_offset = 0.012
    trailing_only_offset_is_reached = False
    '\n    END HYPEROPT\n    '
    timeframe = '1m'
    # Make sure these match or are not overridden in config
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    # Custom stoploss
    use_custom_stoploss = True
    process_only_new_candles = True
    startup_candle_count = 200
    order_types = {'entry': 'market', 'exit': 'market', 'emergencyexit': 'market', 'forceentry': 'market', 'forceexit': 'market', 'stoploss': 'market', 'stoploss_on_exchange': False, 'stoploss_on_exchange_interval': 60, 'stoploss_on_exchange_limit_ratio': 0.99}
    # hard stoploss profit
    pHSL = DecimalParameter(-0.5, -0.04, default=-0.08, decimals=3, space='exit', load=True)
    # profit threshold 1, trigger point, SL_1 is used
    pPF_1 = DecimalParameter(0.008, 0.02, default=0.016, decimals=3, space='exit', load=True)
    pSL_1 = DecimalParameter(0.008, 0.02, default=0.011, decimals=3, space='exit', load=True)
    # profit threshold 2, SL_2 is used
    pPF_2 = DecimalParameter(0.04, 0.1, default=0.08, decimals=3, space='exit', load=True)
    pSL_2 = DecimalParameter(0.02, 0.07, default=0.04, decimals=3, space='exit', load=True)
    # entry param
    # ClucHA
    clucha_bbdelta_close = DecimalParameter(0.01, 0.05, default=entry_params['clucha_bbdelta_close'], decimals=5, space='entry', optimize=True)
    clucha_bbdelta_tail = DecimalParameter(0.7, 1.2, default=entry_params['clucha_bbdelta_tail'], decimals=5, space='entry', optimize=True)
    clucha_close_bblower = DecimalParameter(0.001, 0.05, default=entry_params['clucha_close_bblower'], decimals=5, space='entry', optimize=True)
    clucha_closedelta_close = DecimalParameter(0.001, 0.05, default=entry_params['clucha_closedelta_close'], decimals=5, space='entry', optimize=True)
    clucha_rocr_1h = DecimalParameter(0.1, 1.0, default=entry_params['clucha_rocr_1h'], decimals=5, space='entry', optimize=True)
    # lambo1
    lambo1_ema_14_factor = DecimalParameter(0.8, 1.2, decimals=3, default=entry_params['lambo1_ema_14_factor'], space='entry', optimize=True)
    lambo1_rsi_4_limit = IntParameter(5, 60, default=entry_params['lambo1_rsi_4_limit'], space='entry', optimize=True)
    lambo1_rsi_14_limit = IntParameter(5, 60, default=entry_params['lambo1_rsi_14_limit'], space='entry', optimize=True)
    # lambo2
    lambo2_ema_14_factor = DecimalParameter(0.8, 1.2, decimals=3, default=entry_params['lambo2_ema_14_factor'], space='entry', optimize=True)
    lambo2_rsi_4_limit = IntParameter(5, 60, default=entry_params['lambo2_rsi_4_limit'], space='entry', optimize=True)
    lambo2_rsi_14_limit = IntParameter(5, 60, default=entry_params['lambo2_rsi_14_limit'], space='entry', optimize=True)
    # local_uptrend
    local_trend_ema_diff = DecimalParameter(0, 0.2, default=entry_params['local_trend_ema_diff'], space='entry', optimize=True)
    local_trend_bb_factor = DecimalParameter(0.8, 1.2, default=entry_params['local_trend_bb_factor'], space='entry', optimize=True)
    local_trend_closedelta = DecimalParameter(5.0, 30.0, default=entry_params['local_trend_closedelta'], space='entry', optimize=True)
    # ewo_1 and ewo_low
    ewo_candles_entry = IntParameter(2, 30, default=entry_params['ewo_candles_entry'], space='entry', optimize=True)
    ewo_candles_exit = IntParameter(2, 35, default=entry_params['ewo_candles_exit'], space='entry', optimize=True)
    ewo_low_offset = DecimalParameter(0.7, 1.2, default=entry_params['ewo_low_offset'], decimals=5, space='entry', optimize=True)
    ewo_high_offset = DecimalParameter(0.75, 1.5, default=entry_params['ewo_high_offset'], decimals=5, space='entry', optimize=True)
    ewo_high = DecimalParameter(2.0, 15.0, default=entry_params['ewo_high'], space='entry', optimize=True)
    ewo_1_rsi_14 = IntParameter(10, 100, default=entry_params['ewo_1_rsi_14'], space='entry', optimize=True)
    ewo_1_rsi_4 = IntParameter(1, 50, default=entry_params['ewo_1_rsi_4'], space='entry', optimize=True)
    ewo_low_rsi_4 = IntParameter(1, 50, default=entry_params['ewo_low_rsi_4'], space='entry', optimize=True)
    ewo_low = DecimalParameter(-20.0, -8.0, default=entry_params['ewo_low'], space='entry', optimize=True)
    # cofi
    cofi_ema = DecimalParameter(0.6, 1.4, default=entry_params['cofi_ema'], space='entry', optimize=True)
    cofi_fastk = IntParameter(1, 100, default=entry_params['cofi_fastk'], space='entry', optimize=True)
    cofi_fastd = IntParameter(1, 100, default=entry_params['cofi_fastd'], space='entry', optimize=True)
    cofi_adx = IntParameter(1, 100, default=entry_params['cofi_adx'], space='entry', optimize=True)
    cofi_ewo_high = DecimalParameter(1.0, 15.0, default=entry_params['cofi_ewo_high'], space='entry', optimize=True)
    # nfi32
    nfi32_rsi_4 = IntParameter(1, 100, default=entry_params['nfi32_rsi_4'], space='entry', optimize=True)
    nfi32_rsi_14 = IntParameter(1, 100, default=entry_params['nfi32_rsi_4'], space='entry', optimize=True)
    nfi32_sma_factor = DecimalParameter(0.7, 1.2, default=entry_params['nfi32_sma_factor'], decimals=5, space='entry', optimize=True)
    nfi32_cti_limit = DecimalParameter(-1.2, 0, default=entry_params['nfi32_cti_limit'], decimals=5, space='entry', optimize=True)
    entry_btc_safe_1d = DecimalParameter(-0.5, -0.015, default=entry_params['entry_btc_safe_1d'], optimize=True)
    antipump_threshold = DecimalParameter(0, 0.4, default=entry_params['antipump_threshold'], space='entry', optimize=True)
    ewo_1_enabled = BooleanParameter(default=entry_params['ewo_1_enabled'], space='entry', optimize=True)
    ewo_low_enabled = BooleanParameter(default=entry_params['ewo_low_enabled'], space='entry', optimize=True)
    cofi_enabled = BooleanParameter(default=entry_params['cofi_enabled'], space='entry', optimize=True)
    lambo1_enabled = BooleanParameter(default=entry_params['lambo1_enabled'], space='entry', optimize=True)
    lambo2_enabled = BooleanParameter(default=entry_params['lambo2_enabled'], space='entry', optimize=True)
    local_trend_enabled = BooleanParameter(default=entry_params['local_trend_enabled'], space='entry', optimize=True)
    nfi32_enabled = BooleanParameter(default=entry_params['nfi32_enabled'], space='entry', optimize=True)
    clucha_enabled = BooleanParameter(default=entry_params['clucha_enabled'], space='entry', optimize=True)

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, '1h') for pair in pairs]
        informative_pairs += [('BTC/USDT', '1m')]
        informative_pairs += [('BTC/USDT', '1d')]
        return informative_pairs
    ############################################################################

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> float:
        # hard stoploss profit
        HSL = self.pHSL.value
        PF_1 = self.pPF_1.value
        SL_1 = self.pSL_1.value
        PF_2 = self.pPF_2.value
        SL_2 = self.pSL_2.value
        # For profits between PF_1 and PF_2 the stoploss (sl_profit) used is linearly interpolated
        # between the values of SL_1 and SL_2. For all profits above PL_2 the sl_profit value
        # rises linearly with current profit, for profits below PF_1 the hard stoploss profit is used.
        if current_profit > PF_2:
            sl_profit = SL_2 + (current_profit - PF_2)
        elif current_profit > PF_1:
            sl_profit = SL_1 + (current_profit - PF_1) * (SL_2 - SL_1) / (PF_2 - PF_1)
        else:
            sl_profit = HSL
        # Only for hyperopt invalid return
        if sl_profit >= current_profit:
            return -0.99
        return stoploss_from_open(sl_profit, current_profit)
    ############################################################################

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Heikin Ashi Candles
        heikinashi = qtpylib.heikinashi(dataframe)
        dataframe['ha_open'] = heikinashi['open']
        dataframe['ha_close'] = heikinashi['close']
        dataframe['ha_high'] = heikinashi['high']
        dataframe['ha_low'] = heikinashi['low']
        dataframe['ema_8'] = ta.EMA(dataframe, timeperiod=8)
        dataframe['ema_14'] = ta.EMA(dataframe, timeperiod=14)
        dataframe['ema_26'] = ta.EMA(dataframe, timeperiod=26)
        dataframe['sma_15'] = ta.SMA(dataframe, timeperiod=15)
        dataframe['rsi_4'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_14'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_20'] = ta.RSI(dataframe, timeperiod=20)
        # CTI
        dataframe['cti'] = pta.cti(dataframe['close'], length=20)
        # Cofi
        stoch_fast = ta.STOCHF(dataframe, 5, 3, 0, 3, 0)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']
        dataframe['adx'] = ta.ADX(dataframe)
        # Set Up Bollinger Bands
        mid, lower = bollinger_bands(ha_typical_price(dataframe), window_size=40, num_of_std=2)
        dataframe['lower'] = lower
        dataframe['mid'] = mid
        bollinger2 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband2'] = bollinger2['lower']
        dataframe['bb_middleband2'] = bollinger2['mid']
        dataframe['bb_upperband2'] = bollinger2['upper']
        dataframe['closedelta'] = (dataframe['close'] - dataframe['close'].shift()).abs()
        # # ClucHA
        dataframe['bbdelta'] = (mid - dataframe['lower']).abs()
        dataframe['ha_closedelta'] = (dataframe['ha_close'] - dataframe['ha_close'].shift()).abs()
        dataframe['tail'] = (dataframe['ha_close'] - dataframe['ha_low']).abs()
        dataframe['bb_lowerband'] = dataframe['lower']
        dataframe['bb_middleband'] = dataframe['mid']
        dataframe['ema_fast'] = ta.EMA(dataframe['ha_close'], timeperiod=3)
        dataframe['ema_slow'] = ta.EMA(dataframe['ha_close'], timeperiod=50)
        dataframe['rocr'] = ta.ROCR(dataframe['ha_close'], timeperiod=28)
        # Elliot
        dataframe['EWO'] = EWO(dataframe, 50, 200)
        rsi = ta.RSI(dataframe)
        dataframe['rsi'] = rsi
        rsi = 0.1 * (rsi - 50)
        dataframe['fisher'] = (np.exp(2 * rsi) - 1) / (np.exp(2 * rsi) + 1)
        inf_tf = '1h'
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=inf_tf)
        inf_heikinashi = qtpylib.heikinashi(informative)
        informative['ha_close'] = inf_heikinashi['close']
        informative['rocr'] = ta.ROCR(informative['ha_close'], timeperiod=168)
        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, inf_tf, ffill=True)
        ### BTC protection
        dataframe['btc_1m'] = self.dp.get_pair_dataframe('BTC/USDT', timeframe='1m')['close']
        btc_1d = self.dp.get_pair_dataframe('BTC/USDT', timeframe='1d')[['date', 'close']].rename(columns={'close': 'btc'}).shift(1)
        dataframe = merge_informative_pair(dataframe, btc_1d, '1m', '1d', ffill=True)
        # Pump strength
        dataframe['zema_30'] = ftt.zema(dataframe, period=30)
        dataframe['zema_200'] = ftt.zema(dataframe, period=200)
        dataframe['pump_strength'] = (dataframe['zema_30'] - dataframe['zema_200']) / dataframe['zema_30']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        dataframe.loc[:, 'enter_tag'] = ''
        dataframe[f'ma_entry_{self.ewo_candles_entry.value}'] = ta.EMA(dataframe, timeperiod=int(self.ewo_candles_entry.value))
        dataframe[f'ma_exit_{self.ewo_candles_exit.value}'] = ta.EMA(dataframe, timeperiod=int(self.ewo_candles_exit.value))  # Make sure Volume is not 0
        is_btc_safe = (pct_change(dataframe['btc_1d'], dataframe['btc_1m']).fillna(0) > self.entry_btc_safe_1d.value) & (dataframe['volume'] > 0)
        is_pump_safe = dataframe['pump_strength'] < self.antipump_threshold.value
        lambo1 = bool(self.lambo1_enabled.value) & (dataframe['close'] < dataframe['ema_14'] * self.lambo1_ema_14_factor.value) & (dataframe['rsi_4'] < int(self.lambo1_rsi_4_limit.value)) & (dataframe['rsi_14'] < int(self.lambo1_rsi_14_limit.value))
        dataframe.loc[lambo1, 'enter_tag'] += 'lambo1_'
        conditions.append(lambo1)
        lambo2 = bool(self.lambo2_enabled.value) & (dataframe['close'] < dataframe['ema_14'] * self.lambo2_ema_14_factor.value) & (dataframe['rsi_4'] < int(self.lambo2_rsi_4_limit.value)) & (dataframe['rsi_14'] < int(self.lambo2_rsi_14_limit.value))
        dataframe.loc[lambo2, 'enter_tag'] += 'lambo2_'
        conditions.append(lambo2)
        local_uptrend = bool(self.local_trend_enabled.value) & (dataframe['ema_26'] > dataframe['ema_14']) & (dataframe['ema_26'] - dataframe['ema_14'] > dataframe['open'] * self.local_trend_ema_diff.value) & (dataframe['ema_26'].shift() - dataframe['ema_14'].shift() > dataframe['open'] / 100) & (dataframe['close'] < dataframe['bb_lowerband2'] * self.local_trend_bb_factor.value) & (dataframe['closedelta'] > dataframe['close'] * self.local_trend_closedelta.value / 1000)
        dataframe.loc[local_uptrend, 'enter_tag'] += 'local_uptrend_'
        conditions.append(local_uptrend)
        nfi_32 = bool(self.nfi32_enabled.value) & (dataframe['rsi_20'] < dataframe['rsi_20'].shift(1)) & (dataframe['rsi_4'] < self.nfi32_rsi_4.value) & (dataframe['rsi_14'] > self.nfi32_rsi_14.value) & (dataframe['close'] < dataframe['sma_15'] * self.nfi32_sma_factor.value) & (dataframe['cti'] < self.nfi32_cti_limit.value)
        dataframe.loc[nfi_32, 'enter_tag'] += 'nfi_32_'
        conditions.append(nfi_32)
        ewo_1 = bool(self.ewo_1_enabled.value) & (dataframe['rsi_4'] < self.ewo_1_rsi_4.value) & (dataframe['close'] < dataframe[f'ma_entry_{self.ewo_candles_entry.value}'] * self.ewo_low_offset.value) & (dataframe['EWO'] > self.ewo_high.value) & (dataframe['rsi_14'] < self.ewo_1_rsi_14.value) & (dataframe['close'] < dataframe[f'ma_exit_{self.ewo_candles_exit.value}'] * self.ewo_high_offset.value)
        dataframe.loc[ewo_1, 'enter_tag'] += 'ewo1_'
        conditions.append(ewo_1)
        ewo_low = bool(self.ewo_low_enabled.value) & (dataframe['rsi_4'] < self.ewo_low_rsi_4.value) & (dataframe['close'] < dataframe[f'ma_entry_{self.ewo_candles_entry.value}'] * self.ewo_low_offset.value) & (dataframe['EWO'] < self.ewo_low.value) & (dataframe['close'] < dataframe[f'ma_exit_{self.ewo_candles_exit.value}'] * self.ewo_high_offset.value)
        dataframe.loc[ewo_low, 'enter_tag'] += 'ewo_low_'
        conditions.append(ewo_low)
        cofi = bool(self.cofi_enabled.value) & (dataframe['open'] < dataframe['ema_8'] * self.cofi_ema.value) & qtpylib.crossed_above(dataframe['fastk'], dataframe['fastd']) & (dataframe['fastk'] < self.cofi_fastk.value) & (dataframe['fastd'] < self.cofi_fastd.value) & (dataframe['adx'] > self.cofi_adx.value) & (dataframe['EWO'] > self.cofi_ewo_high.value)
        dataframe.loc[cofi, 'enter_tag'] += 'cofi_'
        conditions.append(cofi)
        clucHA = bool(self.clucha_enabled.value) & dataframe['rocr_1h'].gt(self.clucha_rocr_1h.value) & (dataframe['lower'].shift().gt(0) & dataframe['bbdelta'].gt(dataframe['ha_close'] * self.clucha_bbdelta_close.value) & dataframe['ha_closedelta'].gt(dataframe['ha_close'] * self.clucha_closedelta_close.value) & dataframe['tail'].lt(dataframe['bbdelta'] * self.clucha_bbdelta_tail.value) & dataframe['ha_close'].lt(dataframe['lower'].shift()) & dataframe['ha_close'].le(dataframe['ha_close'].shift()) | (dataframe['ha_close'] < dataframe['ema_slow']) & (dataframe['ha_close'] < self.clucha_close_bblower.value * dataframe['bb_lowerband']))
        dataframe.loc[clucHA, 'enter_tag'] += 'clucHA_'
        conditions.append(clucHA)
        # is_btc_safe &  # broken?
        # is_pump_safe &
        dataframe.loc[reduce(lambda x, y: x | y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        params = self.exit_params
        dataframe.loc[(dataframe['fisher'] > params['exit-fisher']) & dataframe['ha_high'].le(dataframe['ha_high'].shift(1)) & dataframe['ha_high'].shift(1).le(dataframe['ha_high'].shift(2)) & dataframe['ha_close'].le(dataframe['ha_close'].shift(1)) & (dataframe['ema_fast'] > dataframe['ha_close']) & (dataframe['ha_close'] * params['exit-bbmiddle-close'] > dataframe['bb_middleband']) & (dataframe['volume'] > 0), 'exit_long'] = 1
        return dataframe

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float, rate: float, time_in_force: str, exit_reason: str, current_time: datetime, **kwargs) -> bool:
        trade.exit_reason = exit_reason + '_' + trade.entry_tag
        return True

def pct_change(a, b):
    return (b - a) / a

def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['low'] * 100
    return emadif