# --- Do not remove these libs ---
import pandas as pd  # noqa
import talib.abstract as ta
from pandas import DataFrame
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy.interface import IStrategy
pd.options.mode.chained_assignment = None  # default='warn'
from datetime import datetime, timedelta
from functools import reduce
import numpy as np
import technical.indicators as ftt
from freqtrade.strategy import merge_informative_pair, stoploss_from_open

class ichiV1(IStrategy):
    INTERFACE_VERSION = 3
    # NOTE: settings as of the 25th july 21
    # Buy hyperspace params:
    # NOTE: Good value (Win% ~70%), alot of trades
    #"entry_min_fan_magnitude_gain": 1.008 # NOTE: Very save value (Win% ~90%), only the biggest moves 1.008,
    entry_params = {'entry_trend_above_senkou_level': 1, 'entry_trend_bullish_level': 6, 'entry_fan_magnitude_shift_value': 3, 'entry_min_fan_magnitude_gain': 1.002}
    # Sell hyperspace params:
    # NOTE: was 15m but kept bailing out in dryrun
    exit_params = {'exit_trend_indicator': 'trend_close_2h'}
    # ROI table:
    minimal_roi = {'0': 0.059, '10': 0.037, '41': 0.012, '114': 0}
    # Stoploss:
    stoploss = -0.275
    # Optimal timeframe for the strategy
    timeframe = '5m'
    startup_candle_count = 96
    process_only_new_candles = False
    trailing_stop = False
    #trailing_stop_positive = 0.002
    #trailing_stop_positive_offset = 0.025
    #trailing_only_offset_is_reached = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    # fill area between senkou_a and senkou_b
    #optional
    #optional
    #optional
    # plot senkou_b, too. Not only the area to it.
    plot_config = {'main_plot': {'senkou_a': {'color': 'green', 'fill_to': 'senkou_b', 'fill_label': 'Ichimoku Cloud', 'fill_color': 'rgba(255,76,46,0.2)'}, 'senkou_b': {}, 'trend_close_5m': {'color': '#FF5733'}, 'trend_close_15m': {'color': '#FF8333'}, 'trend_close_30m': {'color': '#FFB533'}, 'trend_close_1h': {'color': '#FFE633'}, 'trend_close_2h': {'color': '#E3FF33'}, 'trend_close_4h': {'color': '#C4FF33'}, 'trend_close_6h': {'color': '#61FF33'}, 'trend_close_8h': {'color': '#33FF7D'}}, 'subplots': {'fan_magnitude': {'fan_magnitude': {}}, 'fan_magnitude_gain': {'fan_magnitude_gain': {}}}}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        heikinashi = qtpylib.heikinashi(dataframe)
        dataframe['open'] = heikinashi['open']
        #dataframe['close'] = heikinashi['close']
        dataframe['high'] = heikinashi['high']
        dataframe['low'] = heikinashi['low']
        dataframe['trend_close_5m'] = dataframe['close']
        dataframe['trend_close_15m'] = ta.EMA(dataframe['close'], timeperiod=3)
        dataframe['trend_close_30m'] = ta.EMA(dataframe['close'], timeperiod=6)
        dataframe['trend_close_1h'] = ta.EMA(dataframe['close'], timeperiod=12)
        dataframe['trend_close_2h'] = ta.EMA(dataframe['close'], timeperiod=24)
        dataframe['trend_close_4h'] = ta.EMA(dataframe['close'], timeperiod=48)
        dataframe['trend_close_6h'] = ta.EMA(dataframe['close'], timeperiod=72)
        dataframe['trend_close_8h'] = ta.EMA(dataframe['close'], timeperiod=96)
        dataframe['trend_open_5m'] = dataframe['open']
        dataframe['trend_open_15m'] = ta.EMA(dataframe['open'], timeperiod=3)
        dataframe['trend_open_30m'] = ta.EMA(dataframe['open'], timeperiod=6)
        dataframe['trend_open_1h'] = ta.EMA(dataframe['open'], timeperiod=12)
        dataframe['trend_open_2h'] = ta.EMA(dataframe['open'], timeperiod=24)
        dataframe['trend_open_4h'] = ta.EMA(dataframe['open'], timeperiod=48)
        dataframe['trend_open_6h'] = ta.EMA(dataframe['open'], timeperiod=72)
        dataframe['trend_open_8h'] = ta.EMA(dataframe['open'], timeperiod=96)
        dataframe['fan_magnitude'] = dataframe['trend_close_1h'] / dataframe['trend_close_8h']
        dataframe['fan_magnitude_gain'] = dataframe['fan_magnitude'] / dataframe['fan_magnitude'].shift(1)
        ichimoku = ftt.ichimoku(dataframe, conversion_line_period=20, base_line_periods=60, laggin_span=120, displacement=30)
        dataframe['chikou_span'] = ichimoku['chikou_span']
        dataframe['tenkan_sen'] = ichimoku['tenkan_sen']
        dataframe['kijun_sen'] = ichimoku['kijun_sen']
        dataframe['senkou_a'] = ichimoku['senkou_span_a']
        dataframe['senkou_b'] = ichimoku['senkou_span_b']
        dataframe['leading_senkou_span_a'] = ichimoku['leading_senkou_span_a']
        dataframe['leading_senkou_span_b'] = ichimoku['leading_senkou_span_b']
        dataframe['cloud_green'] = ichimoku['cloud_green']
        dataframe['cloud_red'] = ichimoku['cloud_red']
        dataframe['atr'] = ta.ATR(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # Trending market
        if self.entry_params['entry_trend_above_senkou_level'] >= 1:
            conditions.append(dataframe['trend_close_5m'] > dataframe['senkou_a'])
            conditions.append(dataframe['trend_close_5m'] > dataframe['senkou_b'])
        if self.entry_params['entry_trend_above_senkou_level'] >= 2:
            conditions.append(dataframe['trend_close_15m'] > dataframe['senkou_a'])
            conditions.append(dataframe['trend_close_15m'] > dataframe['senkou_b'])
        if self.entry_params['entry_trend_above_senkou_level'] >= 3:
            conditions.append(dataframe['trend_close_30m'] > dataframe['senkou_a'])
            conditions.append(dataframe['trend_close_30m'] > dataframe['senkou_b'])
        if self.entry_params['entry_trend_above_senkou_level'] >= 4:
            conditions.append(dataframe['trend_close_1h'] > dataframe['senkou_a'])
            conditions.append(dataframe['trend_close_1h'] > dataframe['senkou_b'])
        if self.entry_params['entry_trend_above_senkou_level'] >= 5:
            conditions.append(dataframe['trend_close_2h'] > dataframe['senkou_a'])
            conditions.append(dataframe['trend_close_2h'] > dataframe['senkou_b'])
        if self.entry_params['entry_trend_above_senkou_level'] >= 6:
            conditions.append(dataframe['trend_close_4h'] > dataframe['senkou_a'])
            conditions.append(dataframe['trend_close_4h'] > dataframe['senkou_b'])
        if self.entry_params['entry_trend_above_senkou_level'] >= 7:
            conditions.append(dataframe['trend_close_6h'] > dataframe['senkou_a'])
            conditions.append(dataframe['trend_close_6h'] > dataframe['senkou_b'])
        if self.entry_params['entry_trend_above_senkou_level'] >= 8:
            conditions.append(dataframe['trend_close_8h'] > dataframe['senkou_a'])
            conditions.append(dataframe['trend_close_8h'] > dataframe['senkou_b'])
        # Trends bullish
        if self.entry_params['entry_trend_bullish_level'] >= 1:
            conditions.append(dataframe['trend_close_5m'] > dataframe['trend_open_5m'])
        if self.entry_params['entry_trend_bullish_level'] >= 2:
            conditions.append(dataframe['trend_close_15m'] > dataframe['trend_open_15m'])
        if self.entry_params['entry_trend_bullish_level'] >= 3:
            conditions.append(dataframe['trend_close_30m'] > dataframe['trend_open_30m'])
        if self.entry_params['entry_trend_bullish_level'] >= 4:
            conditions.append(dataframe['trend_close_1h'] > dataframe['trend_open_1h'])
        if self.entry_params['entry_trend_bullish_level'] >= 5:
            conditions.append(dataframe['trend_close_2h'] > dataframe['trend_open_2h'])
        if self.entry_params['entry_trend_bullish_level'] >= 6:
            conditions.append(dataframe['trend_close_4h'] > dataframe['trend_open_4h'])
        if self.entry_params['entry_trend_bullish_level'] >= 7:
            conditions.append(dataframe['trend_close_6h'] > dataframe['trend_open_6h'])
        if self.entry_params['entry_trend_bullish_level'] >= 8:
            conditions.append(dataframe['trend_close_8h'] > dataframe['trend_open_8h'])
        # Trends magnitude
        conditions.append(dataframe['fan_magnitude_gain'] >= self.entry_params['entry_min_fan_magnitude_gain'])
        conditions.append(dataframe['fan_magnitude'] > 1)
        for x in range(self.entry_params['entry_fan_magnitude_shift_value']):
            conditions.append(dataframe['fan_magnitude'].shift(x + 1) < dataframe['fan_magnitude'])
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append(qtpylib.crossed_below(dataframe['trend_close_5m'], dataframe[self.exit_params['exit_trend_indicator']]))
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'exit_long'] = 1
        return dataframe