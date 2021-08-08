# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

from functools import reduce
from typing import Any, Callable, Dict, List

import talib.abstract as ta
from pandas import DataFrame
from skopt.space import Categorical, Dimension, Integer

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.optimize.hyperopt_interface import IHyperOpt


class DefaultHyperOpt(IHyperOpt):
    """
    Default hyperopt provided by the Freqtrade bot.
    You can override it with your own Hyperopt
    """
    @staticmethod
    def populate_indicators(dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Add several indicators needed for buy and sell strategies defined below.
        """
        # ADX
        dataframe['adx'] = ta.ADX(dataframe)
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        # MFI
        dataframe['mfi'] = ta.MFI(dataframe)
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe)
        # Stochastic Fast
        stoch_fast = ta.STOCHF(dataframe)
        dataframe['fastd'] = stoch_fast['fastd']
        # Minus-DI
        dataframe['minus_di'] = ta.MINUS_DI(dataframe)
        # Bollinger bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        # SAR
        dataframe['sar'] = ta.SAR(dataframe)

        return dataframe

    @staticmethod
    def buy_strategy_generator(params: Dict[str, Any]) -> Callable:
        """
        Define the buy strategy parameters to be used by Hyperopt.
        """
        def populate_buy_trend(dataframe: DataFrame, metadata: dict) -> DataFrame:
            """
            Buy strategy Hyperopt will build and use.
            """
            conditions = []

            # GUARDS AND TRENDS
            if 'mfi-enabled' in params and params['mfi-enabled']:
                conditions.append(dataframe['mfi'] < params['mfi-value'])
            if 'fastd-enabled' in params and params['fastd-enabled']:
                conditions.append(dataframe['fastd'] < params['fastd-value'])
            if 'adx-enabled' in params and params['adx-enabled']:
                conditions.append(dataframe['adx'] > params['adx-value'])
            if 'rsi-enabled' in params and params['rsi-enabled']:
                conditions.append(dataframe['rsi'] < params['rsi-value'])

            # TRIGGERS
            if 'trigger' in params:
                if params['trigger'] == 'bb_lower':
                    conditions.append(dataframe['close'] < dataframe['bb_lowerband'])
                if params['trigger'] == 'macd_cross_signal':
                    conditions.append(qtpylib.crossed_above(
                        dataframe['macd'], dataframe['macdsignal']
                    ))
                if params['trigger'] == 'sar_reversal':
                    conditions.append(qtpylib.crossed_above(
                        dataframe['close'], dataframe['sar']
                    ))

            if conditions:
                dataframe.loc[
                    reduce(lambda x, y: x & y, conditions),
                    'buy'] = 1

            return dataframe

        return populate_buy_trend

    @staticmethod
    def indicator_space() -> List[Dimension]:
        """
        Define your Hyperopt space for searching buy strategy parameters.
        """
        return [
            Integer(10, 25, name='mfi-value'),
            Integer(15, 45, name='fastd-value'),
            Integer(20, 50, name='adx-value'),
            Integer(20, 40, name='rsi-value'),
            Categorical([True, False], name='mfi-enabled'),
            Categorical([True, False], name='fastd-enabled'),
            Categorical([True, False], name='adx-enabled'),
            Categorical([True, False], name='rsi-enabled'),
            Categorical(['bb_lower', 'macd_cross_signal', 'sar_reversal'], name='trigger')
        ]

    @staticmethod
    def short_strategy_generator(params: Dict[str, Any]) -> Callable:
        """
        Define the short strategy parameters to be used by Hyperopt.
        """
        def populate_short_trend(dataframe: DataFrame, metadata: dict) -> DataFrame:
            """
            Buy strategy Hyperopt will build and use.
            """
            conditions = []

            # GUARDS AND TRENDS
            if 'mfi-enabled' in params and params['mfi-enabled']:
                conditions.append(dataframe['mfi'] > params['mfi-value'])
            if 'fastd-enabled' in params and params['fastd-enabled']:
                conditions.append(dataframe['fastd'] > params['fastd-value'])
            if 'adx-enabled' in params and params['adx-enabled']:
                conditions.append(dataframe['adx'] < params['adx-value'])
            if 'rsi-enabled' in params and params['rsi-enabled']:
                conditions.append(dataframe['rsi'] > params['rsi-value'])

            # TRIGGERS
            if 'trigger' in params:
                if params['trigger'] == 'bb_upper':
                    conditions.append(dataframe['close'] > dataframe['bb_upperband'])
                if params['trigger'] == 'macd_cross_signal':
                    conditions.append(qtpylib.crossed_below(
                        dataframe['macd'], dataframe['macdsignal']
                    ))
                if params['trigger'] == 'sar_reversal':
                    conditions.append(qtpylib.crossed_below(
                        dataframe['close'], dataframe['sar']
                    ))

            if conditions:
                dataframe.loc[
                    reduce(lambda x, y: x & y, conditions),
                    'short'] = 1

            return dataframe

        return populate_short_trend

    @staticmethod
    def short_indicator_space() -> List[Dimension]:
        """
        Define your Hyperopt space for searching short strategy parameters.
        """
        return [
            Integer(75, 90, name='mfi-value'),
            Integer(55, 85, name='fastd-value'),
            Integer(50, 80, name='adx-value'),
            Integer(60, 80, name='rsi-value'),
            Categorical([True, False], name='mfi-enabled'),
            Categorical([True, False], name='fastd-enabled'),
            Categorical([True, False], name='adx-enabled'),
            Categorical([True, False], name='rsi-enabled'),
            Categorical(['bb_upper', 'macd_cross_signal', 'sar_reversal'], name='trigger')
        ]

    @staticmethod
    def sell_strategy_generator(params: Dict[str, Any]) -> Callable:
        """
        Define the sell strategy parameters to be used by Hyperopt.
        """
        def populate_sell_trend(dataframe: DataFrame, metadata: dict) -> DataFrame:
            """
            Sell strategy Hyperopt will build and use.
            """
            conditions = []

            # GUARDS AND TRENDS
            if 'sell-mfi-enabled' in params and params['sell-mfi-enabled']:
                conditions.append(dataframe['mfi'] > params['sell-mfi-value'])
            if 'sell-fastd-enabled' in params and params['sell-fastd-enabled']:
                conditions.append(dataframe['fastd'] > params['sell-fastd-value'])
            if 'sell-adx-enabled' in params and params['sell-adx-enabled']:
                conditions.append(dataframe['adx'] < params['sell-adx-value'])
            if 'sell-rsi-enabled' in params and params['sell-rsi-enabled']:
                conditions.append(dataframe['rsi'] > params['sell-rsi-value'])

            # TRIGGERS
            if 'sell-trigger' in params:
                if params['sell-trigger'] == 'sell-bb_upper':
                    conditions.append(dataframe['close'] > dataframe['bb_upperband'])
                if params['sell-trigger'] == 'sell-macd_cross_signal':
                    conditions.append(qtpylib.crossed_above(
                        dataframe['macdsignal'], dataframe['macd']
                    ))
                if params['sell-trigger'] == 'sell-sar_reversal':
                    conditions.append(qtpylib.crossed_above(
                        dataframe['sar'], dataframe['close']
                    ))

            if conditions:
                dataframe.loc[
                    reduce(lambda x, y: x & y, conditions),
                    'sell'] = 1

            return dataframe

        return populate_sell_trend

    @staticmethod
    def exit_short_strategy_generator(params: Dict[str, Any]) -> Callable:
        """
        Define the exit_short strategy parameters to be used by Hyperopt.
        """
        def populate_exit_short_trend(dataframe: DataFrame, metadata: dict) -> DataFrame:
            """
            Exit_short strategy Hyperopt will build and use.
            """
            conditions = []

            # GUARDS AND TRENDS
            if 'exit-short-mfi-enabled' in params and params['exit-short-mfi-enabled']:
                conditions.append(dataframe['mfi'] < params['exit-short-mfi-value'])
            if 'exit-short-fastd-enabled' in params and params['exit-short-fastd-enabled']:
                conditions.append(dataframe['fastd'] < params['exit-short-fastd-value'])
            if 'exit-short-adx-enabled' in params and params['exit-short-adx-enabled']:
                conditions.append(dataframe['adx'] > params['exit-short-adx-value'])
            if 'exit-short-rsi-enabled' in params and params['exit-short-rsi-enabled']:
                conditions.append(dataframe['rsi'] < params['exit-short-rsi-value'])

            # TRIGGERS
            if 'exit-short-trigger' in params:
                if params['exit-short-trigger'] == 'exit-short-bb_lower':
                    conditions.append(dataframe['close'] < dataframe['bb_lowerband'])
                if params['exit-short-trigger'] == 'exit-short-macd_cross_signal':
                    conditions.append(qtpylib.crossed_below(
                        dataframe['macdsignal'], dataframe['macd']
                    ))
                if params['exit-short-trigger'] == 'exit-short-sar_reversal':
                    conditions.append(qtpylib.crossed_below(
                        dataframe['sar'], dataframe['close']
                    ))

            if conditions:
                dataframe.loc[
                    reduce(lambda x, y: x & y, conditions),
                    'exit_short'] = 1

            return dataframe

        return populate_exit_short_trend

    @staticmethod
    def sell_indicator_space() -> List[Dimension]:
        """
        Define your Hyperopt space for searching sell strategy parameters.
        """
        return [
            Integer(75, 100, name='sell-mfi-value'),
            Integer(50, 100, name='sell-fastd-value'),
            Integer(50, 100, name='sell-adx-value'),
            Integer(60, 100, name='sell-rsi-value'),
            Categorical([True, False], name='sell-mfi-enabled'),
            Categorical([True, False], name='sell-fastd-enabled'),
            Categorical([True, False], name='sell-adx-enabled'),
            Categorical([True, False], name='sell-rsi-enabled'),
            Categorical(['sell-bb_upper',
                         'sell-macd_cross_signal',
                         'sell-sar_reversal'], name='sell-trigger')
        ]

    @staticmethod
    def exit_short_indicator_space() -> List[Dimension]:
        """
        Define your Hyperopt space for searching exit short strategy parameters.
        """
        return [
            Integer(1, 25, name='exit_short-mfi-value'),
            Integer(1, 50, name='exit_short-fastd-value'),
            Integer(1, 50, name='exit_short-adx-value'),
            Integer(1, 40, name='exit_short-rsi-value'),
            Categorical([True, False], name='exit_short-mfi-enabled'),
            Categorical([True, False], name='exit_short-fastd-enabled'),
            Categorical([True, False], name='exit_short-adx-enabled'),
            Categorical([True, False], name='exit_short-rsi-enabled'),
            Categorical(['exit_short-bb_lower',
                         'exit_short-macd_cross_signal',
                         'exit_short-sar_reversal'], name='exit_short-trigger')
        ]

    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators. Should be a copy of same method from strategy.
        Must align to populate_indicators in this file.
        Only used when --spaces does not include buy space.
        """
        dataframe.loc[
            (
                (dataframe['close'] < dataframe['bb_lowerband']) &
                (dataframe['mfi'] < 16) &
                (dataframe['adx'] > 25) &
                (dataframe['rsi'] < 21)
            ),
            'buy'] = 1

        return dataframe

    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators. Should be a copy of same method from strategy.
        Must align to populate_indicators in this file.
        Only used when --spaces does not include sell space.
        """
        dataframe.loc[
            (
                (qtpylib.crossed_above(
                    dataframe['macdsignal'], dataframe['macd']
                )) &
                (dataframe['fastd'] > 54)
            ),
            'sell'] = 1

        return dataframe

    def populate_short_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators. Should be a copy of same method from strategy.
        Must align to populate_indicators in this file.
        Only used when --spaces does not include short space.
        """
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['bb_upperband']) &
                (dataframe['mfi'] < 84) &
                (dataframe['adx'] > 75) &
                (dataframe['rsi'] < 79)
            ),
            'buy'] = 1

        return dataframe

    def populate_exit_short_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators. Should be a copy of same method from strategy.
        Must align to populate_indicators in this file.
        Only used when --spaces does not include exit_short space.
        """
        dataframe.loc[
            (
                (qtpylib.crossed_below(
                    dataframe['macdsignal'], dataframe['macd']
                )) &
                (dataframe['fastd'] < 46)
            ),
            'sell'] = 1

        return dataframe
