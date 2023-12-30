import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import merge_informative_pair, DecimalParameter, IntParameter, CategoricalParameter
from pandas import DataFrame, Series
from functools import reduce
from freqtrade.persistence import Trade
from datetime import datetime, timedelta
from technical.indicators import zema
###########################################################################################################
##                NostalgiaForInfinityV7 by iterativ                                                     ##
##                                                                                                       ##
##    Strategy for Freqtrade https://github.com/freqtrade/freqtrade                                      ##
##                                                                                                       ##
###########################################################################################################
##               GENERAL RECOMMENDATIONS                                                                 ##
##                                                                                                       ##
##   For optimal performance, suggested to use between 4 and 6 open trades, with unlimited stake.        ##
##   A pairlist with 40 to 80 pairs. Volume pairlist works well.                                         ##
##   Prefer stable coin (USDT, BUSDT etc) pairs, instead of BTC or ETH pairs.                            ##
##   Highly recommended to blacklist leveraged tokens (*BULL, *BEAR, *UP, *DOWN etc).                    ##
##   Ensure that you don't override any variables in you config.json. Especially                         ##
##   the timeframe (must be 5m).                                                                         ##
##     use_exit_signal must set to true (or not set at all).                                             ##
##     exit_profit_only must set to false (or not set at all).                                           ##
##     ignore_roi_if_entry_signal must set to true (or not set at all).                                    ##
##                                                                                                       ##
###########################################################################################################
##               DONATIONS                                                                               ##
##                                                                                                       ##
##   Absolutely not required. However, will be accepted as a token of appreciation.                      ##
##                                                                                                       ##
##   BTC: bc1qvflsvddkmxh7eqhc4jyu5z5k6xcw3ay8jl49sk                                                     ##
##   ETH (ERC20): 0x83D3cFb8001BDC5d2211cBeBB8cB3461E5f7Ec91                                             ##
##   BEP20/BSC (ETH, BNB, ...): 0x86A0B21a20b39d16424B7c8003E4A7e12d78ABEe                               ##
##                                                                                                       ##
###########################################################################################################

class NostalgiaForInfinityV7_SMA(IStrategy):
    INTERFACE_VERSION = 3
    # # ROI table:
    minimal_roi = {'0': 10}
    stoploss = -0.99
    # Trailing stoploss (not used)
    trailing_stop = True
    trailing_only_offset_is_reached = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.03
    use_custom_stoploss = False
    # Optimal timeframe for the strategy.
    timeframe = '5m'
    inf_1h = '1h'
    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True
    # These values can be overridden in the "ask_strategy" section in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True
    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 400
    # Optional order type mapping.
    order_types = {'entry': 'limit', 'exit': 'limit', 'trailing_stop_loss': 'limit', 'stoploss': 'limit', 'stoploss_on_exchange': False}
    #############################################################
    #############
    # Enable/Disable conditions
    #############
    entry_params = {'entry_condition_1_enable': True, 'entry_condition_2_enable': True, 'entry_condition_3_enable': True, 'entry_condition_4_enable': True, 'entry_condition_5_enable': True, 'entry_condition_6_enable': True, 'entry_condition_7_enable': True, 'entry_condition_8_enable': True, 'entry_condition_9_enable': True, 'entry_condition_10_enable': True, 'entry_condition_11_enable': True, 'entry_condition_12_enable': True, 'entry_condition_13_enable': True, 'entry_condition_14_enable': True, 'entry_condition_15_enable': True, 'entry_condition_16_enable': True, 'entry_condition_17_enable': True, 'entry_condition_18_enable': True, 'entry_condition_19_enable': True, 'entry_condition_20_enable': True, 'entry_condition_21_enable': True, 'entry_condition_22_enable': True, 'entry_condition_23_enable': True, 'entry_condition_24_enable': True, 'entry_condition_25_enable': True, 'entry_condition_26_enable': True}
    #############
    # Enable/Disable conditions
    #############
    exit_params = {'exit_condition_1_enable': True, 'exit_condition_2_enable': True, 'exit_condition_3_enable': True, 'exit_condition_4_enable': True, 'exit_condition_5_enable': True, 'exit_condition_6_enable': True, 'exit_condition_7_enable': True, 'exit_condition_8_enable': True}
    #############################################################
    entry_condition_1_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_01_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_01_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='26', space='entry', optimize=False, load=True)
    entry_01_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_01_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True)
    entry_01_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_01_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_01_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_01_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_01_protection__sma200_rising = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_01_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='28', space='entry', optimize=False, load=True)
    entry_01_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_01_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_01_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_01_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='80', space='entry', optimize=False, load=True)
    entry_01_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_01_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='70', space='entry', optimize=False, load=True)
    entry_01_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_2_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_02_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_02_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_02_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_02_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_02_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_02_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_02_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_02_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='20', space='entry', optimize=False, load=True)
    entry_02_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_02_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_02_protection__safe_pump = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_02_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_02_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_02_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_02_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_02_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_02_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_condition_3_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_03_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_03_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_03_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_03_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_03_protection__ema_fast = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_03_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True)
    entry_03_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_03_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True)
    entry_03_protection__safe_dips = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_03_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_03_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_03_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True)
    entry_03_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True)
    entry_03_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_03_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_03_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_03_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_condition_4_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_04_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_04_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_04_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_04_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_04_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_04_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_04_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_04_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_04_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_04_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='40', space='entry', optimize=False, load=True)
    entry_04_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_04_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='110', space='entry', optimize=False, load=True)
    entry_04_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='48', space='entry', optimize=False, load=True)
    entry_04_protection__sma200_rising = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_04_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_04_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_04_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='20', space='entry', optimize=False, load=True)
    entry_condition_5_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_05_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_05_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True)
    entry_05_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_05_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_05_protection__ema_fast = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_05_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True)
    entry_05_protection__ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_05_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_05_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_05_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True)
    entry_05_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_05_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='20', space='entry', optimize=False, load=True)
    entry_05_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True)
    entry_05_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_05_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_05_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_05_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_condition_6_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_06_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_06_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_06_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_06_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True)
    entry_06_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_06_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_06_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_06_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_06_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_06_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_06_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_06_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_06_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_06_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_06_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_06_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='20', space='entry', optimize=False, load=True)
    entry_06_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True)
    entry_condition_7_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_07_protection__ema_fast = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_07_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True)
    entry_07_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_07_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='12', space='entry', optimize=False, load=True)
    entry_07_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_07_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_07_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_07_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_07_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_07_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_07_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_07_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_07_protection__safe_dips = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_07_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_07_protection__safe_pump = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_07_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_07_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_8_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_08_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_08_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_08_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_08_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='12', space='entry', optimize=False, load=True)
    entry_08_protection__close_above_ema_fast = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_08_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_08_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_08_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_08_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_08_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_08_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_08_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_08_protection__safe_dips = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_08_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True)
    entry_08_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_08_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='120', space='entry', optimize=False, load=True)
    entry_08_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_9_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_09_protection__ema_fast = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_09_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True)
    entry_09_protection__ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_09_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_09_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_09_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_09_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_09_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_09_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_09_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_09_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_09_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_09_protection__safe_dips = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_09_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_09_protection__safe_pump = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_09_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_09_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_10_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_10_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_10_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_10_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_10_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_10_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_10_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_10_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_10_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_10_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_10_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_10_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_10_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='24', space='entry', optimize=False, load=True)
    entry_10_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_10_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True)
    entry_10_protection__safe_pump = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_10_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_10_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_11_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_11_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_11_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_11_protection__ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_11_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_11_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_11_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_11_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_11_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_11_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_11_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_11_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_11_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_11_protection__safe_dips = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_11_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True)
    entry_11_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_11_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_11_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_12_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_12_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_12_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_12_protection__ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_12_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_12_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_12_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_12_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_12_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_12_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_12_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_12_protection__sma200_1h_rising = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_12_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='24', space='entry', optimize=False, load=True)
    entry_12_protection__safe_dips = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_12_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True)
    entry_12_protection__safe_pump = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_12_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_12_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_13_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_13_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_13_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_13_protection__ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_13_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_13_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_13_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_13_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_13_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_13_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_13_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_13_protection__sma200_1h_rising = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_13_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='24', space='entry', optimize=False, load=True)
    entry_13_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_13_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_13_protection__safe_pump = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_13_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_13_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_14_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_14_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_14_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_14_protection__ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_14_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_14_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_14_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_14_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_14_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_14_protection__sma200_rising = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_14_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='30', space='entry', optimize=False, load=True)
    entry_14_protection__sma200_1h_rising = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_14_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_14_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_14_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_14_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_14_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='70', space='entry', optimize=False, load=True)
    entry_14_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_15_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_15_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_15_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_15_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_15_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_15_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_15_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_15_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_15_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_15_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_15_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_15_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_15_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_15_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_15_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_15_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_15_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_15_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True)
    entry_condition_16_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_16_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_16_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_16_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_16_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_16_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_16_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_16_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_16_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='50', space='entry', optimize=False, load=True)
    entry_16_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_16_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_16_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_16_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_16_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_16_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_16_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_16_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_16_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_17_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_17_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_17_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_17_protection__ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_17_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_17_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_17_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_17_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_17_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_17_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_17_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_17_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_17_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_17_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_17_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_17_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_17_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='120', space='entry', optimize=False, load=True)
    entry_17_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_18_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_18_protection__ema_fast = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_18_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True)
    entry_18_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_18_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_18_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_18_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_18_protection__close_above_ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_18_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_18_protection__sma200_rising = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_18_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='44', space='entry', optimize=False, load=True)
    entry_18_protection__sma200_1h_rising = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_18_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='72', space='entry', optimize=False, load=True)
    entry_18_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_18_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_18_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_18_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='60', space='entry', optimize=False, load=True)
    entry_18_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_19_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_19_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_19_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_19_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_19_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True)
    entry_19_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_19_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_19_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_19_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_19_protection__sma200_rising = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_19_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='36', space='entry', optimize=False, load=True)
    entry_19_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_19_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_19_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_19_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_19_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_19_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_19_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_20_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_20_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_20_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_20_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_20_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_20_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_20_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_20_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_20_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_20_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_20_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_20_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_20_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_20_protection__safe_dips = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_20_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_20_protection__safe_pump = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_20_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_20_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_21_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_21_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_21_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_21_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_21_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_21_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_21_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_21_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_21_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_21_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_21_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_21_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_21_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_21_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_21_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='90', space='entry', optimize=False, load=True)
    entry_21_protection__safe_pump = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_21_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_21_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_22_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_22_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_22_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_22_protection__ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_22_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_22_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_22_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_22_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_22_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_22_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_22_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_22_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_22_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_22_protection__safe_dips = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_22_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_22_protection__safe_pump = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_22_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_22_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_23_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_23_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_23_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_23_protection__ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_23_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_23_protection__close_above_ema_fast = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_23_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_23_protection__close_above_ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_23_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_23_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_23_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_23_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_23_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True)
    entry_23_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_23_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True)
    entry_23_protection__safe_pump = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_23_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_23_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_24_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_24_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_24_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_24_protection__ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_24_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True)
    entry_24_protection__close_above_ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_24_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True)
    entry_24_protection__close_above_ema_slow = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_24_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True)
    entry_24_protection__sma200_rising = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_24_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='30', space='entry', optimize=False, load=True)
    entry_24_protection__sma200_1h_rising = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_24_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='36', space='entry', optimize=False, load=True)
    entry_24_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_24_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True)
    entry_24_protection__safe_pump = CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)
    entry_24_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True)
    entry_24_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True)
    entry_condition_26_enable = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_26_protection__optimize = False
    entry_26_parameters__optimize = False
    entry_26_protection__ema_fast = CategoricalParameter([True, False], default=False, space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__ema_fast_len = CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__ema_slow_len = CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__close_above_ema_fast = CategoricalParameter([True, False], default=True, space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__close_above_ema_fast_len = CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='50', space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__close_above_ema_slow = CategoricalParameter([True, False], default=True, space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__close_above_ema_slow_len = CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__sma200_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__sma200_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='30', space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__sma200_1h_rising = CategoricalParameter([True, False], default=False, space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__sma200_1h_rising_val = CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__safe_dips = CategoricalParameter([True, False], default=True, space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__safe_dips_type = CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__safe_pump = CategoricalParameter([True, False], default=True, space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__safe_pump_type = CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=entry_26_protection__optimize, load=True)
    entry_26_protection__safe_pump_period = CategoricalParameter(['24', '36', '48'], default='48', space='entry', optimize=entry_26_protection__optimize, load=True)
    # Strict dips - level 10
    entry_dip_threshold_10_1 = DecimalParameter(0.001, 0.05, default=0.015, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_10_2 = DecimalParameter(0.01, 0.2, default=0.1, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_10_3 = DecimalParameter(0.1, 0.3, default=0.24, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_10_4 = DecimalParameter(0.3, 0.5, default=0.42, space='entry', decimals=3, optimize=False, load=True)
    # Strict dips - level 20
    entry_dip_threshold_20_1 = DecimalParameter(0.001, 0.05, default=0.016, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_20_2 = DecimalParameter(0.01, 0.2, default=0.11, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_20_3 = DecimalParameter(0.1, 0.4, default=0.26, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_20_4 = DecimalParameter(0.36, 0.56, default=0.44, space='entry', decimals=3, optimize=False, load=True)
    # Strict dips - level 30
    entry_dip_threshold_30_1 = DecimalParameter(0.001, 0.05, default=0.018, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_30_2 = DecimalParameter(0.01, 0.2, default=0.12, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_30_3 = DecimalParameter(0.1, 0.4, default=0.28, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_30_4 = DecimalParameter(0.36, 0.56, default=0.46, space='entry', decimals=3, optimize=False, load=True)
    # Strict dips - level 40
    entry_dip_threshold_40_1 = DecimalParameter(0.001, 0.05, default=0.019, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_40_2 = DecimalParameter(0.01, 0.2, default=0.13, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_40_3 = DecimalParameter(0.1, 0.4, default=0.3, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_40_4 = DecimalParameter(0.36, 0.56, default=0.48, space='entry', decimals=3, optimize=False, load=True)
    # Normal dips - level 50
    entry_dip_threshold_50_1 = DecimalParameter(0.001, 0.05, default=0.02, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_50_2 = DecimalParameter(0.01, 0.2, default=0.14, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_50_3 = DecimalParameter(0.05, 0.4, default=0.32, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_50_4 = DecimalParameter(0.2, 0.5, default=0.5, space='entry', decimals=3, optimize=False, load=True)
    # Normal dips - level 60
    entry_dip_threshold_60_1 = DecimalParameter(0.001, 0.05, default=0.022, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_60_2 = DecimalParameter(0.1, 0.22, default=0.18, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_60_3 = DecimalParameter(0.2, 0.4, default=0.34, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_60_4 = DecimalParameter(0.4, 0.6, default=0.56, space='entry', decimals=3, optimize=False, load=True)
    # Normal dips - level 70
    entry_dip_threshold_70_1 = DecimalParameter(0.001, 0.05, default=0.023, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_70_2 = DecimalParameter(0.16, 0.28, default=0.2, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_70_3 = DecimalParameter(0.2, 0.4, default=0.36, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_70_4 = DecimalParameter(0.5, 0.7, default=0.6, space='entry', decimals=3, optimize=False, load=True)
    # Normal dips - level 80
    entry_dip_threshold_80_1 = DecimalParameter(0.001, 0.05, default=0.024, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_80_2 = DecimalParameter(0.16, 0.28, default=0.22, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_80_3 = DecimalParameter(0.2, 0.4, default=0.38, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_80_4 = DecimalParameter(0.5, 0.7, default=0.66, space='entry', decimals=3, optimize=False, load=True)
    # Normal dips - level 70
    entry_dip_threshold_90_1 = DecimalParameter(0.001, 0.05, default=0.025, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_90_2 = DecimalParameter(0.16, 0.28, default=0.23, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_90_3 = DecimalParameter(0.3, 0.5, default=0.4, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_90_4 = DecimalParameter(0.6, 0.8, default=0.7, space='entry', decimals=3, optimize=False, load=True)
    # Loose dips - level 100
    entry_dip_threshold_100_1 = DecimalParameter(0.001, 0.05, default=0.026, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_100_2 = DecimalParameter(0.16, 0.3, default=0.24, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_100_3 = DecimalParameter(0.3, 0.5, default=0.42, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_100_4 = DecimalParameter(0.6, 1.0, default=0.8, space='entry', decimals=3, optimize=False, load=True)
    # Loose dips - level 110
    entry_dip_threshold_110_1 = DecimalParameter(0.001, 0.05, default=0.027, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_110_2 = DecimalParameter(0.16, 0.3, default=0.26, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_110_3 = DecimalParameter(0.3, 0.5, default=0.44, space='entry', decimals=3, optimize=False, load=True)
    entry_dip_threshold_110_4 = DecimalParameter(0.6, 1.0, default=0.84, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 10
    entry_pump_pull_threshold_10_24 = DecimalParameter(1.5, 3.0, default=2.2, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_10_24 = DecimalParameter(0.4, 1.0, default=0.42, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 10
    entry_pump_pull_threshold_10_36 = DecimalParameter(1.5, 3.0, default=2.0, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_10_36 = DecimalParameter(0.4, 1.0, default=0.58, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 10
    entry_pump_pull_threshold_10_48 = DecimalParameter(1.5, 3.0, default=2.0, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_10_48 = DecimalParameter(0.4, 1.0, default=0.8, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 20
    entry_pump_pull_threshold_20_24 = DecimalParameter(1.5, 3.0, default=2.2, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_20_24 = DecimalParameter(0.4, 1.0, default=0.46, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 20
    entry_pump_pull_threshold_20_36 = DecimalParameter(1.5, 3.0, default=2.0, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_20_36 = DecimalParameter(0.4, 1.0, default=0.6, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 20
    entry_pump_pull_threshold_20_48 = DecimalParameter(1.5, 3.0, default=2.0, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_20_48 = DecimalParameter(0.4, 1.0, default=0.81, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 30
    entry_pump_pull_threshold_30_24 = DecimalParameter(1.5, 3.0, default=2.2, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_30_24 = DecimalParameter(0.4, 1.0, default=0.5, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 30
    entry_pump_pull_threshold_30_36 = DecimalParameter(1.5, 3.0, default=2.0, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_30_36 = DecimalParameter(0.4, 1.0, default=0.62, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 30
    entry_pump_pull_threshold_30_48 = DecimalParameter(1.5, 3.0, default=2.0, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_30_48 = DecimalParameter(0.4, 1.0, default=0.82, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 40
    entry_pump_pull_threshold_40_24 = DecimalParameter(1.5, 3.0, default=2.2, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_40_24 = DecimalParameter(0.4, 1.0, default=0.54, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 40
    entry_pump_pull_threshold_40_36 = DecimalParameter(1.5, 3.0, default=2.0, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_40_36 = DecimalParameter(0.4, 1.0, default=0.63, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 40
    entry_pump_pull_threshold_40_48 = DecimalParameter(1.5, 3.0, default=2.0, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_40_48 = DecimalParameter(0.4, 1.0, default=0.84, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 50
    entry_pump_pull_threshold_50_24 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_50_24 = DecimalParameter(0.4, 1.0, default=0.6, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 50
    entry_pump_pull_threshold_50_36 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_50_36 = DecimalParameter(0.4, 1.0, default=0.64, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 50
    entry_pump_pull_threshold_50_48 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_50_48 = DecimalParameter(0.4, 1.0, default=0.85, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 60
    entry_pump_pull_threshold_60_24 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_60_24 = DecimalParameter(0.4, 1.0, default=0.62, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 60
    entry_pump_pull_threshold_60_36 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_60_36 = DecimalParameter(0.4, 1.0, default=0.66, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 60
    entry_pump_pull_threshold_60_48 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_60_48 = DecimalParameter(0.4, 1.0, default=0.9, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 70
    entry_pump_pull_threshold_70_24 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_70_24 = DecimalParameter(0.4, 1.0, default=0.63, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 70
    entry_pump_pull_threshold_70_36 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_70_36 = DecimalParameter(0.4, 1.0, default=0.67, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 70
    entry_pump_pull_threshold_70_48 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_70_48 = DecimalParameter(0.4, 1.0, default=0.95, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 80
    entry_pump_pull_threshold_80_24 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_80_24 = DecimalParameter(0.4, 1.0, default=0.64, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 80
    entry_pump_pull_threshold_80_36 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_80_36 = DecimalParameter(0.4, 1.0, default=0.68, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 80
    entry_pump_pull_threshold_80_48 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_80_48 = DecimalParameter(0.8, 1.1, default=1.0, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 90
    entry_pump_pull_threshold_90_24 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_90_24 = DecimalParameter(0.4, 1.0, default=0.65, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 90
    entry_pump_pull_threshold_90_36 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_90_36 = DecimalParameter(0.4, 1.0, default=0.69, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 90
    entry_pump_pull_threshold_90_48 = DecimalParameter(1.5, 3.0, default=1.75, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_90_48 = DecimalParameter(0.8, 1.2, default=1.1, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 100
    entry_pump_pull_threshold_100_24 = DecimalParameter(1.5, 3.0, default=1.7, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_100_24 = DecimalParameter(0.4, 1.0, default=0.66, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 100
    entry_pump_pull_threshold_100_36 = DecimalParameter(1.5, 3.0, default=1.7, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_100_36 = DecimalParameter(0.4, 1.0, default=0.7, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 100
    entry_pump_pull_threshold_100_48 = DecimalParameter(1.3, 2.0, default=1.4, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_100_48 = DecimalParameter(0.4, 1.8, default=1.6, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 110
    entry_pump_pull_threshold_110_24 = DecimalParameter(1.5, 3.0, default=1.7, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_110_24 = DecimalParameter(0.4, 1.0, default=0.7, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 110
    entry_pump_pull_threshold_110_36 = DecimalParameter(1.5, 3.0, default=1.7, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_110_36 = DecimalParameter(0.4, 1.0, default=0.74, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 110
    entry_pump_pull_threshold_110_48 = DecimalParameter(1.3, 2.0, default=1.4, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_110_48 = DecimalParameter(1.4, 2.0, default=1.8, space='entry', decimals=3, optimize=False, load=True)
    # 24 hours - level 120
    entry_pump_pull_threshold_120_24 = DecimalParameter(1.5, 3.0, default=1.7, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_120_24 = DecimalParameter(0.4, 1.0, default=0.78, space='entry', decimals=3, optimize=False, load=True)
    # 36 hours - level 120
    entry_pump_pull_threshold_120_36 = DecimalParameter(1.5, 3.0, default=1.7, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_120_36 = DecimalParameter(0.4, 1.0, default=0.78, space='entry', decimals=3, optimize=False, load=True)
    # 48 hours - level 120
    entry_pump_pull_threshold_120_48 = DecimalParameter(1.3, 2.0, default=1.4, space='entry', decimals=2, optimize=False, load=True)
    entry_pump_threshold_120_48 = DecimalParameter(1.4, 2.8, default=2.0, space='entry', decimals=3, optimize=False, load=True)
    entry_min_inc_1 = DecimalParameter(0.01, 0.05, default=0.022, space='entry', decimals=3, optimize=False, load=True)
    entry_rsi_1h_min_1 = DecimalParameter(25.0, 40.0, default=30.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_max_1 = DecimalParameter(70.0, 90.0, default=84.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1 = DecimalParameter(20.0, 40.0, default=36.0, space='entry', decimals=1, optimize=False, load=True)
    entry_mfi_1 = DecimalParameter(20.0, 40.0, default=36.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_min_2 = DecimalParameter(30.0, 40.0, default=32.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_max_2 = DecimalParameter(70.0, 95.0, default=84.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_diff_2 = DecimalParameter(30.0, 50.0, default=39.0, space='entry', decimals=1, optimize=False, load=True)
    entry_mfi_2 = DecimalParameter(30.0, 56.0, default=49.0, space='entry', decimals=1, optimize=False, load=True)
    entry_bb_offset_2 = DecimalParameter(0.97, 0.999, default=0.983, space='entry', decimals=3, optimize=False, load=True)
    entry_bb40_bbdelta_close_3 = DecimalParameter(0.005, 0.06, default=0.059, space='entry', optimize=False, load=True)
    entry_bb40_closedelta_close_3 = DecimalParameter(0.01, 0.03, default=0.023, space='entry', optimize=False, load=True)
    entry_bb40_tail_bbdelta_3 = DecimalParameter(0.15, 0.45, default=0.418, space='entry', optimize=False, load=True)
    entry_ema_rel_3 = DecimalParameter(0.97, 0.999, default=0.986, space='entry', decimals=3, optimize=False, load=True)
    entry_bb20_close_bblowerband_4 = DecimalParameter(0.96, 0.99, default=0.98, space='entry', optimize=False, load=True)
    entry_bb20_volume_4 = DecimalParameter(1.0, 20.0, default=10.0, space='entry', decimals=2, optimize=False, load=True)
    entry_ema_open_mult_5 = DecimalParameter(0.016, 0.03, default=0.018, space='entry', decimals=3, optimize=False, load=True)
    entry_bb_offset_5 = DecimalParameter(0.98, 1.0, default=0.996, space='entry', decimals=3, optimize=False, load=True)
    entry_ema_rel_5 = DecimalParameter(0.97, 0.999, default=0.944, space='entry', decimals=3, optimize=False, load=True)
    entry_ema_open_mult_6 = DecimalParameter(0.02, 0.03, default=0.021, space='entry', decimals=3, optimize=False, load=True)
    entry_bb_offset_6 = DecimalParameter(0.98, 0.999, default=0.984, space='entry', decimals=3, optimize=False, load=True)
    entry_ema_open_mult_7 = DecimalParameter(0.02, 0.04, default=0.03, space='entry', decimals=3, optimize=False, load=True)
    entry_rsi_7 = DecimalParameter(24.0, 50.0, default=37.0, space='entry', decimals=1, optimize=False, load=True)
    entry_volume_8 = DecimalParameter(1.0, 6.0, default=2.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_8 = DecimalParameter(16.0, 30.0, default=29.0, space='entry', decimals=1, optimize=False, load=True)
    entry_tail_diff_8 = DecimalParameter(3.0, 10.0, default=3.5, space='entry', decimals=1, optimize=False, load=True)
    entry_ma_offset_9 = DecimalParameter(0.91, 0.94, default=0.922, space='entry', decimals=3, optimize=False, load=True)
    entry_bb_offset_9 = DecimalParameter(0.96, 0.98, default=0.942, space='entry', decimals=3, optimize=False, load=True)
    entry_rsi_1h_min_9 = DecimalParameter(26.0, 40.0, default=30.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_max_9 = DecimalParameter(70.0, 90.0, default=88.0, space='entry', decimals=1, optimize=False, load=True)
    entry_mfi_9 = DecimalParameter(36.0, 56.0, default=50.0, space='entry', decimals=1, optimize=False, load=True)
    entry_ma_offset_10 = DecimalParameter(0.93, 0.97, default=0.948, space='entry', decimals=3, optimize=False, load=True)
    entry_bb_offset_10 = DecimalParameter(0.97, 0.99, default=0.985, space='entry', decimals=3, optimize=False, load=True)
    entry_rsi_1h_10 = DecimalParameter(20.0, 40.0, default=37.0, space='entry', decimals=1, optimize=False, load=True)
    entry_ma_offset_11 = DecimalParameter(0.93, 0.99, default=0.934, space='entry', decimals=3, optimize=False, load=True)
    entry_min_inc_11 = DecimalParameter(0.005, 0.05, default=0.01, space='entry', decimals=3, optimize=False, load=True)
    entry_rsi_1h_min_11 = DecimalParameter(40.0, 60.0, default=55.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_max_11 = DecimalParameter(70.0, 90.0, default=84.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_11 = DecimalParameter(34.0, 50.0, default=48.0, space='entry', decimals=1, optimize=False, load=True)
    entry_mfi_11 = DecimalParameter(30.0, 46.0, default=36.0, space='entry', decimals=1, optimize=False, load=True)
    entry_ma_offset_12 = DecimalParameter(0.93, 0.97, default=0.922, space='entry', decimals=3, optimize=False, load=True)
    entry_rsi_12 = DecimalParameter(26.0, 40.0, default=30.0, space='entry', decimals=1, optimize=False, load=True)
    entry_ewo_12 = DecimalParameter(1.0, 6.0, default=1.8, space='entry', decimals=1, optimize=False, load=True)
    entry_ma_offset_13 = DecimalParameter(0.93, 0.98, default=0.99, space='entry', decimals=3, optimize=False, load=True)
    entry_ewo_13 = DecimalParameter(-14.0, -7.0, default=-11.4, space='entry', decimals=1, optimize=False, load=True)
    entry_ema_open_mult_14 = DecimalParameter(0.01, 0.03, default=0.014, space='entry', decimals=3, optimize=False, load=True)
    entry_bb_offset_14 = DecimalParameter(0.98, 1.0, default=0.988, space='entry', decimals=3, optimize=False, load=True)
    entry_ma_offset_14 = DecimalParameter(0.93, 0.99, default=0.98, space='entry', decimals=3, optimize=False, load=True)
    entry_ema_open_mult_15 = DecimalParameter(0.01, 0.03, default=0.018, space='entry', decimals=3, optimize=False, load=True)
    entry_ma_offset_15 = DecimalParameter(0.93, 0.99, default=0.954, space='entry', decimals=3, optimize=False, load=True)
    entry_rsi_15 = DecimalParameter(20.0, 36.0, default=28.0, space='entry', decimals=1, optimize=False, load=True)
    entry_ema_rel_15 = DecimalParameter(0.97, 0.999, default=0.988, space='entry', decimals=3, optimize=False, load=True)
    entry_ma_offset_16 = DecimalParameter(0.93, 0.97, default=0.952, space='entry', decimals=3, optimize=False, load=True)
    entry_rsi_16 = DecimalParameter(26.0, 50.0, default=31.0, space='entry', decimals=1, optimize=False, load=True)
    entry_ewo_16 = DecimalParameter(2.0, 6.0, default=2.8, space='entry', decimals=1, optimize=False, load=True)
    entry_ma_offset_17 = DecimalParameter(0.93, 0.98, default=0.952, space='entry', decimals=3, optimize=False, load=True)
    entry_ewo_17 = DecimalParameter(-18.0, -10.0, default=-12.8, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_18 = DecimalParameter(16.0, 32.0, default=26.0, space='entry', decimals=1, optimize=False, load=True)
    entry_bb_offset_18 = DecimalParameter(0.98, 1.0, default=0.982, space='entry', decimals=3, optimize=False, load=True)
    entry_rsi_1h_min_19 = DecimalParameter(40.0, 70.0, default=50.0, space='entry', decimals=1, optimize=False, load=True)
    entry_chop_min_19 = DecimalParameter(20.0, 60.0, default=24.1, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_20 = DecimalParameter(20.0, 36.0, default=27.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_20 = DecimalParameter(14.0, 30.0, default=20.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_21 = DecimalParameter(10.0, 28.0, default=23.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_21 = DecimalParameter(18.0, 40.0, default=24.0, space='entry', decimals=1, optimize=False, load=True)
    entry_volume_22 = DecimalParameter(0.5, 6.0, default=3.0, space='entry', decimals=1, optimize=False, load=True)
    entry_bb_offset_22 = DecimalParameter(0.98, 1.0, default=0.98, space='entry', decimals=3, optimize=False, load=True)
    entry_ma_offset_22 = DecimalParameter(0.93, 0.98, default=0.94, space='entry', decimals=3, optimize=False, load=True)
    entry_ewo_22 = DecimalParameter(2.0, 10.0, default=4.2, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_22 = DecimalParameter(26.0, 56.0, default=37.0, space='entry', decimals=1, optimize=False, load=True)
    entry_bb_offset_23 = DecimalParameter(0.97, 1.0, default=0.987, space='entry', decimals=3, optimize=False, load=True)
    entry_ewo_23 = DecimalParameter(2.0, 10.0, default=7.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_23 = DecimalParameter(20.0, 40.0, default=30.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_23 = DecimalParameter(60.0, 80.0, default=70.0, space='entry', decimals=1, optimize=False, load=True)
    entry_24_rsi_max = DecimalParameter(26.0, 60.0, default=60.0, space='entry', decimals=1, optimize=False, load=True)
    entry_24_rsi_1h_min = DecimalParameter(40.0, 90.0, default=66.9, space='entry', decimals=1, optimize=False, load=True)
    entry_26_zema_low_offset = DecimalParameter(0.9, 0.99, default=0.93, space='entry', optimize=entry_26_parameters__optimize, load=True)
    # Sell
    exit_condition_1_enable = CategoricalParameter([True, False], default=True, space='exit', optimize=False, load=True)
    exit_condition_2_enable = CategoricalParameter([True, False], default=True, space='exit', optimize=False, load=True)
    exit_condition_3_enable = CategoricalParameter([True, False], default=True, space='exit', optimize=False, load=True)
    exit_condition_4_enable = CategoricalParameter([True, False], default=True, space='exit', optimize=False, load=True)
    exit_condition_5_enable = CategoricalParameter([True, False], default=True, space='exit', optimize=False, load=True)
    exit_condition_6_enable = CategoricalParameter([True, False], default=True, space='exit', optimize=False, load=True)
    exit_condition_7_enable = CategoricalParameter([True, False], default=True, space='exit', optimize=False, load=True)
    exit_condition_8_enable = CategoricalParameter([True, False], default=True, space='exit', optimize=False, load=True)
    # 48h for pump exit checks
    exit_pump_threshold_48_1 = DecimalParameter(0.5, 1.2, default=0.9, space='exit', decimals=2, optimize=False, load=True)
    exit_pump_threshold_48_2 = DecimalParameter(0.4, 0.9, default=0.7, space='exit', decimals=2, optimize=False, load=True)
    exit_pump_threshold_48_3 = DecimalParameter(0.3, 0.7, default=0.5, space='exit', decimals=2, optimize=False, load=True)
    # 36h for pump exit checks
    exit_pump_threshold_36_1 = DecimalParameter(0.5, 0.9, default=0.72, space='exit', decimals=2, optimize=False, load=True)
    exit_pump_threshold_36_2 = DecimalParameter(3.0, 6.0, default=4.0, space='exit', decimals=2, optimize=False, load=True)
    exit_pump_threshold_36_3 = DecimalParameter(0.8, 1.6, default=1.0, space='exit', decimals=2, optimize=False, load=True)
    # 24h for pump exit checks
    exit_pump_threshold_24_1 = DecimalParameter(0.5, 0.9, default=0.68, space='exit', decimals=2, optimize=False, load=True)
    exit_pump_threshold_24_2 = DecimalParameter(0.3, 0.6, default=0.62, space='exit', decimals=2, optimize=False, load=True)
    exit_pump_threshold_24_3 = DecimalParameter(0.2, 0.5, default=0.88, space='exit', decimals=2, optimize=False, load=True)
    exit_rsi_bb_1 = DecimalParameter(60.0, 80.0, default=79.5, space='exit', decimals=1, optimize=False, load=True)
    exit_rsi_bb_2 = DecimalParameter(72.0, 90.0, default=81, space='exit', decimals=1, optimize=False, load=True)
    exit_rsi_main_3 = DecimalParameter(77.0, 90.0, default=82, space='exit', decimals=1, optimize=False, load=True)
    exit_dual_rsi_rsi_4 = DecimalParameter(72.0, 84.0, default=73.4, space='exit', decimals=1, optimize=False, load=True)
    exit_dual_rsi_rsi_1h_4 = DecimalParameter(78.0, 92.0, default=79.6, space='exit', decimals=1, optimize=False, load=True)
    exit_ema_relative_5 = DecimalParameter(0.005, 0.05, default=0.024, space='exit', optimize=False, load=True)
    exit_rsi_diff_5 = DecimalParameter(0.0, 20.0, default=4.4, space='exit', optimize=False, load=True)
    exit_rsi_under_6 = DecimalParameter(72.0, 90.0, default=79.0, space='exit', decimals=1, optimize=False, load=True)
    exit_rsi_1h_7 = DecimalParameter(80.0, 95.0, default=81.7, space='exit', decimals=1, optimize=False, load=True)
    exit_bb_relative_8 = DecimalParameter(1.05, 1.3, default=1.1, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_profit_0 = DecimalParameter(0.01, 0.1, default=0.01, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_0 = DecimalParameter(30.0, 40.0, default=34.0, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_profit_1 = DecimalParameter(0.01, 0.1, default=0.02, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_1 = DecimalParameter(30.0, 50.0, default=35.0, space='exit', decimals=2, optimize=False, load=True)
    exit_custom_profit_2 = DecimalParameter(0.01, 0.1, default=0.03, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_2 = DecimalParameter(30.0, 50.0, default=37.0, space='exit', decimals=2, optimize=False, load=True)
    exit_custom_profit_3 = DecimalParameter(0.01, 0.1, default=0.04, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_3 = DecimalParameter(30.0, 50.0, default=42.0, space='exit', decimals=2, optimize=False, load=True)
    exit_custom_profit_4 = DecimalParameter(0.01, 0.1, default=0.05, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_4 = DecimalParameter(35.0, 50.0, default=43.0, space='exit', decimals=2, optimize=False, load=True)
    exit_custom_profit_5 = DecimalParameter(0.01, 0.1, default=0.06, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_5 = DecimalParameter(35.0, 50.0, default=45.0, space='exit', decimals=2, optimize=False, load=True)
    exit_custom_profit_6 = DecimalParameter(0.01, 0.1, default=0.07, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_6 = DecimalParameter(38.0, 55.0, default=48.0, space='exit', decimals=2, optimize=False, load=True)
    exit_custom_profit_7 = DecimalParameter(0.01, 0.1, default=0.08, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_7 = DecimalParameter(40.0, 58.0, default=54.0, space='exit', decimals=2, optimize=False, load=True)
    exit_custom_profit_8 = DecimalParameter(0.06, 0.1, default=0.09, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_8 = DecimalParameter(40.0, 50.0, default=55.0, space='exit', decimals=2, optimize=False, load=True)
    exit_custom_profit_9 = DecimalParameter(0.05, 0.14, default=0.1, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_9 = DecimalParameter(40.0, 60.0, default=54.0, space='exit', decimals=2, optimize=False, load=True)
    exit_custom_profit_10 = DecimalParameter(0.1, 0.14, default=0.12, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_10 = DecimalParameter(38.0, 50.0, default=42.0, space='exit', decimals=2, optimize=False, load=True)
    exit_custom_profit_11 = DecimalParameter(0.16, 0.45, default=0.2, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_rsi_11 = DecimalParameter(28.0, 40.0, default=34.0, space='exit', decimals=2, optimize=False, load=True)
    # Profit under EMA200
    exit_custom_under_profit_0 = DecimalParameter(0.01, 0.4, default=0.01, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_0 = DecimalParameter(28.0, 40.0, default=35.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_under_profit_1 = DecimalParameter(0.01, 0.1, default=0.02, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_1 = DecimalParameter(36.0, 60.0, default=56.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_under_profit_2 = DecimalParameter(0.01, 0.1, default=0.03, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_2 = DecimalParameter(46.0, 66.0, default=57.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_under_profit_3 = DecimalParameter(0.01, 0.1, default=0.04, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_3 = DecimalParameter(50.0, 68.0, default=58.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_under_profit_4 = DecimalParameter(0.02, 0.1, default=0.05, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_4 = DecimalParameter(50.0, 68.0, default=59.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_under_profit_5 = DecimalParameter(0.02, 0.1, default=0.06, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_5 = DecimalParameter(46.0, 62.0, default=60.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_under_profit_6 = DecimalParameter(0.03, 0.1, default=0.07, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_6 = DecimalParameter(44.0, 60.0, default=56.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_under_profit_7 = DecimalParameter(0.04, 0.1, default=0.08, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_7 = DecimalParameter(46.0, 60.0, default=54.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_under_profit_8 = DecimalParameter(0.06, 0.12, default=0.09, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_8 = DecimalParameter(40.0, 58.0, default=55.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_under_profit_9 = DecimalParameter(0.08, 0.14, default=0.1, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_9 = DecimalParameter(40.0, 60.0, default=54.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_under_profit_10 = DecimalParameter(0.1, 0.16, default=0.12, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_10 = DecimalParameter(30.0, 50.0, default=42.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_under_profit_11 = DecimalParameter(0.16, 0.3, default=0.2, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_under_rsi_11 = DecimalParameter(24.0, 40.0, default=34.0, space='exit', decimals=1, optimize=False, load=True)
    # Profit targets for pumped pairs 48h 1
    exit_custom_pump_profit_1_1 = DecimalParameter(0.01, 0.03, default=0.01, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_1_1 = DecimalParameter(26.0, 40.0, default=34.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_1_2 = DecimalParameter(0.01, 0.6, default=0.02, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_1_2 = DecimalParameter(36.0, 50.0, default=40.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_1_3 = DecimalParameter(0.02, 0.1, default=0.04, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_1_3 = DecimalParameter(38.0, 50.0, default=42.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_1_4 = DecimalParameter(0.06, 0.12, default=0.1, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_1_4 = DecimalParameter(36.0, 48.0, default=42.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_1_5 = DecimalParameter(0.14, 0.24, default=0.2, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_1_5 = DecimalParameter(20.0, 40.0, default=34.0, space='exit', decimals=1, optimize=False, load=True)
    # Profit targets for pumped pairs 36h 1
    exit_custom_pump_profit_2_1 = DecimalParameter(0.01, 0.03, default=0.01, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_2_1 = DecimalParameter(26.0, 40.0, default=34.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_2_2 = DecimalParameter(0.01, 0.6, default=0.02, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_2_2 = DecimalParameter(36.0, 50.0, default=40.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_2_3 = DecimalParameter(0.02, 0.1, default=0.04, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_2_3 = DecimalParameter(38.0, 50.0, default=40.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_2_4 = DecimalParameter(0.06, 0.12, default=0.1, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_2_4 = DecimalParameter(36.0, 48.0, default=42.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_2_5 = DecimalParameter(0.14, 0.24, default=0.2, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_2_5 = DecimalParameter(20.0, 40.0, default=34.0, space='exit', decimals=1, optimize=False, load=True)
    # Profit targets for pumped pairs 24h 1
    exit_custom_pump_profit_3_1 = DecimalParameter(0.01, 0.03, default=0.01, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_3_1 = DecimalParameter(26.0, 40.0, default=34.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_3_2 = DecimalParameter(0.01, 0.6, default=0.02, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_3_2 = DecimalParameter(34.0, 50.0, default=40.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_3_3 = DecimalParameter(0.02, 0.1, default=0.04, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_3_3 = DecimalParameter(38.0, 50.0, default=40.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_3_4 = DecimalParameter(0.06, 0.12, default=0.1, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_3_4 = DecimalParameter(36.0, 48.0, default=42.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_profit_3_5 = DecimalParameter(0.14, 0.24, default=0.2, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_rsi_3_5 = DecimalParameter(20.0, 40.0, default=34.0, space='exit', decimals=1, optimize=False, load=True)
    # SMA descending
    exit_custom_dec_profit_min_1 = DecimalParameter(0.01, 0.1, default=0.05, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_dec_profit_max_1 = DecimalParameter(0.06, 0.16, default=0.12, space='exit', decimals=3, optimize=False, load=True)
    # Under EMA100
    exit_custom_dec_profit_min_2 = DecimalParameter(0.05, 0.12, default=0.07, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_dec_profit_max_2 = DecimalParameter(0.06, 0.2, default=0.16, space='exit', decimals=3, optimize=False, load=True)
    # Trail 1
    exit_trail_profit_min_1 = DecimalParameter(0.1, 0.2, default=0.16, space='exit', decimals=2, optimize=False, load=True)
    exit_trail_profit_max_1 = DecimalParameter(0.4, 0.7, default=0.6, space='exit', decimals=2, optimize=False, load=True)
    exit_trail_down_1 = DecimalParameter(0.01, 0.08, default=0.03, space='exit', decimals=3, optimize=False, load=True)
    exit_trail_rsi_min_1 = DecimalParameter(16.0, 36.0, default=20.0, space='exit', decimals=1, optimize=False, load=True)
    exit_trail_rsi_max_1 = DecimalParameter(30.0, 50.0, default=50.0, space='exit', decimals=1, optimize=False, load=True)
    # Trail 2
    exit_trail_profit_min_2 = DecimalParameter(0.08, 0.16, default=0.1, space='exit', decimals=3, optimize=False, load=True)
    exit_trail_profit_max_2 = DecimalParameter(0.3, 0.5, default=0.4, space='exit', decimals=2, optimize=False, load=True)
    exit_trail_down_2 = DecimalParameter(0.02, 0.08, default=0.03, space='exit', decimals=3, optimize=False, load=True)
    exit_trail_rsi_min_2 = DecimalParameter(16.0, 36.0, default=20.0, space='exit', decimals=1, optimize=False, load=True)
    exit_trail_rsi_max_2 = DecimalParameter(30.0, 50.0, default=50.0, space='exit', decimals=1, optimize=False, load=True)
    # Trail 3
    exit_trail_profit_min_3 = DecimalParameter(0.01, 0.12, default=0.06, space='exit', decimals=3, optimize=False, load=True)
    exit_trail_profit_max_3 = DecimalParameter(0.1, 0.3, default=0.2, space='exit', decimals=2, optimize=False, load=True)
    exit_trail_down_3 = DecimalParameter(0.01, 0.06, default=0.05, space='exit', decimals=3, optimize=False, load=True)
    # Under & near EMA200, accept profit
    exit_custom_profit_under_rel_1 = DecimalParameter(0.01, 0.04, default=0.024, space='exit', optimize=False, load=True)
    exit_custom_profit_under_rsi_diff_1 = DecimalParameter(0.0, 20.0, default=4.4, space='exit', optimize=False, load=True)
    # Under & near EMA200, take the loss
    exit_custom_stoploss_under_rel_1 = DecimalParameter(0.001, 0.02, default=0.004, space='exit', optimize=False, load=True)
    exit_custom_stoploss_under_rsi_diff_1 = DecimalParameter(0.0, 20.0, default=10.0, space='exit', optimize=False, load=True)
    # Long duration/recover stoploss 1
    exit_custom_stoploss_long_profit_min_1 = DecimalParameter(-0.1, -0.02, default=-0.08, space='exit', optimize=False, load=True)
    exit_custom_stoploss_long_profit_max_1 = DecimalParameter(-0.06, -0.01, default=-0.04, space='exit', optimize=False, load=True)
    exit_custom_stoploss_long_recover_1 = DecimalParameter(0.05, 0.15, default=0.1, space='exit', optimize=False, load=True)
    exit_custom_stoploss_long_rsi_diff_1 = DecimalParameter(0.0, 20.0, default=4.0, space='exit', optimize=False, load=True)
    # Long duration/recover stoploss 2
    exit_custom_stoploss_long_recover_2 = DecimalParameter(0.03, 0.15, default=0.06, space='exit', optimize=False, load=True)
    exit_custom_stoploss_long_rsi_diff_2 = DecimalParameter(30.0, 50.0, default=40.0, space='exit', optimize=False, load=True)
    # Pumped, descending SMA
    exit_custom_pump_dec_profit_min_1 = DecimalParameter(0.001, 0.04, default=0.005, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_dec_profit_max_1 = DecimalParameter(0.03, 0.08, default=0.05, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_dec_profit_min_2 = DecimalParameter(0.01, 0.08, default=0.04, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_dec_profit_max_2 = DecimalParameter(0.04, 0.1, default=0.06, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_dec_profit_min_3 = DecimalParameter(0.02, 0.1, default=0.06, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_dec_profit_max_3 = DecimalParameter(0.06, 0.12, default=0.09, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_dec_profit_min_4 = DecimalParameter(0.01, 0.05, default=0.02, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_dec_profit_max_4 = DecimalParameter(0.02, 0.1, default=0.04, space='exit', decimals=3, optimize=False, load=True)
    # Pumped 48h 1, under EMA200
    exit_custom_pump_under_profit_min_1 = DecimalParameter(0.02, 0.06, default=0.04, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_under_profit_max_1 = DecimalParameter(0.04, 0.1, default=0.09, space='exit', decimals=3, optimize=False, load=True)
    # Pumped trail 1
    exit_custom_pump_trail_profit_min_1 = DecimalParameter(0.01, 0.12, default=0.05, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_trail_profit_max_1 = DecimalParameter(0.06, 0.16, default=0.07, space='exit', decimals=2, optimize=False, load=True)
    exit_custom_pump_trail_down_1 = DecimalParameter(0.01, 0.06, default=0.05, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_pump_trail_rsi_min_1 = DecimalParameter(16.0, 36.0, default=20.0, space='exit', decimals=1, optimize=False, load=True)
    exit_custom_pump_trail_rsi_max_1 = DecimalParameter(30.0, 50.0, default=70.0, space='exit', decimals=1, optimize=False, load=True)
    # Stoploss, pumped, 48h 1
    exit_custom_stoploss_pump_max_profit_1 = DecimalParameter(0.01, 0.04, default=0.025, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_stoploss_pump_min_1 = DecimalParameter(-0.1, -0.01, default=-0.02, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_stoploss_pump_max_1 = DecimalParameter(-0.1, -0.01, default=-0.01, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_stoploss_pump_ma_offset_1 = DecimalParameter(0.7, 0.99, default=0.94, space='exit', decimals=2, optimize=False, load=True)
    # Stoploss, pumped, 48h 1
    exit_custom_stoploss_pump_max_profit_2 = DecimalParameter(0.01, 0.04, default=0.025, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_stoploss_pump_loss_2 = DecimalParameter(-0.1, -0.01, default=-0.05, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_stoploss_pump_ma_offset_2 = DecimalParameter(0.7, 0.99, default=0.92, space='exit', decimals=2, optimize=False, load=True)
    # Stoploss, pumped, 36h 3
    exit_custom_stoploss_pump_max_profit_3 = DecimalParameter(0.01, 0.04, default=0.008, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_stoploss_pump_loss_3 = DecimalParameter(-0.16, -0.06, default=-0.12, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_stoploss_pump_ma_offset_3 = DecimalParameter(0.7, 0.99, default=0.88, space='exit', decimals=2, optimize=False, load=True)
    # Recover
    exit_custom_recover_profit_1 = DecimalParameter(0.01, 0.06, default=0.04, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_recover_min_loss_1 = DecimalParameter(0.06, 0.16, default=0.12, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_recover_profit_min_2 = DecimalParameter(0.01, 0.04, default=0.01, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_recover_profit_max_2 = DecimalParameter(0.02, 0.08, default=0.05, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_recover_min_loss_2 = DecimalParameter(0.04, 0.16, default=0.06, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_recover_rsi_2 = DecimalParameter(32.0, 52.0, default=46.0, space='exit', decimals=1, optimize=False, load=True)
    # Profit for long duration trades
    exit_custom_long_profit_min_1 = DecimalParameter(0.01, 0.04, default=0.03, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_long_profit_max_1 = DecimalParameter(0.02, 0.08, default=0.04, space='exit', decimals=3, optimize=False, load=True)
    exit_custom_long_duration_min_1 = IntParameter(700, 2000, default=900, space='exit', optimize=False, load=True)
    #############################################################

    def get_ticker_indicator(self):
        return int(self.timeframe[:-1])

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float, current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        max_profit = (trade.max_rate - trade.open_rate) / trade.open_rate
        max_loss = (trade.open_rate - trade.min_rate) / trade.min_rate
        if last_candle is not None:
            if (current_profit > self.exit_custom_profit_11.value) & (last_candle['rsi'] < self.exit_custom_rsi_11.value):
                return 'signal_profit_11'
            if (self.exit_custom_profit_11.value > current_profit > self.exit_custom_profit_10.value) & (last_candle['rsi'] < self.exit_custom_rsi_10.value):
                return 'signal_profit_10'
            if (self.exit_custom_profit_10.value > current_profit > self.exit_custom_profit_9.value) & (last_candle['rsi'] < self.exit_custom_rsi_9.value):
                return 'signal_profit_9'
            if (self.exit_custom_profit_9.value > current_profit > self.exit_custom_profit_8.value) & (last_candle['rsi'] < self.exit_custom_rsi_8.value):
                return 'signal_profit_8'
            if (self.exit_custom_profit_8.value > current_profit > self.exit_custom_profit_7.value) & (last_candle['rsi'] < self.exit_custom_rsi_7.value):
                return 'signal_profit_7'
            if (self.exit_custom_profit_7.value > current_profit > self.exit_custom_profit_6.value) & (last_candle['rsi'] < self.exit_custom_rsi_6.value):
                return 'signal_profit_6'
            if (self.exit_custom_profit_6.value > current_profit > self.exit_custom_profit_5.value) & (last_candle['rsi'] < self.exit_custom_rsi_5.value):
                return 'signal_profit_5'
            elif (self.exit_custom_profit_5.value > current_profit > self.exit_custom_profit_4.value) & (last_candle['rsi'] < self.exit_custom_rsi_4.value):
                return 'signal_profit_4'
            elif (self.exit_custom_profit_4.value > current_profit > self.exit_custom_profit_3.value) & (last_candle['rsi'] < self.exit_custom_rsi_3.value):
                return 'signal_profit_3'
            elif (self.exit_custom_profit_3.value > current_profit > self.exit_custom_profit_2.value) & (last_candle['rsi'] < self.exit_custom_rsi_2.value):
                return 'signal_profit_2'
            elif (self.exit_custom_profit_2.value > current_profit > self.exit_custom_profit_1.value) & (last_candle['rsi'] < self.exit_custom_rsi_1.value):
                return 'signal_profit_1'
            elif (self.exit_custom_profit_1.value > current_profit > self.exit_custom_profit_0.value) & (last_candle['rsi'] < self.exit_custom_rsi_0.value):
                return 'signal_profit_0'
            # check if close is under EMA200
            elif (current_profit > self.exit_custom_under_profit_11.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_11.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_11'
            elif (self.exit_custom_under_profit_11.value > current_profit > self.exit_custom_under_profit_10.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_10.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_10'
            elif (self.exit_custom_under_profit_10.value > current_profit > self.exit_custom_under_profit_9.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_9.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_9'
            elif (self.exit_custom_under_profit_9.value > current_profit > self.exit_custom_under_profit_8.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_8.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_8'
            elif (self.exit_custom_under_profit_8.value > current_profit > self.exit_custom_under_profit_7.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_7.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_7'
            elif (self.exit_custom_under_profit_7.value > current_profit > self.exit_custom_under_profit_6.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_6.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_6'
            elif (self.exit_custom_under_profit_6.value > current_profit > self.exit_custom_under_profit_5.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_5.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_5'
            elif (self.exit_custom_under_profit_5.value > current_profit > self.exit_custom_under_profit_4.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_4.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_4'
            elif (self.exit_custom_under_profit_4.value > current_profit > self.exit_custom_under_profit_3.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_3.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_3'
            elif (self.exit_custom_under_profit_3.value > current_profit > self.exit_custom_under_profit_2.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_2.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_2'
            elif (self.exit_custom_under_profit_2.value > current_profit > self.exit_custom_under_profit_1.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_1.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_1'
            elif (self.exit_custom_under_profit_1.value > current_profit > self.exit_custom_under_profit_0.value) & (last_candle['rsi'] < self.exit_custom_under_rsi_0.value) & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_u_0'
            # check if the pair is "pumped"
            elif last_candle['exit_pump_48_1_1h'] & (current_profit > self.exit_custom_pump_profit_1_5.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_1_5.value):
                return 'signal_profit_p_1_5'
            elif last_candle['exit_pump_48_1_1h'] & (self.exit_custom_pump_profit_1_5.value > current_profit > self.exit_custom_pump_profit_1_4.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_1_4.value):
                return 'signal_profit_p_1_4'
            elif last_candle['exit_pump_48_1_1h'] & (self.exit_custom_pump_profit_1_4.value > current_profit > self.exit_custom_pump_profit_1_3.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_1_3.value):
                return 'signal_profit_p_1_3'
            elif last_candle['exit_pump_48_1_1h'] & (self.exit_custom_pump_profit_1_3.value > current_profit > self.exit_custom_pump_profit_1_2.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_1_2.value):
                return 'signal_profit_p_1_2'
            elif last_candle['exit_pump_48_1_1h'] & (self.exit_custom_pump_profit_1_2.value > current_profit > self.exit_custom_pump_profit_1_1.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_1_1.value):
                return 'signal_profit_p_1_1'
            elif last_candle['exit_pump_36_1_1h'] & (current_profit > self.exit_custom_pump_profit_2_5.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_2_5.value):
                return 'signal_profit_p_2_5'
            elif last_candle['exit_pump_36_1_1h'] & (self.exit_custom_pump_profit_2_5.value > current_profit > self.exit_custom_pump_profit_2_4.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_2_4.value):
                return 'signal_profit_p_2_4'
            elif last_candle['exit_pump_36_1_1h'] & (self.exit_custom_pump_profit_2_4.value > current_profit > self.exit_custom_pump_profit_2_3.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_2_3.value):
                return 'signal_profit_p_2_3'
            elif last_candle['exit_pump_36_1_1h'] & (self.exit_custom_pump_profit_2_3.value > current_profit > self.exit_custom_pump_profit_2_2.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_2_2.value):
                return 'signal_profit_p_2_2'
            elif last_candle['exit_pump_36_1_1h'] & (self.exit_custom_pump_profit_2_2.value > current_profit > self.exit_custom_pump_profit_2_1.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_2_1.value):
                return 'signal_profit_p_2_1'
            elif last_candle['exit_pump_24_1_1h'] & (current_profit > self.exit_custom_pump_profit_3_5.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_3_5.value):
                return 'signal_profit_p_3_5'
            elif last_candle['exit_pump_24_1_1h'] & (self.exit_custom_pump_profit_3_5.value > current_profit > self.exit_custom_pump_profit_3_4.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_3_4.value):
                return 'signal_profit_p_3_4'
            elif last_candle['exit_pump_24_1_1h'] & (self.exit_custom_pump_profit_3_4.value > current_profit > self.exit_custom_pump_profit_3_3.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_3_3.value):
                return 'signal_profit_p_3_3'
            elif last_candle['exit_pump_24_1_1h'] & (self.exit_custom_pump_profit_3_3.value > current_profit > self.exit_custom_pump_profit_3_2.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_3_2.value):
                return 'signal_profit_p_3_2'
            elif last_candle['exit_pump_24_1_1h'] & (self.exit_custom_pump_profit_3_2.value > current_profit > self.exit_custom_pump_profit_3_1.value) & (last_candle['rsi'] < self.exit_custom_pump_rsi_3_1.value):
                return 'signal_profit_p_3_1'
            elif (self.exit_custom_dec_profit_max_1.value > current_profit > self.exit_custom_dec_profit_min_1.value) & last_candle['sma_200_dec_20']:
                return 'signal_profit_d_1'
            elif (self.exit_custom_dec_profit_max_2.value > current_profit > self.exit_custom_dec_profit_min_2.value) & (last_candle['close'] < last_candle['ema_100']):
                return 'signal_profit_d_2'
            # Trailing
            elif (self.exit_trail_profit_max_1.value > current_profit > self.exit_trail_profit_min_1.value) & (self.exit_trail_rsi_min_1.value < last_candle['rsi'] < self.exit_trail_rsi_max_1.value) & (max_profit > current_profit + self.exit_trail_down_1.value):
                return 'signal_profit_t_1'
            elif (self.exit_trail_profit_max_2.value > current_profit > self.exit_trail_profit_min_2.value) & (self.exit_trail_rsi_min_2.value < last_candle['rsi'] < self.exit_trail_rsi_max_2.value) & (max_profit > current_profit + self.exit_trail_down_2.value):
                return 'signal_profit_t_2'
            elif (self.exit_trail_profit_max_3.value > current_profit > self.exit_trail_profit_min_3.value) & (max_profit > current_profit + self.exit_trail_down_3.value) & last_candle['sma_200_dec_20_1h']:
                return 'signal_profit_t_3'
            elif (last_candle['close'] < last_candle['ema_200']) & (current_profit > self.exit_trail_profit_min_3.value) & (current_profit < self.exit_trail_profit_max_3.value) & (max_profit > current_profit + self.exit_trail_down_3.value):
                return 'signal_profit_u_t_1'
            # elif (last_candle['exit_pump_48_1_1h']) & (0.06 > current_profit > 0.04) & (last_candle['rsi'] < 54.0) & (current_time - timedelta(minutes=30) < trade.open_date_utc):
            #     return 'signal_profit_p_s_1'
            elif (current_profit > 0.0) & (last_candle['close'] < last_candle['ema_200']) & ((last_candle['ema_200'] - last_candle['close']) / last_candle['close'] < self.exit_custom_profit_under_rel_1.value) & (last_candle['rsi'] > last_candle['rsi_1h'] + self.exit_custom_profit_under_rsi_diff_1.value):
                return 'signal_profit_u_e_1'
            elif (current_profit < -0.0) & (last_candle['close'] < last_candle['ema_200']) & ((last_candle['ema_200'] - last_candle['close']) / last_candle['close'] < self.exit_custom_stoploss_under_rel_1.value) & (last_candle['rsi'] > last_candle['rsi_1h'] + self.exit_custom_stoploss_under_rsi_diff_1.value) & last_candle['sma_200_dec_24'] & (current_time - timedelta(minutes=720) > trade.open_date_utc):
                return 'signal_stoploss_u_1'
            elif (self.exit_custom_stoploss_long_profit_min_1.value < current_profit < self.exit_custom_stoploss_long_profit_max_1.value) & (current_profit > -max_loss + self.exit_custom_stoploss_long_recover_1.value) & (last_candle['close'] < last_candle['ema_200']) & (last_candle['rsi'] > last_candle['rsi_1h'] + self.exit_custom_stoploss_long_rsi_diff_1.value) & last_candle['sma_200_dec_24'] & (current_time - timedelta(minutes=1200) > trade.open_date_utc):
                return 'signal_stoploss_l_r_u_1'
            elif (current_profit < -0.0) & (current_profit > -max_loss + self.exit_custom_stoploss_long_recover_2.value) & (last_candle['close'] < last_candle['ema_200']) & (last_candle['rsi'] > last_candle['rsi_1h'] + self.exit_custom_stoploss_long_rsi_diff_2.value) & last_candle['sma_200_dec_24'] & (current_time - timedelta(minutes=1200) > trade.open_date_utc):
                return 'signal_stoploss_l_r_u_2'
            elif (self.exit_custom_pump_dec_profit_max_1.value > current_profit > self.exit_custom_pump_dec_profit_min_1.value) & last_candle['exit_pump_48_1_1h'] & last_candle['sma_200_dec_20'] & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_p_d_1'
            elif (self.exit_custom_pump_dec_profit_max_2.value > current_profit > self.exit_custom_pump_dec_profit_min_2.value) & last_candle['exit_pump_48_2_1h'] & last_candle['sma_200_dec_20'] & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_p_d_2'
            elif (self.exit_custom_pump_dec_profit_max_3.value > current_profit > self.exit_custom_pump_dec_profit_min_3.value) & last_candle['exit_pump_48_3_1h'] & last_candle['sma_200_dec_20'] & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_p_d_3'
            elif (self.exit_custom_pump_dec_profit_max_4.value > current_profit > self.exit_custom_pump_dec_profit_min_4.value) & last_candle['sma_200_dec_20'] & last_candle['exit_pump_24_2_1h']:
                return 'signal_profit_p_d_4'
            # Pumped 48h 1, under EMA200
            elif (self.exit_custom_pump_under_profit_max_1.value > current_profit > self.exit_custom_pump_under_profit_min_1.value) & last_candle['exit_pump_48_1_1h'] & (last_candle['close'] < last_candle['ema_200']):
                return 'signal_profit_p_u_1'
            # Pumped 36h 2, trail 1
            elif last_candle['exit_pump_36_2_1h'] & (self.exit_custom_pump_trail_profit_max_1.value > current_profit > self.exit_custom_pump_trail_profit_min_1.value) & (self.exit_custom_pump_trail_rsi_min_1.value < last_candle['rsi'] < self.exit_custom_pump_trail_rsi_max_1.value) & (max_profit > current_profit + self.exit_custom_pump_trail_down_1.value):
                return 'signal_profit_p_t_1'
            # elif (max_profit < self.exit_custom_stoploss_pump_max_profit_1.value) & (self.exit_custom_stoploss_pump_min_1.value < current_profit < self.exit_custom_stoploss_pump_max_1.value) & (last_candle['exit_pump_48_1_1h']) & (last_candle['sma_200_dec_20']) & (last_candle['close'] < (last_candle['ema_200'] * self.exit_custom_stoploss_pump_ma_offset_1.value)):
            #     return 'signal_stoploss_p_1'
            elif (max_profit < self.exit_custom_stoploss_pump_max_profit_2.value) & (current_profit < self.exit_custom_stoploss_pump_loss_2.value) & last_candle['exit_pump_48_1_1h'] & last_candle['sma_200_dec_20_1h'] & (last_candle['close'] < last_candle['ema_200'] * self.exit_custom_stoploss_pump_ma_offset_2.value):
                return 'signal_stoploss_p_2'
            elif (max_profit < self.exit_custom_stoploss_pump_max_profit_3.value) & (current_profit < self.exit_custom_stoploss_pump_loss_3.value) & last_candle['exit_pump_36_3_1h'] & (last_candle['close'] < last_candle['ema_200'] * self.exit_custom_stoploss_pump_ma_offset_3.value):
                return 'signal_stoploss_p_3'
            # Recover
            elif (max_loss > self.exit_custom_recover_min_loss_1.value) & (current_profit > self.exit_custom_recover_profit_1.value):
                return 'signal_profit_r_1'
            elif (max_loss > self.exit_custom_recover_min_loss_2.value) & (self.exit_custom_recover_profit_max_2.value > current_profit > self.exit_custom_recover_profit_min_2.value) & (last_candle['rsi'] < self.exit_custom_recover_rsi_2.value):
                return 'signal_profit_r_2'
            # Take profit for long duration trades
            elif (self.exit_custom_long_profit_min_1.value < current_profit < self.exit_custom_long_profit_max_1.value) & (current_time - timedelta(minutes=self.exit_custom_long_duration_min_1.value) > trade.open_date_utc):
                return 'signal_profit_l_1'
        return None

    def range_percent_change(self, dataframe: DataFrame, method, length: int) -> float:
        """
        Rolling Percentage Change Maximum across interval.

        :param dataframe: DataFrame The original OHLC dataframe
        :param method: High to Low / Open to Close
        :param length: int The length to look back
        """
        df = dataframe.copy()
        if method == 'HL':
            return (df['high'].rolling(length).max() - df['low'].rolling(length).min()) / df['low'].rolling(length).min()
        elif method == 'OC':
            return (df['open'].rolling(length).max() - df['close'].rolling(length).min()) / df['close'].rolling(length).min()
        else:
            raise ValueError(f'Method {method} not defined!')

    def top_percent_change(self, dataframe: DataFrame, length: int) -> float:
        """
        Percentage change of the current close from the range maximum Open price

        :param dataframe: DataFrame The original OHLC dataframe
        :param length: int The length to look back
        """
        df = dataframe.copy()
        if length == 0:
            return (df['open'] - df['close']) / df['close']
        else:
            return (df['open'].rolling(length).max() - df['close']) / df['close']

    def range_maxgap(self, dataframe: DataFrame, length: int) -> float:
        """
        Maximum Price Gap across interval.

        :param dataframe: DataFrame The original OHLC dataframe
        :param length: int The length to look back
        """
        df = dataframe.copy()
        return df['open'].rolling(length).max() - df['close'].rolling(length).min()

    def range_maxgap_adjusted(self, dataframe: DataFrame, length: int, adjustment: float) -> float:
        """
        Maximum Price Gap across interval adjusted.

        :param dataframe: DataFrame The original OHLC dataframe
        :param length: int The length to look back
        :param adjustment: int The adjustment to be applied
        """
        return self.range_maxgap(dataframe, length) / adjustment

    def range_height(self, dataframe: DataFrame, length: int) -> float:
        """
        Current close distance to range bottom.

        :param dataframe: DataFrame The original OHLC dataframe
        :param length: int The length to look back
        """
        df = dataframe.copy()
        return df['close'] - df['close'].rolling(length).min()

    def safe_pump(self, dataframe: DataFrame, length: int, thresh: float, pull_thresh: float) -> bool:
        """
        Determine if entry after a pump is safe.

        :param dataframe: DataFrame The original OHLC dataframe
        :param length: int The length to look back
        :param thresh: int Maximum percentage change threshold
        :param pull_thresh: int Pullback from interval maximum threshold
        """
        df = dataframe.copy()
        return (df[f'oc_pct_change_{length}'] < thresh) | (self.range_maxgap_adjusted(df, length, pull_thresh) > self.range_height(df, length))

    def safe_dips(self, dataframe: DataFrame, thresh_0, thresh_2, thresh_12, thresh_144) -> bool:
        """
        Determine if dip is safe to enter.

        :param dataframe: DataFrame The original OHLC dataframe
        :param thresh_0: Threshold value for 0 length top pct change
        :param thresh_2: Threshold value for 2 length top pct change
        :param thresh_12: Threshold value for 12 length top pct change
        :param thresh_144: Threshold value for 144 length top pct change
        """
        return (dataframe['tpct_change_0'] < thresh_0) & (dataframe['tpct_change_2'] < thresh_2) & (dataframe['tpct_change_12'] < thresh_12) & (dataframe['tpct_change_144'] < thresh_144)

    def informative_pairs(self):
        # get access to all pairs available in whitelist.
        pairs = self.dp.current_whitelist()
        # Assign tf to each pair so they can be downloaded and cached for strategy.
        informative_pairs = [(pair, '1h') for pair in pairs]
        return informative_pairs

    def informative_1h_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        assert self.dp, 'DataProvider is required for multiple timeframes.'
        # Get the informative pair
        informative_1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=self.inf_1h)
        informative_1h['ema_fast'] = ta.EMA(informative_1h, timeperiod=20)
        informative_1h['ema_slow'] = ta.EMA(informative_1h, timeperiod=25)
        informative_1h['uptrend'] = (informative_1h['ema_fast'] > informative_1h['ema_slow']).astype('int')
        # EMA
        informative_1h['ema_12'] = ta.EMA(informative_1h, timeperiod=12)
        informative_1h['ema_15'] = ta.EMA(informative_1h, timeperiod=15)
        informative_1h['ema_20'] = ta.EMA(informative_1h, timeperiod=20)
        informative_1h['ema_26'] = ta.EMA(informative_1h, timeperiod=26)
        informative_1h['ema_35'] = ta.EMA(informative_1h, timeperiod=35)
        informative_1h['ema_50'] = ta.EMA(informative_1h, timeperiod=50)
        informative_1h['ema_100'] = ta.EMA(informative_1h, timeperiod=100)
        informative_1h['ema_200'] = ta.EMA(informative_1h, timeperiod=200)
        # SMA
        informative_1h['sma_200'] = ta.SMA(informative_1h, timeperiod=200)
        informative_1h['sma_200_dec_20'] = informative_1h['sma_200'] < informative_1h['sma_200'].shift(20)
        # RSI
        informative_1h['rsi'] = ta.RSI(informative_1h, timeperiod=14)
        # BB
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(informative_1h), window=20, stds=2)
        informative_1h['bb20_2_low'] = bollinger['lower']
        informative_1h['bb20_2_mid'] = bollinger['mid']
        informative_1h['bb20_2_upp'] = bollinger['upper']
        # Chaikin Money Flow
        informative_1h['cmf'] = chaikin_money_flow(informative_1h, 20)
        # Pump protections
        informative_1h['hl_pct_change_48'] = self.range_percent_change(informative_1h, 'HL', 48)
        informative_1h['hl_pct_change_36'] = self.range_percent_change(informative_1h, 'HL', 36)
        informative_1h['hl_pct_change_24'] = self.range_percent_change(informative_1h, 'HL', 24)
        informative_1h['oc_pct_change_48'] = self.range_percent_change(informative_1h, 'OC', 48)
        informative_1h['oc_pct_change_36'] = self.range_percent_change(informative_1h, 'OC', 36)
        informative_1h['oc_pct_change_24'] = self.range_percent_change(informative_1h, 'OC', 24)
        informative_1h['safe_pump_24_10'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_10_24.value, self.entry_pump_pull_threshold_10_24.value)
        informative_1h['safe_pump_36_10'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_10_36.value, self.entry_pump_pull_threshold_10_36.value)
        informative_1h['safe_pump_48_10'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_10_48.value, self.entry_pump_pull_threshold_10_48.value)
        informative_1h['safe_pump_24_20'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_20_24.value, self.entry_pump_pull_threshold_20_24.value)
        informative_1h['safe_pump_36_20'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_20_36.value, self.entry_pump_pull_threshold_20_36.value)
        informative_1h['safe_pump_48_20'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_20_48.value, self.entry_pump_pull_threshold_20_48.value)
        informative_1h['safe_pump_24_30'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_30_24.value, self.entry_pump_pull_threshold_30_24.value)
        informative_1h['safe_pump_36_30'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_30_36.value, self.entry_pump_pull_threshold_30_36.value)
        informative_1h['safe_pump_48_30'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_30_48.value, self.entry_pump_pull_threshold_30_48.value)
        informative_1h['safe_pump_24_40'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_40_24.value, self.entry_pump_pull_threshold_40_24.value)
        informative_1h['safe_pump_36_40'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_40_36.value, self.entry_pump_pull_threshold_40_36.value)
        informative_1h['safe_pump_48_40'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_40_48.value, self.entry_pump_pull_threshold_40_48.value)
        informative_1h['safe_pump_24_50'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_50_24.value, self.entry_pump_pull_threshold_50_24.value)
        informative_1h['safe_pump_36_50'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_50_36.value, self.entry_pump_pull_threshold_50_36.value)
        informative_1h['safe_pump_48_50'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_50_48.value, self.entry_pump_pull_threshold_50_48.value)
        informative_1h['safe_pump_24_60'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_60_24.value, self.entry_pump_pull_threshold_60_24.value)
        informative_1h['safe_pump_36_60'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_60_36.value, self.entry_pump_pull_threshold_60_36.value)
        informative_1h['safe_pump_48_60'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_60_48.value, self.entry_pump_pull_threshold_60_48.value)
        informative_1h['safe_pump_24_70'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_70_24.value, self.entry_pump_pull_threshold_70_24.value)
        informative_1h['safe_pump_36_70'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_70_36.value, self.entry_pump_pull_threshold_70_36.value)
        informative_1h['safe_pump_48_70'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_70_48.value, self.entry_pump_pull_threshold_70_48.value)
        informative_1h['safe_pump_24_80'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_80_24.value, self.entry_pump_pull_threshold_80_24.value)
        informative_1h['safe_pump_36_80'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_80_36.value, self.entry_pump_pull_threshold_80_36.value)
        informative_1h['safe_pump_48_80'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_80_48.value, self.entry_pump_pull_threshold_80_48.value)
        informative_1h['safe_pump_24_90'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_90_24.value, self.entry_pump_pull_threshold_90_24.value)
        informative_1h['safe_pump_36_90'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_90_36.value, self.entry_pump_pull_threshold_90_36.value)
        informative_1h['safe_pump_48_90'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_90_48.value, self.entry_pump_pull_threshold_90_48.value)
        informative_1h['safe_pump_24_100'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_100_24.value, self.entry_pump_pull_threshold_100_24.value)
        informative_1h['safe_pump_36_100'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_100_36.value, self.entry_pump_pull_threshold_100_36.value)
        informative_1h['safe_pump_48_100'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_100_48.value, self.entry_pump_pull_threshold_100_48.value)
        informative_1h['safe_pump_24_110'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_110_24.value, self.entry_pump_pull_threshold_110_24.value)
        informative_1h['safe_pump_36_110'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_110_36.value, self.entry_pump_pull_threshold_110_36.value)
        informative_1h['safe_pump_48_110'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_110_48.value, self.entry_pump_pull_threshold_110_48.value)
        informative_1h['safe_pump_24_120'] = self.safe_pump(informative_1h, 24, self.entry_pump_threshold_120_24.value, self.entry_pump_pull_threshold_120_24.value)
        informative_1h['safe_pump_36_120'] = self.safe_pump(informative_1h, 36, self.entry_pump_threshold_120_36.value, self.entry_pump_pull_threshold_120_36.value)
        informative_1h['safe_pump_48_120'] = self.safe_pump(informative_1h, 48, self.entry_pump_threshold_120_48.value, self.entry_pump_pull_threshold_120_48.value)
        informative_1h['exit_pump_48_1'] = informative_1h['hl_pct_change_48'] > self.exit_pump_threshold_48_1.value
        informative_1h['exit_pump_48_2'] = informative_1h['hl_pct_change_48'] > self.exit_pump_threshold_48_2.value
        informative_1h['exit_pump_48_3'] = informative_1h['hl_pct_change_48'] > self.exit_pump_threshold_48_3.value
        informative_1h['exit_pump_36_1'] = informative_1h['hl_pct_change_36'] > self.exit_pump_threshold_36_1.value
        informative_1h['exit_pump_36_2'] = informative_1h['hl_pct_change_36'] > self.exit_pump_threshold_36_2.value
        informative_1h['exit_pump_36_3'] = informative_1h['hl_pct_change_36'] > self.exit_pump_threshold_36_3.value
        informative_1h['exit_pump_24_1'] = informative_1h['hl_pct_change_24'] > self.exit_pump_threshold_24_1.value
        informative_1h['exit_pump_24_2'] = informative_1h['hl_pct_change_24'] > self.exit_pump_threshold_24_2.value
        informative_1h['exit_pump_24_3'] = informative_1h['hl_pct_change_24'] > self.exit_pump_threshold_24_3.value
        return informative_1h

    def normal_tf_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # BB 40 - STD2
        bb_40_std2 = qtpylib.bollinger_bands(dataframe['close'], window=40, stds=2)
        dataframe['bb40_2_low'] = bb_40_std2['lower']
        dataframe['bb40_2_mid'] = bb_40_std2['mid']
        dataframe['bb40_2_delta'] = (bb_40_std2['mid'] - dataframe['bb40_2_low']).abs()
        dataframe['closedelta'] = (dataframe['close'] - dataframe['close'].shift()).abs()
        dataframe['tail'] = (dataframe['close'] - dataframe['bb40_2_low']).abs()
        # BB 20 - STD2
        bb_20_std2 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb20_2_low'] = bb_20_std2['lower']
        dataframe['bb20_2_mid'] = bb_20_std2['mid']
        dataframe['bb20_2_upp'] = bb_20_std2['upper']
        # EMA 200
        dataframe['ema_12'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ema_15'] = ta.EMA(dataframe, timeperiod=15)
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_26'] = ta.EMA(dataframe, timeperiod=26)
        dataframe['ema_35'] = ta.EMA(dataframe, timeperiod=35)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['ma_lower'] = ta.SMA(dataframe, timeperiod=15) * 0.953
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_slow'] = ta.RSI(dataframe, timeperiod=20)
        dataframe['rsi_slow_descending'] = (dataframe['rsi_slow'] < dataframe['rsi_slow'].shift()).astype('int')
        # SMA
        dataframe['sma_5'] = ta.SMA(dataframe, timeperiod=5)
        dataframe['sma_30'] = ta.SMA(dataframe, timeperiod=30)
        dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=200)
        dataframe['sma_200_dec_20'] = dataframe['sma_200'] < dataframe['sma_200'].shift(20)
        dataframe['sma_200_dec_24'] = dataframe['sma_200'] < dataframe['sma_200'].shift(24)
        # MFI
        dataframe['mfi'] = ta.MFI(dataframe)
        # EWO
        dataframe['ewo'] = EWO(dataframe, 50, 200)
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        # Chopiness
        dataframe['chop'] = qtpylib.chopiness(dataframe, 14)
        # Zero-Lag EMA
        dataframe['zema'] = zema(dataframe, period=61)
        # Dip protection
        dataframe['tpct_change_0'] = self.top_percent_change(dataframe, 0)
        dataframe['tpct_change_2'] = self.top_percent_change(dataframe, 2)
        dataframe['tpct_change_12'] = self.top_percent_change(dataframe, 12)
        dataframe['tpct_change_144'] = self.top_percent_change(dataframe, 144)
        dataframe['safe_dips_10'] = self.safe_dips(dataframe, self.entry_dip_threshold_10_1.value, self.entry_dip_threshold_10_2.value, self.entry_dip_threshold_10_3.value, self.entry_dip_threshold_10_4.value)
        dataframe['safe_dips_20'] = self.safe_dips(dataframe, self.entry_dip_threshold_20_1.value, self.entry_dip_threshold_20_2.value, self.entry_dip_threshold_20_3.value, self.entry_dip_threshold_20_4.value)
        dataframe['safe_dips_30'] = self.safe_dips(dataframe, self.entry_dip_threshold_30_1.value, self.entry_dip_threshold_30_2.value, self.entry_dip_threshold_30_3.value, self.entry_dip_threshold_30_4.value)
        dataframe['safe_dips_40'] = self.safe_dips(dataframe, self.entry_dip_threshold_40_1.value, self.entry_dip_threshold_40_2.value, self.entry_dip_threshold_40_3.value, self.entry_dip_threshold_40_4.value)
        dataframe['safe_dips_50'] = self.safe_dips(dataframe, self.entry_dip_threshold_50_1.value, self.entry_dip_threshold_50_2.value, self.entry_dip_threshold_50_3.value, self.entry_dip_threshold_50_4.value)
        dataframe['safe_dips_60'] = self.safe_dips(dataframe, self.entry_dip_threshold_60_1.value, self.entry_dip_threshold_60_2.value, self.entry_dip_threshold_60_3.value, self.entry_dip_threshold_60_4.value)
        dataframe['safe_dips_70'] = self.safe_dips(dataframe, self.entry_dip_threshold_70_1.value, self.entry_dip_threshold_70_2.value, self.entry_dip_threshold_70_3.value, self.entry_dip_threshold_70_4.value)
        dataframe['safe_dips_80'] = self.safe_dips(dataframe, self.entry_dip_threshold_80_1.value, self.entry_dip_threshold_80_2.value, self.entry_dip_threshold_80_3.value, self.entry_dip_threshold_80_4.value)
        dataframe['safe_dips_90'] = self.safe_dips(dataframe, self.entry_dip_threshold_90_1.value, self.entry_dip_threshold_90_2.value, self.entry_dip_threshold_90_3.value, self.entry_dip_threshold_90_4.value)
        dataframe['safe_dips_100'] = self.safe_dips(dataframe, self.entry_dip_threshold_100_1.value, self.entry_dip_threshold_100_2.value, self.entry_dip_threshold_100_3.value, self.entry_dip_threshold_100_4.value)
        dataframe['safe_dips_110'] = self.safe_dips(dataframe, self.entry_dip_threshold_110_1.value, self.entry_dip_threshold_110_2.value, self.entry_dip_threshold_110_3.value, self.entry_dip_threshold_110_4.value)
        # Volume
        dataframe['volume_mean_4'] = dataframe['volume'].rolling(4).mean().shift(1)
        dataframe['volume_mean_30'] = dataframe['volume'].rolling(30).mean()
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # The indicators for the 1h informative timeframe
        informative_1h = self.informative_1h_indicators(dataframe, metadata)
        dataframe = merge_informative_pair(dataframe, informative_1h, self.timeframe, self.inf_1h, ffill=True)
        # The indicators for the normal (5m) timeframe
        dataframe = self.normal_tf_indicators(dataframe, metadata)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        #&
        #(
        #(dataframe['open']<dataframe['hma_fast_1h'])
        #&
        #(dataframe['low'].abs()<dataframe['hma_fast_1h'])
        #|
        #(dataframe['open']>dataframe['hma_fast_1h'])
        #&
        #(dataframe['low'].abs()>dataframe['hma_fast_1h'])
        #&
        #(
        #(dataframe['open']<dataframe['ema_slow_1h'])
        #&
        #(dataframe['low'].abs()<dataframe['ema_slow_1h'])
        #|
        #(dataframe['open']>dataframe['ema_slow_1h'])
        #&
        #(dataframe['low'].abs()>dataframe['ema_slow_1h'])
        #)
        #)
        conditions.append((dataframe['rsi_slow_descending'].rolling(1).sum() == 1) & (dataframe['rsi_fast'] < 35) & (dataframe['uptrend_1h'] > 0) & (dataframe['close'] < dataframe['ma_lower']) & (dataframe['open'] > dataframe['ma_lower']) & (dataframe['volume'] > 0) & ((dataframe['open'] < dataframe['ema_fast_1h']) & (dataframe['low'].abs() < dataframe['ema_fast_1h']) | (dataframe['open'] > dataframe['ema_fast_1h']) & (dataframe['low'].abs() > dataframe['ema_fast_1h'])))
        # Protections
        entry_01_protections = [True]
        if self.entry_01_protection__ema_fast.value:
            entry_01_protections.append(dataframe[f'ema_{self.entry_01_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_01_protection__ema_slow.value:
            entry_01_protections.append(dataframe[f'ema_{self.entry_01_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_01_protection__close_above_ema_fast.value:
            entry_01_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_01_protection__close_above_ema_fast_len.value}'])
        if self.entry_01_protection__close_above_ema_slow.value:
            entry_01_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_01_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_01_protection__sma200_rising.value:
            entry_01_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_01_protection__sma200_rising_val.value)))
        if self.entry_01_protection__sma200_1h_rising.value:
            entry_01_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_01_protection__sma200_1h_rising_val.value)))
        if self.entry_01_protection__safe_dips.value:
            entry_01_protections.append(dataframe[f'safe_dips_{self.entry_01_protection__safe_dips_type.value}'])
        if self.entry_01_protection__safe_pump.value:
            entry_01_protections.append(dataframe[f'safe_pump_{self.entry_01_protection__safe_pump_period.value}_{self.entry_01_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_01_logic = []
        entry_01_logic.append(reduce(lambda x, y: x & y, entry_01_protections))
        entry_01_logic.append((dataframe['close'] - dataframe['open'].rolling(36).min()) / dataframe['open'].rolling(36).min() > self.entry_min_inc_1.value)
        entry_01_logic.append(dataframe['rsi_1h'] > self.entry_rsi_1h_min_1.value)
        entry_01_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_max_1.value)
        entry_01_logic.append(dataframe['rsi'] < self.entry_rsi_1.value)
        entry_01_logic.append(dataframe['mfi'] < self.entry_mfi_1.value)
        entry_01_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_01_trigger'] = reduce(lambda x, y: x & y, entry_01_logic)
        if self.entry_condition_1_enable.value:
            conditions.append(dataframe['entry_01_trigger'])
        # Protections
        entry_02_protections = [True]
        if self.entry_02_protection__ema_fast.value:
            entry_02_protections.append(dataframe[f'ema_{self.entry_02_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_02_protection__ema_slow.value:
            entry_02_protections.append(dataframe[f'ema_{self.entry_02_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_02_protection__close_above_ema_fast.value:
            entry_02_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_02_protection__close_above_ema_fast_len.value}'])
        if self.entry_02_protection__close_above_ema_slow.value:
            entry_02_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_02_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_02_protection__sma200_rising.value:
            entry_02_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_02_protection__sma200_rising_val.value)))
        if self.entry_02_protection__sma200_1h_rising.value:
            entry_02_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_02_protection__sma200_1h_rising_val.value)))
        if self.entry_02_protection__safe_dips.value:
            entry_02_protections.append(dataframe[f'safe_dips_{self.entry_02_protection__safe_dips_type.value}'])
        if self.entry_02_protection__safe_pump.value:
            entry_02_protections.append(dataframe[f'safe_pump_{self.entry_02_protection__safe_pump_period.value}_{self.entry_02_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_02_logic = []
        entry_02_logic.append(reduce(lambda x, y: x & y, entry_02_protections))
        #entry_02_logic.append(dataframe['volume_mean_4'] * self.entry_volume_2.value > dataframe['volume'])
        entry_02_logic.append(dataframe['rsi'] < dataframe['rsi_1h'] - self.entry_rsi_1h_diff_2.value)
        entry_02_logic.append(dataframe['mfi'] < self.entry_mfi_2.value)
        entry_02_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_2.value)
        entry_02_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_02_trigger'] = reduce(lambda x, y: x & y, entry_02_logic)
        if self.entry_condition_2_enable.value:
            conditions.append(dataframe['entry_02_trigger'])
        # Protections
        entry_03_protections = [True]
        if self.entry_03_protection__ema_fast.value:
            entry_03_protections.append(dataframe[f'ema_{self.entry_03_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_03_protection__ema_slow.value:
            entry_03_protections.append(dataframe[f'ema_{self.entry_03_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_03_protection__close_above_ema_fast.value:
            entry_03_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_03_protection__close_above_ema_fast_len.value}'])
        if self.entry_03_protection__close_above_ema_slow.value:
            entry_03_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_03_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_03_protection__sma200_rising.value:
            entry_03_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_03_protection__sma200_rising_val.value)))
        if self.entry_03_protection__sma200_1h_rising.value:
            entry_03_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_03_protection__sma200_1h_rising_val.value)))
        if self.entry_03_protection__safe_dips.value:
            entry_03_protections.append(dataframe[f'safe_dips_{self.entry_03_protection__safe_dips_type.value}'])
        if self.entry_03_protection__safe_pump.value:
            entry_03_protections.append(dataframe[f'safe_pump_{self.entry_03_protection__safe_pump_period.value}_{self.entry_03_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        entry_03_protections.append(dataframe['close'] > dataframe['ema_200_1h'] * self.entry_ema_rel_3.value)
        # Logic
        entry_03_logic = []
        entry_03_logic.append(reduce(lambda x, y: x & y, entry_03_protections))
        entry_03_logic.append(dataframe['bb40_2_low'].shift().gt(0))
        entry_03_logic.append(dataframe['bb40_2_delta'].gt(dataframe['close'] * self.entry_bb40_bbdelta_close_3.value))
        entry_03_logic.append(dataframe['closedelta'].gt(dataframe['close'] * self.entry_bb40_closedelta_close_3.value))
        entry_03_logic.append(dataframe['tail'].lt(dataframe['bb40_2_delta'] * self.entry_bb40_tail_bbdelta_3.value))
        entry_03_logic.append(dataframe['close'].lt(dataframe['bb40_2_low'].shift()))
        entry_03_logic.append(dataframe['close'].le(dataframe['close'].shift()))
        entry_03_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_03_trigger'] = reduce(lambda x, y: x & y, entry_03_logic)
        if self.entry_condition_3_enable.value:
            conditions.append(dataframe['entry_03_trigger'])
        # Protections
        entry_04_protections = [True]
        if self.entry_04_protection__ema_fast.value:
            entry_04_protections.append(dataframe[f'ema_{self.entry_04_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_04_protection__ema_slow.value:
            entry_04_protections.append(dataframe[f'ema_{self.entry_04_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_04_protection__close_above_ema_fast.value:
            entry_04_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_04_protection__close_above_ema_fast_len.value}'])
        if self.entry_04_protection__close_above_ema_slow.value:
            entry_04_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_04_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_04_protection__sma200_rising.value:
            entry_04_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_04_protection__sma200_rising_val.value)))
        if self.entry_04_protection__sma200_1h_rising.value:
            entry_04_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_04_protection__sma200_1h_rising_val.value)))
        if self.entry_04_protection__safe_dips.value:
            entry_04_protections.append(dataframe[f'safe_dips_{self.entry_04_protection__safe_dips_type.value}'])
        if self.entry_04_protection__safe_pump.value:
            entry_04_protections.append(dataframe[f'safe_pump_{self.entry_04_protection__safe_pump_period.value}_{self.entry_04_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_04_logic = []
        entry_04_logic.append(reduce(lambda x, y: x & y, entry_04_protections))
        entry_04_logic.append(dataframe['close'] < dataframe['ema_50'])
        entry_04_logic.append(dataframe['close'] < self.entry_bb20_close_bblowerband_4.value * dataframe['bb20_2_low'])
        entry_04_logic.append(dataframe['volume'] < dataframe['volume_mean_30'].shift(1) * self.entry_bb20_volume_4.value)
        # Populate
        dataframe.loc[:, 'entry_04_trigger'] = reduce(lambda x, y: x & y, entry_04_logic)
        if self.entry_condition_4_enable.value:
            conditions.append(dataframe['entry_04_trigger'])
        # Protections
        entry_05_protections = [True]
        if self.entry_05_protection__ema_fast.value:
            entry_05_protections.append(dataframe[f'ema_{self.entry_05_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_05_protection__ema_slow.value:
            entry_05_protections.append(dataframe[f'ema_{self.entry_05_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_05_protection__close_above_ema_fast.value:
            entry_05_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_05_protection__close_above_ema_fast_len.value}'])
        if self.entry_05_protection__close_above_ema_slow.value:
            entry_05_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_05_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_05_protection__sma200_rising.value:
            entry_05_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_05_protection__sma200_rising_val.value)))
        if self.entry_05_protection__sma200_1h_rising.value:
            entry_05_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_05_protection__sma200_1h_rising_val.value)))
        if self.entry_05_protection__safe_dips.value:
            entry_05_protections.append(dataframe[f'safe_dips_{self.entry_05_protection__safe_dips_type.value}'])
        if self.entry_05_protection__safe_pump.value:
            entry_05_protections.append(dataframe[f'safe_pump_{self.entry_05_protection__safe_pump_period.value}_{self.entry_05_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        entry_05_protections.append(dataframe['close'] > dataframe['ema_200_1h'] * self.entry_ema_rel_5.value)
        # Logic
        entry_05_logic = []
        entry_05_logic.append(reduce(lambda x, y: x & y, entry_05_protections))
        entry_05_logic.append(dataframe['ema_26'] > dataframe['ema_12'])
        entry_05_logic.append(dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_open_mult_5.value)
        entry_05_logic.append(dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100)
        entry_05_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_5.value)
        entry_05_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_05_trigger'] = reduce(lambda x, y: x & y, entry_05_logic)
        if self.entry_condition_5_enable.value:
            conditions.append(dataframe['entry_05_trigger'])
        # Protections
        entry_06_protections = [True]
        if self.entry_06_protection__ema_fast.value:
            entry_06_protections.append(dataframe[f'ema_{self.entry_06_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_06_protection__ema_slow.value:
            entry_06_protections.append(dataframe[f'ema_{self.entry_06_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_06_protection__close_above_ema_fast.value:
            entry_06_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_06_protection__close_above_ema_fast_len.value}'])
        if self.entry_06_protection__close_above_ema_slow.value:
            entry_06_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_06_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_06_protection__sma200_rising.value:
            entry_06_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_06_protection__sma200_rising_val.value)))
        if self.entry_06_protection__sma200_1h_rising.value:
            entry_06_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_06_protection__sma200_1h_rising_val.value)))
        if self.entry_06_protection__safe_dips.value:
            entry_06_protections.append(dataframe[f'safe_dips_{self.entry_06_protection__safe_dips_type.value}'])
        if self.entry_06_protection__safe_pump.value:
            entry_06_protections.append(dataframe[f'safe_pump_{self.entry_06_protection__safe_pump_period.value}_{self.entry_06_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_06_logic = []
        entry_06_logic.append(reduce(lambda x, y: x & y, entry_06_protections))
        entry_06_logic.append(dataframe['ema_26'] > dataframe['ema_12'])
        entry_06_logic.append(dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_open_mult_6.value)
        entry_06_logic.append(dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100)
        entry_06_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_6.value)
        entry_06_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_06_trigger'] = reduce(lambda x, y: x & y, entry_06_logic)
        if self.entry_condition_6_enable.value:
            conditions.append(dataframe['entry_06_trigger'])
        # Protections
        entry_07_protections = [True]
        if self.entry_07_protection__ema_fast.value:
            entry_07_protections.append(dataframe[f'ema_{self.entry_07_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_07_protection__ema_slow.value:
            entry_07_protections.append(dataframe[f'ema_{self.entry_07_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_07_protection__close_above_ema_fast.value:
            entry_07_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_07_protection__close_above_ema_fast_len.value}'])
        if self.entry_07_protection__close_above_ema_slow.value:
            entry_07_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_07_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_07_protection__sma200_rising.value:
            entry_07_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_07_protection__sma200_rising_val.value)))
        if self.entry_07_protection__sma200_1h_rising.value:
            entry_07_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_07_protection__sma200_1h_rising_val.value)))
        if self.entry_07_protection__safe_dips.value:
            entry_07_protections.append(dataframe[f'safe_dips_{self.entry_07_protection__safe_dips_type.value}'])
        if self.entry_07_protection__safe_pump.value:
            entry_07_protections.append(dataframe[f'safe_pump_{self.entry_07_protection__safe_pump_period.value}_{self.entry_07_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_07_logic = []
        entry_07_logic.append(reduce(lambda x, y: x & y, entry_07_protections))
        #entry_07_logic.append(dataframe['volume'].rolling(4).mean() * self.entry_volume_7.value > dataframe['volume'])
        entry_07_logic.append(dataframe['ema_26'] > dataframe['ema_12'])
        entry_07_logic.append(dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_open_mult_7.value)
        entry_07_logic.append(dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100)
        entry_07_logic.append(dataframe['rsi'] < self.entry_rsi_7.value)
        entry_07_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_07_trigger'] = reduce(lambda x, y: x & y, entry_07_logic)
        if self.entry_condition_7_enable.value:
            conditions.append(dataframe['entry_07_trigger'])
        # Protections
        entry_08_protections = [True]
        if self.entry_08_protection__ema_fast.value:
            entry_08_protections.append(dataframe[f'ema_{self.entry_08_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_08_protection__ema_slow.value:
            entry_08_protections.append(dataframe[f'ema_{self.entry_08_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_08_protection__close_above_ema_fast.value:
            entry_08_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_08_protection__close_above_ema_fast_len.value}'])
        if self.entry_08_protection__close_above_ema_slow.value:
            entry_08_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_08_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_08_protection__sma200_rising.value:
            entry_08_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_08_protection__sma200_rising_val.value)))
        if self.entry_08_protection__sma200_1h_rising.value:
            entry_08_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_08_protection__sma200_1h_rising_val.value)))
        if self.entry_08_protection__safe_dips.value:
            entry_08_protections.append(dataframe[f'safe_dips_{self.entry_08_protection__safe_dips_type.value}'])
        if self.entry_08_protection__safe_pump.value:
            entry_08_protections.append(dataframe[f'safe_pump_{self.entry_08_protection__safe_pump_period.value}_{self.entry_08_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_08_logic = []
        entry_08_logic.append(reduce(lambda x, y: x & y, entry_08_protections))
        entry_08_logic.append(dataframe['rsi'] < self.entry_rsi_8.value)
        entry_08_logic.append(dataframe['volume'] > dataframe['volume'].shift(1) * self.entry_volume_8.value)
        entry_08_logic.append(dataframe['close'] > dataframe['open'])
        entry_08_logic.append(dataframe['close'] - dataframe['low'] > (dataframe['close'] - dataframe['open']) * self.entry_tail_diff_8.value)
        entry_08_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_08_trigger'] = reduce(lambda x, y: x & y, entry_08_logic)
        if self.entry_condition_8_enable.value:
            conditions.append(dataframe['entry_08_trigger'])
        # Protections
        entry_09_protections = [True]
        if self.entry_09_protection__ema_fast.value:
            entry_09_protections.append(dataframe[f'ema_{self.entry_09_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_09_protection__ema_slow.value:
            entry_09_protections.append(dataframe[f'ema_{self.entry_09_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_09_protection__close_above_ema_fast.value:
            entry_09_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_09_protection__close_above_ema_fast_len.value}'])
        if self.entry_09_protection__close_above_ema_slow.value:
            entry_09_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_09_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_09_protection__sma200_rising.value:
            entry_09_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_09_protection__sma200_rising_val.value)))
        if self.entry_09_protection__sma200_1h_rising.value:
            entry_09_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_09_protection__sma200_1h_rising_val.value)))
        if self.entry_09_protection__safe_dips.value:
            entry_09_protections.append(dataframe[f'safe_dips_{self.entry_09_protection__safe_dips_type.value}'])
        if self.entry_09_protection__safe_pump.value:
            entry_09_protections.append(dataframe[f'safe_pump_{self.entry_09_protection__safe_pump_period.value}_{self.entry_09_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        entry_09_protections.append(dataframe['ema_50'] > dataframe['ema_200'])
        # Logic
        entry_09_logic = []
        entry_09_logic.append(reduce(lambda x, y: x & y, entry_09_protections))
        #entry_09_logic.append(dataframe['volume_mean_4'] * self.entry_volume_9.value > dataframe['volume'])
        entry_09_logic.append(dataframe['close'] < dataframe['ema_20'] * self.entry_ma_offset_9.value)
        entry_09_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_9.value)
        entry_09_logic.append(dataframe['rsi_1h'] > self.entry_rsi_1h_min_9.value)
        entry_09_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_max_9.value)
        entry_09_logic.append(dataframe['mfi'] < self.entry_mfi_9.value)
        entry_09_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_09_trigger'] = reduce(lambda x, y: x & y, entry_09_logic)
        if self.entry_condition_9_enable.value:
            conditions.append(dataframe['entry_09_trigger'])
        # Protections
        entry_10_protections = [True]
        if self.entry_10_protection__ema_fast.value:
            entry_10_protections.append(dataframe[f'ema_{self.entry_10_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_10_protection__ema_slow.value:
            entry_10_protections.append(dataframe[f'ema_{self.entry_10_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_10_protection__close_above_ema_fast.value:
            entry_10_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_10_protection__close_above_ema_fast_len.value}'])
        if self.entry_10_protection__close_above_ema_slow.value:
            entry_10_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_10_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_10_protection__sma200_rising.value:
            entry_10_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_10_protection__sma200_rising_val.value)))
        if self.entry_10_protection__sma200_1h_rising.value:
            entry_10_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_10_protection__sma200_1h_rising_val.value)))
        if self.entry_10_protection__safe_dips.value:
            entry_10_protections.append(dataframe[f'safe_dips_{self.entry_10_protection__safe_dips_type.value}'])
        if self.entry_10_protection__safe_pump.value:
            entry_10_protections.append(dataframe[f'safe_pump_{self.entry_10_protection__safe_pump_period.value}_{self.entry_10_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        entry_10_protections.append(dataframe['ema_50_1h'] > dataframe['ema_100_1h'])
        # Logic
        entry_10_logic = []
        entry_10_logic.append(reduce(lambda x, y: x & y, entry_10_protections))
        entry_10_logic.append(dataframe['close'] < dataframe['sma_30'] * self.entry_ma_offset_10.value)
        entry_10_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_10.value)
        entry_10_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_10.value)
        entry_10_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_10_trigger'] = reduce(lambda x, y: x & y, entry_10_logic)
        if self.entry_condition_10_enable.value:
            conditions.append(dataframe['entry_10_trigger'])
        # Protections
        entry_11_protections = [True]
        if self.entry_11_protection__ema_fast.value:
            entry_11_protections.append(dataframe[f'ema_{self.entry_11_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_11_protection__ema_slow.value:
            entry_11_protections.append(dataframe[f'ema_{self.entry_11_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_11_protection__close_above_ema_fast.value:
            entry_11_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_11_protection__close_above_ema_fast_len.value}'])
        if self.entry_11_protection__close_above_ema_slow.value:
            entry_11_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_11_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_11_protection__sma200_rising.value:
            entry_11_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_11_protection__sma200_rising_val.value)))
        if self.entry_11_protection__sma200_1h_rising.value:
            entry_11_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_11_protection__sma200_1h_rising_val.value)))
        if self.entry_11_protection__safe_dips.value:
            entry_11_protections.append(dataframe[f'safe_dips_{self.entry_11_protection__safe_dips_type.value}'])
        if self.entry_11_protection__safe_pump.value:
            entry_11_protections.append(dataframe[f'safe_pump_{self.entry_11_protection__safe_pump_period.value}_{self.entry_11_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        entry_11_protections.append(dataframe['ema_50_1h'] > dataframe['ema_100_1h'])
        entry_11_protections.append(dataframe['safe_pump_36_50_1h'])
        entry_11_protections.append(dataframe['safe_pump_48_100_1h'])
        # Logic
        entry_11_logic = []
        entry_11_logic.append(reduce(lambda x, y: x & y, entry_11_protections))
        entry_11_logic.append((dataframe['close'] - dataframe['open'].rolling(36).min()) / dataframe['open'].rolling(36).min() > self.entry_min_inc_11.value)
        entry_11_logic.append(dataframe['close'] < dataframe['sma_30'] * self.entry_ma_offset_11.value)
        entry_11_logic.append(dataframe['rsi_1h'] > self.entry_rsi_1h_min_11.value)
        entry_11_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_max_11.value)
        entry_11_logic.append(dataframe['rsi'] < self.entry_rsi_11.value)
        entry_11_logic.append(dataframe['mfi'] < self.entry_mfi_11.value)
        entry_11_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_11_trigger'] = reduce(lambda x, y: x & y, entry_11_logic)
        if self.entry_condition_11_enable.value:
            conditions.append(dataframe['entry_11_trigger'])
        # Protections
        entry_12_protections = [True]
        if self.entry_12_protection__ema_fast.value:
            entry_12_protections.append(dataframe[f'ema_{self.entry_12_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_12_protection__ema_slow.value:
            entry_12_protections.append(dataframe[f'ema_{self.entry_12_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_12_protection__close_above_ema_fast.value:
            entry_12_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_12_protection__close_above_ema_fast_len.value}'])
        if self.entry_12_protection__close_above_ema_slow.value:
            entry_12_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_12_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_12_protection__sma200_rising.value:
            entry_12_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_12_protection__sma200_rising_val.value)))
        if self.entry_12_protection__sma200_1h_rising.value:
            entry_12_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_12_protection__sma200_1h_rising_val.value)))
        if self.entry_12_protection__safe_dips.value:
            entry_12_protections.append(dataframe[f'safe_dips_{self.entry_12_protection__safe_dips_type.value}'])
        if self.entry_12_protection__safe_pump.value:
            entry_12_protections.append(dataframe[f'safe_pump_{self.entry_12_protection__safe_pump_period.value}_{self.entry_12_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_12_logic = []
        entry_12_logic.append(reduce(lambda x, y: x & y, entry_12_protections))
        #entry_12_logic.append((dataframe['volume_mean_4'] * self.entry_volume_12.value) > dataframe['volume'])
        entry_12_logic.append(dataframe['close'] < dataframe['sma_30'] * self.entry_ma_offset_12.value)
        entry_12_logic.append(dataframe['ewo'] > self.entry_ewo_12.value)
        entry_12_logic.append(dataframe['rsi'] < self.entry_rsi_12.value)
        entry_12_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_12_trigger'] = reduce(lambda x, y: x & y, entry_12_logic)
        if self.entry_condition_12_enable.value:
            conditions.append(dataframe['entry_12_trigger'])
        # Protections
        entry_13_protections = [True]
        if self.entry_13_protection__ema_fast.value:
            entry_13_protections.append(dataframe[f'ema_{self.entry_13_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_13_protection__ema_slow.value:
            entry_13_protections.append(dataframe[f'ema_{self.entry_13_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_13_protection__close_above_ema_fast.value:
            entry_13_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_13_protection__close_above_ema_fast_len.value}'])
        if self.entry_13_protection__close_above_ema_slow.value:
            entry_13_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_13_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_13_protection__sma200_rising.value:
            entry_13_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_13_protection__sma200_rising_val.value)))
        if self.entry_13_protection__sma200_1h_rising.value:
            entry_13_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_13_protection__sma200_1h_rising_val.value)))
        if self.entry_13_protection__safe_dips.value:
            entry_13_protections.append(dataframe[f'safe_dips_{self.entry_13_protection__safe_dips_type.value}'])
        if self.entry_13_protection__safe_pump.value:
            entry_13_protections.append(dataframe[f'safe_pump_{self.entry_13_protection__safe_pump_period.value}_{self.entry_13_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        entry_13_protections.append(dataframe['ema_50_1h'] > dataframe['ema_100_1h'])
        #entry_13_protections.append(dataframe['safe_pump_36_loose_1h'])
        # Logic
        entry_13_logic = []
        entry_13_logic.append(reduce(lambda x, y: x & y, entry_13_protections))
        #entry_13_logic.append((dataframe['volume_mean_4'] * self.entry_volume_13.value) > dataframe['volume'])
        entry_13_logic.append(dataframe['close'] < dataframe['sma_30'] * self.entry_ma_offset_13.value)
        entry_13_logic.append(dataframe['ewo'] < self.entry_ewo_13.value)
        entry_13_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_13_trigger'] = reduce(lambda x, y: x & y, entry_13_logic)
        if self.entry_condition_13_enable.value:
            conditions.append(dataframe['entry_13_trigger'])
        # Protections
        entry_14_protections = [True]
        if self.entry_14_protection__ema_fast.value:
            entry_14_protections.append(dataframe[f'ema_{self.entry_14_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_14_protection__ema_slow.value:
            entry_14_protections.append(dataframe[f'ema_{self.entry_14_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_14_protection__close_above_ema_fast.value:
            entry_14_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_14_protection__close_above_ema_fast_len.value}'])
        if self.entry_14_protection__close_above_ema_slow.value:
            entry_14_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_14_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_14_protection__sma200_rising.value:
            entry_14_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_14_protection__sma200_rising_val.value)))
        if self.entry_14_protection__sma200_1h_rising.value:
            entry_14_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_14_protection__sma200_1h_rising_val.value)))
        if self.entry_14_protection__safe_dips.value:
            entry_14_protections.append(dataframe[f'safe_dips_{self.entry_14_protection__safe_dips_type.value}'])
        if self.entry_14_protection__safe_pump.value:
            entry_14_protections.append(dataframe[f'safe_pump_{self.entry_14_protection__safe_pump_period.value}_{self.entry_14_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_14_logic = []
        entry_14_logic.append(reduce(lambda x, y: x & y, entry_14_protections))
        #entry_14_logic.append(dataframe['volume_mean_4'] * self.entry_volume_14.value > dataframe['volume'])
        entry_14_logic.append(dataframe['ema_26'] > dataframe['ema_12'])
        entry_14_logic.append(dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_open_mult_14.value)
        entry_14_logic.append(dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100)
        entry_14_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_14.value)
        entry_14_logic.append(dataframe['close'] < dataframe['ema_20'] * self.entry_ma_offset_14.value)
        entry_14_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_14_trigger'] = reduce(lambda x, y: x & y, entry_14_logic)
        if self.entry_condition_14_enable.value:
            conditions.append(dataframe['entry_14_trigger'])
        # Protections
        entry_15_protections = [True]
        if self.entry_15_protection__ema_fast.value:
            entry_15_protections.append(dataframe[f'ema_{self.entry_15_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_15_protection__ema_slow.value:
            entry_15_protections.append(dataframe[f'ema_{self.entry_15_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_15_protection__close_above_ema_fast.value:
            entry_15_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_15_protection__close_above_ema_fast_len.value}'])
        if self.entry_15_protection__close_above_ema_slow.value:
            entry_15_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_15_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_15_protection__sma200_rising.value:
            entry_15_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_15_protection__sma200_rising_val.value)))
        if self.entry_15_protection__sma200_1h_rising.value:
            entry_15_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_15_protection__sma200_1h_rising_val.value)))
        if self.entry_15_protection__safe_dips.value:
            entry_15_protections.append(dataframe[f'safe_dips_{self.entry_15_protection__safe_dips_type.value}'])
        if self.entry_15_protection__safe_pump.value:
            entry_15_protections.append(dataframe[f'safe_pump_{self.entry_15_protection__safe_pump_period.value}_{self.entry_15_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        entry_15_protections.append(dataframe['close'] > dataframe['ema_200_1h'] * self.entry_ema_rel_15.value)
        # Logic
        entry_15_logic = []
        entry_15_logic.append(reduce(lambda x, y: x & y, entry_15_protections))
        entry_15_logic.append(dataframe['ema_26'] > dataframe['ema_12'])
        entry_15_logic.append(dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_open_mult_15.value)
        entry_15_logic.append(dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100)
        entry_15_logic.append(dataframe['rsi'] < self.entry_rsi_15.value)
        entry_15_logic.append(dataframe['close'] < dataframe['ema_20'] * self.entry_ma_offset_15.value)
        entry_15_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_15_trigger'] = reduce(lambda x, y: x & y, entry_15_logic)
        if self.entry_condition_15_enable.value:
            conditions.append(dataframe['entry_15_trigger'])
        # Protections
        entry_16_protections = [True]
        if self.entry_16_protection__ema_fast.value:
            entry_16_protections.append(dataframe[f'ema_{self.entry_16_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_16_protection__ema_slow.value:
            entry_16_protections.append(dataframe[f'ema_{self.entry_16_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_16_protection__close_above_ema_fast.value:
            entry_16_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_16_protection__close_above_ema_fast_len.value}'])
        if self.entry_16_protection__close_above_ema_slow.value:
            entry_16_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_16_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_16_protection__sma200_rising.value:
            entry_16_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_16_protection__sma200_rising_val.value)))
        if self.entry_16_protection__sma200_1h_rising.value:
            entry_16_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_16_protection__sma200_1h_rising_val.value)))
        if self.entry_16_protection__safe_dips.value:
            entry_16_protections.append(dataframe[f'safe_dips_{self.entry_16_protection__safe_dips_type.value}'])
        if self.entry_16_protection__safe_pump.value:
            entry_16_protections.append(dataframe[f'safe_pump_{self.entry_16_protection__safe_pump_period.value}_{self.entry_16_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_16_logic = []
        entry_16_logic.append(reduce(lambda x, y: x & y, entry_16_protections))
        #entry_16_logic.append((dataframe['volume_mean_4'] * self.entry_volume_16.value) > dataframe['volume'])
        entry_16_logic.append(dataframe['close'] < dataframe['ema_20'] * self.entry_ma_offset_16.value)
        entry_16_logic.append(dataframe['ewo'] > self.entry_ewo_16.value)
        entry_16_logic.append(dataframe['rsi'] < self.entry_rsi_16.value)
        entry_16_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_16_trigger'] = reduce(lambda x, y: x & y, entry_16_logic)
        if self.entry_condition_16_enable.value:
            conditions.append(dataframe['entry_16_trigger'])
        # Protections
        entry_17_protections = [True]
        if self.entry_17_protection__ema_fast.value:
            entry_17_protections.append(dataframe[f'ema_{self.entry_17_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_17_protection__ema_slow.value:
            entry_17_protections.append(dataframe[f'ema_{self.entry_17_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_17_protection__close_above_ema_fast.value:
            entry_17_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_17_protection__close_above_ema_fast_len.value}'])
        if self.entry_17_protection__close_above_ema_slow.value:
            entry_17_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_17_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_17_protection__sma200_rising.value:
            entry_17_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_17_protection__sma200_rising_val.value)))
        if self.entry_17_protection__sma200_1h_rising.value:
            entry_17_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_17_protection__sma200_1h_rising_val.value)))
        if self.entry_17_protection__safe_dips.value:
            entry_17_protections.append(dataframe[f'safe_dips_{self.entry_17_protection__safe_dips_type.value}'])
        if self.entry_17_protection__safe_pump.value:
            entry_17_protections.append(dataframe[f'safe_pump_{self.entry_17_protection__safe_pump_period.value}_{self.entry_17_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_17_logic = []
        entry_17_logic.append(reduce(lambda x, y: x & y, entry_17_protections))
        entry_17_logic.append(dataframe['close'] < dataframe['ema_20'] * self.entry_ma_offset_17.value)
        entry_17_logic.append(dataframe['ewo'] < self.entry_ewo_17.value)
        entry_17_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_17_trigger'] = reduce(lambda x, y: x & y, entry_17_logic)
        if self.entry_condition_17_enable.value:
            conditions.append(dataframe['entry_17_trigger'])
        # Protections
        entry_18_protections = [True]
        if self.entry_18_protection__ema_fast.value:
            entry_18_protections.append(dataframe[f'ema_{self.entry_18_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_18_protection__ema_slow.value:
            entry_18_protections.append(dataframe[f'ema_{self.entry_18_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_18_protection__close_above_ema_fast.value:
            entry_18_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_18_protection__close_above_ema_fast_len.value}'])
        if self.entry_18_protection__close_above_ema_slow.value:
            entry_18_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_18_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_18_protection__sma200_rising.value:
            entry_18_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_18_protection__sma200_rising_val.value)))
        if self.entry_18_protection__sma200_1h_rising.value:
            entry_18_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_18_protection__sma200_1h_rising_val.value)))
        if self.entry_18_protection__safe_dips.value:
            entry_18_protections.append(dataframe[f'safe_dips_{self.entry_18_protection__safe_dips_type.value}'])
        if self.entry_18_protection__safe_pump.value:
            entry_18_protections.append(dataframe[f'safe_pump_{self.entry_18_protection__safe_pump_period.value}_{self.entry_18_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        #entry_18_protections.append(dataframe['ema_100'] > dataframe['ema_200'])
        entry_18_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(20))
        entry_18_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(36))
        # Logic
        entry_18_logic = []
        entry_18_logic.append(reduce(lambda x, y: x & y, entry_18_protections))
        #entry_18_logic.append((dataframe['volume_mean_4'] * self.entry_volume_18.value) > dataframe['volume'])
        entry_18_logic.append(dataframe['rsi'] < self.entry_rsi_18.value)
        entry_18_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_18.value)
        entry_18_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_18_trigger'] = reduce(lambda x, y: x & y, entry_18_logic)
        if self.entry_condition_18_enable.value:
            conditions.append(dataframe['entry_18_trigger'])
        # Protections
        entry_19_protections = [True]
        if self.entry_19_protection__ema_fast.value:
            entry_19_protections.append(dataframe[f'ema_{self.entry_19_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_19_protection__ema_slow.value:
            entry_19_protections.append(dataframe[f'ema_{self.entry_19_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_19_protection__close_above_ema_fast.value:
            entry_19_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_19_protection__close_above_ema_fast_len.value}'])
        if self.entry_19_protection__close_above_ema_slow.value:
            entry_19_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_19_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_19_protection__sma200_rising.value:
            entry_19_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_19_protection__sma200_rising_val.value)))
        if self.entry_19_protection__sma200_1h_rising.value:
            entry_19_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_19_protection__sma200_1h_rising_val.value)))
        if self.entry_19_protection__safe_dips.value:
            entry_19_protections.append(dataframe[f'safe_dips_{self.entry_19_protection__safe_dips_type.value}'])
        if self.entry_19_protection__safe_pump.value:
            entry_19_protections.append(dataframe[f'safe_pump_{self.entry_19_protection__safe_pump_period.value}_{self.entry_19_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        entry_19_protections.append(dataframe['ema_50_1h'] > dataframe['ema_200_1h'])
        # Logic
        entry_19_logic = []
        entry_19_logic.append(reduce(lambda x, y: x & y, entry_19_protections))
        entry_19_logic.append(dataframe['close'].shift(1) > dataframe['ema_100_1h'])
        entry_19_logic.append(dataframe['low'] < dataframe['ema_100_1h'])
        entry_19_logic.append(dataframe['close'] > dataframe['ema_100_1h'])
        entry_19_logic.append(dataframe['rsi_1h'] > self.entry_rsi_1h_min_19.value)
        entry_19_logic.append(dataframe['chop'] < self.entry_chop_min_19.value)
        entry_19_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_19_trigger'] = reduce(lambda x, y: x & y, entry_19_logic)
        if self.entry_condition_19_enable.value:
            conditions.append(dataframe['entry_19_trigger'])
        # Protections
        entry_20_protections = [True]
        if self.entry_20_protection__ema_fast.value:
            entry_20_protections.append(dataframe[f'ema_{self.entry_20_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_20_protection__ema_slow.value:
            entry_20_protections.append(dataframe[f'ema_{self.entry_20_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_20_protection__close_above_ema_fast.value:
            entry_20_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_20_protection__close_above_ema_fast_len.value}'])
        if self.entry_20_protection__close_above_ema_slow.value:
            entry_20_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_20_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_20_protection__sma200_rising.value:
            entry_20_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_20_protection__sma200_rising_val.value)))
        if self.entry_20_protection__sma200_1h_rising.value:
            entry_20_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_20_protection__sma200_1h_rising_val.value)))
        if self.entry_20_protection__safe_dips.value:
            entry_20_protections.append(dataframe[f'safe_dips_{self.entry_20_protection__safe_dips_type.value}'])
        if self.entry_20_protection__safe_pump.value:
            entry_20_protections.append(dataframe[f'safe_pump_{self.entry_20_protection__safe_pump_period.value}_{self.entry_20_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_20_logic = []
        entry_20_logic.append(reduce(lambda x, y: x & y, entry_20_protections))
        #entry_20_logic.append((dataframe['volume_mean_4'] * self.entry_volume_20.value) > dataframe['volume'])
        entry_20_logic.append(dataframe['rsi'] < self.entry_rsi_20.value)
        entry_20_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_20.value)
        entry_20_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_20_trigger'] = reduce(lambda x, y: x & y, entry_20_logic)
        if self.entry_condition_20_enable.value:
            conditions.append(dataframe['entry_20_trigger'])
        # Protections
        entry_21_protections = [True]
        if self.entry_21_protection__ema_fast.value:
            entry_21_protections.append(dataframe[f'ema_{self.entry_21_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_21_protection__ema_slow.value:
            entry_21_protections.append(dataframe[f'ema_{self.entry_21_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_21_protection__close_above_ema_fast.value:
            entry_21_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_21_protection__close_above_ema_fast_len.value}'])
        if self.entry_21_protection__close_above_ema_slow.value:
            entry_21_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_21_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_21_protection__sma200_rising.value:
            entry_21_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_21_protection__sma200_rising_val.value)))
        if self.entry_21_protection__sma200_1h_rising.value:
            entry_21_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_21_protection__sma200_1h_rising_val.value)))
        if self.entry_21_protection__safe_dips.value:
            entry_21_protections.append(dataframe[f'safe_dips_{self.entry_21_protection__safe_dips_type.value}'])
        if self.entry_21_protection__safe_pump.value:
            entry_21_protections.append(dataframe[f'safe_pump_{self.entry_21_protection__safe_pump_period.value}_{self.entry_21_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_21_logic = []
        entry_21_logic.append(reduce(lambda x, y: x & y, entry_21_protections))
        #entry_21_logic.append((dataframe['volume_mean_4'] * self.entry_volume_21.value) > dataframe['volume'])
        entry_21_logic.append(dataframe['rsi'] < self.entry_rsi_21.value)
        entry_21_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_21.value)
        entry_21_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_21_trigger'] = reduce(lambda x, y: x & y, entry_21_logic)
        if self.entry_condition_21_enable.value:
            conditions.append(dataframe['entry_21_trigger'])
        # Protections
        entry_22_protections = [True]
        if self.entry_22_protection__ema_fast.value:
            entry_22_protections.append(dataframe[f'ema_{self.entry_22_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_22_protection__ema_slow.value:
            entry_22_protections.append(dataframe[f'ema_{self.entry_22_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_22_protection__close_above_ema_fast.value:
            entry_22_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_22_protection__close_above_ema_fast_len.value}'])
        if self.entry_22_protection__close_above_ema_slow.value:
            entry_22_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_22_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_22_protection__sma200_rising.value:
            entry_22_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_22_protection__sma200_rising_val.value)))
        if self.entry_22_protection__sma200_1h_rising.value:
            entry_22_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_22_protection__sma200_1h_rising_val.value)))
        if self.entry_22_protection__safe_dips.value:
            entry_22_protections.append(dataframe[f'safe_dips_{self.entry_22_protection__safe_dips_type.value}'])
        if self.entry_22_protection__safe_pump.value:
            entry_22_protections.append(dataframe[f'safe_pump_{self.entry_22_protection__safe_pump_period.value}_{self.entry_22_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        entry_22_protections.append(dataframe['ema_100_1h'] > dataframe['ema_100_1h'].shift(12))
        entry_22_protections.append(dataframe['ema_200_1h'] > dataframe['ema_200_1h'].shift(36))
        # Logic
        entry_22_logic = []
        entry_22_logic.append(reduce(lambda x, y: x & y, entry_22_protections))
        entry_22_logic.append(dataframe['volume_mean_4'] * self.entry_volume_22.value > dataframe['volume'])
        entry_22_logic.append(dataframe['close'] < dataframe['sma_30'] * self.entry_ma_offset_22.value)
        entry_22_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_22.value)
        entry_22_logic.append(dataframe['ewo'] > self.entry_ewo_22.value)
        entry_22_logic.append(dataframe['rsi'] < self.entry_rsi_22.value)
        entry_22_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_22_trigger'] = reduce(lambda x, y: x & y, entry_22_logic)
        if self.entry_condition_22_enable.value:
            conditions.append(dataframe['entry_22_trigger'])
        # Protections
        entry_23_protections = [True]
        if self.entry_23_protection__ema_fast.value:
            entry_23_protections.append(dataframe[f'ema_{self.entry_23_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_23_protection__ema_slow.value:
            entry_23_protections.append(dataframe[f'ema_{self.entry_23_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_23_protection__close_above_ema_fast.value:
            entry_23_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_23_protection__close_above_ema_fast_len.value}'])
        if self.entry_23_protection__close_above_ema_slow.value:
            entry_23_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_23_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_23_protection__sma200_rising.value:
            entry_23_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_23_protection__sma200_rising_val.value)))
        if self.entry_23_protection__sma200_1h_rising.value:
            entry_23_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_23_protection__sma200_1h_rising_val.value)))
        if self.entry_23_protection__safe_dips.value:
            entry_23_protections.append(dataframe[f'safe_dips_{self.entry_23_protection__safe_dips_type.value}'])
        if self.entry_23_protection__safe_pump.value:
            entry_23_protections.append(dataframe[f'safe_pump_{self.entry_23_protection__safe_pump_period.value}_{self.entry_23_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_23_logic = []
        entry_23_logic.append(reduce(lambda x, y: x & y, entry_23_protections))
        entry_23_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_23.value)
        entry_23_logic.append(dataframe['ewo'] > self.entry_ewo_23.value)
        entry_23_logic.append(dataframe['rsi'] < self.entry_rsi_23.value)
        entry_23_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_23.value)
        entry_23_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_23_trigger'] = reduce(lambda x, y: x & y, entry_23_logic)
        if self.entry_condition_23_enable.value:
            conditions.append(dataframe['entry_23_trigger'])
        # Protections
        entry_24_protections = [True]
        if self.entry_24_protection__ema_fast.value:
            entry_24_protections.append(dataframe[f'ema_{self.entry_24_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_24_protection__ema_slow.value:
            entry_24_protections.append(dataframe[f'ema_{self.entry_24_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_24_protection__close_above_ema_fast.value:
            entry_24_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_24_protection__close_above_ema_fast_len.value}'])
        if self.entry_24_protection__close_above_ema_slow.value:
            entry_24_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_24_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_24_protection__sma200_rising.value:
            entry_24_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_24_protection__sma200_rising_val.value)))
        if self.entry_24_protection__sma200_1h_rising.value:
            entry_24_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_24_protection__sma200_1h_rising_val.value)))
        if self.entry_24_protection__safe_dips.value:
            entry_24_protections.append(dataframe[f'safe_dips_{self.entry_24_protection__safe_dips_type.value}'])
        if self.entry_24_protection__safe_pump.value:
            entry_24_protections.append(dataframe[f'safe_pump_{self.entry_24_protection__safe_pump_period.value}_{self.entry_24_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_24_logic = []
        entry_24_logic.append(reduce(lambda x, y: x & y, entry_24_protections))
        entry_24_logic.append(dataframe['ema_12_1h'].shift(12) < dataframe['ema_35_1h'].shift(12))
        entry_24_logic.append(dataframe['ema_12_1h'].shift(12) < dataframe['ema_35_1h'].shift(12))
        entry_24_logic.append(dataframe['ema_12_1h'] > dataframe['ema_35_1h'])
        entry_24_logic.append(dataframe['cmf_1h'].shift(12) < 0)
        entry_24_logic.append(dataframe['cmf_1h'] > 0)
        entry_24_logic.append(dataframe['rsi'] < self.entry_24_rsi_max.value)
        entry_24_logic.append(dataframe['rsi_1h'] > self.entry_24_rsi_1h_min.value)
        entry_24_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_24_trigger'] = reduce(lambda x, y: x & y, entry_24_logic)
        if self.entry_condition_24_enable.value:
            conditions.append(dataframe['entry_24_trigger'])
        # Protections
        entry_26_protections = [True]
        if self.entry_26_protection__ema_fast.value:
            entry_26_protections.append(dataframe[f'ema_{self.entry_26_protection__ema_fast_len.value}'] > dataframe['ema_200'])
        if self.entry_26_protection__ema_slow.value:
            entry_26_protections.append(dataframe[f'ema_{self.entry_26_protection__ema_slow_len.value}_1h'] > dataframe['ema_200_1h'])
        if self.entry_26_protection__close_above_ema_fast.value:
            entry_26_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_26_protection__close_above_ema_fast_len.value}'])
        if self.entry_26_protection__close_above_ema_slow.value:
            entry_26_protections.append(dataframe['close'] > dataframe[f'ema_{self.entry_26_protection__close_above_ema_slow_len.value}_1h'])
        if self.entry_26_protection__sma200_rising.value:
            entry_26_protections.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(self.entry_26_protection__sma200_rising_val.value)))
        if self.entry_26_protection__sma200_1h_rising.value:
            entry_26_protections.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(self.entry_26_protection__sma200_1h_rising_val.value)))
        if self.entry_26_protection__safe_dips.value:
            entry_26_protections.append(dataframe[f'safe_dips_{self.entry_26_protection__safe_dips_type.value}'])
        if self.entry_26_protection__safe_pump.value:
            entry_26_protections.append(dataframe[f'safe_pump_{self.entry_26_protection__safe_pump_period.value}_{self.entry_26_protection__safe_pump_type.value}_1h'])
        # Non-Standard protections (add below)
        # Logic
        entry_26_logic = []
        entry_26_logic.append(reduce(lambda x, y: x & y, entry_26_protections))
        entry_26_logic.append(dataframe['close'] < dataframe['zema'] * self.entry_26_zema_low_offset.value)
        entry_26_logic.append(dataframe['volume'] > 0)
        # Populate
        dataframe.loc[:, 'entry_26_trigger'] = reduce(lambda x, y: x & y, entry_26_logic)
        if self.entry_condition_26_enable.value:
            conditions.append(dataframe['entry_26_trigger'])
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append(self.exit_condition_1_enable.value & (dataframe['rsi'] > self.exit_rsi_bb_1.value) & (dataframe['close'] > dataframe['bb20_2_upp']) & (dataframe['close'].shift(1) > dataframe['bb20_2_upp'].shift(1)) & (dataframe['close'].shift(2) > dataframe['bb20_2_upp'].shift(2)) & (dataframe['close'].shift(3) > dataframe['bb20_2_upp'].shift(3)) & (dataframe['close'].shift(4) > dataframe['bb20_2_upp'].shift(4)) & (dataframe['close'].shift(5) > dataframe['bb20_2_upp'].shift(5)) & (dataframe['volume'] > 0))
        conditions.append(self.exit_condition_2_enable.value & (dataframe['rsi'] > self.exit_rsi_bb_2.value) & (dataframe['close'] > dataframe['bb20_2_upp']) & (dataframe['close'].shift(1) > dataframe['bb20_2_upp'].shift(1)) & (dataframe['close'].shift(2) > dataframe['bb20_2_upp'].shift(2)) & (dataframe['volume'] > 0))
        conditions.append(self.exit_condition_3_enable.value & (dataframe['rsi'] > self.exit_rsi_main_3.value) & (dataframe['volume'] > 0))
        conditions.append(self.exit_condition_4_enable.value & (dataframe['rsi'] > self.exit_dual_rsi_rsi_4.value) & (dataframe['rsi_1h'] > self.exit_dual_rsi_rsi_1h_4.value) & (dataframe['volume'] > 0))
        conditions.append(self.exit_condition_6_enable.value & (dataframe['close'] < dataframe['ema_200']) & (dataframe['close'] > dataframe['ema_50']) & (dataframe['rsi'] > self.exit_rsi_under_6.value) & (dataframe['volume'] > 0))
        conditions.append(self.exit_condition_7_enable.value & (dataframe['rsi_1h'] > self.exit_rsi_1h_7.value) & qtpylib.crossed_below(dataframe['ema_12'], dataframe['ema_26']) & (dataframe['volume'] > 0))
        conditions.append(self.exit_condition_8_enable.value & (dataframe['close'] > dataframe['bb20_2_upp_1h'] * self.exit_bb_relative_8.value) & (dataframe['volume'] > 0))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'exit_long'] = 1
        return dataframe
# Elliot Wave Oscillator

def EWO(dataframe, sma1_length=5, sma2_length=35):
    df = dataframe.copy()
    sma1 = ta.EMA(df, timeperiod=sma1_length)
    sma2 = ta.EMA(df, timeperiod=sma2_length)
    smadif = (sma1 - sma2) / df['close'] * 100
    return smadif
# Chaikin Money Flow

def chaikin_money_flow(dataframe, n=20, fillna=False):
    """Chaikin Money Flow (CMF)
    It measures the amount of Money Flow Volume over a specific period.
    http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:chaikin_money_flow_cmf
    Args:
        dataframe(pandas.Dataframe): dataframe containing ohlcv
        n(int): n period.
        fillna(bool): if True, fill nan values.
    Returns:
        pandas.Series: New feature generated.
    """
    df = dataframe.copy()
    mfv = (df['close'] - df['low'] - (df['high'] - df['close'])) / (df['high'] - df['low'])
    mfv = mfv.fillna(0.0)  # float division by zero
    mfv *= df['volume']
    cmf = mfv.rolling(n, min_periods=0).sum() / df['volume'].rolling(n, min_periods=0).sum()
    if fillna:
        cmf = cmf.replace([np.inf, -np.inf], np.nan).fillna(0)
    return Series(cmf, name='cmf')