# --- Do not remove these libs ---
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
import pandas_ta as pta
import math
from math import e
from freqtrade.persistence import Trade
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame, Series, DatetimeIndex, merge
from datetime import datetime, timedelta
from freqtrade.strategy import merge_informative_pair, CategoricalParameter, DecimalParameter, IntParameter, stoploss_from_open
from freqtrade.exchange import timeframe_to_prev_date
from functools import reduce
from technical.indicators import RMI, zema, ichimoku
# --------------------------------

def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['low'] * 100
    return emadif

def SROC(dataframe, roclen=21, emalen=13, smooth=21):
    df = dataframe.copy()
    roc = ta.ROC(df, timeperiod=roclen)
    ema = ta.EMA(df, timeperiod=emalen)
    sroc = ta.ROC(ema, timeperiod=smooth)
    return sroc
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
# Chaikin Money Flow

def chaikin_money_flow(dataframe, n=20, fillna=False) -> Series:
    """Chaikin Money Flow (CMF)
    It measures the amount of Money Flow Volume over a specific period.
    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:chaikin_money_flow_cmf
    Args:
        dataframe(pandas.Dataframe): dataframe containing ohlcv
        n(int): n period.
        fillna(bool): if fill nan values.
    Returns:
        pandas.Series: New feature generated.
    """
    mfv = (dataframe['close'] - dataframe['low'] - (dataframe['high'] - dataframe['close'])) / (dataframe['high'] - dataframe['low'])
    mfv = mfv.fillna(0.0)  # float division by zero
    mfv *= dataframe['volume']
    cmf = mfv.rolling(n, min_periods=0).sum() / dataframe['volume'].rolling(n, min_periods=0).sum()
    if fillna:
        cmf = cmf.replace([np.inf, -np.inf], np.nan).fillna(0)
    return Series(cmf, name='cmf')

class BB_RPB_TSL_v103(IStrategy):
    INTERFACE_VERSION = 3
    '\n        BB_RPB_TSL\n        @author jilv220\n        Simple bollinger brand strategy inspired by this blog  ( https://hacks-for-life.blogspot.com/2020/12/freqtrade-notes.html )\n        RPB, which stands for Real Pull Back, taken from ( https://github.com/GeorgeMurAlkh/freqtrade-stuff/blob/main/user_data/strategies/TheRealPullbackV2.py )\n        The trailing custom stoploss taken from BigZ04_TSL from Perkmeister ( modded by ilya )\n        I modified it to better suit my taste and added Hyperopt for this strategy.\n    '
    # (1) Use exit signal
    ##########################################################################
    # Hyperopt result area
    # entry space
    ##
    ##
    #
    ##
    ##
    ##
    ##
    ##
    entry_params = {'max_slip': 0.668, 'entry_bb_width_1h': 0.954, 'entry_roc_1h': 86, 'entry_threshold': 0.003, 'entry_bb_factor': 0.999, 'entry_bb_delta': 0.025, 'entry_bb_width': 0.095, 'entry_cci': -116, 'entry_cci_length': 25, 'entry_rmi': 49, 'entry_rmi_length': 17, 'entry_srsi_fk': 32, 'entry_closedelta': 17.922, 'entry_ema_diff': 0.026, 'entry_ema_high': 0.968, 'entry_ema_low': 0.935, 'entry_ewo': -5.001, 'entry_rsi': 23, 'entry_rsi_fast': 44, 'entry_ema_high_2': 1.154, 'entry_ema_low_2': 0.974, 'entry_ewo_high_2': 3.886, 'entry_rsi_ewo_2': 35, 'entry_rsi_fast_ewo_2': 36, 'entry_closedelta_local_dip': 12.044, 'entry_ema_diff_local_dip': 0.024, 'entry_ema_high_local_dip': 1.014, 'entry_rsi_local_dip': 21}
    # exit space
    ##
    ##
    exit_params = {'exit_cmf': -0.046, 'exit_ema': 0.988, 'exit_ema_close_delta': 0.022, 'exit_deadfish_bb_factor': 0.954, 'exit_deadfish_bb_width': 0.043, 'exit_deadfish_volume_factor': 2.37}
    minimal_roi = {'0': 0.205}
    # Optimal timeframe for the strategy
    timeframe = '5m'
    inf_1h = '1h'
    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True
    # Disabled
    stoploss = -0.99
    # Custom stoploss
    use_custom_stoploss = True
    use_exit_signal = True
    ############################################################################
    ## Buy params
    is_optimize_dip = False
    entry_rmi = IntParameter(30, 50, default=35, optimize=is_optimize_dip)
    entry_cci = IntParameter(-135, -90, default=-133, optimize=is_optimize_dip)
    entry_srsi_fk = IntParameter(30, 50, default=25, optimize=is_optimize_dip)
    entry_cci_length = IntParameter(25, 45, default=25, optimize=is_optimize_dip)
    entry_rmi_length = IntParameter(8, 20, default=8, optimize=is_optimize_dip)
    is_optimize_break = False
    entry_bb_width = DecimalParameter(0.065, 0.135, default=0.095, optimize=is_optimize_break)
    entry_bb_delta = DecimalParameter(0.018, 0.035, default=0.025, optimize=is_optimize_break)
    is_optimize_local_uptrend = False
    entry_ema_diff = DecimalParameter(0.022, 0.027, default=0.025, optimize=is_optimize_local_uptrend)
    entry_bb_factor = DecimalParameter(0.99, 0.999, default=0.995, optimize=False)
    entry_closedelta = DecimalParameter(12.0, 18.0, default=15.0, optimize=is_optimize_local_uptrend)
    is_optimize_local_dip = False
    entry_ema_diff_local_dip = DecimalParameter(0.022, 0.027, default=0.025, optimize=is_optimize_local_dip)
    entry_ema_high_local_dip = DecimalParameter(0.9, 1.2, default=0.942, optimize=is_optimize_local_dip)
    entry_closedelta_local_dip = DecimalParameter(12.0, 18.0, default=15.0, optimize=is_optimize_local_dip)
    entry_rsi_local_dip = IntParameter(15, 45, default=28, optimize=is_optimize_local_dip)
    entry_crsi_local_dip = IntParameter(10, 18, default=10, optimize=False)
    is_optimize_ewo = False
    entry_rsi_fast = IntParameter(35, 50, default=45, optimize=is_optimize_ewo)
    entry_rsi = IntParameter(15, 35, default=35, optimize=is_optimize_ewo)
    entry_ewo = DecimalParameter(-6.0, 5, default=-5.585, optimize=is_optimize_ewo)
    entry_ema_low = DecimalParameter(0.9, 0.99, default=0.942, optimize=is_optimize_ewo)
    entry_ema_high = DecimalParameter(0.95, 1.2, default=1.084, optimize=is_optimize_ewo)
    is_optimize_ewo_2 = True
    entry_rsi_fast_ewo_2 = IntParameter(35, 50, default=45, optimize=is_optimize_ewo_2)
    entry_rsi_ewo_2 = IntParameter(15, 35, default=35, optimize=is_optimize_ewo_2)
    entry_ema_low_2 = DecimalParameter(0.96, 0.978, default=0.96, optimize=is_optimize_ewo_2)
    entry_ema_high_2 = DecimalParameter(1.05, 1.2, default=1.09, optimize=is_optimize_ewo_2)
    entry_ewo_high_2 = DecimalParameter(2, 12, default=3.553, optimize=is_optimize_ewo_2)
    is_optimize_btc_safe = False
    entry_btc_safe = IntParameter(-300, 50, default=-200, optimize=is_optimize_btc_safe)
    entry_btc_safe_1d = DecimalParameter(-0.075, -0.025, default=-0.05, optimize=is_optimize_btc_safe)
    entry_threshold = DecimalParameter(0.003, 0.012, default=0.008, optimize=is_optimize_btc_safe)
    is_optimize_check = False
    entry_roc_1h = IntParameter(-25, 200, default=10, optimize=is_optimize_check)
    entry_bb_width_1h = DecimalParameter(0.3, 2.0, default=0.3, optimize=is_optimize_check)
    ## Slippage params
    is_optimize_slip = False
    max_slip = DecimalParameter(0.33, 0.8, default=0.33, decimals=3, space='entry', optimize=is_optimize_slip, load=True)
    ## Sell params
    exit_btc_safe = IntParameter(-400, -300, default=-365, optimize=False)
    is_optimize_exit_stoploss = False
    exit_cmf = DecimalParameter(-0.4, 0.0, default=0.0, optimize=is_optimize_exit_stoploss)
    exit_ema_close_delta = DecimalParameter(0.022, 0.027, default=0.024, optimize=is_optimize_exit_stoploss)
    exit_ema = DecimalParameter(0.97, 0.99, default=0.987, optimize=is_optimize_exit_stoploss)
    is_optimize_deadfish = True
    exit_deadfish_bb_width = DecimalParameter(0.03, 0.75, default=0.05, optimize=is_optimize_deadfish)
    exit_deadfish_profit = DecimalParameter(-0.1, -0.05, default=-0.05, optimize=False)
    exit_deadfish_bb_factor = DecimalParameter(0.9, 1.2, default=1.0, optimize=is_optimize_deadfish)
    exit_deadfish_volume_factor = DecimalParameter(1, 2.5, default=1.0, optimize=is_optimize_deadfish)
    ## Trailing params
    is_optimize_trailing = False
    p_target_1 = DecimalParameter(0.05, 0.199, default=0.05, decimals=3, space='exit', optimize=is_optimize_trailing, load=True)
    p_target_2 = DecimalParameter(0.03, 0.099, default=0.03, decimals=3, space='exit', optimize=is_optimize_trailing, load=True)
    p_target_3 = DecimalParameter(0.02, 0.059, default=0.02, decimals=3, space='exit', optimize=is_optimize_trailing, load=True)
    p_target_4 = DecimalParameter(0.01, 0.029, default=0.01, decimals=3, space='exit', optimize=is_optimize_trailing, load=True)
    ############################################################################

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, '1h') for pair in pairs]
        return informative_pairs

    def informative_1h_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        assert self.dp, 'DataProvider is required for multiple timeframes.'
        # Get the informative pair
        informative_1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=self.inf_1h)
        # EMA
        informative_1h['ema_50'] = ta.EMA(informative_1h, timeperiod=50)
        informative_1h['ema_100'] = ta.EMA(informative_1h, timeperiod=100)
        informative_1h['ema_200'] = ta.EMA(informative_1h, timeperiod=200)
        # CTI
        informative_1h['cti'] = pta.cti(informative_1h['close'], length=20)
        # CRSI (3, 2, 100)
        crsi_closechange = informative_1h['close'] / informative_1h['close'].shift(1)
        crsi_updown = np.where(crsi_closechange.gt(1), 1.0, np.where(crsi_closechange.lt(1), -1.0, 0.0))
        informative_1h['crsi'] = (ta.RSI(informative_1h['close'], timeperiod=3) + ta.RSI(crsi_updown, timeperiod=2) + ta.ROC(informative_1h['close'], 100)) / 3
        # Williams %R
        informative_1h['r_480'] = williams_r(informative_1h, period=480)
        # Bollinger bands
        bollinger2 = qtpylib.bollinger_bands(qtpylib.typical_price(informative_1h), window=20, stds=2)
        informative_1h['bb_lowerband2'] = bollinger2['lower']
        informative_1h['bb_middleband2'] = bollinger2['mid']
        informative_1h['bb_upperband2'] = bollinger2['upper']
        informative_1h['bb_width'] = (informative_1h['bb_upperband2'] - informative_1h['bb_lowerband2']) / informative_1h['bb_middleband2']
        # ROC
        informative_1h['roc'] = ta.ROC(dataframe, timeperiod=9)
        # MOMDIV
        mom = momdiv(informative_1h)
        informative_1h['momdiv_entry'] = mom['momdiv_entry']
        informative_1h['momdiv_exit'] = mom['momdiv_exit']
        informative_1h['momdiv_coh'] = mom['momdiv_coh']
        informative_1h['momdiv_col'] = mom['momdiv_col']
        # RSI
        informative_1h['rsi'] = ta.RSI(informative_1h, timeperiod=14)
        # CMF
        informative_1h['cmf'] = chaikin_money_flow(informative_1h, 20)
        return informative_1h
    ############################################################################
    ### Custom functions

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> float:
        sl_new = 1
        if current_profit > 0.2:
            sl_new = self.p_target_1.value
        elif current_profit > 0.1:
            sl_new = self.p_target_2.value
        elif current_profit > 0.06:
            sl_new = self.p_target_3.value
        elif current_profit > 0.03:
            sl_new = self.p_target_4.value
        return sl_new
    # From NFIX

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float, current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]
        max_profit = (trade.max_rate - trade.open_rate) / trade.open_rate
        max_loss = (trade.open_rate - trade.min_rate) / trade.min_rate
        # exit trail
        if 0.012 > current_profit >= 0.0:
            if max_profit > current_profit + 0.045 and last_candle['rsi'] < 46.0:
                return 'exit_profit_t_0_1'
            elif max_profit > current_profit + 0.025 and last_candle['rsi'] < 32.0:
                return 'exit_profit_t_0_2'
            elif max_profit > current_profit + 0.05 and last_candle['rsi'] < 48.0:
                return 'exit_profit_t_0_3'
        elif 0.02 > current_profit >= 0.012:
            if max_profit > current_profit + 0.01 and last_candle['rsi'] < 39.0:
                return 'exit_profit_t_1_1'
            elif max_profit > current_profit + 0.035 and last_candle['rsi'] < 45.0 and (last_candle['cmf'] < -0.0) and (last_candle['cmf_1h'] < -0.0):
                return 'exit_profit_t_1_2'
            elif max_profit > current_profit + 0.02 and last_candle['rsi'] < 40.0 and (last_candle['cmf'] < -0.0) and (last_candle['cti_1h'] > 0.8):
                return 'exit_profit_t_1_4'
            elif max_profit > current_profit + 0.04 and last_candle['rsi'] < 49.0 and (last_candle['cmf_1h'] < -0.0):
                return 'exit_profit_t_1_5'
            elif max_profit > current_profit + 0.06 and last_candle['rsi'] < 43.0 and (last_candle['cmf'] < -0.0):
                return 'exit_profit_t_1_7'
            elif max_profit > current_profit + 0.025 and last_candle['rsi'] < 40.0 and (last_candle['cmf'] < -0.1) and (last_candle['rsi_1h'] < 50.0):
                return 'exit_profit_t_1_9'
            elif max_profit > current_profit + 0.025 and last_candle['rsi'] < 46.0 and (last_candle['cmf'] < -0.0) and (last_candle['r_480_1h'] > -20.0):
                return 'exit_profit_t_1_10'
            elif max_profit > current_profit + 0.025 and last_candle['rsi'] < 42.0:
                return 'exit_profit_t_1_11'
            elif max_profit > current_profit + 0.01 and last_candle['rsi'] < 44.0 and (last_candle['cmf'] < -0.25):
                return 'exit_profit_t_1_12'
        # exit bear
        if last_candle['close'] < last_candle['ema_200']:
            if 0.02 > current_profit >= 0.01:
                if last_candle['rsi'] < 34.0 and last_candle['cmf'] < 0.0:
                    return 'exit_profit_u_bear_1_1'
                elif last_candle['rsi'] < 44.0 and last_candle['cmf'] < -0.4:
                    return 'exit_profit_u_bear_1_2'
        # exit quick
        if 0.06 > current_profit > 0.02 and last_candle['rsi'] > 80.0:
            return 'signal_profit_q_1'
        if 0.06 > current_profit > 0.02 and last_candle['cti'] > 0.95:
            return 'signal_profit_q_2'
        # stoploss - deadfish
        if current_profit < self.exit_deadfish_profit.value and last_candle['close'] < last_candle['ema_200'] and (last_candle['bb_width'] < self.exit_deadfish_bb_width.value) and (last_candle['close'] > last_candle['bb_middleband2'] * self.exit_deadfish_bb_factor.value) and (last_candle['volume_mean_12'] < last_candle['volume_mean_24'] * self.exit_deadfish_volume_factor.value):
            return 'exit_stoploss_deadfish'
        return None
    ## Confirm Entry

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float, time_in_force: str, **kwargs) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        max_slip = self.max_slip.value
        if len(dataframe) < 1:
            return False
        dataframe = dataframe.iloc[-1].squeeze()
        if rate > dataframe['close']:
            slippage = (rate / dataframe['close'] - 1) * 100
            #print("open rate is : " + str(rate))
            #print("last candle close is : " + str(dataframe['close']))
            #print("slippage is : " + str(slippage) )
            #print("############################################################################")
            if slippage < max_slip:
                return True
            else:
                return False
        return True
    ############################################################################

    def normal_tf_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bollinger bands
        bollinger2 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband2'] = bollinger2['lower']
        dataframe['bb_middleband2'] = bollinger2['mid']
        dataframe['bb_upperband2'] = bollinger2['upper']
        bollinger3 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=3)
        dataframe['bb_lowerband3'] = bollinger3['lower']
        dataframe['bb_middleband3'] = bollinger3['mid']
        dataframe['bb_upperband3'] = bollinger3['upper']
        ### Other BB checks
        dataframe['bb_width'] = (dataframe['bb_upperband2'] - dataframe['bb_lowerband2']) / dataframe['bb_middleband2']
        dataframe['bb_delta'] = (dataframe['bb_lowerband2'] - dataframe['bb_lowerband3']) / dataframe['bb_lowerband2']
        # CCI hyperopt
        for val in self.entry_cci_length.range:
            dataframe[f'cci_length_{val}'] = ta.CCI(dataframe, val)
        dataframe['cci'] = ta.CCI(dataframe, 26)
        dataframe['cci_long'] = ta.CCI(dataframe, 170)
        # RMI hyperopt
        for val in self.entry_rmi_length.range:
            dataframe[f'rmi_length_{val}'] = RMI(dataframe, length=val, mom=4)
        # SRSI hyperopt
        stoch = ta.STOCHRSI(dataframe, 15, 20, 2, 2)
        dataframe['srsi_fk'] = stoch['fastk']
        dataframe['srsi_fd'] = stoch['fastd']
        # BinH
        dataframe['closedelta'] = (dataframe['close'] - dataframe['close'].shift()).abs()
        # SMA
        dataframe['sma_9'] = ta.SMA(dataframe, timeperiod=9)
        dataframe['sma_15'] = ta.SMA(dataframe, timeperiod=15)
        dataframe['sma_21'] = ta.SMA(dataframe, timeperiod=21)
        dataframe['sma_30'] = ta.SMA(dataframe, timeperiod=30)
        dataframe['sma_75'] = ta.SMA(dataframe, timeperiod=75)
        # CTI
        dataframe['cti'] = pta.cti(dataframe['close'], length=20)
        # CMF
        dataframe['cmf'] = chaikin_money_flow(dataframe, 20)
        # CRSI (3, 2, 100)
        crsi_closechange = dataframe['close'] / dataframe['close'].shift(1)
        crsi_updown = np.where(crsi_closechange.gt(1), 1.0, np.where(crsi_closechange.lt(1), -1.0, 0.0))
        dataframe['crsi'] = (ta.RSI(dataframe['close'], timeperiod=3) + ta.RSI(crsi_updown, timeperiod=2) + ta.ROC(dataframe['close'], 100)) / 3
        # EMA
        dataframe['ema_8'] = ta.EMA(dataframe, timeperiod=8)
        dataframe['ema_12'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ema_13'] = ta.EMA(dataframe, timeperiod=13)
        dataframe['ema_16'] = ta.EMA(dataframe, timeperiod=16)
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=16)
        dataframe['ema_26'] = ta.EMA(dataframe, timeperiod=26)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
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
        dataframe['r_32'] = williams_r(dataframe, period=32)
        dataframe['r_96'] = williams_r(dataframe, period=96)
        dataframe['r_480'] = williams_r(dataframe, period=480)
        # Volume
        dataframe['volume_mean_4'] = dataframe['volume'].rolling(4).mean().shift(1)
        dataframe['volume_mean_12'] = dataframe['volume'].rolling(12).mean().shift(1)
        dataframe['volume_mean_24'] = dataframe['volume'].rolling(24).mean().shift(1)
        # MFI
        dataframe['mfi'] = ta.MFI(dataframe)
        # Heiken Ashi
        heikinashi = qtpylib.heikinashi(dataframe)
        # Profit Maximizer - PMAX
        dataframe['pm'], dataframe['pmx'] = pmax(heikinashi, MAtype=1, length=9, multiplier=27, period=10, src=3)
        dataframe['source'] = (dataframe['high'] + dataframe['low'] + dataframe['open'] + dataframe['close']) / 4
        dataframe['pmax_thresh'] = ta.EMA(dataframe['source'], timeperiod=9)
        # SROC
        dataframe['sroc'] = SROC(dataframe)
        # MOMDIV
        mom = momdiv(dataframe)
        dataframe['momdiv_entry'] = mom['momdiv_entry']
        dataframe['momdiv_exit'] = mom['momdiv_exit']
        dataframe['momdiv_coh'] = mom['momdiv_coh']
        dataframe['momdiv_col'] = mom['momdiv_col']
        return dataframe
    ############################################################################

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # The indicators for the 1h informative timeframe
        informative_1h = self.informative_1h_indicators(dataframe, metadata)
        dataframe = merge_informative_pair(dataframe, informative_1h, self.timeframe, self.inf_1h, ffill=True)
        # The indicators for the normal (5m) timeframe
        dataframe = self.normal_tf_indicators(dataframe, metadata)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        dataframe.loc[:, 'enter_tag'] = ''
        is_dip = (dataframe[f'rmi_length_{self.entry_rmi_length.value}'] < self.entry_rmi.value) & (dataframe[f'cci_length_{self.entry_cci_length.value}'] <= self.entry_cci.value) & (dataframe['srsi_fk'] < self.entry_srsi_fk.value)  # from BinH
        is_break = (dataframe['bb_delta'] > self.entry_bb_delta.value) & (dataframe['bb_width'] > self.entry_bb_width.value) & (dataframe['closedelta'] > dataframe['close'] * self.entry_closedelta.value / 1000) & (dataframe['close'] < dataframe['bb_lowerband3'] * self.entry_bb_factor.value)  # from NFI next gen
        is_local_uptrend = (dataframe['ema_26'] > dataframe['ema_12']) & (dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_diff.value) & (dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100) & (dataframe['close'] < dataframe['bb_lowerband2'] * self.entry_bb_factor.value) & (dataframe['closedelta'] > dataframe['close'] * self.entry_closedelta.value / 1000)
        is_local_dip = (dataframe['ema_26'] > dataframe['ema_12']) & (dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_diff_local_dip.value) & (dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100) & (dataframe['close'] < dataframe['ema_20'] * self.entry_ema_high_local_dip.value) & (dataframe['rsi'] < self.entry_rsi_local_dip.value) & (dataframe['crsi'] > self.entry_crsi_local_dip.value) & (dataframe['closedelta'] > dataframe['close'] * self.entry_closedelta_local_dip.value / 1000)  # from SMA offset
        is_ewo = (dataframe['rsi_fast'] < self.entry_rsi_fast.value) & (dataframe['close'] < dataframe['ema_8'] * self.entry_ema_low.value) & (dataframe['EWO'] > self.entry_ewo.value) & (dataframe['close'] < dataframe['ema_16'] * self.entry_ema_high.value) & (dataframe['rsi'] < self.entry_rsi.value)
        is_ewo_2 = (dataframe['ema_200_1h'] > dataframe['ema_200_1h'].shift(12)) & (dataframe['ema_200_1h'].shift(12) > dataframe['ema_200_1h'].shift(24)) & (dataframe['rsi_fast'] < self.entry_rsi_fast_ewo_2.value) & (dataframe['close'] < dataframe['ema_8'] * self.entry_ema_low_2.value) & (dataframe['EWO'] > self.entry_ewo_high_2.value) & (dataframe['close'] < dataframe['ema_16'] * self.entry_ema_high_2.value) & (dataframe['rsi'] < self.entry_rsi_ewo_2.value)
        # NFI quick mode
        is_nfi_13 = (dataframe['ema_50_1h'] > dataframe['ema_100_1h']) & (dataframe['close'] < dataframe['sma_30'] * 0.99) & (dataframe['cti'] < -0.92) & (dataframe['EWO'] < -5.585) & (dataframe['cti_1h'] < -0.88) & (dataframe['crsi_1h'] > 10.0)  # NFIX 26
        is_nfi_32 = (dataframe['rsi_slow'] < dataframe['rsi_slow'].shift(1)) & (dataframe['rsi_fast'] < 46) & (dataframe['rsi'] > 25.0) & (dataframe['close'] < dataframe['sma_15'] * 0.93) & (dataframe['cti'] < -0.9)
        is_nfi_33 = (dataframe['close'] < dataframe['ema_13'] * 0.978) & (dataframe['EWO'] > 8) & (dataframe['cti'] < -0.88) & (dataframe['rsi'] < 32) & (dataframe['r_14'] < -98.0) & (dataframe['volume'] < dataframe['volume_mean_4'] * 2.5)
        is_nfi_38 = (dataframe['pm'] > dataframe['pmax_thresh']) & (dataframe['close'] < dataframe['sma_75'] * 0.98) & (dataframe['EWO'] < -4.4) & (dataframe['cti'] < -0.95) & (dataframe['r_14'] < -97) & (dataframe['crsi_1h'] > 0.5)
        is_additional_check = (dataframe['roc_1h'] < self.entry_roc_1h.value) & (dataframe['bb_width_1h'] < self.entry_bb_width_1h.value)
        ## Additional Check
        is_BB_checked = is_dip & is_break
        ## Condition Append
        conditions.append(is_BB_checked)  # ~2.32 / 91.1% / 46.27%      D
        dataframe.loc[is_BB_checked, 'enter_tag'] += 'bb '
        conditions.append(is_local_uptrend)  # ~3.28 / 92.4% / 69.72%
        dataframe.loc[is_local_uptrend, 'enter_tag'] += 'local_uptrend '
        conditions.append(is_local_dip)  # ~0.76 / 91.1% / 15.54%
        dataframe.loc[is_local_dip, 'enter_tag'] += 'local_dip '
        conditions.append(is_ewo)  # ~0.92 / 92.0% / 43.74%      D
        dataframe.loc[is_ewo, 'enter_tag'] += 'ewo '
        conditions.append(is_ewo_2)  # ~3.47 / 77.4% / 24.01%      D
        dataframe.loc[is_ewo_2, 'enter_tag'] += 'ewo2 '
        conditions.append(is_nfi_13)  # ~0.4 / 100%                 D
        dataframe.loc[is_nfi_13, 'enter_tag'] += 'nfi_13 '
        conditions.append(is_nfi_32)  # ~0.78 / 92.0 % / 37.41%     D
        dataframe.loc[is_nfi_32, 'enter_tag'] += 'nfi_32 '
        conditions.append(is_nfi_33)  # ~0.11 / 100%                D
        dataframe.loc[is_nfi_33, 'enter_tag'] += 'nfi_33 '
        conditions.append(is_nfi_38)  # ~1.07 / 83.2% / 70.22%      F
        dataframe.loc[is_nfi_38, 'enter_tag'] += 'nfi_38 '
        if conditions:
            dataframe.loc[is_additional_check & reduce(lambda x, y: x | y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # Make sure Volume is not 0
        dataframe.loc[((dataframe['close'] < dataframe['ema_200'] * self.exit_ema.value) & (dataframe['cmf'] < self.exit_cmf.value) & ((dataframe['ema_200'] - dataframe['close']) / dataframe['close'] < self.exit_ema_close_delta.value) & (dataframe['rsi'] > dataframe['rsi'].shift(1)) | (dataframe['pm'] <= dataframe['pmax_thresh']) & (dataframe['close'] > dataframe['sma_21'] * 1.1) & ((dataframe['momdiv_exit_1h'] == True) | (dataframe['momdiv_exit'] == True) | (dataframe['momdiv_coh'] == True)) | (dataframe['pm'] > dataframe['pmax_thresh']) & (dataframe['close'] > dataframe['sma_21'] * 1.016) & ((dataframe['momdiv_exit_1h'] == True) | (dataframe['momdiv_exit'] == True) | (dataframe['momdiv_coh'] == True))) & (dataframe['volume'] > 0), 'exit_long'] = 1
        return dataframe
# PMAX

def pmax(df, period, multiplier, length, MAtype, src):
    period = int(period)
    multiplier = int(multiplier)
    length = int(length)
    MAtype = int(MAtype)
    src = int(src)
    mavalue = f'MA_{MAtype}_{length}'
    atr = f'ATR_{period}'
    pm = f'pm_{period}_{multiplier}_{length}_{MAtype}'
    pmx = f'pmX_{period}_{multiplier}_{length}_{MAtype}'
    # MAtype==1 --> EMA
    # MAtype==2 --> DEMA
    # MAtype==3 --> T3
    # MAtype==4 --> SMA
    # MAtype==5 --> VIDYA
    # MAtype==6 --> TEMA
    # MAtype==7 --> WMA
    # MAtype==8 --> VWMA
    # MAtype==9 --> zema
    if src == 1:
        masrc = df['close']
    elif src == 2:
        masrc = (df['high'] + df['low']) / 2
    elif src == 3:
        masrc = (df['high'] + df['low'] + df['close'] + df['open']) / 4
    if MAtype == 1:
        mavalue = ta.EMA(masrc, timeperiod=length)
    elif MAtype == 2:
        mavalue = ta.DEMA(masrc, timeperiod=length)
    elif MAtype == 3:
        mavalue = ta.T3(masrc, timeperiod=length)
    elif MAtype == 4:
        mavalue = ta.SMA(masrc, timeperiod=length)
    elif MAtype == 5:
        mavalue = VIDYA(df, length=length)
    elif MAtype == 6:
        mavalue = ta.TEMA(masrc, timeperiod=length)
    elif MAtype == 7:
        mavalue = ta.WMA(df, timeperiod=length)
    elif MAtype == 8:
        mavalue = vwma(df, length)
    elif MAtype == 9:
        mavalue = zema(df, period=length)
    df[atr] = ta.ATR(df, timeperiod=period)
    df['basic_ub'] = mavalue + multiplier / 10 * df[atr]
    df['basic_lb'] = mavalue - multiplier / 10 * df[atr]
    basic_ub = df['basic_ub'].values
    final_ub = np.full(len(df), 0.0)
    basic_lb = df['basic_lb'].values
    final_lb = np.full(len(df), 0.0)
    for i in range(period, len(df)):
        final_ub[i] = basic_ub[i] if basic_ub[i] < final_ub[i - 1] or mavalue[i - 1] > final_ub[i - 1] else final_ub[i - 1]
        final_lb[i] = basic_lb[i] if basic_lb[i] > final_lb[i - 1] or mavalue[i - 1] < final_lb[i - 1] else final_lb[i - 1]
    df['final_ub'] = final_ub
    df['final_lb'] = final_lb
    pm_arr = np.full(len(df), 0.0)
    for i in range(period, len(df)):
        pm_arr[i] = final_ub[i] if pm_arr[i - 1] == final_ub[i - 1] and mavalue[i] <= final_ub[i] else final_lb[i] if pm_arr[i - 1] == final_ub[i - 1] and mavalue[i] > final_ub[i] else final_lb[i] if pm_arr[i - 1] == final_lb[i - 1] and mavalue[i] >= final_lb[i] else final_ub[i] if pm_arr[i - 1] == final_lb[i - 1] and mavalue[i] < final_lb[i] else 0.0
    pm = Series(pm_arr)
    # Mark the trend direction up/down
    pmx = np.where(pm_arr > 0.0, np.where(mavalue < pm_arr, 'down', 'up'), np.NaN)
    return (pm, pmx)
# Mom DIV

def momdiv(dataframe: DataFrame, mom_length: int=10, bb_length: int=20, bb_dev: float=2.0, lookback: int=30) -> DataFrame:
    mom: Series = ta.MOM(dataframe, timeperiod=mom_length)
    upperband, middleband, lowerband = ta.BBANDS(mom, timeperiod=bb_length, nbdevup=bb_dev, nbdevdn=bb_dev, matype=0)
    enter_long = qtpylib.crossed_below(mom, lowerband)
    exit_long = qtpylib.crossed_above(mom, upperband)
    hh = dataframe['high'].rolling(lookback).max()
    ll = dataframe['low'].rolling(lookback).min()
    coh = dataframe['high'] >= hh
    col = dataframe['low'] <= ll
    df = DataFrame({'momdiv_mom': mom, 'momdiv_upperb': upperband, 'momdiv_lowerb': lowerband, 'momdiv_entry': enter_long, 'momdiv_exit': exit_long, 'momdiv_coh': coh, 'momdiv_col': col}, index=dataframe['close'].index)
    return df