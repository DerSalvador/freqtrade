from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa

class EMAPriceCrossoverWithThreshold(IStrategy):
    INTERFACE_VERSION = 3
    '\n    EMAPriceCrossoverWithThreshold\n    author@: Paul Csapak\n    github@: https://github.com/paulcpk/freqtrade-strategies-that-work\n\n    How to use it?\n\n    > freqtrade download-data --timeframes 1h --timerange=20180301-20200301\n    > freqtrade backtesting --export trades -s EMAPriceCrossoverWithThreshold --timeframe 1h --timerange=20180301-20200301\n    > freqtrade plot-dataframe -s EMAPriceCrossoverWithThreshold --indicators1 ema800 --timeframe 1h --timerange=20180301-20200301\n\n    '
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    # minimal_roi = {
    #     "40": 0.0,
    #     "30": 0.01,
    #     "20": 0.02,
    #     "0": 0.04
    # }
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.15
    # Optimal timeframe for the strategy
    timeframe = '1h'
    # trailing stoploss
    trailing_stop = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        threshold_percentage = 1
        dataframe['ema800'] = ta.EMA(dataframe, timeperiod=800)
        dataframe['ema_threshold'] = dataframe['ema800'] * (100 - threshold_percentage) / 100
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Close price crossed above EMA
        # Ensure this candle had volume (important for backtesting)
        dataframe.loc[qtpylib.crossed_above(dataframe['close'], dataframe['ema800']) & (dataframe['volume'] > 0), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Close price crossed below EMA threshold
        dataframe.loc[qtpylib.crossed_below(dataframe['close'], dataframe['ema_threshold']), 'exit_long'] = 1
        return dataframe