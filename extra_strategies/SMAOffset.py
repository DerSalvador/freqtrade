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
# author @tirail
ma_types = {'SMA': ta.SMA, 'EMA': ta.EMA}

class SMAOffset(IStrategy):
    INTERFACE_VERSION = 3  # hyperopt and paste results here
    # Buy hyperspace params:
    entry_params = {'base_nb_candles_entry': 30, 'entry_trigger': 'SMA', 'low_offset': 0.958}  # Sell hyperspace params:
    exit_params = {'base_nb_candles_exit': 30, 'high_offset': 1.012, 'exit_trigger': 'EMA'}  # Stoploss:
    stoploss = -0.5  # ROI table:
    minimal_roi = {'0': 1}
    base_nb_candles_entry = IntParameter(5, 80, default=entry_params['base_nb_candles_entry'], space='entry')
    base_nb_candles_exit = IntParameter(5, 80, default=exit_params['base_nb_candles_exit'], space='exit')
    low_offset = DecimalParameter(0.8, 0.99, default=entry_params['low_offset'], space='entry')
    high_offset = DecimalParameter(0.8, 1.1, default=exit_params['high_offset'], space='exit')
    entry_trigger = CategoricalParameter(ma_types.keys(), default=entry_params['entry_trigger'], space='entry')
    exit_trigger = CategoricalParameter(ma_types.keys(), default=exit_params['exit_trigger'], space='exit')  # Trailing stop:
    trailing_stop = False
    trailing_stop_positive = 0.0001
    trailing_stop_positive_offset = 0
    trailing_only_offset_is_reached = False  # Optimal timeframe for the strategy
    timeframe = '5m'
    use_exit_signal = True
    exit_profit_only = False
    process_only_new_candles = True
    startup_candle_count = 30
    plot_config = {'main_plot': {'ma_offset_entry': {'color': 'orange'}, 'ma_offset_exit': {'color': 'orange'}}}
    use_custom_stoploss = False

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> float:
        return 1

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if not self.config['runmode'].value == 'hyperopt':
            dataframe['ma_offset_entry'] = ma_types[self.entry_trigger.value](dataframe, int(self.base_nb_candles_entry.value)) * self.low_offset.value
            dataframe['ma_offset_exit'] = ma_types[self.exit_trigger.value](dataframe, int(self.base_nb_candles_exit.value)) * self.high_offset.value
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if self.config['runmode'].value == 'hyperopt':
            dataframe['ma_offset_entry'] = ma_types[self.entry_trigger.value](dataframe, int(self.base_nb_candles_entry.value)) * self.low_offset.value
        dataframe.loc[(dataframe['close'] < dataframe['ma_offset_entry']) & (dataframe['volume'] > 0), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if self.config['runmode'].value == 'hyperopt':
            dataframe['ma_offset_exit'] = ma_types[self.exit_trigger.value](dataframe, int(self.base_nb_candles_exit.value)) * self.high_offset.value
        dataframe.loc[(dataframe['close'] > dataframe['ma_offset_exit']) & (dataframe['volume'] > 0), 'exit_long'] = 1
        return dataframe