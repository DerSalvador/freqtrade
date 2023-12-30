"""
this strat entry deep and exit up and it's not smart sorry
u or gain profit or just hodl(when drawdown)
i fixed some of false signal, thank EMA(200)
when long drawdown, some time u get only exit_profit_offset! Because get false exit signal bellow entry price.
but u have no stop-loss and exit only profit

Do Backtesting first
freqtrade backtesting -s SmartMoneyStrategy --timerange 20210601- -i 1h -p DOT/USDT

Lets plot:
freqtrade plot-dataframe -s SmartMoneyStrategy --timerange 20210601- -i 1h -p DOT/USDT --indicators1 ema_200 --indicators2 cmf mfi

Params hyper-optable, just use class SmartMoneyStrategyHyperopt
freqtrade hyperopt --hyperopt-loss SharpeHyperOptLoss --strategy SmartMoneyStrategyHyperopt --spaces entry exit --timerange 20210601- --dry-run-wallet 160 --stake 12 -i 1h -e 1000
"""
import numpy
import talib.abstract as ta
from pandas import DataFrame
from technical.indicators import chaikin_money_flow
from freqtrade.strategy import DecimalParameter, IStrategy, IntParameter

class SmartMoneyStrategy(IStrategy):
    INTERFACE_VERSION = 3
    # Minimal ROI designed for the strategy.
    minimal_roi = {'0': 10}
    # Stoploss:
    stoploss = -1
    # Optimal timeframe for the strategy
    timeframe = '30m'
    exit_profit_only = True
    exit_profit_offset = 0.01
    # enumeration of indicators

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Chaikin
        dataframe['cmf'] = chaikin_money_flow(dataframe, period=20)
        # MFI
        dataframe['mfi'] = ta.MFI(dataframe)
        # EMA
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        return dataframe
    # params for entry

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['close'] < dataframe['ema_200']) & (dataframe['mfi'] < 35) & (dataframe['cmf'] < -0.07), 'enter_long'] = 1
        return dataframe
    # params for exit

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['close'] > dataframe['ema_200']) & (dataframe['mfi'] > 70) & (dataframe['cmf'] > 0.2), 'exit_long'] = 1
        #         dataframe.to_csv('./exit_result.csv')
        return dataframe
# FOR HYPEROPT

class SmartMoneyStrategyHyperopt(IStrategy):
    INTERFACE_VERSION = 3
    # ROI table:
    minimal_roi = {'0': 10}
    # Stoploss:
    stoploss = -1
    # Optimal timeframe for the strategy
    timeframe = '1h'
    exit_profit_only = True
    exit_profit_offset = 0.01
    # entry params
    entry_mfi = IntParameter(20, 60, default=35, space='entry')
    entry_cmf = DecimalParameter(-0.4, -0.01, decimals=2, default=-0.07, space='entry')
    # exit params
    exit_mfi = IntParameter(50, 95, default=70, space='exit')
    exit_cmf = DecimalParameter(0.1, 0.6, decimals=2, default=0.2, space='exit')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Chaikin
        dataframe['cmf'] = chaikin_money_flow(dataframe, period=20)
        # MFI
        dataframe['mfi'] = ta.MFI(dataframe)
        # EMA
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['close'] < dataframe['ema_200']) & (dataframe['mfi'] < self.entry_mfi.value) & (dataframe['cmf'] < self.entry_cmf.value), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['close'] > dataframe['ema_200']) & (dataframe['mfi'] > self.exit_mfi.value) & (dataframe['cmf'] > self.exit_cmf.value), 'exit_long'] = 1
        return dataframe