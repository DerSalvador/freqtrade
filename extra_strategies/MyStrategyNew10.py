# MyStrategyNew10
# Author: @ntsd (Jirawat Boonkumnerd)
# Github: https://github.com/ntsd
# V2 Update: Add periods for each timeframe
# V3 Update: Add operators
# V6 Update: Optimise by categories
# V7 Update: Optimise by using int parameter
# V8 Update: exit trend condition use from entry condition
# V8.1 Update: Remove second timeframe and second indicator to use same as first
# V9 Update: use all timeframe but optimise periods
# V10 Update: Add exit parameters and fix operator using cross above only the first timeframe
# freqtrade download-data --exchange binance -t 5m 15m 1h 4h --days 500
# freqtrade download-data --exchange binance -t 1d --days 1000
# ShortTradeDurHyperOptLoss, OnlyProfitHyperOptLoss, SharpeHyperOptLoss, SharpeHyperOptLossDaily, SortinoHyperOptLoss, SortinoHyperOptLossDaily
# freqtrade hyperopt --hyperopt-loss OnlyProfitHyperOptLoss --spaces entry exit --timeframe 5m -e 10000 --timerange 20200801-20210820 --strategy MyStrategyNew10
# freqtrade backtesting --timeframe 5m --timerange 20200801-20210820 --strategy MyStrategyNew10
from freqtrade.strategy import IStrategy, CategoricalParameter, IntParameter, merge_informative_pair
from pandas import DataFrame, Series
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from functools import reduce
import numpy as np
########################### Static Parameters ###########################
INDICATORS = ('EMA', 'SMA')
# Timeframes available for the exchange `Binance`: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
TIMEFRAMES = ('5m', '15m', '1h', '4h', '1d')
BASE_TIMEFRAME = TIMEFRAMES[0]
INFO_TIMEFRAMES = TIMEFRAMES[1:]
TIMEFRAMES_LEN = len(TIMEFRAMES)
SELL_TIMEFRAME = '1h'
PERIODS = []
n = 5
for i in range(1, 15):
    PERIODS.append(n)
    n += i
PERIODS_LEN = len(PERIODS)
MAX_CONDITIONS = TIMEFRAMES_LEN
# Default parameter
enter_long = {'entry_fperiod_0': 11, 'entry_fperiod_1': 0, 'entry_fperiod_2': 4, 'entry_fperiod_3': 4, 'entry_fperiod_4': 2, 'entry_indicator_0': 'SMA', 'entry_indicator_1': 'EMA', 'entry_indicator_2': 'SMA', 'entry_indicator_3': 'EMA', 'entry_indicator_4': 'SMA', 'entry_speriod_0': 0, 'entry_speriod_1': 1, 'entry_speriod_2': 10, 'entry_speriod_3': 7, 'entry_speriod_4': 5}
exit_long = {'exit_fperiod_0': 1, 'exit_indicator_0': 'EMA', 'exit_speriod_0': 10}
########################### Indicator ###########################

def normalize(df):
    df = (df - df.min()) / (df.max() - df.min())
    return df

def apply_indicator(dataframe: DataFrame, key: str, indicator: str, period: int):
    if key in dataframe.keys():
        return
    result = getattr(ta, indicator)(dataframe, timeperiod=period)
    # dataframe[key] = normalize(result)
    dataframe[key] = result
########################### Operators ###########################

def greater_operator(dataframe: DataFrame, main_indicator: str, crossed_indicator: str):
    return dataframe[main_indicator] > dataframe[crossed_indicator]

def true_operator(dataframe: DataFrame, main_indicator: str, crossed_indicator: str):
    return dataframe['volume'] > 10

def close_operator(dataframe: DataFrame, main_indicator: str, crossed_indicator: str):
    return np.isclose(dataframe[main_indicator], dataframe[crossed_indicator])

def crossed_operator(dataframe: DataFrame, main_indicator: str, crossed_indicator: str):
    return qtpylib.crossed_below(dataframe[main_indicator], dataframe[crossed_indicator]) | qtpylib.crossed_above(dataframe[main_indicator], dataframe[crossed_indicator])

def crossed_above_operator(dataframe: DataFrame, main_indicator: str, crossed_indicator: str):
    return qtpylib.crossed_above(dataframe[main_indicator], dataframe[crossed_indicator])

def crossed_below_operator(dataframe: DataFrame, main_indicator: str, crossed_indicator: str):
    return qtpylib.crossed_below(dataframe[main_indicator], dataframe[crossed_indicator])
OPERATORS = {'D': true_operator, '>': greater_operator, '=': close_operator, 'C': crossed_operator, 'CA': crossed_above_operator, 'CB': crossed_below_operator}

def apply_operator(dataframe: DataFrame, main_indicator, crossed_indicator, operator) -> tuple[Series, DataFrame]:
    condition = OPERATORS[operator](dataframe, main_indicator, crossed_indicator)
    return (condition, dataframe)
########################### HyperOpt Parameters ###########################

class DefaultValue:

    def __init__(self, value) -> None:
        self.value = value

def get_parameter_keys(trend: str, condition_idx: int):
    k_1 = f'{trend}_indicator_{condition_idx}'
    k_2 = f'{trend}_fperiod_{condition_idx}'
    k_3 = f'{trend}_speriod_{condition_idx}'
    return (k_1, k_2, k_3)

def set_hyperopt_parameters(self):
    trend = 'entry'
    for condition_idx in range(MAX_CONDITIONS):
        k_1, k_2, k_3 = get_parameter_keys(trend, condition_idx)
        if condition_idx < 4:
            setattr(self, k_1, CategoricalParameter(INDICATORS, space=trend))
            setattr(self, k_2, IntParameter(0, PERIODS_LEN - 1, space=trend, default=0))
            setattr(self, k_3, IntParameter(0, PERIODS_LEN - 1, space=trend, default=0))
        else:  # use default for 1 day timeframe
            setattr(self, k_1, DefaultValue(entry[k_1]))
            setattr(self, k_2, DefaultValue(entry[k_2]))
            setattr(self, k_3, DefaultValue(entry[k_3]))
    trend = 'exit'
    condition_idx = 0
    k_1, k_2, k_3 = get_parameter_keys(trend, condition_idx)
    setattr(self, k_1, CategoricalParameter(INDICATORS, space=trend))
    setattr(self, k_2, IntParameter(0, PERIODS_LEN - 1, space=trend, default=0))
    setattr(self, k_3, IntParameter(0, PERIODS_LEN - 1, space=trend, default=0))
    # setattr(self, k_1, DefaultValue(exit[k_1]))
    # setattr(self, k_2, DefaultValue(exit[k_2]))
    # setattr(self, k_3, DefaultValue(exit[k_3]))
    return self

@set_hyperopt_parameters
class MyStrategyNew10(IStrategy):
    INTERFACE_VERSION = 3
    # ROI table:
    minimal_roi = {'0': 1}
    # Trailing stop:
    trailing_stop = False
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = False
    # Stoploss
    stoploss = -1
    # Timeframe
    timeframe = BASE_TIMEFRAME
    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True
    # These values can be overridden in the "ask_strategy" section in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True
    # Number of candles the strategy requires before producing valid signals
    startup_candle_count = 500

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        print('Self:', self.__dict__)

    def get_hyperopt_parameters(self, trend: str, condition_idx: int):
        k_1, k_2, k_3 = get_parameter_keys(trend, condition_idx)
        indicator = getattr(self, k_1).value
        fperiod = getattr(self, k_2).value
        speriod = getattr(self, k_3).value
        return (indicator, fperiod, speriod)

    def get_indicators_pair(self, trend: str, condition_idx: int) -> tuple[str, str, str]:
        indicator, fperiod, speriod = self.get_hyperopt_parameters(trend, condition_idx)
        if fperiod == speriod:
            return (None, None, None)
        if trend == 'exit':
            operator = 'CB'
            exit_timeframe = SELL_TIMEFRAME
            main_indicator = f'{indicator}_{PERIODS[fperiod]}_{exit_timeframe}'
            crossed_indicator = f'{indicator}_{PERIODS[speriod]}_{exit_timeframe}'
        else:
            operator = 'CA' if condition_idx == 0 else '>'
            main_indicator = f'{indicator}_{PERIODS[fperiod]}_{TIMEFRAMES[condition_idx]}'
            crossed_indicator = f'{indicator}_{PERIODS[speriod]}_{TIMEFRAMES[condition_idx]}'
        return (main_indicator, crossed_indicator, operator)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        assert self.dp, 'DataProvider is required for multiple timeframes.'
        avalidable_indicators = set()
        avalidable_info_timeframes = set()
        avalidable_periods = set()
        run_mode = self.dp.runmode.value
        if run_mode in ('backtest', 'live', 'dry_run'):
            # for these mode only add for current parameters setting
            trend = 'entry'
            for condition_idx in range(MAX_CONDITIONS):
                indicator, fperiod, speriod = self.get_hyperopt_parameters(trend, condition_idx)
                avalidable_indicators.add(indicator)
                avalidable_info_timeframes.add(TIMEFRAMES[condition_idx])
                avalidable_periods.add(PERIODS[fperiod])
                avalidable_periods.add(PERIODS[speriod])
            trend = 'exit'
            indicator, fperiod, speriod = self.get_hyperopt_parameters(trend, 0)
            avalidable_indicators.add(indicator)
            avalidable_periods.add(PERIODS[fperiod])
            avalidable_periods.add(PERIODS[speriod])
        else:
            avalidable_indicators = INDICATORS
            avalidable_info_timeframes = INFO_TIMEFRAMES
            avalidable_periods = PERIODS
        # apply info timeframe indicator
        for info_timeframe in avalidable_info_timeframes:
            info_dataframe = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=info_timeframe)
            for indicator in avalidable_indicators:
                for period in avalidable_periods:
                    apply_indicator(info_dataframe, f'{indicator}_{period}', indicator, period)
            dataframe = merge_informative_pair(dataframe, info_dataframe, self.timeframe, info_timeframe, ffill=True)
        # apply base timeframe indicator
        for indicator in avalidable_indicators:
            for period in avalidable_periods:
                apply_indicator(dataframe, f'{indicator}_{period}_{BASE_TIMEFRAME}', indicator, period)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        trend = 'entry'
        conditions = list()
        for condition_idx in range(MAX_CONDITIONS):
            main_indicator, crossed_indicator, operator = self.get_indicators_pair(trend, condition_idx)
            if not operator:
                continue
            condition, dataframe = apply_operator(dataframe, main_indicator, crossed_indicator, operator)
            conditions.append(condition)
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = list()
        condition_idx = 0
        main_indicator, crossed_indicator, operator = self.get_indicators_pair('exit', condition_idx)
        if operator:
            condition, dataframe = apply_operator(dataframe, main_indicator, crossed_indicator, operator)
            conditions.append(condition)  # bitwaise not condition
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'exit_long'] = 1
        return dataframe