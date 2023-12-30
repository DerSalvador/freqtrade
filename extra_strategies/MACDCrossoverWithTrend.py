from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa

class MACDCrossoverWithTrend(IStrategy):
    INTERFACE_VERSION = 3
    '\n    MACDCrossoverWithTrend\n    author@: Paul Csapak\n    github@: https://github.com/paulcpk/freqtrade-strategies-that-work\n\n    How to use it?\n\n    > freqtrade download-data --timeframes 1h --timerange=20180301-20200301\n    > freqtrade backtesting --export trades -s MACDCrossoverWithTrend --timeframe 1h --timerange=20180301-20200301\n    > freqtrade plot-dataframe -s MACDCrossoverWithTrend --indicators1 ema100 --timeframe 1h --timerange=20180301-20200301\n\n    '
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    # minimal_roi = {
    #     "40": 0.0,
    #     "30": 0.01,
    #     "20": 0.02,
    #     "0": 0.04
    # }
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.2
    # Optimal timeframe for the strategy
    timeframe = '1h'
    # trailing stoploss
    trailing_stop = False
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.04

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        dataframe['ema100'] = ta.EMA(dataframe, timeperiod=100)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # MACD is below zero
        # Signal crosses above MACD
        # Candle low is above EMA
        # Ensure this candle had volume (important for backtesting)
        dataframe.loc[(dataframe['macd'] < 0) & qtpylib.crossed_above(dataframe['macd'], dataframe['macdsignal']) & (dataframe['low'] > dataframe['ema100']) & (dataframe['volume'] > 0), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MACD crosses above Signal
        # OR price is below trend ema
        dataframe.loc[qtpylib.crossed_below(dataframe['macd'], 0) | (dataframe['low'] < dataframe['ema100']), 'exit_long'] = 1
        return dataframe