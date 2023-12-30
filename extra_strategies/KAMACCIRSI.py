# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# --- Do not remove these libs ---
from functools import reduce
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from freqtrade.strategy import IStrategy
# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class KAMACCIRSI(IStrategy):
    """
    author@: werkkrew
    github@: https://github.com/werkkrew/freqtrade-strategies

    Strategy using 3 indicators with fully customizable parameters and full hyperopt support
    including indicator periods as well as cross points.

    There is nothing groundbreaking about this strategy, how it works, or what it does.
    It was mostly an experiment for me to learn Freqtrade strategies and hyperopt development.

    Default hyperopt defined parameters below were done on 60 days of data from Kraken against 20 BTC pairs
    using the SharpeHyperOptLoss loss function.

    Suggestions and improvements are welcome!

    Supports exiting via strategy, as well as ROI and Stoploss/Trailing Stoploss

    Indicators Used:
    KAMA "Kaufman Adaptive Moving Average" (Short Duration)
    KAMA (Long Duration)
    CCI "Commodity Channel Index"
    RSI "Relative Strength Index"

    Buy Strategy:
        kama-cross OR kama-slope
            kama-short > kama-long
            kama-long-slope > 1
        cci-enabled?
            cci > X
        rsi-enabled?
            rsi > Y

    Sell Strategy:
        kama-cross OR kama-slope
            kama-short < kama-long
            kama-long-slope < 1
        cci-enabled?
            cci < A
        rsi-enabled?
            rsi < B

    Ideas and Todo:
        - Add informative pairs to help decision (e.g. BTC/USD to inform other */BTC pairs)
    """
    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3
    '\n    HYPEROPT SETTINGS\n    The following is set by Hyperopt, or can be set by hand if you wish:\n\n    - minimal_roi table\n    - stoploss\n    - trailing stoploss\n    - for entry/exit separate\n        - kama-trigger = cross, slope\n        - kama-short timeperiod\n        - kama-long timeperiod\n        - cci period\n        - cci upper / lower threshold\n        - rsi period\n        - rsi upper / lower threshold\n\n    PASTE OUTPUT FROM HYPEROPT HERE\n    '
    # Buy hyperspace params:
    entry_params = {'cci-enabled': True, 'cci-limit': 198, 'cci-period': 18, 'kama-long-period': 46, 'kama-short-period': 11, 'kama-trigger': 'cross', 'rsi-enabled': False, 'rsi-limit': 72, 'rsi-period': 5}
    # Sell hyperspace params:
    exit_params = {'exit-cci-enabled': False, 'exit-cci-limit': -144, 'exit-cci-period': 18, 'exit-kama-long-period': 41, 'exit-kama-short-period': 5, 'exit-kama-trigger': 'cross', 'exit-rsi-enabled': False, 'exit-rsi-limit': 69, 'exit-rsi-period': 12}
    # ROI table:
    minimal_roi = {'0': 0.11599, '18': 0.03112, '34': 0.01895, '131': 0}
    # Stoploss:
    stoploss = -0.32982
    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.28596
    trailing_stop_positive_offset = 0.29771
    trailing_only_offset_is_reached = True
    '\n    END HYPEROPT\n    '
    timeframe = '5m'
    # Make sure these match or are not overridden in config
    use_exit_signal = True
    exit_profit_only = True
    exit_profit_offset = 0.01
    ignore_roi_if_entry_signal = False
    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False
    # Number of candles the strategy requires before producing valid signals
    # Set this to the highest period value in the indicator_params dict or highest of the ranges in the hyperopt settings (default: 72)
    startup_candle_count: int = 72
    '\n    Not currently being used for anything, thinking about implementing this later.\n    '

    def informative_pairs(self):
        # https://www.freqtrade.io/en/latest/strategy-customization/#additional-data-informative_pairs
        informative_pairs = [(f"{self.config['stake_currency']}/USD", self.timeframe)]
        return informative_pairs
    '\n    Populate all of the indicators we need (note: indicators are separate for entry/exit)\n    '

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # # Commodity Channel Index: values [Oversold:-100, Overbought:100]
        dataframe['entry-cci'] = ta.CCI(dataframe, timeperiod=self.entry_params['cci-period'])
        dataframe['exit-cci'] = ta.CCI(dataframe, timeperiod=self.exit_params['exit-cci-period'])
        # RSI
        dataframe['entry-rsi'] = ta.RSI(dataframe, timeperiod=self.entry_params['rsi-period'])
        dataframe['exit-rsi'] = ta.RSI(dataframe, timeperiod=self.exit_params['exit-rsi-period'])
        # KAMA - Kaufman Adaptive Moving Average
        dataframe['entry-kama-short'] = ta.KAMA(dataframe, timeperiod=self.entry_params['kama-short-period'])
        dataframe['entry-kama-long'] = ta.KAMA(dataframe, timeperiod=self.entry_params['kama-long-period'])
        dataframe['entry-kama-long-slope'] = dataframe['entry-kama-long'] / dataframe['entry-kama-long'].shift()
        dataframe['exit-kama-short'] = ta.KAMA(dataframe, timeperiod=self.exit_params['exit-kama-short-period'])
        dataframe['exit-kama-long'] = ta.KAMA(dataframe, timeperiod=self.exit_params['exit-kama-long-period'])
        dataframe['exit-kama-long-slope'] = dataframe['exit-kama-long'] / dataframe['exit-kama-long'].shift()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        if self.entry_params['rsi-enabled']:
            conditions.append(dataframe['entry-rsi'] > self.entry_params['rsi-limit'])
        if self.entry_params['cci-enabled']:
            conditions.append(dataframe['entry-cci'] > self.entry_params['cci-limit'])
        if self.entry_params['kama-trigger'] == 'cross':
            conditions.append(dataframe['entry-kama-short'] > dataframe['entry-kama-long'])
        if self.entry_params['kama-trigger'] == 'slope':
            conditions.append(dataframe['entry-kama-long'] > 1)
        # Check that volume is not 0
        conditions.append(dataframe['volume'] > 0)
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        if self.exit_params['exit-rsi-enabled']:
            conditions.append(dataframe['exit-rsi'] < self.exit_params['exit-rsi-limit'])
        if self.exit_params['exit-cci-enabled']:
            conditions.append(dataframe['exit-cci'] < self.exit_params['exit-cci-limit'])
        if self.exit_params['exit-kama-trigger'] == 'cross':
            conditions.append(dataframe['exit-kama-short'] < dataframe['exit-kama-long'])
        if self.exit_params['exit-kama-trigger'] == 'slope':
            conditions.append(dataframe['exit-kama-long'] < 1)
        # Check that volume is not 0
        conditions.append(dataframe['volume'] > 0)
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'exit_long'] = 1
        return dataframe