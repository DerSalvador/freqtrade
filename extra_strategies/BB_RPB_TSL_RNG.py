# --- Do not remove these libs ---
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
import pandas_ta as pta
from freqtrade.persistence import Trade
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame, Series, DatetimeIndex, merge
from datetime import datetime, timedelta
from freqtrade.strategy import merge_informative_pair, CategoricalParameter, DecimalParameter, IntParameter, stoploss_from_open
from functools import reduce
from technical.indicators import RMI, zema
# --------------------------------

def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['low'] * 100
    return emadif
# Williams %R

def williams_r(dataframe: DataFrame, period: int=14) -> Series:
    """Williams %R, or just %R, is a technical analysis oscillator showing the current closing price in relation to the high and low
        of the past N days (for a given N). It was developed by a publisher and promoter of trading materials, Larry Williams.
        Its purpose is to tell whether a stock or commodity market is trading near the high or the low, or somewhere in between,
        of its recent trading range.
        The oscillator is on a negative scale, from −100 (lowest) up to 0 (highest).
    """
    highest_high = dataframe['high'].rolling(center=False, window=period).max()
    lowest_low = dataframe['low'].rolling(center=False, window=period).min()
    WR = Series((highest_high - dataframe['close']) / (highest_high - lowest_low), name=f'{period} Williams %R')
    return WR * -100

class BB_RPB_TSL_RNG(IStrategy):
    INTERFACE_VERSION = 3
    '\n        BB_RPB_TSL\n        @author jilv220\n        Simple bollinger brand strategy inspired by this blog  ( https://hacks-for-life.blogspot.com/2020/12/freqtrade-notes.html )\n        RPB, which stands for Real Pull Back, taken from ( https://github.com/GeorgeMurAlkh/freqtrade-stuff/blob/main/user_data/strategies/TheRealPullbackV2.py )\n        The trailing custom stoploss taken from BigZ04_TSL from Perkmeister ( modded by ilya )\n        I modified it to better suit my taste and added Hyperopt for this strategy.\n    '
    ##########################################################################
    # Hyperopt result area
    # entry space
    ##
    ##
    ##
    ##
    ##
    ##
    ##
    entry_params = {'entry_btc_safe': -289, 'entry_btc_safe_1d': -0.05, 'entry_threshold': 0.003, 'entry_bb_factor': 0.999, 'entry_bb_delta': 0.025, 'entry_bb_width': 0.095, 'entry_cci': -116, 'entry_cci_length': 25, 'entry_rmi': 49, 'entry_rmi_length': 17, 'entry_srsi_fk': 32, 'entry_closedelta': 12.148, 'entry_ema_diff': 0.022, 'entry_adx': 20, 'entry_fastd': 20, 'entry_fastk': 22, 'entry_ema_cofi': 0.98, 'entry_ewo_high': 4.179, 'entry_ema_high_2': 1.087, 'entry_ema_low_2': 0.97}
    # exit space
    exit_params = {'pHSL': -0.178, 'pPF_1': 0.019, 'pPF_2': 0.065, 'pSL_1': 0.019, 'pSL_2': 0.062, 'exit_btc_safe': -389, 'base_nb_candles_exit': 24, 'high_offset': 0.991, 'high_offset_2': 0.997}
    # really hard to use this
    minimal_roi = {'0': 0.1}
    # Optimal timeframe for the strategy
    timeframe = '5m'
    inf_1h = '1h'
    # Disabled
    stoploss = -0.99
    # Custom stoploss
    use_custom_stoploss = True
    use_exit_signal = True
    process_only_new_candles = True
    ############################################################################
    ## Buy params
    is_optimize_dip = False
    entry_rmi = IntParameter(30, 50, default=35, optimize=is_optimize_dip)
    entry_cci = IntParameter(-135, -90, default=-133, optimize=is_optimize_dip)
    entry_srsi_fk = IntParameter(30, 50, default=25, optimize=is_optimize_dip)
    entry_cci_length = IntParameter(25, 45, default=25, optimize=is_optimize_dip)
    entry_rmi_length = IntParameter(8, 20, default=8, optimize=is_optimize_dip)
    is_optimize_break = False
    entry_bb_width = DecimalParameter(0.05, 0.2, default=0.15, optimize=is_optimize_break)
    entry_bb_delta = DecimalParameter(0.025, 0.08, default=0.04, optimize=is_optimize_break)
    is_optimize_local_dip = False
    entry_ema_diff = DecimalParameter(0.022, 0.027, default=0.025, optimize=is_optimize_local_dip)
    entry_bb_factor = DecimalParameter(0.99, 0.999, default=0.995, optimize=False)
    entry_closedelta = DecimalParameter(12.0, 18.0, default=15.0, optimize=is_optimize_local_dip)
    is_optimize_ewo = False
    entry_rsi_fast = IntParameter(35, 50, default=45, optimize=False)
    entry_rsi = IntParameter(15, 30, default=35, optimize=False)
    entry_ewo = DecimalParameter(-6.0, 5, default=-5.585, optimize=is_optimize_ewo)
    entry_ema_low = DecimalParameter(0.9, 0.99, default=0.942, optimize=is_optimize_ewo)
    entry_ema_high = DecimalParameter(0.95, 1.2, default=1.084, optimize=is_optimize_ewo)
    is_optimize_ewo_2 = False
    entry_ema_low_2 = DecimalParameter(0.96, 0.978, default=0.96, optimize=is_optimize_ewo_2)
    entry_ema_high_2 = DecimalParameter(1.05, 1.2, default=1.09, optimize=is_optimize_ewo_2)
    is_optimize_cofi = False
    entry_ema_cofi = DecimalParameter(0.96, 0.98, default=0.97, optimize=is_optimize_cofi)
    entry_fastk = IntParameter(20, 30, default=20, optimize=is_optimize_cofi)
    entry_fastd = IntParameter(20, 30, default=20, optimize=is_optimize_cofi)
    entry_adx = IntParameter(20, 30, default=30, optimize=is_optimize_cofi)
    entry_ewo_high = DecimalParameter(2, 12, default=3.553, optimize=is_optimize_cofi)
    is_optimize_btc_safe = False
    entry_btc_safe = IntParameter(-300, 50, default=-200, optimize=is_optimize_btc_safe)
    entry_btc_safe_1d = DecimalParameter(-0.075, -0.025, default=-0.05, optimize=is_optimize_btc_safe)
    entry_threshold = DecimalParameter(0.003, 0.012, default=0.008, optimize=is_optimize_btc_safe)
    # Buy params toggle
    entry_is_dip_enabled = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_is_break_enabled = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    ## Sell params
    exit_btc_safe = IntParameter(-400, -300, default=-365, optimize=True)
    base_nb_candles_exit = IntParameter(5, 80, default=exit_params['base_nb_candles_exit'], space='exit', optimize=True)
    high_offset = DecimalParameter(0.95, 1.1, default=exit_params['high_offset'], space='exit', optimize=True)
    high_offset_2 = DecimalParameter(0.99, 1.5, default=exit_params['high_offset_2'], space='exit', optimize=True)
    ## Trailing params
    # hard stoploss profit
    pHSL = DecimalParameter(-0.2, -0.04, default=-0.08, decimals=3, space='exit', load=True)
    # profit threshold 1, trigger point, SL_1 is used
    pPF_1 = DecimalParameter(0.008, 0.02, default=0.016, decimals=3, space='exit', load=True)
    pSL_1 = DecimalParameter(0.008, 0.02, default=0.011, decimals=3, space='exit', load=True)
    # profit threshold 2, SL_2 is used
    pPF_2 = DecimalParameter(0.04, 0.1, default=0.08, decimals=3, space='exit', load=True)
    pSL_2 = DecimalParameter(0.02, 0.07, default=0.04, decimals=3, space='exit', load=True)
    ############################################################################

    def informative_pairs(self):
        informative_pairs = [('BTC/USDT', '5m')]
        return informative_pairs
    ############################################################################
    ## Custom Trailing stoploss ( credit to Perkmeister for this custom stoploss to help the strategy ride a green candle )

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
        assert self.dp, 'DataProvider is required for multiple timeframes.'
        # Bollinger bands (hyperopt hard to implement)
        bollinger2 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband2'] = bollinger2['lower']
        dataframe['bb_middleband2'] = bollinger2['mid']
        dataframe['bb_upperband2'] = bollinger2['upper']
        bollinger3 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=3)
        dataframe['bb_lowerband3'] = bollinger3['lower']
        dataframe['bb_middleband3'] = bollinger3['mid']
        dataframe['bb_upperband3'] = bollinger3['upper']
        ### BTC protection
        # BTC info
        inf_tf = '5m'
        informative = self.dp.get_pair_dataframe('BTC/USDT', timeframe=inf_tf)
        informative_past = informative.copy().shift(1)  # Get recent BTC info
        # BTC 5m dump protection
        informative_past_source = (informative_past['open'] + informative_past['close'] + informative_past['high'] + informative_past['low']) / 4  # Get BTC price
        informative_threshold = informative_past_source * self.entry_threshold.value  # BTC dump n% in 5 min
        informative_past_delta = informative_past['close'].shift(1) - informative_past['close']  # should be positive if dump
        informative_diff = informative_threshold - informative_past_delta  # Need be larger than 0
        dataframe['btc_threshold'] = informative_threshold
        dataframe['btc_diff'] = informative_diff
        # BTC 1d dump protection
        informative_past_1d = informative.copy().shift(288)
        informative_past_source_1d = (informative_past_1d['open'] + informative_past_1d['close'] + informative_past_1d['high'] + informative_past_1d['low']) / 4
        dataframe['btc_5m'] = informative_past_source
        dataframe['btc_1d'] = informative_past_source_1d
        ### Other checks
        dataframe['bb_width'] = (dataframe['bb_upperband2'] - dataframe['bb_lowerband2']) / dataframe['bb_middleband2']
        dataframe['bb_delta'] = (dataframe['bb_lowerband2'] - dataframe['bb_lowerband3']) / dataframe['bb_lowerband2']
        dataframe['bb_bottom_cross'] = qtpylib.crossed_below(dataframe['close'], dataframe['bb_lowerband3']).astype('int')
        # CCI hyperopt
        for val in self.entry_cci_length.range:
            dataframe[f'cci_length_{val}'] = ta.CCI(dataframe, val)
        dataframe['cci'] = ta.CCI(dataframe, 26)
        dataframe['cci_long'] = ta.CCI(dataframe, 170)
        # RMI hyperopt
        for val in self.entry_rmi_length.range:
            dataframe[f'rmi_length_{val}'] = RMI(dataframe, length=val, mom=4)
        #dataframe['rmi'] = RMI(dataframe, length=8, mom=4)
        # SRSI hyperopt ?
        stoch = ta.STOCHRSI(dataframe, 15, 20, 2, 2)
        dataframe['srsi_fk'] = stoch['fastk']
        dataframe['srsi_fd'] = stoch['fastd']
        # BinH
        dataframe['closedelta'] = (dataframe['close'] - dataframe['close'].shift()).abs()
        # SMA
        dataframe['sma_15'] = ta.SMA(dataframe, timeperiod=15)
        dataframe['sma_30'] = ta.SMA(dataframe, timeperiod=30)
        # CTI
        dataframe['cti'] = pta.cti(dataframe['close'], length=20)
        # EMA
        dataframe['ema_8'] = ta.EMA(dataframe, timeperiod=8)
        dataframe['ema_12'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ema_13'] = ta.EMA(dataframe, timeperiod=13)
        dataframe['ema_16'] = ta.EMA(dataframe, timeperiod=16)
        dataframe['ema_26'] = ta.EMA(dataframe, timeperiod=26)
        dataframe['hma_50'] = qtpylib.hull_moving_average(dataframe['close'], window=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        dataframe['sma_9'] = ta.SMA(dataframe, timeperiod=9)
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_slow'] = ta.RSI(dataframe, timeperiod=20)
        # Elliot
        dataframe['EWO'] = EWO(dataframe, 50, 200)
        # Cofi
        stoch_fast = ta.STOCHF(dataframe, 5, 3, 0, 3, 0)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']
        dataframe['adx'] = ta.ADX(dataframe)
        # Williams %R
        dataframe['r_14'] = williams_r(dataframe, period=14)
        # Volume
        dataframe['volume_mean_4'] = dataframe['volume'].rolling(4).mean().shift(1)
        # Calculate all ma_exit values
        for val in self.base_nb_candles_exit.range:
            dataframe[f'ma_exit_{val}'] = ta.EMA(dataframe, timeperiod=val)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        dataframe.loc[:, 'enter_tag'] = ''
        if self.entry_is_dip_enabled.value:
            is_dip = (dataframe[f'rmi_length_{self.entry_rmi_length.value}'] < self.entry_rmi.value) & (dataframe[f'cci_length_{self.entry_cci_length.value}'] <= self.entry_cci.value) & (dataframe['srsi_fk'] < self.entry_srsi_fk.value)
        #conditions.append(is_dip)
        if self.entry_is_break_enabled.value:  #"entry_bb_delta": 0.025 0.036
            #"entry_bb_width": 0.095 0.133
            # from BinH
            is_break = (dataframe['bb_delta'] > self.entry_bb_delta.value) & (dataframe['bb_width'] > self.entry_bb_width.value) & (dataframe['closedelta'] > dataframe['close'] * self.entry_closedelta.value / 1000) & (dataframe['close'] < dataframe['bb_lowerband3'] * self.entry_bb_factor.value)
        #conditions.append(is_break)
        # from NFI next gen
        is_local_uptrend = (dataframe['ema_26'] > dataframe['ema_12']) & (dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_diff.value) & (dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100) & (dataframe['close'] < dataframe['bb_lowerband2'] * self.entry_bb_factor.value) & (dataframe['closedelta'] > dataframe['close'] * self.entry_closedelta.value / 1000)  # from SMA offset
        is_ewo = (dataframe['rsi_fast'] < self.entry_rsi_fast.value) & (dataframe['close'] < dataframe['ema_8'] * self.entry_ema_low.value) & (dataframe['EWO'] > self.entry_ewo.value) & (dataframe['close'] < dataframe['ema_16'] * self.entry_ema_high.value) & (dataframe['rsi'] < self.entry_rsi.value)
        is_ewo_2 = (dataframe['rsi_fast'] < self.entry_rsi_fast.value) & (dataframe['close'] < dataframe['ema_8'] * self.entry_ema_low_2.value) & (dataframe['EWO'] > self.entry_ewo_high.value) & (dataframe['close'] < dataframe['ema_16'] * self.entry_ema_high_2.value) & (dataframe['rsi'] < self.entry_rsi.value)
        is_cofi = (dataframe['open'] < dataframe['ema_8'] * self.entry_ema_cofi.value) & qtpylib.crossed_above(dataframe['fastk'], dataframe['fastd']) & (dataframe['fastk'] < self.entry_fastk.value) & (dataframe['fastd'] < self.entry_fastd.value) & (dataframe['adx'] > self.entry_adx.value) & (dataframe['EWO'] > self.entry_ewo_high.value)
        # NFI quick mode
        is_nfi_32 = (dataframe['rsi_slow'] < dataframe['rsi_slow'].shift(1)) & (dataframe['rsi_fast'] < 46) & (dataframe['rsi'] > 19) & (dataframe['close'] < dataframe['sma_15'] * 0.942) & (dataframe['cti'] < -0.86)
        is_nfi_33 = (dataframe['close'] < dataframe['ema_13'] * 0.978) & (dataframe['EWO'] > 8) & (dataframe['cti'] < -0.88) & (dataframe['rsi'] < 32) & (dataframe['r_14'] < -98.0) & (dataframe['volume'] < dataframe['volume_mean_4'] * 2.5)
        # is_btc_safe = (
        #         (dataframe['btc_diff'] > self.entry_btc_safe.value)
        #        &(dataframe['btc_5m'] - dataframe['btc_1d'] > dataframe['btc_1d'] * self.entry_btc_safe_1d.value)
        #        &(dataframe['volume'] > 0)           # Make sure Volume is not 0
        #     )
        is_BB_checked = is_dip & is_break
        #print(dataframe['btc_5m'])
        #print(dataframe['btc_1d'])
        #print(dataframe['btc_5m'] - dataframe['btc_1d'])
        #print(dataframe['btc_1d'] * -0.025)
        #print(dataframe['btc_5m'] - dataframe['btc_1d'] > dataframe['btc_1d'] * -0.025)
        ## condition append
        conditions.append(is_BB_checked)  # ~1.7 89%
        dataframe.loc[is_BB_checked, 'enter_tag'] += 'bb '
        conditions.append(is_local_uptrend)  # ~3.84 90.2%
        dataframe.loc[is_local_uptrend, 'enter_tag'] += 'local uptrend '
        conditions.append(is_ewo)  # ~2.26 93.5%
        dataframe.loc[is_ewo, 'enter_tag'] += 'ewo '
        conditions.append(is_ewo_2)  # ~3.68 90.3%
        dataframe.loc[is_ewo_2, 'enter_tag'] += 'ewo2 '
        conditions.append(is_cofi)  # ~3.21 90.8%
        dataframe.loc[is_cofi, 'enter_tag'] += 'cofi '
        conditions.append(is_nfi_32)  # ~2.43 91.3%
        dataframe.loc[is_nfi_32, 'enter_tag'] += 'nfi 32 '
        conditions.append(is_nfi_33)  # ~0.11 100%
        dataframe.loc[is_nfi_33, 'enter_tag'] += 'nfi 33 '
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append((dataframe['close'] > dataframe['sma_9']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset_2.value) & (dataframe['rsi'] > 50) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']) | (dataframe['sma_9'] > dataframe['sma_9'].shift(1) + dataframe['sma_9'].shift(1) * 0.005) & (dataframe['close'] < dataframe['hma_50']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset.value) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow']))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'exit_long'] = 1
        return dataframe