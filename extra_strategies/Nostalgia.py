import logging
import pathlib
import rapidjson
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
from freqtrade.misc import json_load
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import merge_informative_pair, timeframe_to_minutes
from freqtrade.strategy import DecimalParameter, IntParameter, CategoricalParameter
from pandas import DataFrame, Series
from functools import reduce
import math
from freqtrade.persistence import Trade
from datetime import datetime, timedelta
from technical.util import resample_to_interval, resampled_merge
from technical.indicators import zema
log = logging.getLogger(__name__)

class Nostalgia(IStrategy):
    INTERFACE_VERSION = 3
    # # ROI table:
    minimal_roi = {'0': 10}
    stoploss = -0.99
    # Trailing stoploss (not used)
    trailing_stop = False
    trailing_only_offset_is_reached = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.03
    use_custom_stoploss = False
    # Optimal timeframe for the strategy.
    timeframe = '5m'
    res_timeframe = 'none'
    info_timeframe = '1h'
    has_BTC_base_tf = False
    has_BTC_info_tf = True
    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True
    # These values can be overridden in the "ask_strategy" section in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True
    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 480
    # Optional order type mapping.
    order_types = {'entry': 'limit', 'exit': 'limit', 'trailing_stop_loss': 'limit', 'stoploss': 'limit', 'stoploss_on_exchange': False}
    #############################################################
    #############
    # Enable/Disable conditions
    #############
    entry_params = {'entry_condition_1_enable': True, 'entry_condition_2_enable': True, 'entry_condition_3_enable': True, 'entry_condition_4_enable': True, 'entry_condition_5_enable': True, 'entry_condition_6_enable': True, 'entry_condition_7_enable': True, 'entry_condition_8_enable': True, 'entry_condition_9_enable': True, 'entry_condition_10_enable': True, 'entry_condition_11_enable': True, 'entry_condition_12_enable': True, 'entry_condition_13_enable': True, 'entry_condition_14_enable': True, 'entry_condition_15_enable': True, 'entry_condition_16_enable': True, 'entry_condition_17_enable': True, 'entry_condition_18_enable': True, 'entry_condition_19_enable': True, 'entry_condition_20_enable': True, 'entry_condition_21_enable': True, 'entry_condition_22_enable': True, 'entry_condition_23_enable': True, 'entry_condition_24_enable': True, 'entry_condition_25_enable': True, 'entry_condition_26_enable': True, 'entry_condition_27_enable': True, 'entry_condition_28_enable': True, 'entry_condition_29_enable': True, 'entry_condition_30_enable': True, 'entry_condition_31_enable': True}
    #############
    # Enable/Disable conditions
    #############
    exit_params = {'exit_condition_1_enable': True, 'exit_condition_2_enable': True, 'exit_condition_3_enable': True, 'exit_condition_4_enable': True, 'exit_condition_5_enable': True, 'exit_condition_6_enable': True, 'exit_condition_7_enable': True, 'exit_condition_8_enable': True}
    #############################################################
    entry_protection_params = {1: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='26', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='28', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='80', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='70', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 2: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='20', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 3: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 4: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='20', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='110', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='48', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 5: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='20', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 6: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='20', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 7: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='12', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 8: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='12', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='120', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 9: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 10: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='24', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 11: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 12: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='24', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 13: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='24', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 14: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='30', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='70', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 15: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 16: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='50', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 17: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='120', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 18: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='44', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='72', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='60', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 19: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='36', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 20: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 21: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='90', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 22: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='110', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 23: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 24: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='200', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='30', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='36', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='20', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 25: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='20', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='20', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='24', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 26: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='30', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='100', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='48', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 27: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='30', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)}, 28: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='30', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='110', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)}, 29: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='30', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='110', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 30: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='200', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='30', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='50', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='110', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='36', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}, 31: {'enable': CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True), 'ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_fast_len': CategoricalParameter(['26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'ema_slow_len': CategoricalParameter(['26', '50', '100', '200'], default='100', space='entry', optimize=False, load=True), 'close_above_ema_fast': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_fast_len': CategoricalParameter(['12', '20', '26', '50', '100', '200'], default='50', space='entry', optimize=False, load=True), 'close_above_ema_slow': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'close_above_ema_slow_len': CategoricalParameter(['15', '50', '200'], default='100', space='entry', optimize=False, load=True), 'sma200_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='30', space='entry', optimize=False, load=True), 'sma200_1h_rising': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'sma200_1h_rising_val': CategoricalParameter(['20', '30', '36', '44', '50'], default='50', space='entry', optimize=False, load=True), 'safe_dips': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_dips_type': CategoricalParameter(['10', '50', '100'], default='110', space='entry', optimize=False, load=True), 'safe_pump': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True), 'safe_pump_type': CategoricalParameter(['10', '50', '100'], default='10', space='entry', optimize=False, load=True), 'safe_pump_period': CategoricalParameter(['24', '36', '48'], default='48', space='entry', optimize=False, load=True), 'btc_1h_not_downtrend': CategoricalParameter([True, False], default=False, space='entry', optimize=False, load=True)}}
    entry_condition_1_enable = entry_protection_params[1]['enable']
    entry_1_protection__ema_fast = entry_protection_params[1]['ema_fast']
    entry_1_protection__ema_fast_len = entry_protection_params[1]['ema_fast_len']
    entry_1_protection__ema_slow = entry_protection_params[1]['ema_slow']
    entry_1_protection__ema_slow_len = entry_protection_params[1]['ema_slow_len']
    entry_1_protection__close_above_ema_fast = entry_protection_params[1]['close_above_ema_fast']
    entry_1_protection__close_above_ema_fast_len = entry_protection_params[1]['close_above_ema_fast_len']
    entry_1_protection__close_above_ema_slow = entry_protection_params[1]['close_above_ema_slow']
    entry_1_protection__close_above_ema_slow_len = entry_protection_params[1]['close_above_ema_slow_len']
    entry_1_protection__sma200_rising = entry_protection_params[1]['sma200_rising']
    entry_1_protection__sma200_rising_val = entry_protection_params[1]['sma200_rising_val']
    entry_1_protection__sma200_1h_rising = entry_protection_params[1]['sma200_1h_rising']
    entry_1_protection__sma200_1h_rising_val = entry_protection_params[1]['sma200_1h_rising_val']
    entry_1_protection__safe_dips = entry_protection_params[1]['safe_dips']
    entry_1_protection__safe_dips_type = entry_protection_params[1]['safe_dips_type']
    entry_1_protection__safe_pump = entry_protection_params[1]['safe_pump']
    entry_1_protection__safe_pump_type = entry_protection_params[1]['safe_pump_type']
    entry_1_protection__safe_pump_period = entry_protection_params[1]['safe_pump_period']
    entry_1_protection__btc_1h_not_downtrend = entry_protection_params[1]['btc_1h_not_downtrend']
    entry_condition_2_enable = entry_protection_params[2]['enable']
    entry_2_protection__ema_fast = entry_protection_params[2]['ema_fast']
    entry_2_protection__ema_fast_len = entry_protection_params[2]['ema_fast_len']
    entry_2_protection__ema_slow = entry_protection_params[2]['ema_slow']
    entry_2_protection__ema_slow_len = entry_protection_params[2]['ema_slow_len']
    entry_2_protection__close_above_ema_fast = entry_protection_params[2]['close_above_ema_fast']
    entry_2_protection__close_above_ema_fast_len = entry_protection_params[2]['close_above_ema_fast_len']
    entry_2_protection__close_above_ema_slow = entry_protection_params[2]['close_above_ema_slow']
    entry_2_protection__close_above_ema_slow_len = entry_protection_params[2]['close_above_ema_slow_len']
    entry_2_protection__sma200_rising = entry_protection_params[2]['sma200_rising']
    entry_2_protection__sma200_rising_val = entry_protection_params[2]['sma200_rising_val']
    entry_2_protection__sma200_1h_rising = entry_protection_params[2]['sma200_1h_rising']
    entry_2_protection__sma200_1h_rising_val = entry_protection_params[2]['sma200_1h_rising_val']
    entry_2_protection__safe_dips = entry_protection_params[2]['safe_dips']
    entry_2_protection__safe_dips_type = entry_protection_params[2]['safe_dips_type']
    entry_2_protection__safe_pump = entry_protection_params[2]['safe_pump']
    entry_2_protection__safe_pump_type = entry_protection_params[2]['safe_pump_type']
    entry_2_protection__safe_pump_period = entry_protection_params[2]['safe_pump_period']
    entry_2_protection__btc_1h_not_downtrend = entry_protection_params[2]['btc_1h_not_downtrend']
    entry_condition_3_enable = entry_protection_params[3]['enable']
    entry_3_protection__ema_fast = entry_protection_params[3]['ema_fast']
    entry_3_protection__ema_fast_len = entry_protection_params[3]['ema_fast_len']
    entry_3_protection__ema_slow = entry_protection_params[3]['ema_slow']
    entry_3_protection__ema_slow_len = entry_protection_params[3]['ema_slow_len']
    entry_3_protection__close_above_ema_fast = entry_protection_params[3]['close_above_ema_fast']
    entry_3_protection__close_above_ema_fast_len = entry_protection_params[3]['close_above_ema_fast_len']
    entry_3_protection__close_above_ema_slow = entry_protection_params[3]['close_above_ema_slow']
    entry_3_protection__close_above_ema_slow_len = entry_protection_params[3]['close_above_ema_slow_len']
    entry_3_protection__sma200_rising = entry_protection_params[3]['sma200_rising']
    entry_3_protection__sma200_rising_val = entry_protection_params[3]['sma200_rising_val']
    entry_3_protection__sma200_1h_rising = entry_protection_params[3]['sma200_1h_rising']
    entry_3_protection__sma200_1h_rising_val = entry_protection_params[3]['sma200_1h_rising_val']
    entry_3_protection__safe_dips = entry_protection_params[3]['safe_dips']
    entry_3_protection__safe_dips_type = entry_protection_params[3]['safe_dips_type']
    entry_3_protection__safe_pump = entry_protection_params[3]['safe_pump']
    entry_3_protection__safe_pump_type = entry_protection_params[3]['safe_pump_type']
    entry_3_protection__safe_pump_period = entry_protection_params[3]['safe_pump_period']
    entry_3_protection__btc_1h_not_downtrend = entry_protection_params[3]['btc_1h_not_downtrend']
    entry_condition_4_enable = entry_protection_params[4]['enable']
    entry_4_protection__ema_fast = entry_protection_params[4]['ema_fast']
    entry_4_protection__ema_fast_len = entry_protection_params[4]['ema_fast_len']
    entry_4_protection__ema_slow = entry_protection_params[4]['ema_slow']
    entry_4_protection__ema_slow_len = entry_protection_params[4]['ema_slow_len']
    entry_4_protection__close_above_ema_fast = entry_protection_params[4]['close_above_ema_fast']
    entry_4_protection__close_above_ema_fast_len = entry_protection_params[4]['close_above_ema_fast_len']
    entry_4_protection__close_above_ema_slow = entry_protection_params[4]['close_above_ema_slow']
    entry_4_protection__close_above_ema_slow_len = entry_protection_params[4]['close_above_ema_slow_len']
    entry_4_protection__sma200_rising = entry_protection_params[4]['sma200_rising']
    entry_4_protection__sma200_rising_val = entry_protection_params[4]['sma200_rising_val']
    entry_4_protection__sma200_1h_rising = entry_protection_params[4]['sma200_1h_rising']
    entry_4_protection__sma200_1h_rising_val = entry_protection_params[4]['sma200_1h_rising_val']
    entry_4_protection__safe_dips = entry_protection_params[4]['safe_dips']
    entry_4_protection__safe_dips_type = entry_protection_params[4]['safe_dips_type']
    entry_4_protection__safe_pump = entry_protection_params[4]['safe_pump']
    entry_4_protection__safe_pump_type = entry_protection_params[4]['safe_pump_type']
    entry_4_protection__safe_pump_period = entry_protection_params[4]['safe_pump_period']
    entry_4_protection__btc_1h_not_downtrend = entry_protection_params[4]['btc_1h_not_downtrend']
    entry_condition_5_enable = entry_protection_params[5]['enable']
    entry_5_protection__ema_fast = entry_protection_params[5]['ema_fast']
    entry_5_protection__ema_fast_len = entry_protection_params[5]['ema_fast_len']
    entry_5_protection__ema_slow = entry_protection_params[5]['ema_slow']
    entry_5_protection__ema_slow_len = entry_protection_params[5]['ema_slow_len']
    entry_5_protection__close_above_ema_fast = entry_protection_params[5]['close_above_ema_fast']
    entry_5_protection__close_above_ema_fast_len = entry_protection_params[5]['close_above_ema_fast_len']
    entry_5_protection__close_above_ema_slow = entry_protection_params[5]['close_above_ema_slow']
    entry_5_protection__close_above_ema_slow_len = entry_protection_params[5]['close_above_ema_slow_len']
    entry_5_protection__sma200_rising = entry_protection_params[5]['sma200_rising']
    entry_5_protection__sma200_rising_val = entry_protection_params[5]['sma200_rising_val']
    entry_5_protection__sma200_1h_rising = entry_protection_params[5]['sma200_1h_rising']
    entry_5_protection__sma200_1h_rising_val = entry_protection_params[5]['sma200_1h_rising_val']
    entry_5_protection__safe_dips = entry_protection_params[5]['safe_dips']
    entry_5_protection__safe_dips_type = entry_protection_params[5]['safe_dips_type']
    entry_5_protection__safe_pump = entry_protection_params[5]['safe_pump']
    entry_5_protection__safe_pump_type = entry_protection_params[5]['safe_pump_type']
    entry_5_protection__safe_pump_period = entry_protection_params[5]['safe_pump_period']
    entry_5_protection__btc_1h_not_downtrend = entry_protection_params[5]['btc_1h_not_downtrend']
    entry_condition_6_enable = entry_protection_params[6]['enable']
    entry_6_protection__ema_fast = entry_protection_params[6]['ema_fast']
    entry_6_protection__ema_fast_len = entry_protection_params[6]['ema_fast_len']
    entry_6_protection__ema_slow = entry_protection_params[6]['ema_slow']
    entry_6_protection__ema_slow_len = entry_protection_params[6]['ema_slow_len']
    entry_6_protection__close_above_ema_fast = entry_protection_params[6]['close_above_ema_fast']
    entry_6_protection__close_above_ema_fast_len = entry_protection_params[6]['close_above_ema_fast_len']
    entry_6_protection__close_above_ema_slow = entry_protection_params[6]['close_above_ema_slow']
    entry_6_protection__close_above_ema_slow_len = entry_protection_params[6]['close_above_ema_slow_len']
    entry_6_protection__sma200_rising = entry_protection_params[6]['sma200_rising']
    entry_6_protection__sma200_rising_val = entry_protection_params[6]['sma200_rising_val']
    entry_6_protection__sma200_1h_rising = entry_protection_params[6]['sma200_1h_rising']
    entry_6_protection__sma200_1h_rising_val = entry_protection_params[6]['sma200_1h_rising_val']
    entry_6_protection__safe_dips = entry_protection_params[6]['safe_dips']
    entry_6_protection__safe_dips_type = entry_protection_params[6]['safe_dips_type']
    entry_6_protection__safe_pump = entry_protection_params[6]['safe_pump']
    entry_6_protection__safe_pump_type = entry_protection_params[6]['safe_pump_type']
    entry_6_protection__safe_pump_period = entry_protection_params[6]['safe_pump_period']
    entry_6_protection__btc_1h_not_downtrend = entry_protection_params[6]['btc_1h_not_downtrend']
    entry_condition_7_enable = entry_protection_params[7]['enable']
    entry_7_protection__ema_fast = entry_protection_params[7]['ema_fast']
    entry_7_protection__ema_fast_len = entry_protection_params[7]['ema_fast_len']
    entry_7_protection__ema_slow = entry_protection_params[7]['ema_slow']
    entry_7_protection__ema_slow_len = entry_protection_params[7]['ema_slow_len']
    entry_7_protection__close_above_ema_fast = entry_protection_params[7]['close_above_ema_fast']
    entry_7_protection__close_above_ema_fast_len = entry_protection_params[7]['close_above_ema_fast_len']
    entry_7_protection__close_above_ema_slow = entry_protection_params[7]['close_above_ema_slow']
    entry_7_protection__close_above_ema_slow_len = entry_protection_params[7]['close_above_ema_slow_len']
    entry_7_protection__sma200_rising = entry_protection_params[7]['sma200_rising']
    entry_7_protection__sma200_rising_val = entry_protection_params[7]['sma200_rising_val']
    entry_7_protection__sma200_1h_rising = entry_protection_params[7]['sma200_1h_rising']
    entry_7_protection__sma200_1h_rising_val = entry_protection_params[7]['sma200_1h_rising_val']
    entry_7_protection__safe_dips = entry_protection_params[7]['safe_dips']
    entry_7_protection__safe_dips_type = entry_protection_params[7]['safe_dips_type']
    entry_7_protection__safe_pump = entry_protection_params[7]['safe_pump']
    entry_7_protection__safe_pump_type = entry_protection_params[7]['safe_pump_type']
    entry_7_protection__safe_pump_period = entry_protection_params[7]['safe_pump_period']
    entry_7_protection__btc_1h_not_downtrend = entry_protection_params[7]['btc_1h_not_downtrend']
    entry_condition_8_enable = entry_protection_params[8]['enable']
    entry_8_protection__ema_fast = entry_protection_params[8]['ema_fast']
    entry_8_protection__ema_fast_len = entry_protection_params[8]['ema_fast_len']
    entry_8_protection__ema_slow = entry_protection_params[8]['ema_slow']
    entry_8_protection__ema_slow_len = entry_protection_params[8]['ema_slow_len']
    entry_8_protection__close_above_ema_fast = entry_protection_params[8]['close_above_ema_fast']
    entry_8_protection__close_above_ema_fast_len = entry_protection_params[8]['close_above_ema_fast_len']
    entry_8_protection__close_above_ema_slow = entry_protection_params[8]['close_above_ema_slow']
    entry_8_protection__close_above_ema_slow_len = entry_protection_params[8]['close_above_ema_slow_len']
    entry_8_protection__sma200_rising = entry_protection_params[8]['sma200_rising']
    entry_8_protection__sma200_rising_val = entry_protection_params[8]['sma200_rising_val']
    entry_8_protection__sma200_1h_rising = entry_protection_params[8]['sma200_1h_rising']
    entry_8_protection__sma200_1h_rising_val = entry_protection_params[8]['sma200_1h_rising_val']
    entry_8_protection__safe_dips = entry_protection_params[8]['safe_dips']
    entry_8_protection__safe_dips_type = entry_protection_params[8]['safe_dips_type']
    entry_8_protection__safe_pump = entry_protection_params[8]['safe_pump']
    entry_8_protection__safe_pump_type = entry_protection_params[8]['safe_pump_type']
    entry_8_protection__safe_pump_period = entry_protection_params[8]['safe_pump_period']
    entry_8_protection__btc_1h_not_downtrend = entry_protection_params[8]['btc_1h_not_downtrend']
    entry_condition_9_enable = entry_protection_params[9]['enable']
    entry_9_protection__ema_fast = entry_protection_params[9]['ema_fast']
    entry_9_protection__ema_fast_len = entry_protection_params[9]['ema_fast_len']
    entry_9_protection__ema_slow = entry_protection_params[9]['ema_slow']
    entry_9_protection__ema_slow_len = entry_protection_params[9]['ema_slow_len']
    entry_9_protection__close_above_ema_fast = entry_protection_params[9]['close_above_ema_fast']
    entry_9_protection__close_above_ema_fast_len = entry_protection_params[9]['close_above_ema_fast_len']
    entry_9_protection__close_above_ema_slow = entry_protection_params[9]['close_above_ema_slow']
    entry_9_protection__close_above_ema_slow_len = entry_protection_params[9]['close_above_ema_slow_len']
    entry_9_protection__sma200_rising = entry_protection_params[9]['sma200_rising']
    entry_9_protection__sma200_rising_val = entry_protection_params[9]['sma200_rising_val']
    entry_9_protection__sma200_1h_rising = entry_protection_params[9]['sma200_1h_rising']
    entry_9_protection__sma200_1h_rising_val = entry_protection_params[9]['sma200_1h_rising_val']
    entry_9_protection__safe_dips = entry_protection_params[9]['safe_dips']
    entry_9_protection__safe_dips_type = entry_protection_params[9]['safe_dips_type']
    entry_9_protection__safe_pump = entry_protection_params[9]['safe_pump']
    entry_9_protection__safe_pump_type = entry_protection_params[9]['safe_pump_type']
    entry_9_protection__safe_pump_period = entry_protection_params[9]['safe_pump_period']
    entry_9_protection__btc_1h_not_downtrend = entry_protection_params[9]['btc_1h_not_downtrend']
    entry_condition_10_enable = entry_protection_params[10]['enable']
    entry_10_protection__ema_fast = entry_protection_params[10]['ema_fast']
    entry_10_protection__ema_fast_len = entry_protection_params[10]['ema_fast_len']
    entry_10_protection__ema_slow = entry_protection_params[10]['ema_slow']
    entry_10_protection__ema_slow_len = entry_protection_params[10]['ema_slow_len']
    entry_10_protection__close_above_ema_fast = entry_protection_params[10]['close_above_ema_fast']
    entry_10_protection__close_above_ema_fast_len = entry_protection_params[10]['close_above_ema_fast_len']
    entry_10_protection__close_above_ema_slow = entry_protection_params[10]['close_above_ema_slow']
    entry_10_protection__close_above_ema_slow_len = entry_protection_params[10]['close_above_ema_slow_len']
    entry_10_protection__sma200_rising = entry_protection_params[10]['sma200_rising']
    entry_10_protection__sma200_rising_val = entry_protection_params[10]['sma200_rising_val']
    entry_10_protection__sma200_1h_rising = entry_protection_params[10]['sma200_1h_rising']
    entry_10_protection__sma200_1h_rising_val = entry_protection_params[10]['sma200_1h_rising_val']
    entry_10_protection__safe_dips = entry_protection_params[10]['safe_dips']
    entry_10_protection__safe_dips_type = entry_protection_params[10]['safe_dips_type']
    entry_10_protection__safe_pump = entry_protection_params[10]['safe_pump']
    entry_10_protection__safe_pump_type = entry_protection_params[10]['safe_pump_type']
    entry_10_protection__safe_pump_period = entry_protection_params[10]['safe_pump_period']
    entry_10_protection__btc_1h_not_downtrend = entry_protection_params[10]['btc_1h_not_downtrend']
    entry_condition_11_enable = entry_protection_params[11]['enable']
    entry_11_protection__ema_fast = entry_protection_params[11]['ema_fast']
    entry_11_protection__ema_fast_len = entry_protection_params[11]['ema_fast_len']
    entry_11_protection__ema_slow = entry_protection_params[11]['ema_slow']
    entry_11_protection__ema_slow_len = entry_protection_params[11]['ema_slow_len']
    entry_11_protection__close_above_ema_fast = entry_protection_params[11]['close_above_ema_fast']
    entry_11_protection__close_above_ema_fast_len = entry_protection_params[11]['close_above_ema_fast_len']
    entry_11_protection__close_above_ema_slow = entry_protection_params[11]['close_above_ema_slow']
    entry_11_protection__close_above_ema_slow_len = entry_protection_params[11]['close_above_ema_slow_len']
    entry_11_protection__sma200_rising = entry_protection_params[11]['sma200_rising']
    entry_11_protection__sma200_rising_val = entry_protection_params[11]['sma200_rising_val']
    entry_11_protection__sma200_1h_rising = entry_protection_params[11]['sma200_1h_rising']
    entry_11_protection__sma200_1h_rising_val = entry_protection_params[11]['sma200_1h_rising_val']
    entry_11_protection__safe_dips = entry_protection_params[11]['safe_dips']
    entry_11_protection__safe_dips_type = entry_protection_params[11]['safe_dips_type']
    entry_11_protection__safe_pump = entry_protection_params[11]['safe_pump']
    entry_11_protection__safe_pump_type = entry_protection_params[11]['safe_pump_type']
    entry_11_protection__safe_pump_period = entry_protection_params[11]['safe_pump_period']
    entry_11_protection__btc_1h_not_downtrend = entry_protection_params[11]['btc_1h_not_downtrend']
    entry_condition_12_enable = entry_protection_params[12]['enable']
    entry_12_protection__ema_fast = entry_protection_params[12]['ema_fast']
    entry_12_protection__ema_fast_len = entry_protection_params[12]['ema_fast_len']
    entry_12_protection__ema_slow = entry_protection_params[12]['ema_slow']
    entry_12_protection__ema_slow_len = entry_protection_params[12]['ema_slow_len']
    entry_12_protection__close_above_ema_fast = entry_protection_params[12]['close_above_ema_fast']
    entry_12_protection__close_above_ema_fast_len = entry_protection_params[12]['close_above_ema_fast_len']
    entry_12_protection__close_above_ema_slow = entry_protection_params[12]['close_above_ema_slow']
    entry_12_protection__close_above_ema_slow_len = entry_protection_params[12]['close_above_ema_slow_len']
    entry_12_protection__sma200_rising = entry_protection_params[12]['sma200_rising']
    entry_12_protection__sma200_rising_val = entry_protection_params[12]['sma200_rising_val']
    entry_12_protection__sma200_1h_rising = entry_protection_params[12]['sma200_1h_rising']
    entry_12_protection__sma200_1h_rising_val = entry_protection_params[12]['sma200_1h_rising_val']
    entry_12_protection__safe_dips = entry_protection_params[12]['safe_dips']
    entry_12_protection__safe_dips_type = entry_protection_params[12]['safe_dips_type']
    entry_12_protection__safe_pump = entry_protection_params[12]['safe_pump']
    entry_12_protection__safe_pump_type = entry_protection_params[12]['safe_pump_type']
    entry_12_protection__safe_pump_period = entry_protection_params[12]['safe_pump_period']
    entry_12_protection__btc_1h_not_downtrend = entry_protection_params[12]['btc_1h_not_downtrend']
    entry_condition_13_enable = entry_protection_params[13]['enable']
    entry_13_protection__ema_fast = entry_protection_params[13]['ema_fast']
    entry_13_protection__ema_fast_len = entry_protection_params[13]['ema_fast_len']
    entry_13_protection__ema_slow = entry_protection_params[13]['ema_slow']
    entry_13_protection__ema_slow_len = entry_protection_params[13]['ema_slow_len']
    entry_13_protection__close_above_ema_fast = entry_protection_params[13]['close_above_ema_fast']
    entry_13_protection__close_above_ema_fast_len = entry_protection_params[13]['close_above_ema_fast_len']
    entry_13_protection__close_above_ema_slow = entry_protection_params[13]['close_above_ema_slow']
    entry_13_protection__close_above_ema_slow_len = entry_protection_params[13]['close_above_ema_slow_len']
    entry_13_protection__sma200_rising = entry_protection_params[13]['sma200_rising']
    entry_13_protection__sma200_rising_val = entry_protection_params[13]['sma200_rising_val']
    entry_13_protection__sma200_1h_rising = entry_protection_params[13]['sma200_1h_rising']
    entry_13_protection__sma200_1h_rising_val = entry_protection_params[13]['sma200_1h_rising_val']
    entry_13_protection__safe_dips = entry_protection_params[13]['safe_dips']
    entry_13_protection__safe_dips_type = entry_protection_params[13]['safe_dips_type']
    entry_13_protection__safe_pump = entry_protection_params[13]['safe_pump']
    entry_13_protection__safe_pump_type = entry_protection_params[13]['safe_pump_type']
    entry_13_protection__safe_pump_period = entry_protection_params[13]['safe_pump_period']
    entry_13_protection__btc_1h_not_downtrend = entry_protection_params[13]['btc_1h_not_downtrend']
    entry_condition_14_enable = entry_protection_params[14]['enable']
    entry_14_protection__ema_fast = entry_protection_params[14]['ema_fast']
    entry_14_protection__ema_fast_len = entry_protection_params[14]['ema_fast_len']
    entry_14_protection__ema_slow = entry_protection_params[14]['ema_slow']
    entry_14_protection__ema_slow_len = entry_protection_params[14]['ema_slow_len']
    entry_14_protection__close_above_ema_fast = entry_protection_params[14]['close_above_ema_fast']
    entry_14_protection__close_above_ema_fast_len = entry_protection_params[14]['close_above_ema_fast_len']
    entry_14_protection__close_above_ema_slow = entry_protection_params[14]['close_above_ema_slow']
    entry_14_protection__close_above_ema_slow_len = entry_protection_params[14]['close_above_ema_slow_len']
    entry_14_protection__sma200_rising = entry_protection_params[14]['sma200_rising']
    entry_14_protection__sma200_rising_val = entry_protection_params[14]['sma200_rising_val']
    entry_14_protection__sma200_1h_rising = entry_protection_params[14]['sma200_1h_rising']
    entry_14_protection__sma200_1h_rising_val = entry_protection_params[14]['sma200_1h_rising_val']
    entry_14_protection__safe_dips = entry_protection_params[14]['safe_dips']
    entry_14_protection__safe_dips_type = entry_protection_params[14]['safe_dips_type']
    entry_14_protection__safe_pump = entry_protection_params[14]['safe_pump']
    entry_14_protection__safe_pump_type = entry_protection_params[14]['safe_pump_type']
    entry_14_protection__safe_pump_period = entry_protection_params[14]['safe_pump_period']
    entry_14_protection__btc_1h_not_downtrend = entry_protection_params[14]['btc_1h_not_downtrend']
    entry_condition_15_enable = entry_protection_params[15]['enable']
    entry_15_protection__ema_fast = entry_protection_params[15]['ema_fast']
    entry_15_protection__ema_fast_len = entry_protection_params[15]['ema_fast_len']
    entry_15_protection__ema_slow = entry_protection_params[15]['ema_slow']
    entry_15_protection__ema_slow_len = entry_protection_params[15]['ema_slow_len']
    entry_15_protection__close_above_ema_fast = entry_protection_params[15]['close_above_ema_fast']
    entry_15_protection__close_above_ema_fast_len = entry_protection_params[15]['close_above_ema_fast_len']
    entry_15_protection__close_above_ema_slow = entry_protection_params[15]['close_above_ema_slow']
    entry_15_protection__close_above_ema_slow_len = entry_protection_params[15]['close_above_ema_slow_len']
    entry_15_protection__sma200_rising = entry_protection_params[15]['sma200_rising']
    entry_15_protection__sma200_rising_val = entry_protection_params[15]['sma200_rising_val']
    entry_15_protection__sma200_1h_rising = entry_protection_params[15]['sma200_1h_rising']
    entry_15_protection__sma200_1h_rising_val = entry_protection_params[15]['sma200_1h_rising_val']
    entry_15_protection__safe_dips = entry_protection_params[15]['safe_dips']
    entry_15_protection__safe_dips_type = entry_protection_params[15]['safe_dips_type']
    entry_15_protection__safe_pump = entry_protection_params[15]['safe_pump']
    entry_15_protection__safe_pump_type = entry_protection_params[15]['safe_pump_type']
    entry_15_protection__safe_pump_period = entry_protection_params[15]['safe_pump_period']
    entry_15_protection__btc_1h_not_downtrend = entry_protection_params[15]['btc_1h_not_downtrend']
    entry_condition_16_enable = entry_protection_params[16]['enable']
    entry_16_protection__ema_fast = entry_protection_params[16]['ema_fast']
    entry_16_protection__ema_fast_len = entry_protection_params[16]['ema_fast_len']
    entry_16_protection__ema_slow = entry_protection_params[16]['ema_slow']
    entry_16_protection__ema_slow_len = entry_protection_params[16]['ema_slow_len']
    entry_16_protection__close_above_ema_fast = entry_protection_params[16]['close_above_ema_fast']
    entry_16_protection__close_above_ema_fast_len = entry_protection_params[16]['close_above_ema_fast_len']
    entry_16_protection__close_above_ema_slow = entry_protection_params[16]['close_above_ema_slow']
    entry_16_protection__close_above_ema_slow_len = entry_protection_params[16]['close_above_ema_slow_len']
    entry_16_protection__sma200_rising = entry_protection_params[16]['sma200_rising']
    entry_16_protection__sma200_rising_val = entry_protection_params[16]['sma200_rising_val']
    entry_16_protection__sma200_1h_rising = entry_protection_params[16]['sma200_1h_rising']
    entry_16_protection__sma200_1h_rising_val = entry_protection_params[16]['sma200_1h_rising_val']
    entry_16_protection__safe_dips = entry_protection_params[16]['safe_dips']
    entry_16_protection__safe_dips_type = entry_protection_params[16]['safe_dips_type']
    entry_16_protection__safe_pump = entry_protection_params[16]['safe_pump']
    entry_16_protection__safe_pump_type = entry_protection_params[16]['safe_pump_type']
    entry_16_protection__safe_pump_period = entry_protection_params[16]['safe_pump_period']
    entry_16_protection__btc_1h_not_downtrend = entry_protection_params[16]['btc_1h_not_downtrend']
    entry_condition_17_enable = entry_protection_params[17]['enable']
    entry_17_protection__ema_fast = entry_protection_params[17]['ema_fast']
    entry_17_protection__ema_fast_len = entry_protection_params[17]['ema_fast_len']
    entry_17_protection__ema_slow = entry_protection_params[17]['ema_slow']
    entry_17_protection__ema_slow_len = entry_protection_params[17]['ema_slow_len']
    entry_17_protection__close_above_ema_fast = entry_protection_params[17]['close_above_ema_fast']
    entry_17_protection__close_above_ema_fast_len = entry_protection_params[17]['close_above_ema_fast_len']
    entry_17_protection__close_above_ema_slow = entry_protection_params[17]['close_above_ema_slow']
    entry_17_protection__close_above_ema_slow_len = entry_protection_params[17]['close_above_ema_slow_len']
    entry_17_protection__sma200_rising = entry_protection_params[17]['sma200_rising']
    entry_17_protection__sma200_rising_val = entry_protection_params[17]['sma200_rising_val']
    entry_17_protection__sma200_1h_rising = entry_protection_params[17]['sma200_1h_rising']
    entry_17_protection__sma200_1h_rising_val = entry_protection_params[17]['sma200_1h_rising_val']
    entry_17_protection__safe_dips = entry_protection_params[17]['safe_dips']
    entry_17_protection__safe_dips_type = entry_protection_params[17]['safe_dips_type']
    entry_17_protection__safe_pump = entry_protection_params[17]['safe_pump']
    entry_17_protection__safe_pump_type = entry_protection_params[17]['safe_pump_type']
    entry_17_protection__safe_pump_period = entry_protection_params[17]['safe_pump_period']
    entry_17_protection__btc_1h_not_downtrend = entry_protection_params[17]['btc_1h_not_downtrend']
    entry_condition_18_enable = entry_protection_params[18]['enable']
    entry_18_protection__ema_fast = entry_protection_params[18]['ema_fast']
    entry_18_protection__ema_fast_len = entry_protection_params[18]['ema_fast_len']
    entry_18_protection__ema_slow = entry_protection_params[18]['ema_slow']
    entry_18_protection__ema_slow_len = entry_protection_params[18]['ema_slow_len']
    entry_18_protection__close_above_ema_fast = entry_protection_params[18]['close_above_ema_fast']
    entry_18_protection__close_above_ema_fast_len = entry_protection_params[18]['close_above_ema_fast_len']
    entry_18_protection__close_above_ema_slow = entry_protection_params[18]['close_above_ema_slow']
    entry_18_protection__close_above_ema_slow_len = entry_protection_params[18]['close_above_ema_slow_len']
    entry_18_protection__sma200_rising = entry_protection_params[18]['sma200_rising']
    entry_18_protection__sma200_rising_val = entry_protection_params[18]['sma200_rising_val']
    entry_18_protection__sma200_1h_rising = entry_protection_params[18]['sma200_1h_rising']
    entry_18_protection__sma200_1h_rising_val = entry_protection_params[18]['sma200_1h_rising_val']
    entry_18_protection__safe_dips = entry_protection_params[18]['safe_dips']
    entry_18_protection__safe_dips_type = entry_protection_params[18]['safe_dips_type']
    entry_18_protection__safe_pump = entry_protection_params[18]['safe_pump']
    entry_18_protection__safe_pump_type = entry_protection_params[18]['safe_pump_type']
    entry_18_protection__safe_pump_period = entry_protection_params[18]['safe_pump_period']
    entry_18_protection__btc_1h_not_downtrend = entry_protection_params[18]['btc_1h_not_downtrend']
    entry_condition_19_enable = entry_protection_params[19]['enable']
    entry_19_protection__ema_fast = entry_protection_params[19]['ema_fast']
    entry_19_protection__ema_fast_len = entry_protection_params[19]['ema_fast_len']
    entry_19_protection__ema_slow = entry_protection_params[19]['ema_slow']
    entry_19_protection__ema_slow_len = entry_protection_params[19]['ema_slow_len']
    entry_19_protection__close_above_ema_fast = entry_protection_params[19]['close_above_ema_fast']
    entry_19_protection__close_above_ema_fast_len = entry_protection_params[19]['close_above_ema_fast_len']
    entry_19_protection__close_above_ema_slow = entry_protection_params[19]['close_above_ema_slow']
    entry_19_protection__close_above_ema_slow_len = entry_protection_params[19]['close_above_ema_slow_len']
    entry_19_protection__sma200_rising = entry_protection_params[19]['sma200_rising']
    entry_19_protection__sma200_rising_val = entry_protection_params[19]['sma200_rising_val']
    entry_19_protection__sma200_1h_rising = entry_protection_params[19]['sma200_1h_rising']
    entry_19_protection__sma200_1h_rising_val = entry_protection_params[19]['sma200_1h_rising_val']
    entry_19_protection__safe_dips = entry_protection_params[19]['safe_dips']
    entry_19_protection__safe_dips_type = entry_protection_params[19]['safe_dips_type']
    entry_19_protection__safe_pump = entry_protection_params[19]['safe_pump']
    entry_19_protection__safe_pump_type = entry_protection_params[19]['safe_pump_type']
    entry_19_protection__safe_pump_period = entry_protection_params[19]['safe_pump_period']
    entry_19_protection__btc_1h_not_downtrend = entry_protection_params[19]['btc_1h_not_downtrend']
    entry_condition_20_enable = entry_protection_params[20]['enable']
    entry_20_protection__ema_fast = entry_protection_params[20]['ema_fast']
    entry_20_protection__ema_fast_len = entry_protection_params[20]['ema_fast_len']
    entry_20_protection__ema_slow = entry_protection_params[20]['ema_slow']
    entry_20_protection__ema_slow_len = entry_protection_params[20]['ema_slow_len']
    entry_20_protection__close_above_ema_fast = entry_protection_params[20]['close_above_ema_fast']
    entry_20_protection__close_above_ema_fast_len = entry_protection_params[20]['close_above_ema_fast_len']
    entry_20_protection__close_above_ema_slow = entry_protection_params[20]['close_above_ema_slow']
    entry_20_protection__close_above_ema_slow_len = entry_protection_params[20]['close_above_ema_slow_len']
    entry_20_protection__sma200_rising = entry_protection_params[20]['sma200_rising']
    entry_20_protection__sma200_rising_val = entry_protection_params[20]['sma200_rising_val']
    entry_20_protection__sma200_1h_rising = entry_protection_params[20]['sma200_1h_rising']
    entry_20_protection__sma200_1h_rising_val = entry_protection_params[20]['sma200_1h_rising_val']
    entry_20_protection__safe_dips = entry_protection_params[20]['safe_dips']
    entry_20_protection__safe_dips_type = entry_protection_params[20]['safe_dips_type']
    entry_20_protection__safe_pump = entry_protection_params[20]['safe_pump']
    entry_20_protection__safe_pump_type = entry_protection_params[20]['safe_pump_type']
    entry_20_protection__safe_pump_period = entry_protection_params[20]['safe_pump_period']
    entry_20_protection__btc_1h_not_downtrend = entry_protection_params[20]['btc_1h_not_downtrend']
    entry_condition_21_enable = entry_protection_params[21]['enable']
    entry_21_protection__ema_fast = entry_protection_params[21]['ema_fast']
    entry_21_protection__ema_fast_len = entry_protection_params[21]['ema_fast_len']
    entry_21_protection__ema_slow = entry_protection_params[21]['ema_slow']
    entry_21_protection__ema_slow_len = entry_protection_params[21]['ema_slow_len']
    entry_21_protection__close_above_ema_fast = entry_protection_params[21]['close_above_ema_fast']
    entry_21_protection__close_above_ema_fast_len = entry_protection_params[21]['close_above_ema_fast_len']
    entry_21_protection__close_above_ema_slow = entry_protection_params[21]['close_above_ema_slow']
    entry_21_protection__close_above_ema_slow_len = entry_protection_params[21]['close_above_ema_slow_len']
    entry_21_protection__sma200_rising = entry_protection_params[21]['sma200_rising']
    entry_21_protection__sma200_rising_val = entry_protection_params[21]['sma200_rising_val']
    entry_21_protection__sma200_1h_rising = entry_protection_params[21]['sma200_1h_rising']
    entry_21_protection__sma200_1h_rising_val = entry_protection_params[21]['sma200_1h_rising_val']
    entry_21_protection__safe_dips = entry_protection_params[21]['safe_dips']
    entry_21_protection__safe_dips_type = entry_protection_params[21]['safe_dips_type']
    entry_21_protection__safe_pump = entry_protection_params[21]['safe_pump']
    entry_21_protection__safe_pump_type = entry_protection_params[21]['safe_pump_type']
    entry_21_protection__safe_pump_period = entry_protection_params[21]['safe_pump_period']
    entry_21_protection__btc_1h_not_downtrend = entry_protection_params[21]['btc_1h_not_downtrend']
    entry_condition_22_enable = entry_protection_params[22]['enable']
    entry_22_protection__ema_fast = entry_protection_params[22]['ema_fast']
    entry_22_protection__ema_fast_len = entry_protection_params[22]['ema_fast_len']
    entry_22_protection__ema_slow = entry_protection_params[22]['ema_slow']
    entry_22_protection__ema_slow_len = entry_protection_params[22]['ema_slow_len']
    entry_22_protection__close_above_ema_fast = entry_protection_params[22]['close_above_ema_fast']
    entry_22_protection__close_above_ema_fast_len = entry_protection_params[22]['close_above_ema_fast_len']
    entry_22_protection__close_above_ema_slow = entry_protection_params[22]['close_above_ema_slow']
    entry_22_protection__close_above_ema_slow_len = entry_protection_params[22]['close_above_ema_slow_len']
    entry_22_protection__sma200_rising = entry_protection_params[22]['sma200_rising']
    entry_22_protection__sma200_rising_val = entry_protection_params[22]['sma200_rising_val']
    entry_22_protection__sma200_1h_rising = entry_protection_params[22]['sma200_1h_rising']
    entry_22_protection__sma200_1h_rising_val = entry_protection_params[22]['sma200_1h_rising_val']
    entry_22_protection__safe_dips = entry_protection_params[22]['safe_dips']
    entry_22_protection__safe_dips_type = entry_protection_params[22]['safe_dips_type']
    entry_22_protection__safe_pump = entry_protection_params[22]['safe_pump']
    entry_22_protection__safe_pump_type = entry_protection_params[22]['safe_pump_type']
    entry_22_protection__safe_pump_period = entry_protection_params[22]['safe_pump_period']
    entry_22_protection__btc_1h_not_downtrend = entry_protection_params[22]['btc_1h_not_downtrend']
    entry_condition_23_enable = entry_protection_params[23]['enable']
    entry_23_protection__ema_fast = entry_protection_params[23]['ema_fast']
    entry_23_protection__ema_fast_len = entry_protection_params[23]['ema_fast_len']
    entry_23_protection__ema_slow = entry_protection_params[23]['ema_slow']
    entry_23_protection__ema_slow_len = entry_protection_params[23]['ema_slow_len']
    entry_23_protection__close_above_ema_fast = entry_protection_params[23]['close_above_ema_fast']
    entry_23_protection__close_above_ema_fast_len = entry_protection_params[23]['close_above_ema_fast_len']
    entry_23_protection__close_above_ema_slow = entry_protection_params[23]['close_above_ema_slow']
    entry_23_protection__close_above_ema_slow_len = entry_protection_params[23]['close_above_ema_slow_len']
    entry_23_protection__sma200_rising = entry_protection_params[23]['sma200_rising']
    entry_23_protection__sma200_rising_val = entry_protection_params[23]['sma200_rising_val']
    entry_23_protection__sma200_1h_rising = entry_protection_params[23]['sma200_1h_rising']
    entry_23_protection__sma200_1h_rising_val = entry_protection_params[23]['sma200_1h_rising_val']
    entry_23_protection__safe_dips = entry_protection_params[23]['safe_dips']
    entry_23_protection__safe_dips_type = entry_protection_params[23]['safe_dips_type']
    entry_23_protection__safe_pump = entry_protection_params[23]['safe_pump']
    entry_23_protection__safe_pump_type = entry_protection_params[23]['safe_pump_type']
    entry_23_protection__safe_pump_period = entry_protection_params[23]['safe_pump_period']
    entry_23_protection__btc_1h_not_downtrend = entry_protection_params[23]['btc_1h_not_downtrend']
    entry_condition_24_enable = entry_protection_params[24]['enable']
    entry_24_protection__ema_fast = entry_protection_params[24]['ema_fast']
    entry_24_protection__ema_fast_len = entry_protection_params[24]['ema_fast_len']
    entry_24_protection__ema_slow = entry_protection_params[24]['ema_slow']
    entry_24_protection__ema_slow_len = entry_protection_params[24]['ema_slow_len']
    entry_24_protection__close_above_ema_fast = entry_protection_params[24]['close_above_ema_fast']
    entry_24_protection__close_above_ema_fast_len = entry_protection_params[24]['close_above_ema_fast_len']
    entry_24_protection__close_above_ema_slow = entry_protection_params[24]['close_above_ema_slow']
    entry_24_protection__close_above_ema_slow_len = entry_protection_params[24]['close_above_ema_slow_len']
    entry_24_protection__sma200_rising = entry_protection_params[24]['sma200_rising']
    entry_24_protection__sma200_rising_val = entry_protection_params[24]['sma200_rising_val']
    entry_24_protection__sma200_1h_rising = entry_protection_params[24]['sma200_1h_rising']
    entry_24_protection__sma200_1h_rising_val = entry_protection_params[24]['sma200_1h_rising_val']
    entry_24_protection__safe_dips = entry_protection_params[24]['safe_dips']
    entry_24_protection__safe_dips_type = entry_protection_params[24]['safe_dips_type']
    entry_24_protection__safe_pump = entry_protection_params[24]['safe_pump']
    entry_24_protection__safe_pump_type = entry_protection_params[24]['safe_pump_type']
    entry_24_protection__safe_pump_period = entry_protection_params[24]['safe_pump_period']
    entry_24_protection__btc_1h_not_downtrend = entry_protection_params[24]['btc_1h_not_downtrend']
    entry_condition_25_enable = entry_protection_params[25]['enable']
    entry_25_protection__ema_fast = entry_protection_params[25]['ema_fast']
    entry_25_protection__ema_fast_len = entry_protection_params[25]['ema_fast_len']
    entry_25_protection__ema_slow = entry_protection_params[25]['ema_slow']
    entry_25_protection__ema_slow_len = entry_protection_params[25]['ema_slow_len']
    entry_25_protection__close_above_ema_fast = entry_protection_params[25]['close_above_ema_fast']
    entry_25_protection__close_above_ema_fast_len = entry_protection_params[25]['close_above_ema_fast_len']
    entry_25_protection__close_above_ema_slow = entry_protection_params[25]['close_above_ema_slow']
    entry_25_protection__close_above_ema_slow_len = entry_protection_params[25]['close_above_ema_slow_len']
    entry_25_protection__sma200_rising = entry_protection_params[25]['sma200_rising']
    entry_25_protection__sma200_rising_val = entry_protection_params[25]['sma200_rising_val']
    entry_25_protection__sma200_1h_rising = entry_protection_params[25]['sma200_1h_rising']
    entry_25_protection__sma200_1h_rising_val = entry_protection_params[25]['sma200_1h_rising_val']
    entry_25_protection__safe_dips = entry_protection_params[25]['safe_dips']
    entry_25_protection__safe_dips_type = entry_protection_params[25]['safe_dips_type']
    entry_25_protection__safe_pump = entry_protection_params[25]['safe_pump']
    entry_25_protection__safe_pump_type = entry_protection_params[25]['safe_pump_type']
    entry_25_protection__safe_pump_period = entry_protection_params[25]['safe_pump_period']
    entry_25_protection__btc_1h_not_downtrend = entry_protection_params[25]['btc_1h_not_downtrend']
    entry_condition_26_enable = entry_protection_params[26]['enable']
    entry_26_protection__ema_fast = entry_protection_params[26]['ema_fast']
    entry_26_protection__ema_fast_len = entry_protection_params[26]['ema_fast_len']
    entry_26_protection__ema_slow = entry_protection_params[26]['ema_slow']
    entry_26_protection__ema_slow_len = entry_protection_params[26]['ema_slow_len']
    entry_26_protection__close_above_ema_fast = entry_protection_params[26]['close_above_ema_fast']
    entry_26_protection__close_above_ema_fast_len = entry_protection_params[26]['close_above_ema_fast_len']
    entry_26_protection__close_above_ema_slow = entry_protection_params[26]['close_above_ema_slow']
    entry_26_protection__close_above_ema_slow_len = entry_protection_params[26]['close_above_ema_slow_len']
    entry_26_protection__sma200_rising = entry_protection_params[26]['sma200_rising']
    entry_26_protection__sma200_rising_val = entry_protection_params[26]['sma200_rising_val']
    entry_26_protection__sma200_1h_rising = entry_protection_params[26]['sma200_1h_rising']
    entry_26_protection__sma200_1h_rising_val = entry_protection_params[26]['sma200_1h_rising_val']
    entry_26_protection__safe_dips = entry_protection_params[26]['safe_dips']
    entry_26_protection__safe_dips_type = entry_protection_params[26]['safe_dips_type']
    entry_26_protection__safe_pump = entry_protection_params[26]['safe_pump']
    entry_26_protection__safe_pump_type = entry_protection_params[26]['safe_pump_type']
    entry_26_protection__safe_pump_period = entry_protection_params[26]['safe_pump_period']
    entry_26_protection__btc_1h_not_downtrend = entry_protection_params[26]['btc_1h_not_downtrend']
    entry_condition_27_enable = entry_protection_params[27]['enable']
    entry_27_protection__ema_fast = entry_protection_params[27]['ema_fast']
    entry_27_protection__ema_fast_len = entry_protection_params[27]['ema_fast_len']
    entry_27_protection__ema_slow = entry_protection_params[27]['ema_slow']
    entry_27_protection__ema_slow_len = entry_protection_params[27]['ema_slow_len']
    entry_27_protection__close_above_ema_fast = entry_protection_params[27]['close_above_ema_fast']
    entry_27_protection__close_above_ema_fast_len = entry_protection_params[27]['close_above_ema_fast_len']
    entry_27_protection__close_above_ema_slow = entry_protection_params[27]['close_above_ema_slow']
    entry_27_protection__close_above_ema_slow_len = entry_protection_params[27]['close_above_ema_slow_len']
    entry_27_protection__sma200_rising = entry_protection_params[27]['sma200_rising']
    entry_27_protection__sma200_rising_val = entry_protection_params[27]['sma200_rising_val']
    entry_27_protection__sma200_1h_rising = entry_protection_params[27]['sma200_1h_rising']
    entry_27_protection__sma200_1h_rising_val = entry_protection_params[27]['sma200_1h_rising_val']
    entry_27_protection__safe_dips = entry_protection_params[27]['safe_dips']
    entry_27_protection__safe_dips_type = entry_protection_params[27]['safe_dips_type']
    entry_27_protection__safe_pump = entry_protection_params[27]['safe_pump']
    entry_27_protection__safe_pump_type = entry_protection_params[27]['safe_pump_type']
    entry_27_protection__safe_pump_period = entry_protection_params[27]['safe_pump_period']
    entry_27_protection__btc_1h_not_downtrend = entry_protection_params[27]['btc_1h_not_downtrend']
    entry_condition_28_enable = entry_protection_params[28]['enable']
    entry_28_protection__ema_fast = entry_protection_params[28]['ema_fast']
    entry_28_protection__ema_fast_len = entry_protection_params[28]['ema_fast_len']
    entry_28_protection__ema_slow = entry_protection_params[28]['ema_slow']
    entry_28_protection__ema_slow_len = entry_protection_params[28]['ema_slow_len']
    entry_28_protection__close_above_ema_fast = entry_protection_params[28]['close_above_ema_fast']
    entry_28_protection__close_above_ema_fast_len = entry_protection_params[28]['close_above_ema_fast_len']
    entry_28_protection__close_above_ema_slow = entry_protection_params[28]['close_above_ema_slow']
    entry_28_protection__close_above_ema_slow_len = entry_protection_params[28]['close_above_ema_slow_len']
    entry_28_protection__sma200_rising = entry_protection_params[28]['sma200_rising']
    entry_28_protection__sma200_rising_val = entry_protection_params[28]['sma200_rising_val']
    entry_28_protection__sma200_1h_rising = entry_protection_params[28]['sma200_1h_rising']
    entry_28_protection__sma200_1h_rising_val = entry_protection_params[28]['sma200_1h_rising_val']
    entry_28_protection__safe_dips = entry_protection_params[28]['safe_dips']
    entry_28_protection__safe_dips_type = entry_protection_params[28]['safe_dips_type']
    entry_28_protection__safe_pump = entry_protection_params[28]['safe_pump']
    entry_28_protection__safe_pump_type = entry_protection_params[28]['safe_pump_type']
    entry_28_protection__safe_pump_period = entry_protection_params[28]['safe_pump_period']
    entry_28_protection__btc_1h_not_downtrend = entry_protection_params[28]['btc_1h_not_downtrend']
    entry_condition_29_enable = entry_protection_params[29]['enable']
    entry_29_protection__ema_fast = entry_protection_params[29]['ema_fast']
    entry_29_protection__ema_fast_len = entry_protection_params[29]['ema_fast_len']
    entry_29_protection__ema_slow = entry_protection_params[29]['ema_slow']
    entry_29_protection__ema_slow_len = entry_protection_params[29]['ema_slow_len']
    entry_29_protection__close_above_ema_fast = entry_protection_params[29]['close_above_ema_fast']
    entry_29_protection__close_above_ema_fast_len = entry_protection_params[29]['close_above_ema_fast_len']
    entry_29_protection__close_above_ema_slow = entry_protection_params[29]['close_above_ema_slow']
    entry_29_protection__close_above_ema_slow_len = entry_protection_params[29]['close_above_ema_slow_len']
    entry_29_protection__sma200_rising = entry_protection_params[29]['sma200_rising']
    entry_29_protection__sma200_rising_val = entry_protection_params[29]['sma200_rising_val']
    entry_29_protection__sma200_1h_rising = entry_protection_params[29]['sma200_1h_rising']
    entry_29_protection__sma200_1h_rising_val = entry_protection_params[29]['sma200_1h_rising_val']
    entry_29_protection__safe_dips = entry_protection_params[29]['safe_dips']
    entry_29_protection__safe_dips_type = entry_protection_params[29]['safe_dips_type']
    entry_29_protection__safe_pump = entry_protection_params[29]['safe_pump']
    entry_29_protection__safe_pump_type = entry_protection_params[29]['safe_pump_type']
    entry_29_protection__safe_pump_period = entry_protection_params[29]['safe_pump_period']
    entry_29_protection__btc_1h_not_downtrend = entry_protection_params[29]['btc_1h_not_downtrend']
    entry_condition_30_enable = entry_protection_params[30]['enable']
    entry_30_protection__ema_fast = entry_protection_params[30]['ema_fast']
    entry_30_protection__ema_fast_len = entry_protection_params[30]['ema_fast_len']
    entry_30_protection__ema_slow = entry_protection_params[30]['ema_slow']
    entry_30_protection__ema_slow_len = entry_protection_params[30]['ema_slow_len']
    entry_30_protection__close_above_ema_fast = entry_protection_params[30]['close_above_ema_fast']
    entry_30_protection__close_above_ema_fast_len = entry_protection_params[30]['close_above_ema_fast_len']
    entry_30_protection__close_above_ema_slow = entry_protection_params[30]['close_above_ema_slow']
    entry_30_protection__close_above_ema_slow_len = entry_protection_params[30]['close_above_ema_slow_len']
    entry_30_protection__sma200_rising = entry_protection_params[30]['sma200_rising']
    entry_30_protection__sma200_rising_val = entry_protection_params[30]['sma200_rising_val']
    entry_30_protection__sma200_1h_rising = entry_protection_params[30]['sma200_1h_rising']
    entry_30_protection__sma200_1h_rising_val = entry_protection_params[30]['sma200_1h_rising_val']
    entry_30_protection__safe_dips = entry_protection_params[30]['safe_dips']
    entry_30_protection__safe_dips_type = entry_protection_params[30]['safe_dips_type']
    entry_30_protection__safe_pump = entry_protection_params[30]['safe_pump']
    entry_30_protection__safe_pump_type = entry_protection_params[30]['safe_pump_type']
    entry_30_protection__safe_pump_period = entry_protection_params[30]['safe_pump_period']
    entry_30_protection__btc_1h_not_downtrend = entry_protection_params[30]['btc_1h_not_downtrend']
    entry_condition_31_enable = entry_protection_params[31]['enable']
    entry_31_protection__ema_fast = entry_protection_params[31]['ema_fast']
    entry_31_protection__ema_fast_len = entry_protection_params[31]['ema_fast_len']
    entry_31_protection__ema_slow = entry_protection_params[31]['ema_slow']
    entry_31_protection__ema_slow_len = entry_protection_params[31]['ema_slow_len']
    entry_31_protection__close_above_ema_fast = entry_protection_params[31]['close_above_ema_fast']
    entry_31_protection__close_above_ema_fast_len = entry_protection_params[31]['close_above_ema_fast_len']
    entry_31_protection__close_above_ema_slow = entry_protection_params[31]['close_above_ema_slow']
    entry_31_protection__close_above_ema_slow_len = entry_protection_params[31]['close_above_ema_slow_len']
    entry_31_protection__sma200_rising = entry_protection_params[31]['sma200_rising']
    entry_31_protection__sma200_rising_val = entry_protection_params[31]['sma200_rising_val']
    entry_31_protection__sma200_1h_rising = entry_protection_params[31]['sma200_1h_rising']
    entry_31_protection__sma200_1h_rising_val = entry_protection_params[31]['sma200_1h_rising_val']
    entry_31_protection__safe_dips = entry_protection_params[31]['safe_dips']
    entry_31_protection__safe_dips_type = entry_protection_params[31]['safe_dips_type']
    entry_31_protection__safe_pump = entry_protection_params[31]['safe_pump']
    entry_31_protection__safe_pump_type = entry_protection_params[31]['safe_pump_type']
    entry_31_protection__safe_pump_period = entry_protection_params[31]['safe_pump_period']
    entry_31_protection__btc_1h_not_downtrend = entry_protection_params[31]['btc_1h_not_downtrend']
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
    # 5 hours - level 10
    entry_dump_protection_10_5 = DecimalParameter(0.3, 0.8, default=0.4, space='entry', decimals=2, optimize=False, load=True)
    # 5 hours - level 20
    entry_dump_protection_20_5 = DecimalParameter(0.3, 0.8, default=0.44, space='entry', decimals=2, optimize=False, load=True)
    # 5 hours - level 30
    entry_dump_protection_30_5 = DecimalParameter(0.3, 0.8, default=0.5, space='entry', decimals=2, optimize=False, load=True)
    # 5 hours - level 40
    entry_dump_protection_40_5 = DecimalParameter(0.3, 0.8, default=0.58, space='entry', decimals=2, optimize=False, load=True)
    # 5 hours - level 50
    entry_dump_protection_50_5 = DecimalParameter(0.3, 0.8, default=0.66, space='entry', decimals=2, optimize=False, load=True)
    # 5 hours - level 60
    entry_dump_protection_60_5 = DecimalParameter(0.3, 0.8, default=0.74, space='entry', decimals=2, optimize=False, load=True)
    entry_min_inc_1 = DecimalParameter(0.01, 0.05, default=0.022, space='entry', decimals=3, optimize=False, load=True)
    entry_rsi_1h_min_1 = DecimalParameter(25.0, 40.0, default=30.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_max_1 = DecimalParameter(70.0, 90.0, default=84.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1 = DecimalParameter(20.0, 40.0, default=36.0, space='entry', decimals=1, optimize=False, load=True)
    entry_mfi_1 = DecimalParameter(20.0, 40.0, default=44.0, space='entry', decimals=1, optimize=False, load=True)
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
    entry_tail_diff_8 = DecimalParameter(3.0, 10.0, default=2.5, space='entry', decimals=1, optimize=False, load=True)
    entry_ma_offset_9 = DecimalParameter(0.91, 0.94, default=0.922, space='entry', decimals=3, optimize=False, load=True)
    entry_bb_offset_9 = DecimalParameter(0.96, 0.98, default=0.942, space='entry', decimals=3, optimize=False, load=True)
    entry_rsi_1h_min_9 = DecimalParameter(26.0, 40.0, default=20.0, space='entry', decimals=1, optimize=False, load=True)
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
    entry_chop_min_19 = DecimalParameter(20.0, 60.0, default=26.1, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_20 = DecimalParameter(20.0, 36.0, default=27.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_20 = DecimalParameter(14.0, 30.0, default=20.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_21 = DecimalParameter(10.0, 28.0, default=23.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_21 = DecimalParameter(18.0, 40.0, default=24.0, space='entry', decimals=1, optimize=False, load=True)
    entry_volume_22 = DecimalParameter(0.5, 6.0, default=3.0, space='entry', decimals=1, optimize=False, load=True)
    entry_bb_offset_22 = DecimalParameter(0.98, 1.0, default=0.98, space='entry', decimals=3, optimize=False, load=True)
    entry_ma_offset_22 = DecimalParameter(0.93, 0.98, default=0.941, space='entry', decimals=3, optimize=False, load=True)
    entry_ewo_22 = DecimalParameter(2.0, 10.0, default=4.2, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_22 = DecimalParameter(26.0, 56.0, default=37.0, space='entry', decimals=1, optimize=False, load=True)
    entry_bb_offset_23 = DecimalParameter(0.97, 1.0, default=0.983, space='entry', decimals=3, optimize=False, load=True)
    entry_ewo_23 = DecimalParameter(2.0, 10.0, default=7.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_23 = DecimalParameter(20.0, 40.0, default=30.0, space='entry', decimals=1, optimize=False, load=True)
    entry_rsi_1h_23 = DecimalParameter(60.0, 80.0, default=70.0, space='entry', decimals=1, optimize=False, load=True)
    entry_24_rsi_max = DecimalParameter(26.0, 60.0, default=60.0, space='entry', decimals=1, optimize=False, load=True)
    entry_24_rsi_1h_min = DecimalParameter(40.0, 90.0, default=66.9, space='entry', decimals=1, optimize=False, load=True)
    entry_25_ma_offset = DecimalParameter(0.9, 0.99, default=0.922, space='entry', optimize=False, load=True)
    entry_25_rsi_14 = DecimalParameter(26.0, 40.0, default=38.0, space='entry', decimals=1, optimize=False, load=True)
    entry_26_zema_low_offset = DecimalParameter(0.9, 0.99, default=0.93, space='entry', optimize=False, load=True)
    entry_27_wr_max = DecimalParameter(95, 99, default=95.4, space='entry', decimals=1, optimize=False, load=True)
    entry_27_wr_1h_max = DecimalParameter(90, 99, default=97.6, space='entry', decimals=1, optimize=False, load=True)
    entry_27_rsi_max = DecimalParameter(40, 70, default=50, space='entry', decimals=0, optimize=False, load=True)
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
    # Profit over EMA200
    exit_custom_profit_0 = DecimalParameter(0.01, 0.1, default=0.012, space='exit', decimals=3, optimize=False, load=True)
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
    exit_custom_rsi_6 = DecimalParameter(38.0, 55.0, default=52.0, space='exit', decimals=2, optimize=False, load=True)
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
    exit_custom_under_rsi_0 = DecimalParameter(28.0, 40.0, default=38.0, space='exit', decimals=1, optimize=False, load=True)
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
    # Trail 3
    exit_trail_profit_min_4 = DecimalParameter(0.01, 0.12, default=0.03, space='exit', decimals=3, optimize=False, load=True)
    exit_trail_profit_max_4 = DecimalParameter(0.02, 0.1, default=0.06, space='exit', decimals=2, optimize=False, load=True)
    exit_trail_down_4 = DecimalParameter(0.01, 0.06, default=0.02, space='exit', decimals=3, optimize=False, load=True)
    # Under & near EMA200, accept profit
    exit_custom_profit_under_rel_1 = DecimalParameter(0.01, 0.04, default=0.024, space='exit', optimize=False, load=True)
    exit_custom_profit_under_rsi_diff_1 = DecimalParameter(0.0, 20.0, default=4.4, space='exit', optimize=False, load=True)
    # Under & near EMA200, take the loss
    exit_custom_stoploss_under_rel_1 = DecimalParameter(0.001, 0.02, default=0.002, space='exit', optimize=False, load=True)
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
    exit_custom_stoploss_pump_max_profit_1 = DecimalParameter(0.01, 0.04, default=0.01, space='exit', decimals=3, optimize=False, load=True)
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
    exit_custom_recover_profit_1 = DecimalParameter(0.01, 0.06, default=0.06, space='exit', decimals=3, optimize=False, load=True)
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
    hold_trade_ids = hold_trade_ids_profit_ratio = None

    def load_hold_trades_config(self):
        if self.hold_trade_ids is not None and self.hold_trade_ids_profit_ratio is not None:
            # Already loaded
            return
        # Default Values
        self.hold_trade_ids = set()
        self.hold_trade_ids_profit_ratio = 0.005
        # Update values from config file, if it exists
        strat_directory = pathlib.Path(__file__).resolve().parent
        hold_trades_config_file = strat_directory / 'hold-trades.json'
        if not hold_trades_config_file.is_file():
            return
        with hold_trades_config_file.open('r') as f:
            try:
                hold_trades_config = json_load(f)
            except rapidjson.JSONDecodeError as exc:
                log.error('Failed to load JSON from %s: %s', hold_trades_config_file, exc)
            else:
                profit_ratio = hold_trades_config.get('profit_ratio')
                if profit_ratio:
                    if not isinstance(profit_ratio, float):
                        log.error("The 'profit_ratio' config value(%s) in %s is not a float", profit_ratio, hold_trades_config_file)
                    else:
                        self.hold_trade_ids_profit_ratio = profit_ratio
                open_trades = {trade.id: trade for trade in Trade.get_trades_proxy(is_open=True)}
                formatted_profit_ratio = '{}%'.format(self.hold_trade_ids_profit_ratio * 100)
                for trade_id in hold_trades_config.get('trade_ids', ()):
                    if not isinstance(trade_id, int):
                        log.error("The trade_id(%s) defined under 'trade_ids' in %s is not an integer", trade_id, hold_trades_config_file)
                        continue
                    if trade_id in open_trades:
                        log.warning('The trade %s is configured to HOLD until the profit ratio of %s is met', open_trades[trade_id], formatted_profit_ratio)
                        self.hold_trade_ids.add(trade_id)
                    else:
                        log.warning("The trade_id(%s) is no longer open. Please remove it from 'trade_ids' in %s", trade_id, hold_trades_config_file)

    def bot_loop_start(self, **kwargs) -> None:
        """
        Called at the start of the bot iteration (one loop).
        Might be used to perform pair-independent tasks
        (e.g. gather some remote resource for comparison)
        :param **kwargs: Ensure to keep this here so updates to this won't break your strategy.
        """
        self.load_hold_trades_config()
        return super().bot_loop_start(**kwargs)

    def get_ticker_indicator(self):
        return int(self.timeframe[:-1])

    def exit_over_main(self, current_profit: float, last_candle) -> tuple:
        if last_candle['close'] > last_candle['ema_200']:
            if current_profit > self.exit_custom_profit_11.value:
                if last_candle['rsi'] < self.exit_custom_rsi_11.value:
                    return (True, 'signal_profit_11')
            elif self.exit_custom_profit_11.value > current_profit > self.exit_custom_profit_10.value:
                if last_candle['rsi'] < self.exit_custom_rsi_10.value:
                    return (True, 'signal_profit_10')
            elif self.exit_custom_profit_10.value > current_profit > self.exit_custom_profit_9.value:
                if last_candle['rsi'] < self.exit_custom_rsi_9.value:
                    return (True, 'signal_profit_9')
            elif self.exit_custom_profit_9.value > current_profit > self.exit_custom_profit_8.value:
                if last_candle['rsi'] < self.exit_custom_rsi_8.value:
                    return (True, 'signal_profit_8')
            elif self.exit_custom_profit_8.value > current_profit > self.exit_custom_profit_7.value:
                if (last_candle['rsi'] < self.exit_custom_rsi_7.value) & (last_candle['cmf'] < 0.0):
                    return (True, 'signal_profit_7')
            elif self.exit_custom_profit_7.value > current_profit > self.exit_custom_profit_6.value:
                if (last_candle['rsi'] < self.exit_custom_rsi_6.value) & (last_candle['cmf'] < 0.0):
                    return (True, 'signal_profit_6')
            elif self.exit_custom_profit_6.value > current_profit > self.exit_custom_profit_5.value:
                if (last_candle['rsi'] < self.exit_custom_rsi_5.value) & (last_candle['cmf'] < 0.0):
                    return (True, 'signal_profit_5')
            elif self.exit_custom_profit_5.value > current_profit > self.exit_custom_profit_4.value:
                if (last_candle['rsi'] < self.exit_custom_rsi_4.value) & (last_candle['cmf'] < 0.0):
                    return (True, 'signal_profit_4')
            elif self.exit_custom_profit_4.value > current_profit > self.exit_custom_profit_3.value:
                if (last_candle['rsi'] < self.exit_custom_rsi_3.value) & (last_candle['cmf'] < 0.0):
                    return (True, 'signal_profit_3')
            elif self.exit_custom_profit_3.value > current_profit > self.exit_custom_profit_2.value:
                if (last_candle['rsi'] < self.exit_custom_rsi_2.value) & (last_candle['cmf'] < 0.0):
                    return (True, 'signal_profit_2')
            elif self.exit_custom_profit_2.value > current_profit > self.exit_custom_profit_1.value:
                if (last_candle['rsi'] < self.exit_custom_rsi_1.value) & (last_candle['cmf'] < 0.0):
                    return (True, 'signal_profit_1')
            elif self.exit_custom_profit_1.value > current_profit > self.exit_custom_profit_0.value:
                if (last_candle['rsi'] < self.exit_custom_rsi_0.value) & (last_candle['cmf'] < 0.0):
                    return (True, 'signal_profit_0')
        return (False, None)

    def exit_under_main(self, current_profit: float, last_candle) -> tuple:
        if last_candle['close'] < last_candle['ema_200']:
            if current_profit > self.exit_custom_under_profit_11.value:
                if last_candle['rsi'] < self.exit_custom_under_rsi_11.value:
                    return (True, 'signal_profit_u_11')
            elif self.exit_custom_under_profit_11.value > current_profit > self.exit_custom_under_profit_10.value:
                if last_candle['rsi'] < self.exit_custom_under_rsi_10.value:
                    return (True, 'signal_profit_u_10')
            elif self.exit_custom_under_profit_10.value > current_profit > self.exit_custom_under_profit_9.value:
                if last_candle['rsi'] < self.exit_custom_under_rsi_9.value:
                    return (True, 'signal_profit_u_9')
            elif self.exit_custom_under_profit_9.value > current_profit > self.exit_custom_under_profit_8.value:
                if last_candle['rsi'] < self.exit_custom_under_rsi_8.value:
                    return (True, 'signal_profit_u_8')
            elif self.exit_custom_under_profit_8.value > current_profit > self.exit_custom_under_profit_7.value:
                if last_candle['rsi'] < self.exit_custom_under_rsi_7.value:
                    return (True, 'signal_profit_u_7')
            elif self.exit_custom_under_profit_7.value > current_profit > self.exit_custom_under_profit_6.value:
                if last_candle['rsi'] < self.exit_custom_under_rsi_6.value:
                    return (True, 'signal_profit_u_6')
            elif self.exit_custom_under_profit_6.value > current_profit > self.exit_custom_under_profit_5.value:
                if last_candle['rsi'] < self.exit_custom_under_rsi_5.value:
                    return (True, 'signal_profit_u_5')
            elif self.exit_custom_under_profit_5.value > current_profit > self.exit_custom_under_profit_4.value:
                if last_candle['rsi'] < self.exit_custom_under_rsi_4.value:
                    return (True, 'signal_profit_u_4')
            elif self.exit_custom_under_profit_4.value > current_profit > self.exit_custom_under_profit_3.value:
                if last_candle['rsi'] < self.exit_custom_under_rsi_3.value:
                    return (True, 'signal_profit_u_3')
            elif self.exit_custom_under_profit_3.value > current_profit > self.exit_custom_under_profit_2.value:
                if last_candle['rsi'] < self.exit_custom_under_rsi_2.value:
                    return (True, 'signal_profit_u_2')
            elif self.exit_custom_under_profit_2.value > current_profit > self.exit_custom_under_profit_1.value:
                if last_candle['rsi'] < self.exit_custom_under_rsi_1.value:
                    return (True, 'signal_profit_u_1')
            elif self.exit_custom_under_profit_1.value > current_profit > self.exit_custom_under_profit_0.value:
                if (last_candle['rsi'] < self.exit_custom_under_rsi_0.value) & (last_candle['cmf'] < 0.0):
                    return (True, 'signal_profit_u_0')
        return (False, None)

    def exit_pump_main(self, current_profit: float, last_candle) -> tuple:
        if last_candle['exit_pump_48_1_1h']:
            if current_profit > self.exit_custom_pump_profit_1_5.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_1_5.value:
                    return (True, 'signal_profit_p_1_5')
            elif self.exit_custom_pump_profit_1_5.value > current_profit > self.exit_custom_pump_profit_1_4.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_1_4.value:
                    return (True, 'signal_profit_p_1_4')
            elif self.exit_custom_pump_profit_1_4.value > current_profit > self.exit_custom_pump_profit_1_3.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_1_3.value:
                    return (True, 'signal_profit_p_1_3')
            elif self.exit_custom_pump_profit_1_3.value > current_profit > self.exit_custom_pump_profit_1_2.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_1_2.value:
                    return (True, 'signal_profit_p_1_2')
            elif self.exit_custom_pump_profit_1_2.value > current_profit > self.exit_custom_pump_profit_1_1.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_1_1.value:
                    return (True, 'signal_profit_p_1_1')
        elif last_candle['exit_pump_36_1_1h']:
            if current_profit > self.exit_custom_pump_profit_2_5.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_2_5.value:
                    return (True, 'signal_profit_p_2_5')
            elif self.exit_custom_pump_profit_2_5.value > current_profit > self.exit_custom_pump_profit_2_4.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_2_4.value:
                    return (True, 'signal_profit_p_2_4')
            elif self.exit_custom_pump_profit_2_4.value > current_profit > self.exit_custom_pump_profit_2_3.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_2_3.value:
                    return (True, 'signal_profit_p_2_3')
            elif self.exit_custom_pump_profit_2_3.value > current_profit > self.exit_custom_pump_profit_2_2.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_2_2.value:
                    return (True, 'signal_profit_p_2_2')
            elif self.exit_custom_pump_profit_2_2.value > current_profit > self.exit_custom_pump_profit_2_1.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_2_1.value:
                    return (True, 'signal_profit_p_2_1')
        elif last_candle['exit_pump_24_1_1h']:
            if current_profit > self.exit_custom_pump_profit_3_5.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_3_5.value:
                    return (True, 'signal_profit_p_3_5')
            elif self.exit_custom_pump_profit_3_5.value > current_profit > self.exit_custom_pump_profit_3_4.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_3_4.value:
                    return (True, 'signal_profit_p_3_4')
            elif self.exit_custom_pump_profit_3_4.value > current_profit > self.exit_custom_pump_profit_3_3.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_3_3.value:
                    return (True, 'signal_profit_p_3_3')
            elif self.exit_custom_pump_profit_3_3.value > current_profit > self.exit_custom_pump_profit_3_2.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_3_2.value:
                    return (True, 'signal_profit_p_3_2')
            elif self.exit_custom_pump_profit_3_2.value > current_profit > self.exit_custom_pump_profit_3_1.value:
                if last_candle['rsi'] < self.exit_custom_pump_rsi_3_1.value:
                    return (True, 'signal_profit_p_3_1')
        return (False, None)

    def exit_dec_main(self, current_profit: float, last_candle) -> tuple:
        if (self.exit_custom_dec_profit_max_1.value > current_profit > self.exit_custom_dec_profit_min_1.value) & last_candle['sma_200_dec_20']:
            return (True, 'signal_profit_d_1')
        elif (self.exit_custom_dec_profit_max_2.value > current_profit > self.exit_custom_dec_profit_min_2.value) & (last_candle['close'] < last_candle['ema_100']):
            return (True, 'signal_profit_d_2')
        return (False, None)

    def exit_trail_main(self, current_profit: float, last_candle, max_profit: float) -> tuple:
        if (self.exit_trail_profit_max_1.value > current_profit > self.exit_trail_profit_min_1.value) & (self.exit_trail_rsi_min_1.value < last_candle['rsi'] < self.exit_trail_rsi_max_1.value) & (max_profit > current_profit + self.exit_trail_down_1.value):
            return (True, 'signal_profit_t_1')
        elif (self.exit_trail_profit_max_2.value > current_profit > self.exit_trail_profit_min_2.value) & (self.exit_trail_rsi_min_2.value < last_candle['rsi'] < self.exit_trail_rsi_max_2.value) & (max_profit > current_profit + self.exit_trail_down_2.value) & (last_candle['ema_25'] < last_candle['ema_50']):
            return (True, 'signal_profit_t_2')
        elif (self.exit_trail_profit_max_3.value > current_profit > self.exit_trail_profit_min_3.value) & (max_profit > current_profit + self.exit_trail_down_3.value) & last_candle['sma_200_dec_20_1h']:
            return (True, 'signal_profit_t_3')
        elif (self.exit_trail_profit_max_4.value > current_profit > self.exit_trail_profit_min_4.value) & (max_profit > current_profit + self.exit_trail_down_4.value) & last_candle['sma_200_dec_24'] & (last_candle['cmf'] < 0.0):
            return (True, 'signal_profit_t_4')
        elif (last_candle['close'] < last_candle['ema_200']) & (current_profit > self.exit_trail_profit_min_3.value) & (current_profit < self.exit_trail_profit_max_3.value) & (max_profit > current_profit + self.exit_trail_down_3.value):
            return (True, 'signal_profit_u_t_1')
        return (False, None)

    def exit_duration_main(self, current_profit: float, last_candle, trade: 'Trade', current_time: 'datetime') -> tuple:
        # Pumped pair, short duration
        if last_candle['exit_pump_24_1_1h'] & (0.2 > current_profit > 0.07) & (current_time - timedelta(minutes=30) < trade.open_date_utc):
            return (True, 'signal_profit_p_s_1')
        elif (self.exit_custom_long_profit_min_1.value < current_profit < self.exit_custom_long_profit_max_1.value) & (current_time - timedelta(minutes=self.exit_custom_long_duration_min_1.value) > trade.open_date_utc):
            return (True, 'signal_profit_l_1')
        return (False, None)

    def exit_under_min(self, current_profit: float, last_candle) -> tuple:
        if (current_profit > 0.0) & (last_candle['close'] < last_candle['ema_200']) & ((last_candle['ema_200'] - last_candle['close']) / last_candle['close'] < self.exit_custom_profit_under_rel_1.value) & (last_candle['rsi'] > last_candle['rsi_1h'] + self.exit_custom_profit_under_rsi_diff_1.value):
            return (True, 'signal_profit_u_e_1')
        return (False, None)

    def exit_stoploss(self, current_profit: float, last_candle, trade: 'Trade', current_time: 'datetime', max_loss: float, max_profit: float) -> tuple:
        if (current_profit < -0.0) & (last_candle['close'] < last_candle['ema_200']) & ((last_candle['ema_200'] - last_candle['close']) / last_candle['close'] < self.exit_custom_stoploss_under_rel_1.value) & (last_candle['rsi'] > last_candle['rsi_1h'] + self.exit_custom_stoploss_under_rsi_diff_1.value) & (last_candle['cmf'] < -0.2) & last_candle['sma_200_dec_24'] & (current_time - timedelta(minutes=720) > trade.open_date_utc):
            return (True, 'signal_stoploss_u_1')
        # Under EMA200, pair & BTC negative, low max rate
        elif (-0.03 > current_profit > -0.07) & (last_candle['btc_not_downtrend_1h'] is False) & (max_profit < 0.005) & last_candle['sma_200_dec_24'] & (last_candle['cmf'] < 0.0) & (last_candle['close'] < last_candle['ema_200']) & (last_candle['ema_25'] < last_candle['ema_50']):
            return (True, 'signal_stoploss_u_b_1')
        elif (self.exit_custom_stoploss_long_profit_min_1.value < current_profit < self.exit_custom_stoploss_long_profit_max_1.value) & (current_profit > -max_loss + self.exit_custom_stoploss_long_recover_1.value) & (last_candle['cmf'] < 0.0) & (last_candle['close'] < last_candle['ema_200']) & (last_candle['rsi'] > last_candle['rsi_1h'] + self.exit_custom_stoploss_long_rsi_diff_1.value) & last_candle['sma_200_dec_24'] & (current_time - timedelta(minutes=1200) > trade.open_date_utc):
            return (True, 'signal_stoploss_l_r_u_1')
        elif (current_profit < -0.0) & (current_profit > -max_loss + self.exit_custom_stoploss_long_recover_2.value) & (last_candle['close'] < last_candle['ema_200']) & (last_candle['cmf'] < 0.0) & (last_candle['rsi'] > last_candle['rsi_1h'] + self.exit_custom_stoploss_long_rsi_diff_2.value) & last_candle['sma_200_dec_24'] & (current_time - timedelta(minutes=1200) > trade.open_date_utc):
            return (True, 'signal_stoploss_l_r_u_2')
        elif (max_profit < self.exit_custom_stoploss_pump_max_profit_2.value) & (current_profit < self.exit_custom_stoploss_pump_loss_2.value) & last_candle['exit_pump_48_1_1h'] & (last_candle['cmf'] < 0.0) & last_candle['sma_200_dec_20_1h'] & (last_candle['close'] < last_candle['ema_200'] * self.exit_custom_stoploss_pump_ma_offset_2.value):
            return (True, 'signal_stoploss_p_2')
        elif (max_profit < self.exit_custom_stoploss_pump_max_profit_3.value) & (current_profit < self.exit_custom_stoploss_pump_loss_3.value) & last_candle['exit_pump_36_3_1h'] & (last_candle['close'] < last_candle['ema_200'] * self.exit_custom_stoploss_pump_ma_offset_3.value):
            return (True, 'signal_stoploss_p_3')
        return (False, None)

    def exit_pump_dec(self, current_profit: float, last_candle) -> tuple:
        if (self.exit_custom_pump_dec_profit_max_1.value > current_profit > self.exit_custom_pump_dec_profit_min_1.value) & last_candle['exit_pump_48_1_1h'] & last_candle['sma_200_dec_20'] & (last_candle['close'] < last_candle['ema_200']):
            return (True, 'signal_profit_p_d_1')
        elif (self.exit_custom_pump_dec_profit_max_2.value > current_profit > self.exit_custom_pump_dec_profit_min_2.value) & last_candle['exit_pump_48_2_1h'] & last_candle['sma_200_dec_20'] & (last_candle['close'] < last_candle['ema_200']):
            return (True, 'signal_profit_p_d_2')
        elif (self.exit_custom_pump_dec_profit_max_3.value > current_profit > self.exit_custom_pump_dec_profit_min_3.value) & last_candle['exit_pump_48_3_1h'] & last_candle['sma_200_dec_20'] & (last_candle['close'] < last_candle['ema_200']):
            return (True, 'signal_profit_p_d_3')
        elif (self.exit_custom_pump_dec_profit_max_4.value > current_profit > self.exit_custom_pump_dec_profit_min_4.value) & last_candle['sma_200_dec_20'] & last_candle['exit_pump_24_2_1h']:
            return (True, 'signal_profit_p_d_4')
        return (False, None)

    def exit_pump_extra(self, current_profit: float, last_candle, max_profit: float) -> tuple:
        # Pumped 48h 1, under EMA200
        if (self.exit_custom_pump_under_profit_max_1.value > current_profit > self.exit_custom_pump_under_profit_min_1.value) & last_candle['exit_pump_48_1_1h'] & (last_candle['close'] < last_candle['ema_200']):
            return (True, 'signal_profit_p_u_1')
        # Pumped 36h 2, trail 1
        elif last_candle['exit_pump_36_2_1h'] & (self.exit_custom_pump_trail_profit_max_1.value > current_profit > self.exit_custom_pump_trail_profit_min_1.value) & (self.exit_custom_pump_trail_rsi_min_1.value < last_candle['rsi'] < self.exit_custom_pump_trail_rsi_max_1.value) & (max_profit > current_profit + self.exit_custom_pump_trail_down_1.value):
            return (True, 'signal_profit_p_t_1')
        return (False, None)

    def exit_recover(self, current_profit: float, last_candle, max_loss: float) -> tuple:
        if (max_loss > self.exit_custom_recover_min_loss_1.value) & (current_profit > self.exit_custom_recover_profit_1.value):
            return (True, 'signal_profit_r_1')
        elif (max_loss > self.exit_custom_recover_min_loss_2.value) & (self.exit_custom_recover_profit_max_2.value > current_profit > self.exit_custom_recover_profit_min_2.value) & (last_candle['rsi'] < self.exit_custom_recover_rsi_2.value) & (last_candle['ema_25'] < last_candle['ema_50']):
            return (True, 'signal_profit_r_2')
        return (False, None)

    def exit_r_1(self, current_profit: float, last_candle) -> tuple:
        if 0.02 > current_profit > 0.012:
            if last_candle['r_480'] > -2.0:
                return (True, 'signal_profit_w_1_1')
        elif 0.03 > current_profit > 0.02:
            if last_candle['r_480'] > -2.1:
                return (True, 'signal_profit_w_1_2')
        elif 0.04 > current_profit > 0.03:
            if last_candle['r_480'] > -2.2:
                return (True, 'signal_profit_w_1_3')
        elif 0.05 > current_profit > 0.04:
            if last_candle['r_480'] > -2.3:
                return (True, 'signal_profit_w_1_4')
        elif 0.06 > current_profit > 0.05:
            if last_candle['r_480'] > -2.4:
                return (True, 'signal_profit_w_1_5')
        elif 0.07 > current_profit > 0.06:
            if last_candle['r_480'] > -2.5:  ###
                return (True, 'signal_profit_w_1_6')
        elif 0.08 > current_profit > 0.07:
            if last_candle['r_480'] > -2.6:
                return (True, 'signal_profit_w_1_7')
        elif 0.09 > current_profit > 0.08:
            if last_candle['r_480'] > -5.5:
                return (True, 'signal_profit_w_1_8')
        elif 0.1 > current_profit > 0.09:
            if last_candle['r_480'] > -3.0:
                return (True, 'signal_profit_w_1_9')
        elif 0.12 > current_profit > 0.1:
            if last_candle['r_480'] > -8.0:
                return (True, 'signal_profit_w_1_10')
        elif 0.2 > current_profit > 0.12:
            if (last_candle['r_480'] > -2.0) & (last_candle['rsi'] > 78.0):
                return (True, 'signal_profit_w_1_11')
        elif current_profit > 0.2:
            if (last_candle['r_480'] > -1.5) & (last_candle['rsi'] > 80.0):
                return (True, 'signal_profit_w_1_12')
        return (False, None)

    def exit_r_2(self, current_profit: float, last_candle) -> tuple:
        if 0.02 > current_profit > 0.012:
            if (last_candle['r_480'] > -2.0) & (last_candle['rsi'] > 79.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_1')
        elif 0.03 > current_profit > 0.02:
            if (last_candle['r_480'] > -2.1) & (last_candle['rsi'] > 79.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_2')
        elif 0.04 > current_profit > 0.03:
            if (last_candle['r_480'] > -2.2) & (last_candle['rsi'] > 79.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_3')
        elif 0.05 > current_profit > 0.04:
            if (last_candle['r_480'] > -2.3) & (last_candle['rsi'] > 79.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_4')
        elif 0.06 > current_profit > 0.05:
            if (last_candle['r_480'] > -2.4) & (last_candle['rsi'] > 79.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_5')
        elif 0.07 > current_profit > 0.06:
            if (last_candle['r_480'] > -2.5) & (last_candle['rsi'] > 79.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_6')
        elif 0.08 > current_profit > 0.07:
            if (last_candle['r_480'] > -34.0) & (last_candle['rsi'] > 80.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_7')
        elif 0.09 > current_profit > 0.08:
            if (last_candle['r_480'] > -3.0) & (last_candle['rsi'] > 80.5) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_8')
        elif 0.1 > current_profit > 0.09:
            if (last_candle['r_480'] > -2.8) & (last_candle['rsi'] > 80.5) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_9')
        elif 0.12 > current_profit > 0.1:
            if (last_candle['r_480'] > -2.4) & (last_candle['rsi'] > 80.5) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_10')
        elif 0.2 > current_profit > 0.12:
            if (last_candle['r_480'] > -2.2) & (last_candle['rsi'] > 81.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_11')
        elif current_profit > 0.2:
            if (last_candle['r_480'] > -2.0) & (last_candle['rsi'] > 81.5) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_2_12')
        return (False, None)

    def exit_r_3(self, current_profit: float, last_candle) -> tuple:
        if 0.02 > current_profit > 0.012:
            if (last_candle['r_480'] > -6.0) & (last_candle['rsi'] > 74.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_3_1')
        elif 0.03 > current_profit > 0.02:
            if (last_candle['r_480'] > -8.0) & (last_candle['rsi'] > 74.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_3_2')
        elif 0.04 > current_profit > 0.03:
            if (last_candle['r_480'] > -29.0) & (last_candle['rsi'] > 74.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_3_3')
        elif 0.05 > current_profit > 0.04:
            if (last_candle['r_480'] > -30.0) & (last_candle['rsi'] > 79.0) & (last_candle['stochrsi_fastk_96'] > 99.0) & (last_candle['stochrsi_fastd_96'] > 99.0):
                return (True, 'signal_profit_w_3_4')
        return (False, None)

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float, current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        previous_candle_1 = dataframe.iloc[-2].squeeze()
        previous_candle_2 = dataframe.iloc[-3].squeeze()
        previous_candle_3 = dataframe.iloc[-4].squeeze()
        previous_candle_4 = dataframe.iloc[-5].squeeze()
        previous_candle_5 = dataframe.iloc[-6].squeeze()
        max_profit = (trade.max_rate - trade.open_rate) / trade.open_rate
        max_loss = (trade.open_rate - trade.min_rate) / trade.min_rate
        if (last_candle is not None) & (previous_candle_1 is not None) & (previous_candle_2 is not None) & (previous_candle_3 is not None) & (previous_candle_4 is not None) & (previous_candle_5 is not None):
            # Over EMA200, main profit targets
            exit_long, signal_name = self.exit_over_main(current_profit, last_candle)
            if exit_long and signal_name is not None:
                return signal_name
            # Under EMA200, main profit targets
            exit_long, signal_name = self.exit_under_main(current_profit, last_candle)
            if exit_long and signal_name is not None:
                return signal_name
            # The pair is pumped
            exit_long, signal_name = self.exit_pump_main(current_profit, last_candle)
            if exit_long and signal_name is not None:
                return signal_name
            # The pair is descending
            exit_long, signal_name = self.exit_dec_main(current_profit, last_candle)
            if exit_long and signal_name is not None:
                return signal_name
            # Trailing
            exit_long, signal_name = self.exit_trail_main(current_profit, last_candle, max_profit)
            if exit_long and signal_name is not None:
                return signal_name
            # Duration based
            exit_long, signal_name = self.exit_duration_main(current_profit, last_candle, trade, current_time)
            if exit_long and signal_name is not None:
                return signal_name
            # Under EMA200, exit with any profit
            exit_long, signal_name = self.exit_under_min(current_profit, last_candle)
            if exit_long and signal_name is not None:
                return signal_name
            # Stoplosses
            exit_long, signal_name = self.exit_stoploss(current_profit, last_candle, trade, current_time, max_loss, max_profit)
            if exit_long and signal_name is not None:
                return signal_name
            # Pumped descending pairs
            exit_long, signal_name = self.exit_pump_dec(current_profit, last_candle)
            if exit_long and signal_name is not None:
                return signal_name
            # Extra exits for pumped pairs
            exit_long, signal_name = self.exit_pump_extra(current_profit, last_candle, max_profit)
            if exit_long and signal_name is not None:
                return signal_name
            # Extra exits for trades that recovered
            exit_long, signal_name = self.exit_recover(current_profit, last_candle, max_loss)
            if exit_long and signal_name is not None:
                return signal_name
            # Williams %R based exit 1
            exit_long, signal_name = self.exit_r_1(current_profit, last_candle)
            if exit_long and signal_name is not None:
                return signal_name
            # Williams %R based exit 2
            exit_long, signal_name = self.exit_r_2(current_profit, last_candle)
            if exit_long and signal_name is not None:
                return signal_name
            # Williams %R based exit 3
            exit_long, signal_name = self.exit_r_3(current_profit, last_candle)
            if exit_long and signal_name is not None:
                return signal_name
            # Sell signal 1
            if self.exit_condition_1_enable.value & (last_candle['rsi'] > self.exit_rsi_bb_1.value) & (last_candle['close'] > last_candle['bb20_2_upp']) & (previous_candle_1['close'] > previous_candle_1['bb20_2_upp']) & (previous_candle_2['close'] > previous_candle_2['bb20_2_upp']) & (previous_candle_3['close'] > previous_candle_3['bb20_2_upp']) & (previous_candle_4['close'] > previous_candle_4['bb20_2_upp']) & (previous_candle_5['close'] > previous_candle_5['bb20_2_upp']):
                return 'exit_signal_1'
            # Sell signal 2
            elif self.exit_condition_2_enable.value & (last_candle['rsi'] > self.exit_rsi_bb_2.value) & (last_candle['close'] > last_candle['bb20_2_upp']) & (previous_candle_1['close'] > previous_candle_1['bb20_2_upp']) & (previous_candle_2['close'] > previous_candle_2['bb20_2_upp']):
                return 'exit_signal_2'
            # Sell signal 3
            # elif (self.exit_condition_3_enable.value) & (last_candle['rsi'] > self.exit_rsi_main_3.value):
            #     return 'exit_signal_3'
            # Sell signal 4
            elif self.exit_condition_4_enable.value & (last_candle['rsi'] > self.exit_dual_rsi_rsi_4.value) & (last_candle['rsi_1h'] > self.exit_dual_rsi_rsi_1h_4.value):
                return 'exit_signal_4'
            # Sell signal 6
            elif self.exit_condition_6_enable.value & (last_candle['close'] < last_candle['ema_200']) & (last_candle['close'] > last_candle['ema_50']) & (last_candle['rsi'] > self.exit_rsi_under_6.value):
                return 'exit_signal_6'
            # Sell signal 7
            elif self.exit_condition_7_enable.value & (last_candle['rsi_1h'] > self.exit_rsi_1h_7.value) & last_candle['crossed_below_ema_12_26']:
                return 'exit_signal_7'
            # Sell signal 8
            elif self.exit_condition_8_enable.value & (last_candle['close'] > last_candle['bb20_2_upp_1h'] * self.exit_bb_relative_8.value):
                return 'exit_signal_8'
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
        informative_pairs = [(pair, self.info_timeframe) for pair in pairs]
        informative_pairs.append(('BTC/USDT', self.timeframe))
        informative_pairs.append(('BTC/USDT', self.info_timeframe))
        return informative_pairs

    def informative_1h_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        assert self.dp, 'DataProvider is required for multiple timeframes.'
        # Get the informative pair
        informative_1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=self.info_timeframe)
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
        # Williams %R
        informative_1h['r_480'] = williams_r(informative_1h, period=480)
        # Pump protections
        informative_1h['hl_pct_change_48'] = self.range_percent_change(informative_1h, 'HL', 48)
        informative_1h['hl_pct_change_36'] = self.range_percent_change(informative_1h, 'HL', 36)
        informative_1h['hl_pct_change_24'] = self.range_percent_change(informative_1h, 'HL', 24)
        informative_1h['oc_pct_change_48'] = self.range_percent_change(informative_1h, 'OC', 48)
        informative_1h['oc_pct_change_36'] = self.range_percent_change(informative_1h, 'OC', 36)
        informative_1h['oc_pct_change_24'] = self.range_percent_change(informative_1h, 'OC', 24)
        informative_1h['hl_pct_change_5'] = self.range_percent_change(informative_1h, 'HL', 5)
        informative_1h['low_5'] = informative_1h['low'].shift().rolling(5).min()
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
        informative_1h['safe_dump_10'] = (informative_1h['hl_pct_change_5'] < self.entry_dump_protection_10_5.value) | (informative_1h['close'] < informative_1h['low_5']) | (informative_1h['close'] > informative_1h['open'])
        informative_1h['safe_dump_20'] = (informative_1h['hl_pct_change_5'] < self.entry_dump_protection_20_5.value) | (informative_1h['close'] < informative_1h['low_5']) | (informative_1h['close'] > informative_1h['open'])
        informative_1h['safe_dump_30'] = (informative_1h['hl_pct_change_5'] < self.entry_dump_protection_30_5.value) | (informative_1h['close'] < informative_1h['low_5']) | (informative_1h['close'] > informative_1h['open'])
        informative_1h['safe_dump_40'] = (informative_1h['hl_pct_change_5'] < self.entry_dump_protection_40_5.value) | (informative_1h['close'] < informative_1h['low_5']) | (informative_1h['close'] > informative_1h['open'])
        informative_1h['safe_dump_50'] = (informative_1h['hl_pct_change_5'] < self.entry_dump_protection_50_5.value) | (informative_1h['close'] < informative_1h['low_5']) | (informative_1h['close'] > informative_1h['open'])
        informative_1h['safe_dump_60'] = (informative_1h['hl_pct_change_5'] < self.entry_dump_protection_60_5.value) | (informative_1h['close'] < informative_1h['low_5']) | (informative_1h['close'] > informative_1h['open'])
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
        dataframe['ema_25'] = ta.EMA(dataframe, timeperiod=25)
        dataframe['ema_26'] = ta.EMA(dataframe, timeperiod=26)
        dataframe['ema_35'] = ta.EMA(dataframe, timeperiod=35)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        # SMA
        dataframe['sma_5'] = ta.SMA(dataframe, timeperiod=5)
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['sma_30'] = ta.SMA(dataframe, timeperiod=30)
        dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=200)
        dataframe['sma_200_dec_20'] = dataframe['sma_200'] < dataframe['sma_200'].shift(20)
        dataframe['sma_200_dec_24'] = dataframe['sma_200'] < dataframe['sma_200'].shift(24)
        # MFI
        dataframe['mfi'] = ta.MFI(dataframe)
        # CMF
        dataframe['cmf'] = chaikin_money_flow(dataframe, 20)
        # EWO
        dataframe['ewo'] = ewo(dataframe, 50, 200)
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_4'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_20'] = ta.RSI(dataframe, timeperiod=20)
        # Chopiness
        dataframe['chop'] = qtpylib.chopiness(dataframe, 14)
        # Zero-Lag EMA
        dataframe['zema'] = zema(dataframe, period=61)
        # Williams %R
        dataframe['r_480'] = williams_r(dataframe, period=480)
        # Stochastic RSI
        stochrsi = ta.STOCHRSI(dataframe, timeperiod=96, fastk_period=3, fastd_period=3, fastd_matype=0)
        dataframe['stochrsi_fastk_96'] = stochrsi['fastk']
        dataframe['stochrsi_fastd_96'] = stochrsi['fastd']
        # Modified Elder Ray Index
        dataframe['moderi_64'] = moderi(dataframe, 64)
        # TSI
        dataframe['tsi_slow'] = tsi(dataframe, window_slow=20, window_fast=5)
        dataframe['tsi_ema_slow'] = ta.EMA(dataframe['tsi_slow'], timeperiod=5)
        dataframe['tsi_fast'] = tsi(dataframe, window_slow=4, window_fast=2)
        dataframe['tsi_ema_fast'] = ta.EMA(dataframe['tsi_fast'], timeperiod=2)
        # hull
        dataframe['hull_75'] = hull(dataframe, 75)
        # zlema
        dataframe['zlema_68'] = zlema(dataframe, 68)
        # For exit checks
        dataframe['crossed_below_ema_12_26'] = qtpylib.crossed_below(dataframe['ema_12'], dataframe['ema_26'])
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

    def resampled_tf_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Indicators
        # -----------------------------------------------------------------------------------------
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def base_tf_btc_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Indicators
        # -----------------------------------------------------------------------------------------
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        # Add prefix
        # -----------------------------------------------------------------------------------------
        ignore_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        dataframe.rename(columns=lambda s: 'btc_' + s if not s in ignore_columns else s, inplace=True)
        return dataframe

    def info_tf_btc_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Indicators
        # -----------------------------------------------------------------------------------------
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['not_downtrend'] = (dataframe['close'] > dataframe['close'].shift(2)) | (dataframe['rsi'] > 50)
        # Add prefix
        # -----------------------------------------------------------------------------------------
        ignore_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        dataframe.rename(columns=lambda s: 'btc_' + s if not s in ignore_columns else s, inplace=True)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        --> BTC informative (5m/1h)
        ___________________________________________________________________________________________
        """
        if self.has_BTC_base_tf:
            btc_base_tf = self.dp.get_pair_dataframe('BTC/USDT', self.timeframe)
            btc_base_tf = self.base_tf_btc_indicators(btc_base_tf, metadata)
            dataframe = merge_informative_pair(dataframe, btc_base_tf, self.timeframe, self.timeframe, ffill=True)
            drop_columns = [s + '_' + self.timeframe for s in ['date', 'open', 'high', 'low', 'close', 'volume']]
            dataframe.drop(columns=dataframe.columns.intersection(drop_columns), inplace=True)
        if self.has_BTC_info_tf:
            btc_info_tf = self.dp.get_pair_dataframe('BTC/USDT', self.info_timeframe)
            btc_info_tf = self.info_tf_btc_indicators(btc_info_tf, metadata)
            dataframe = merge_informative_pair(dataframe, btc_info_tf, self.timeframe, self.info_timeframe, ffill=True)
            drop_columns = [s + '_' + self.info_timeframe for s in ['date', 'open', 'high', 'low', 'close', 'volume']]
            dataframe.drop(columns=dataframe.columns.intersection(drop_columns), inplace=True)
        '\n        --> Informative timeframe\n        ___________________________________________________________________________________________\n        '
        if self.info_timeframe != 'none':
            informative_1h = self.informative_1h_indicators(dataframe, metadata)
            dataframe = merge_informative_pair(dataframe, informative_1h, self.timeframe, self.info_timeframe, ffill=True)
            drop_columns = [s + '_' + self.info_timeframe for s in ['date']]
            dataframe.drop(columns=dataframe.columns.intersection(drop_columns), inplace=True)
        '\n        --> Resampled to another timeframe\n        ___________________________________________________________________________________________\n        '
        if self.res_timeframe != 'none':
            resampled = resample_to_interval(dataframe, timeframe_to_minutes(self.res_timeframe))
            resampled = self.resampled_tf_indicators(resampled, metadata)
            # Merge resampled info dataframe
            dataframe = resampled_merge(dataframe, resampled, fill_na=True)
            dataframe.rename(columns=lambda s: s + '_{}'.format(self.res_timeframe) if 'resample_' in s else s, inplace=True)
            dataframe.rename(columns=lambda s: s.replace('resample_{}_'.format(self.res_timeframe.replace('m', '')), ''), inplace=True)
            drop_columns = [s + '_' + self.res_timeframe for s in ['date']]
            dataframe.drop(columns=dataframe.columns.intersection(drop_columns), inplace=True)
        '\n        --> The indicators for the normal (5m) timeframe\n        ___________________________________________________________________________________________\n        '
        dataframe = self.normal_tf_indicators(dataframe, metadata)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        entry_protection_list = []
        # Protections [STANDARD] - Common to every condition
        for index in self.entry_protection_params:
            item_entry_protection_list = [True]
            global_entry_protection_params = self.entry_protection_params[index]
            if global_entry_protection_params['ema_fast'].value:
                item_entry_protection_list.append(dataframe[f"ema_{global_entry_protection_params['ema_fast_len'].value}"] > dataframe['ema_200'])
            if global_entry_protection_params['ema_slow'].value:
                item_entry_protection_list.append(dataframe[f"ema_{global_entry_protection_params['ema_slow_len'].value}_1h"] > dataframe['ema_200_1h'])
            if global_entry_protection_params['close_above_ema_fast'].value:
                item_entry_protection_list.append(dataframe['close'] > dataframe[f"ema_{global_entry_protection_params['close_above_ema_fast_len'].value}"])
            if global_entry_protection_params['close_above_ema_slow'].value:
                item_entry_protection_list.append(dataframe['close'] > dataframe[f"ema_{global_entry_protection_params['close_above_ema_slow_len'].value}_1h"])
            if global_entry_protection_params['sma200_rising'].value:
                item_entry_protection_list.append(dataframe['sma_200'] > dataframe['sma_200'].shift(int(global_entry_protection_params['sma200_rising_val'].value)))
            if global_entry_protection_params['sma200_1h_rising'].value:
                item_entry_protection_list.append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(int(global_entry_protection_params['sma200_1h_rising_val'].value)))
            if global_entry_protection_params['safe_dips'].value:
                item_entry_protection_list.append(dataframe[f"safe_dips_{global_entry_protection_params['safe_dips_type'].value}"])
            if global_entry_protection_params['safe_pump'].value:
                item_entry_protection_list.append(dataframe[f"safe_pump_{global_entry_protection_params['safe_pump_period'].value}_{global_entry_protection_params['safe_pump_type'].value}_1h"])
            if global_entry_protection_params['btc_1h_not_downtrend'].value:
                item_entry_protection_list.append(dataframe['btc_not_downtrend_1h'])
            entry_protection_list.append(item_entry_protection_list)
        # Buy Condition #1
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_1_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[0]))
            item_entry_logic.append((dataframe['close'] - dataframe['open'].rolling(36).min()) / dataframe['open'].rolling(36).min() > self.entry_min_inc_1.value)
            item_entry_logic.append(dataframe['rsi_1h'] > self.entry_rsi_1h_min_1.value)
            item_entry_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_max_1.value)
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_1.value)
            item_entry_logic.append(dataframe['mfi'] < self.entry_mfi_1.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #2
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_2_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[1]))
            item_entry_logic.append(dataframe['rsi'] < dataframe['rsi_1h'] - self.entry_rsi_1h_diff_2.value)
            item_entry_logic.append(dataframe['mfi'] < self.entry_mfi_2.value)
            item_entry_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_2.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #3
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_3_enable']:
            # Non-Standard protections (add below)
            entry_protection_list[2].append(dataframe['close'] > dataframe['ema_200_1h'] * self.entry_ema_rel_3.value)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[2]))
            item_entry_logic.append(dataframe['bb40_2_low'].shift().gt(0))
            item_entry_logic.append(dataframe['bb40_2_delta'].gt(dataframe['close'] * self.entry_bb40_bbdelta_close_3.value))
            item_entry_logic.append(dataframe['closedelta'].gt(dataframe['close'] * self.entry_bb40_closedelta_close_3.value))
            item_entry_logic.append(dataframe['tail'].lt(dataframe['bb40_2_delta'] * self.entry_bb40_tail_bbdelta_3.value))
            item_entry_logic.append(dataframe['close'].lt(dataframe['bb40_2_low'].shift()))
            item_entry_logic.append(dataframe['close'].le(dataframe['close'].shift()))
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #4
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_4_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[3]))
            item_entry_logic.append(dataframe['close'] < dataframe['ema_50'])
            item_entry_logic.append(dataframe['close'] < self.entry_bb20_close_bblowerband_4.value * dataframe['bb20_2_low'])
            item_entry_logic.append(dataframe['volume'] < dataframe['volume_mean_30'].shift(1) * self.entry_bb20_volume_4.value)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #5
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_5_enable']:
            # Non-Standard protections (add below)
            entry_protection_list[4].append(dataframe['close'] > dataframe['ema_200_1h'] * self.entry_ema_rel_5.value)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[4]))
            item_entry_logic.append(dataframe['ema_26'] > dataframe['ema_12'])
            item_entry_logic.append(dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_open_mult_5.value)
            item_entry_logic.append(dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100)
            item_entry_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_5.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #6
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_6_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[5]))
            item_entry_logic.append(dataframe['ema_26'] > dataframe['ema_12'])
            item_entry_logic.append(dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_open_mult_6.value)
            item_entry_logic.append(dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100)
            item_entry_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_6.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #7
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_7_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[6]))
            item_entry_logic.append(dataframe['ema_26'] > dataframe['ema_12'])
            item_entry_logic.append(dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_open_mult_7.value)
            item_entry_logic.append(dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100)
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_7.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #8
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_8_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[7]))
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_8.value)
            item_entry_logic.append(dataframe['volume'] > dataframe['volume'].shift(1) * self.entry_volume_8.value)
            item_entry_logic.append(dataframe['close'] > dataframe['open'])
            item_entry_logic.append(dataframe['close'] - dataframe['low'] > (dataframe['close'] - dataframe['open']) * self.entry_tail_diff_8.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #9
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_9_enable']:
            # Non-Standard protections (add below)
            entry_protection_list[8].append(dataframe['ema_50'] > dataframe['ema_200'])
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[8]))
            item_entry_logic.append(dataframe['close'] < dataframe['ema_20'] * self.entry_ma_offset_9.value)
            item_entry_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_9.value)
            item_entry_logic.append(dataframe['rsi_1h'] > self.entry_rsi_1h_min_9.value)
            item_entry_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_max_9.value)
            item_entry_logic.append(dataframe['mfi'] < self.entry_mfi_9.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #10
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_10_enable']:
            # Non-Standard protections (add below)
            entry_protection_list[9].append(dataframe['ema_50_1h'] > dataframe['ema_100_1h'])
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[9]))
            item_entry_logic.append(dataframe['close'] < dataframe['sma_30'] * self.entry_ma_offset_10.value)
            item_entry_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_10.value)
            item_entry_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_10.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #11
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_11_enable']:
            # Non-Standard protections (add below)
            entry_protection_list[10].append(dataframe['ema_50_1h'] > dataframe['ema_100_1h'])
            entry_protection_list[10].append(dataframe['safe_pump_36_50_1h'])
            entry_protection_list[10].append(dataframe['safe_pump_48_100_1h'])
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[10]))
            item_entry_logic.append((dataframe['close'] - dataframe['open'].rolling(36).min()) / dataframe['open'].rolling(36).min() > self.entry_min_inc_11.value)
            item_entry_logic.append(dataframe['close'] < dataframe['sma_30'] * self.entry_ma_offset_11.value)
            item_entry_logic.append(dataframe['rsi_1h'] > self.entry_rsi_1h_min_11.value)
            item_entry_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_max_11.value)
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_11.value)
            item_entry_logic.append(dataframe['mfi'] < self.entry_mfi_11.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #12
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_12_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[11]))
            item_entry_logic.append(dataframe['close'] < dataframe['sma_30'] * self.entry_ma_offset_12.value)
            item_entry_logic.append(dataframe['ewo'] > self.entry_ewo_12.value)
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_12.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #13
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_13_enable']:
            # Non-Standard protections (add below)
            entry_protection_list[12].append(dataframe['ema_50_1h'] > dataframe['ema_100_1h'])
            # entry_13_protections.append(dataframe['safe_pump_36_loose_1h'])
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[12]))
            item_entry_logic.append(dataframe['close'] < dataframe['sma_30'] * self.entry_ma_offset_13.value)
            item_entry_logic.append(dataframe['ewo'] < self.entry_ewo_13.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #14
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_14_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[13]))
            item_entry_logic.append(dataframe['ema_26'] > dataframe['ema_12'])
            item_entry_logic.append(dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_open_mult_14.value)
            item_entry_logic.append(dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100)
            item_entry_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_14.value)
            item_entry_logic.append(dataframe['close'] < dataframe['ema_20'] * self.entry_ma_offset_14.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #15
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_15_enable']:
            # Non-Standard protections (add below)
            entry_protection_list[14].append(dataframe['close'] > dataframe['ema_200_1h'] * self.entry_ema_rel_15.value)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[14]))
            item_entry_logic.append(dataframe['ema_26'] > dataframe['ema_12'])
            item_entry_logic.append(dataframe['ema_26'] - dataframe['ema_12'] > dataframe['open'] * self.entry_ema_open_mult_15.value)
            item_entry_logic.append(dataframe['ema_26'].shift() - dataframe['ema_12'].shift() > dataframe['open'] / 100)
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_15.value)
            item_entry_logic.append(dataframe['close'] < dataframe['ema_20'] * self.entry_ma_offset_15.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #16
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_16_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[15]))
            item_entry_logic.append(dataframe['close'] < dataframe['ema_20'] * self.entry_ma_offset_16.value)
            item_entry_logic.append(dataframe['ewo'] > self.entry_ewo_16.value)
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_16.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #17
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_17_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[16]))
            item_entry_logic.append(dataframe['close'] < dataframe['ema_20'] * self.entry_ma_offset_17.value)
            item_entry_logic.append(dataframe['ewo'] < self.entry_ewo_17.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #18
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_18_enable']:
            # Non-Standard protections (add below)
            # entry_18_protections.append(dataframe['ema_100'] > dataframe['ema_200'])
            entry_protection_list[17].append(dataframe['sma_200'] > dataframe['sma_200'].shift(20))
            entry_protection_list[17].append(dataframe['sma_200_1h'] > dataframe['sma_200_1h'].shift(36))
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[17]))
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_18.value)
            item_entry_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_18.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #19
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_19_enable']:
            # Non-Standard protections (add below)
            entry_protection_list[18].append(dataframe['ema_50_1h'] > dataframe['ema_200_1h'])
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[18]))
            item_entry_logic.append(dataframe['close'].shift(1) > dataframe['ema_100_1h'])
            item_entry_logic.append(dataframe['low'] < dataframe['ema_100_1h'])
            item_entry_logic.append(dataframe['close'] > dataframe['ema_100_1h'])
            item_entry_logic.append(dataframe['rsi_1h'] > self.entry_rsi_1h_min_19.value)
            item_entry_logic.append(dataframe['chop'] < self.entry_chop_min_19.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #20
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_20_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[19]))
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_20.value)
            item_entry_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_20.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #21
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_21_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[20]))
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_21.value)
            item_entry_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_21.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #22
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_22_enable']:
            # Non-Standard protections (add below)
            entry_protection_list[21].append(dataframe['ema_100_1h'] > dataframe['ema_100_1h'].shift(12))
            entry_protection_list[21].append(dataframe['ema_200_1h'] > dataframe['ema_200_1h'].shift(36))
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[21]))
            item_entry_logic.append(dataframe['volume_mean_4'] * self.entry_volume_22.value > dataframe['volume'])
            item_entry_logic.append(dataframe['close'] < dataframe['sma_30'] * self.entry_ma_offset_22.value)
            item_entry_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_22.value)
            item_entry_logic.append(dataframe['ewo'] > self.entry_ewo_22.value)
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_22.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #23
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_23_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[22]))
            item_entry_logic.append(dataframe['close'] < dataframe['bb20_2_low'] * self.entry_bb_offset_23.value)
            item_entry_logic.append(dataframe['ewo'] > self.entry_ewo_23.value)
            item_entry_logic.append(dataframe['rsi'] < self.entry_rsi_23.value)
            item_entry_logic.append(dataframe['rsi_1h'] < self.entry_rsi_1h_23.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #24
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_24_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[23]))
            item_entry_logic.append(dataframe['ema_12_1h'].shift(12) < dataframe['ema_35_1h'].shift(12))
            item_entry_logic.append(dataframe['ema_12_1h'].shift(12) < dataframe['ema_35_1h'].shift(12))
            item_entry_logic.append(dataframe['ema_12_1h'] > dataframe['ema_35_1h'])
            item_entry_logic.append(dataframe['cmf_1h'].shift(12) < 0)
            item_entry_logic.append(dataframe['cmf_1h'] > 0)
            item_entry_logic.append(dataframe['rsi'] < self.entry_24_rsi_max.value)
            item_entry_logic.append(dataframe['rsi_1h'] > self.entry_24_rsi_1h_min.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #25
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_25_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[24]))
            item_entry_logic.append(dataframe['rsi_20'] < dataframe['rsi_20'].shift())
            item_entry_logic.append(dataframe['rsi_4'] < self.entry_25_rsi_14.value)
            item_entry_logic.append(dataframe['ema_20_1h'] > dataframe['ema_26_1h'])
            item_entry_logic.append(dataframe['close'] < dataframe['sma_20'] * self.entry_25_ma_offset.value)
            item_entry_logic.append(dataframe['open'] > dataframe['sma_20'] * self.entry_25_ma_offset.value)
            item_entry_logic.append((dataframe['open'] < dataframe['ema_20_1h']) & (dataframe['low'] < dataframe['ema_20_1h']) | (dataframe['open'] > dataframe['ema_20_1h']) & (dataframe['low'] > dataframe['ema_20_1h']))
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #26
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_26_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[25]))
            item_entry_logic.append(dataframe['close'] < dataframe['zema'] * self.entry_26_zema_low_offset.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #27
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_27_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[26]))
            item_entry_logic.append(dataframe['r_480'] < -self.entry_27_wr_max.value)
            item_entry_logic.append(dataframe['r_480_1h'] < -self.entry_27_wr_1h_max.value)
            item_entry_logic.append(dataframe['rsi_1h'] + dataframe['rsi'] < self.entry_27_rsi_max.value)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #28
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_28_enable']:
            # Non-Standard protections (add below)
            # Logic
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[27]))
            item_entry_logic.append(dataframe['moderi_64'] == True)
            item_entry_logic.append(dataframe['close'] < dataframe['hull_75'] * 0.92)
            item_entry_logic.append(dataframe['ewo'] > 12.4)
            item_entry_logic.append(dataframe['rsi'] < 38.0)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #29
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_29_enable']:
            # Non-Standard protections (add below)
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[28]))
            item_entry_logic.append(dataframe['moderi_64'] == True)
            item_entry_logic.append(dataframe['close'] < dataframe['hull_75'] * 0.9)
            item_entry_logic.append(dataframe['ewo'] < -4.0)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #30
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_30_enable']:
            # Non-Standard protections (add below)
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[29]))
            item_entry_logic.append(dataframe['moderi_64'] == False)
            item_entry_logic.append(dataframe['close'] < dataframe['zlema_68'] * 0.97)
            item_entry_logic.append(dataframe['ewo'] > 9.0)
            item_entry_logic.append(dataframe['rsi'] < 42.0)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        # Buy Condition #31
        # -----------------------------------------------------------------------------------------
        if self.entry_params['entry_condition_31_enable']:
            # Non-Standard protections (add below)
            item_entry_logic = []
            item_entry_logic.append(reduce(lambda x, y: x & y, entry_protection_list[30]))
            item_entry_logic.append(dataframe['moderi_64'] == False)
            item_entry_logic.append(dataframe['close'] < dataframe['zlema_68'] * 0.94)
            item_entry_logic.append(dataframe['ewo'] < -19.0)
            item_entry_logic.append(dataframe['r_480'] < -99.0)
            item_entry_logic.append(dataframe['volume'] > 0)
            conditions.append(reduce(lambda x, y: x & y, item_entry_logic))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe

    def confirm_trade_exit(self, pair: str, trade: 'Trade', order_type: str, amount: float, rate: float, time_in_force: str, exit_reason: str, **kwargs) -> bool:
        """
        Called right before placing a regular exit order.
        Timing for this function is critical, so avoid doing heavy computations or
        network requests in this method.

        For full documentation please go to https://www.freqtrade.io/en/latest/strategy-advanced/

        When not implemented by a strategy, returns True (always confirming).

        :param pair: Pair that's about to be sold.
        :param trade: trade object.
        :param order_type: Order type (as configured in order_types). usually limit or market.
        :param amount: Amount in quote currency.
        :param rate: Rate that's going to be used when using limit orders
        :param time_in_force: Time in force. Defaults to GTC (Good-til-cancelled).
        :param exit_reason: Sell reason.
            Can be any of ['roi', 'stop_loss', 'stoploss_on_exchange', 'trailing_stop_loss',
                           'exit_signal', 'force_exit', 'emergency_exit']
        :param **kwargs: Ensure to keep this here so updates to this won't break your strategy.
        :return bool: When True is returned, then the exit-order is placed on the exchange.
            False aborts the process
        """
        # Just to be sure our hold data is loaded, should be a no-op call after the first bot loop
        self.load_hold_trades_config()
        if not self.hold_trade_ids:
            # We have no pairs we want to hold until profit, exit
            return True
        if trade.id not in self.hold_trade_ids:
            # This pair is not on the list to hold until profit, exit
            return True
        if trade.calc_profit_ratio(rate) >= self.hold_trade_ids_profit_ratio:
            # This pair is on the list to hold, and we reached minimum profit, exit
            return True
        # This pair is on the list to hold, and we haven't reached minimum profit, hold
        return False
# Elliot Wave Oscillator

def ewo(dataframe, sma1_length=5, sma2_length=35):
    df = dataframe.copy()
    sma1 = ta.EMA(df, timeperiod=sma1_length)
    sma2 = ta.EMA(df, timeperiod=sma2_length)
    smadif = (sma1 - sma2) / df['close'] * 100
    return smadif
# Chaikin Money Flow

def chaikin_money_flow(dataframe, n=20, fillna=False) -> Series:
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

def tsi(dataframe: DataFrame, window_slow: int, window_fast: int, fillna=False) -> Series:
    """
    Indicator: True Strength Index (TSI)
    :param dataframe: DataFrame The original OHLC dataframe
    :param window_slow: slow smoothing period
    :param window_fast: fast smoothing period
    :param fillna: If True fill NaN values
    """
    df = dataframe.copy()
    min_periods_slow = 0 if fillna else window_slow
    min_periods_fast = 0 if fillna else window_fast
    close_diff = df['close'].diff()
    close_diff_abs = close_diff.abs()
    smooth_close_diff = close_diff.ewm(span=window_slow, min_periods=min_periods_slow, adjust=False).mean().ewm(span=window_fast, min_periods=min_periods_fast, adjust=False).mean()
    smooth_close_diff_abs = close_diff_abs.ewm(span=window_slow, min_periods=min_periods_slow, adjust=False).mean().ewm(span=window_fast, min_periods=min_periods_fast, adjust=False).mean()
    tsi = smooth_close_diff / smooth_close_diff_abs * 100
    if fillna:
        tsi = tsi.replace([np.inf, -np.inf], np.nan).fillna(0)
    return tsi
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
    WR = Series((highest_high - dataframe['close']) / (highest_high - lowest_low), name='{0} Williams %R'.format(period))
    return WR * -100
# Volume Weighted Moving Average

def vwma(dataframe: DataFrame, length: int=10):
    """Indicator: Volume Weighted Moving Average (VWMA)"""
    # Calculate Result
    pv = dataframe['close'] * dataframe['volume']
    vwma = Series(ta.SMA(pv, timeperiod=length) / ta.SMA(dataframe['volume'], timeperiod=length))
    return vwma
# Modified Elder Ray Index

def moderi(dataframe: DataFrame, len_slow_ma: int=32) -> Series:
    slow_ma = Series(ta.EMA(vwma(dataframe, length=len_slow_ma), timeperiod=len_slow_ma))
    return slow_ma >= slow_ma.shift(1)  # we just need true & false for ERI trend
# zlema

def zlema(dataframe, timeperiod):
    lag = int(math.floor((timeperiod - 1) / 2))
    if isinstance(dataframe, Series):
        ema_data = dataframe + (dataframe - dataframe.shift(lag))
    else:
        ema_data = dataframe['close'] + (dataframe['close'] - dataframe['close'].shift(lag))
    return ta.EMA(ema_data, timeperiod=timeperiod)
# zlhull

def zlhull(dataframe, timeperiod):
    lag = int(math.floor((timeperiod - 1) / 2))
    if isinstance(dataframe, Series):
        wma_data = dataframe + (dataframe - dataframe.shift(lag))
    else:
        wma_data = dataframe['close'] + (dataframe['close'] - dataframe['close'].shift(lag))
    return ta.WMA(2 * ta.WMA(wma_data, int(math.floor(timeperiod / 2))) - ta.WMA(wma_data, timeperiod), int(round(np.sqrt(timeperiod))))
# hull

def hull(dataframe, timeperiod):
    if isinstance(dataframe, Series):
        return ta.WMA(2 * ta.WMA(dataframe, int(math.floor(timeperiod / 2))) - ta.WMA(dataframe, timeperiod), int(round(np.sqrt(timeperiod))))
    else:
        return ta.WMA(2 * ta.WMA(dataframe['close'], int(math.floor(timeperiod / 2))) - ta.WMA(dataframe['close'], timeperiod), int(round(np.sqrt(timeperiod))))