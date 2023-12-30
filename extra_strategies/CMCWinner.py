# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa
# This class is a sample. Feel free to customize it.

class CMCWinner(IStrategy):
    INTERFACE_VERSION = 3
    '\n    This is a test strategy to inspire you.\n    More information in https://github.com/freqtrade/freqtrade/blob/develop/docs/bot-optimization.md\n\n    You can:\n    - Rename the class name (Do not forget to update class_name)\n    - Add any methods you want to build your strategy\n    - Add any lib you need to build your strategy\n\n    You must keep:\n    - the lib in the section "Do not remove these libs"\n    - the prototype for the methods: minimal_roi, stoploss, populate_indicators, populate_entry_trend,\n    populate_exit_trend, hyperopt_space, entry_strategy_generator\n    '
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {'40': 0.0, '30': 0.02, '20': 0.03, '0': 0.05}
    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = -0.05
    # Optimal timeframe for the strategy
    timeframe = '15m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        """
        # Commodity Channel Index: values Oversold:<-100, Overbought:>100
        dataframe['cci'] = ta.CCI(dataframe)
        # MFI
        dataframe['mfi'] = ta.MFI(dataframe)  # CMO
        dataframe['cmo'] = ta.CMO(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """
        dataframe.loc[(dataframe['cci'].shift(1) < -100) & (dataframe['mfi'].shift(1) < 20) & (dataframe['cmo'].shift(1) < -50), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with entry column
        """
        dataframe.loc[(dataframe['cci'].shift(1) > 100) & (dataframe['mfi'].shift(1) > 80) & (dataframe['cmo'].shift(1) > 50), 'exit_long'] = 1
        return dataframe