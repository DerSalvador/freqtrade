# GodStraNew Strategy
# Author: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/
# freqtrade hyperopt --hyperopt-loss SharpeHyperOptLoss --spaces entry roi trailing exit --strategy GodStraNew
# --- Do not remove these libs ---
from freqtrade import data
from freqtrade.strategy import CategoricalParameter, DecimalParameter
from numpy.lib import math
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
# --------------------------------
# Add your lib to import here
# TODO: talib is fast but have not more indicators
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from functools import reduce
import numpy as np
from random import shuffle
#  TODO: this gene is removed 'MAVP' cuz or error on periods
# Bollinger Bands
# Bollinger Bands
# Bollinger Bands
# Double Exponential Moving Average
# Exponential Moving Average
# Hilbert Transform - Instantaneous Trendline
# Kaufman Adaptive Moving Average
# Moving average
# MESA Adaptive Moving Average
# MESA Adaptive Moving Average
# TODO: Fix this
# 'MAVP',               # Moving average with variable period
# MidPoint over period
# Midpoint Price over period
# Parabolic SAR
# Parabolic SAR - Extended
# Simple Moving Average
# Triple Exponential Moving Average (T3)
# Triple Exponential Moving Average
# Triangular Moving Average
# Weighted Moving Average
# Average Directional Movement Index
# Average Directional Movement Index Rating
# Absolute Price Oscillator
# Aroon
# Aroon
# Aroon Oscillator
# Balance Of Power
# Commodity Channel Index
# Chande Momentum Oscillator
# Directional Movement Index
# Moving Average Convergence/Divergence
# Moving Average Convergence/Divergence
# Moving Average Convergence/Divergence
# MACD with controllable MA type
# MACD with controllable MA type
# MACD with controllable MA type
# Moving Average Convergence/Divergence Fix 12/26
# Moving Average Convergence/Divergence Fix 12/26
# Moving Average Convergence/Divergence Fix 12/26
# Money Flow Index
# Minus Directional Indicator
# Minus Directional Movement
# Momentum
# Plus Directional Indicator
# Plus Directional Movement
# Percentage Price Oscillator
# Rate of change : ((price/prevPrice)-1)*100
# Rate of change Percentage: (price-prevPrice)/prevPrice
# Rate of change ratio: (price/prevPrice)
# Rate of change ratio 100 scale: (price/prevPrice)*100
# Relative Strength Index
# Stochastic
# Stochastic
# Stochastic Fast
# Stochastic Fast
# Stochastic Relative Strength Index
# Stochastic Relative Strength Index
# 1-day Rate-Of-Change (ROC) of a Triple Smooth EMA
# Ultimate Oscillator
# Williams' %R
# Chaikin A/D Line
# Chaikin A/D Oscillator
# On Balance Volume
# Average True Range
# Normalized Average True Range
# True Range
# Average Price
# Median Price
# Typical Price
# Weighted Close Price
# Hilbert Transform - Dominant Cycle Period
# Hilbert Transform - Dominant Cycle Phase
# Hilbert Transform - Phasor Components
# Hilbert Transform - Phasor Components
# Hilbert Transform - SineWave
# Hilbert Transform - SineWave
# Hilbert Transform - Trend vs Cycle Mode
# Two Crows
# Three Black Crows
# Three Inside Up/Down
# Three-Line Strike
# Three Outside Up/Down
# Three Stars In The South
# Three Advancing White Soldiers
# Abandoned Baby
# Advance Block
# Belt-hold
# Breakaway
# Closing Marubozu
# Concealing Baby Swallow
# Counterattack
# Dark Cloud Cover
# Doji
# Doji Star
# Dragonfly Doji
# Engulfing Pattern
# Evening Doji Star
# Evening Star
# Up/Down-gap side-by-side white lines
# Gravestone Doji
# Hammer
# Hanging Man
# Harami Pattern
# Harami Cross Pattern
# High-Wave Candle
# Hikkake Pattern
# Modified Hikkake Pattern
# Homing Pigeon
# Identical Three Crows
# In-Neck Pattern
# Inverted Hammer
# Kicking
# Kicking - bull/bear determined by the longer marubozu
# Ladder Bottom
# Long Legged Doji
# Long Line Candle
# Marubozu
# Matching Low
# Mat Hold
# Morning Doji Star
# Morning Star
# On-Neck Pattern
# Piercing Pattern
# Rickshaw Man
# Rising/Falling Three Methods
# Separating Lines
# Shooting Star
# Short Line Candle
# Spinning Top
# Stalled Pattern
# Stick Sandwich
# Takuri (Dragonfly Doji with very long lower shadow)
# Tasuki Gap
# Thrusting Pattern
# Tristar Pattern
# Unique 3 River
# Upside Gap Two Crows
# Upside/Downside Gap Three Methods
# Beta
# Pearson's Correlation Coefficient (r)
# Linear Regression
# Linear Regression Angle
# Linear Regression Intercept
# Linear Regression Slope
# Standard Deviation
# Time Series Forecast
# Variance
all_god_genes = {'Overlap Studies': {'BBANDS-0', 'BBANDS-1', 'BBANDS-2', 'DEMA', 'EMA', 'HT_TRENDLINE', 'KAMA', 'MA', 'MAMA-0', 'MAMA-1', 'MIDPOINT', 'MIDPRICE', 'SAR', 'SAREXT', 'SMA', 'T3', 'TEMA', 'TRIMA', 'WMA'}, 'Momentum Indicators': {'ADX', 'ADXR', 'APO', 'AROON-0', 'AROON-1', 'AROONOSC', 'BOP', 'CCI', 'CMO', 'DX', 'MACD-0', 'MACD-1', 'MACD-2', 'MACDEXT-0', 'MACDEXT-1', 'MACDEXT-2', 'MACDFIX-0', 'MACDFIX-1', 'MACDFIX-2', 'MFI', 'MINUS_DI', 'MINUS_DM', 'MOM', 'PLUS_DI', 'PLUS_DM', 'PPO', 'ROC', 'ROCP', 'ROCR', 'ROCR100', 'RSI', 'STOCH-0', 'STOCH-1', 'STOCHF-0', 'STOCHF-1', 'STOCHRSI-0', 'STOCHRSI-1', 'TRIX', 'ULTOSC', 'WILLR'}, 'Volume Indicators': {'AD', 'ADOSC', 'OBV'}, 'Volatility Indicators': {'ATR', 'NATR', 'TRANGE'}, 'Price Transform': {'AVGPRICE', 'MEDPRICE', 'TYPPRICE', 'WCLPRICE'}, 'Cycle Indicators': {'HT_DCPERIOD', 'HT_DCPHASE', 'HT_PHASOR-0', 'HT_PHASOR-1', 'HT_SINE-0', 'HT_SINE-1', 'HT_TRENDMODE'}, 'Pattern Recognition': {'CDL2CROWS', 'CDL3BLACKCROWS', 'CDL3INSIDE', 'CDL3LINESTRIKE', 'CDL3OUTSIDE', 'CDL3STARSINSOUTH', 'CDL3WHITESOLDIERS', 'CDLABANDONEDBABY', 'CDLADVANCEBLOCK', 'CDLBELTHOLD', 'CDLBREAKAWAY', 'CDLCLOSINGMARUBOZU', 'CDLCONCEALBABYSWALL', 'CDLCOUNTERATTACK', 'CDLDARKCLOUDCOVER', 'CDLDOJI', 'CDLDOJISTAR', 'CDLDRAGONFLYDOJI', 'CDLENGULFING', 'CDLEVENINGDOJISTAR', 'CDLEVENINGSTAR', 'CDLGAPSIDESIDEWHITE', 'CDLGRAVESTONEDOJI', 'CDLHAMMER', 'CDLHANGINGMAN', 'CDLHARAMI', 'CDLHARAMICROSS', 'CDLHIGHWAVE', 'CDLHIKKAKE', 'CDLHIKKAKEMOD', 'CDLHOMINGPIGEON', 'CDLIDENTICAL3CROWS', 'CDLINNECK', 'CDLINVERTEDHAMMER', 'CDLKICKING', 'CDLKICKINGBYLENGTH', 'CDLLADDERBOTTOM', 'CDLLONGLEGGEDDOJI', 'CDLLONGLINE', 'CDLMARUBOZU', 'CDLMATCHINGLOW', 'CDLMATHOLD', 'CDLMORNINGDOJISTAR', 'CDLMORNINGSTAR', 'CDLONNECK', 'CDLPIERCING', 'CDLRICKSHAWMAN', 'CDLRISEFALL3METHODS', 'CDLSEPARATINGLINES', 'CDLSHOOTINGSTAR', 'CDLSHORTLINE', 'CDLSPINNINGTOP', 'CDLSTALLEDPATTERN', 'CDLSTICKSANDWICH', 'CDLTAKURI', 'CDLTASUKIGAP', 'CDLTHRUSTING', 'CDLTRISTAR', 'CDLUNIQUE3RIVER', 'CDLUPSIDEGAP2CROWS', 'CDLXSIDEGAP3METHODS'}, 'Statistic Functions': {'BETA', 'CORREL', 'LINEARREG', 'LINEARREG_ANGLE', 'LINEARREG_INTERCEPT', 'LINEARREG_SLOPE', 'STDDEV', 'TSF', 'VAR'}}
god_genes = set()
########################### SETTINGS ##############################
god_genes = {'SMA'}
# god_genes |= all_god_genes['Overlap Studies']
# god_genes |= all_god_genes['Momentum Indicators']
# god_genes |= all_god_genes['Volume Indicators']
# god_genes |= all_god_genes['Volatility Indicators']
# god_genes |= all_god_genes['Price Transform']
# god_genes |= all_god_genes['Cycle Indicators']
# god_genes |= all_god_genes['Pattern Recognition']
# god_genes |= all_god_genes['Statistic Functions']
timeperiods = [5, 6, 12, 15, 50, 55, 100, 110]  # Disabled gene
# Indicator, bigger than cross indicator
# Indicator, smaller than cross indicator
# Indicator, equal with cross indicator
# Indicator, crossed the cross indicator
# Indicator, crossed above the cross indicator
# Indicator, crossed below the cross indicator
# Normalized indicator, bigger than real number
# Normalized indicator, equal with real number
# Normalized indicator, smaller than real number
# Normalized indicator devided to cross indicator, bigger than real number
# Normalized indicator devided to cross indicator, equal with real number
# Normalized indicator devided to cross indicator, smaller than real number
# Indicator, is in UpTrend status
# Indicator, is in DownTrend status
# Indicator, is in Off trend status(RANGE)
# Indicator, Entered to UpTrend status
# Indicator, Entered to DownTrend status
# Indicator, Entered to Off trend status(RANGE)
operators = ['D', '>', '<', '=', 'C', 'CA', 'CB', '>R', '=R', '<R', '/>R', '/=R', '/<R', 'UT', 'DT', 'OT', 'CUT', 'CDT', 'COT']
# number of candles to check up,don,off trend.
TREND_CHECK_CANDLES = 4
DECIMALS = 1
########################### END SETTINGS ##########################
# DATAFRAME = DataFrame()
god_genes = list(god_genes)
# print('selected indicators for optimzatin: \n', god_genes)
god_genes_with_timeperiod = list()
for god_gene in god_genes:
    for timeperiod in timeperiods:
        god_genes_with_timeperiod.append(f'{god_gene}-{timeperiod}')
# Let give somethings to CatagoricalParam to Play with them
# When just one thing is inside catagorical lists
# TODO: its Not True Way :)
if len(god_genes) == 1:
    god_genes = god_genes * 2
if len(timeperiods) == 1:
    timeperiods = timeperiods * 2
if len(operators) == 1:
    operators = operators * 2

def normalize(df):
    df = (df - df.min()) / (df.max() - df.min())
    return df

def gene_calculator(dataframe, indicator):
    # Cuz Timeperiods not effect calculating CDL patterns recognations
    if 'CDL' in indicator:
        splited_indicator = indicator.split('-')
        splited_indicator[1] = '0'
        new_indicator = '-'.join(splited_indicator)
        # print(indicator, new_indicator)
        indicator = new_indicator
    gene = indicator.split('-')
    gene_name = gene[0]
    gene_len = len(gene)
    if indicator in dataframe.keys():
        # print(f"{indicator}, calculated befoure")
        # print(len(dataframe.keys()))
        return dataframe[indicator]
    else:
        result = None
        # For Pattern Recognations
        if gene_len == 1:
            # print('gene_len == 1\t', indicator)
            result = getattr(ta, gene_name)(dataframe)
            return normalize(result)
        elif gene_len == 2:
            # print('gene_len == 2\t', indicator)
            gene_timeperiod = int(gene[1])
            result = getattr(ta, gene_name)(dataframe, timeperiod=gene_timeperiod)
            return normalize(result)
        # For
        elif gene_len == 3:
            # print('gene_len == 3\t', indicator)
            gene_timeperiod = int(gene[2])
            gene_index = int(gene[1])
            result = getattr(ta, gene_name)(dataframe, timeperiod=gene_timeperiod).iloc[:, gene_index]
            return normalize(result)
        # For trend operators(MA-5-SMA-4)
        elif gene_len == 4:
            # print('gene_len == 4\t', indicator)
            gene_timeperiod = int(gene[1])
            sharp_indicator = f'{gene_name}-{gene_timeperiod}'
            dataframe[sharp_indicator] = getattr(ta, gene_name)(dataframe, timeperiod=gene_timeperiod)
            return normalize(ta.SMA(dataframe[sharp_indicator].fillna(0), TREND_CHECK_CANDLES))
        # For trend operators(STOCH-0-4-SMA-4)
        elif gene_len == 5:
            # print('gene_len == 5\t', indicator)
            gene_timeperiod = int(gene[2])
            gene_index = int(gene[1])
            sharp_indicator = f'{gene_name}-{gene_index}-{gene_timeperiod}'
            dataframe[sharp_indicator] = getattr(ta, gene_name)(dataframe, timeperiod=gene_timeperiod).iloc[:, gene_index]
            return normalize(ta.SMA(dataframe[sharp_indicator].fillna(0), TREND_CHECK_CANDLES))

def condition_generator(dataframe, operator, indicator, crossed_indicator, real_num):
    condition = dataframe['volume'] > 10
    # TODO : it ill callculated in populate indicators.
    dataframe[indicator] = gene_calculator(dataframe, indicator)
    dataframe[crossed_indicator] = gene_calculator(dataframe, crossed_indicator)
    indicator_trend_sma = f'{indicator}-SMA-{TREND_CHECK_CANDLES}'
    if operator in ['UT', 'DT', 'OT', 'CUT', 'CDT', 'COT']:
        dataframe[indicator_trend_sma] = gene_calculator(dataframe, indicator_trend_sma)
    if operator == '>':
        condition = dataframe[indicator] > dataframe[crossed_indicator]
    elif operator == '=':
        condition = np.isclose(dataframe[indicator], dataframe[crossed_indicator])
    elif operator == '<':
        condition = dataframe[indicator] < dataframe[crossed_indicator]
    elif operator == 'C':
        condition = qtpylib.crossed_below(dataframe[indicator], dataframe[crossed_indicator]) | qtpylib.crossed_above(dataframe[indicator], dataframe[crossed_indicator])
    elif operator == 'CA':
        condition = qtpylib.crossed_above(dataframe[indicator], dataframe[crossed_indicator])
    elif operator == 'CB':
        condition = qtpylib.crossed_below(dataframe[indicator], dataframe[crossed_indicator])
    elif operator == '>R':
        condition = dataframe[indicator] > real_num
    elif operator == '=R':
        condition = np.isclose(dataframe[indicator], real_num)
    elif operator == '<R':
        condition = dataframe[indicator] < real_num
    elif operator == '/>R':
        condition = dataframe[indicator].div(dataframe[crossed_indicator]) > real_num
    elif operator == '/=R':
        condition = np.isclose(dataframe[indicator].div(dataframe[crossed_indicator]), real_num)
    elif operator == '/<R':
        condition = dataframe[indicator].div(dataframe[crossed_indicator]) < real_num
    elif operator == 'UT':
        condition = dataframe[indicator] > dataframe[indicator_trend_sma]
    elif operator == 'DT':
        condition = dataframe[indicator] < dataframe[indicator_trend_sma]
    elif operator == 'OT':
        condition = np.isclose(dataframe[indicator], dataframe[indicator_trend_sma])
    elif operator == 'CUT':
        condition = qtpylib.crossed_above(dataframe[indicator], dataframe[indicator_trend_sma]) & (dataframe[indicator] > dataframe[indicator_trend_sma])
    elif operator == 'CDT':
        condition = qtpylib.crossed_below(dataframe[indicator], dataframe[indicator_trend_sma]) & (dataframe[indicator] < dataframe[indicator_trend_sma])
    elif operator == 'COT':
        condition = (qtpylib.crossed_below(dataframe[indicator], dataframe[indicator_trend_sma]) | qtpylib.crossed_above(dataframe[indicator], dataframe[indicator_trend_sma])) & np.isclose(dataframe[indicator], dataframe[indicator_trend_sma])
    return (condition, dataframe)
# Buy hyperspace params:
entry_params = {'entry_crossed_indicator0': 'SMA-5', 'entry_crossed_indicator1': 'SMA-12', 'entry_crossed_indicator2': 'SMA-5', 'entry_indicator0': 'SMA-15', 'entry_indicator1': 'SMA-100', 'entry_indicator2': 'SMA-110', 'entry_operator0': '<R', 'entry_operator1': '>', 'entry_operator2': '>', 'entry_real_num0': 0.2, 'entry_real_num1': 0.5, 'entry_real_num2': 1.0}
# Sell hyperspace params:
exit_params = {'exit_crossed_indicator0': 'SMA-100', 'exit_crossed_indicator1': 'SMA-100', 'exit_crossed_indicator2': 'SMA-15', 'exit_indicator0': 'SMA-5', 'exit_indicator1': 'SMA-5', 'exit_indicator2': 'SMA-12', 'exit_operator0': 'CB', 'exit_operator1': 'CUT', 'exit_operator2': 'OT', 'exit_real_num0': 0.6, 'exit_real_num1': 0.5, 'exit_real_num2': 0.7}

class GodStraNew40(IStrategy):
    INTERFACE_VERSION = 3
    # #################### RESULTS PASTE PLACE ####################
    # #################### END OF RESULT PLACE ####################
    # TODO: Its not dry code!
    # Buy Hyperoptable Parameters/Spaces.
    entry_crossed_indicator0 = CategoricalParameter(god_genes_with_timeperiod, default=entry_params['entry_crossed_indicator0'], space='entry')
    entry_crossed_indicator1 = CategoricalParameter(god_genes_with_timeperiod, default=entry_params['entry_crossed_indicator1'], space='entry')
    entry_crossed_indicator2 = CategoricalParameter(god_genes_with_timeperiod, default=entry_params['entry_crossed_indicator2'], space='entry')
    entry_indicator0 = CategoricalParameter(god_genes_with_timeperiod, default=entry_params['entry_indicator0'], space='entry')
    entry_indicator1 = CategoricalParameter(god_genes_with_timeperiod, default=entry_params['entry_indicator1'], space='entry')
    entry_indicator2 = CategoricalParameter(god_genes_with_timeperiod, default=entry_params['entry_indicator2'], space='entry')
    entry_operator0 = CategoricalParameter(operators, default=entry_params['entry_operator0'], space='entry')
    entry_operator1 = CategoricalParameter(operators, default=entry_params['entry_operator1'], space='entry')
    entry_operator2 = CategoricalParameter(operators, default=entry_params['entry_operator2'], space='entry')
    entry_real_num0 = DecimalParameter(0, 1, decimals=DECIMALS, default=entry_params['entry_real_num0'], space='entry')
    entry_real_num1 = DecimalParameter(0, 1, decimals=DECIMALS, default=entry_params['entry_real_num1'], space='entry')
    entry_real_num2 = DecimalParameter(0, 1, decimals=DECIMALS, default=entry_params['entry_real_num2'], space='entry')
    # Sell Hyperoptable Parameters/Spaces.
    exit_crossed_indicator0 = CategoricalParameter(god_genes_with_timeperiod, default=exit_params['exit_crossed_indicator0'], space='exit')
    exit_crossed_indicator1 = CategoricalParameter(god_genes_with_timeperiod, default=exit_params['exit_crossed_indicator1'], space='exit')
    exit_crossed_indicator2 = CategoricalParameter(god_genes_with_timeperiod, default=exit_params['exit_crossed_indicator2'], space='exit')
    exit_indicator0 = CategoricalParameter(god_genes_with_timeperiod, default=exit_params['exit_indicator0'], space='exit')
    exit_indicator1 = CategoricalParameter(god_genes_with_timeperiod, default=exit_params['exit_indicator1'], space='exit')
    exit_indicator2 = CategoricalParameter(god_genes_with_timeperiod, default=exit_params['exit_indicator2'], space='exit')
    exit_operator0 = CategoricalParameter(operators, default=exit_params['exit_operator0'], space='exit')
    exit_operator1 = CategoricalParameter(operators, default=exit_params['exit_operator1'], space='exit')
    exit_operator2 = CategoricalParameter(operators, default=exit_params['exit_operator2'], space='exit')
    exit_real_num0 = DecimalParameter(0, 1, decimals=DECIMALS, default=exit_params['exit_real_num0'], space='exit')
    exit_real_num1 = DecimalParameter(0, 1, decimals=DECIMALS, default=exit_params['exit_real_num1'], space='exit')
    exit_real_num2 = DecimalParameter(0, 1, decimals=DECIMALS, default=exit_params['exit_real_num2'], space='exit')
    # Stoploss:
    stoploss = -1
    # Buy hypers
    timeframe = '4h'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        It's good to calculate all indicators in all time periods here and so optimize the strategy.
        But this strategy can take much time to generate anything that may not use in his optimization.
        I just calculate the specific indicators in specific time period inside entry and exit strategy populator methods if needed.
        Also, this method (populate_indicators) just calculates default value of hyperoptable params
        so using this method have not big benefits instade of calculating useable things inside entry and exit trand populators
        """
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = list()
        # TODO: Its not dry code!
        entry_indicator = self.entry_indicator0.value
        entry_crossed_indicator = self.entry_crossed_indicator0.value
        entry_operator = self.entry_operator0.value
        entry_real_num = self.entry_real_num0.value
        condition, dataframe = condition_generator(dataframe, entry_operator, entry_indicator, entry_crossed_indicator, entry_real_num)
        conditions.append(condition)
        # backup
        entry_indicator = self.entry_indicator1.value
        entry_crossed_indicator = self.entry_crossed_indicator1.value
        entry_operator = self.entry_operator1.value
        entry_real_num = self.entry_real_num1.value
        condition, dataframe = condition_generator(dataframe, entry_operator, entry_indicator, entry_crossed_indicator, entry_real_num)
        conditions.append(condition)
        entry_indicator = self.entry_indicator2.value
        entry_crossed_indicator = self.entry_crossed_indicator2.value
        entry_operator = self.entry_operator2.value
        entry_real_num = self.entry_real_num2.value
        condition, dataframe = condition_generator(dataframe, entry_operator, entry_indicator, entry_crossed_indicator, entry_real_num)
        conditions.append(condition)
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'enter_long'] = 1
        # print(len(dataframe.keys()))
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = list()
        # TODO: Its not dry code!
        exit_indicator = self.exit_indicator0.value
        exit_crossed_indicator = self.exit_crossed_indicator0.value
        exit_operator = self.exit_operator0.value
        exit_real_num = self.exit_real_num0.value
        condition, dataframe = condition_generator(dataframe, exit_operator, exit_indicator, exit_crossed_indicator, exit_real_num)
        conditions.append(condition)
        exit_indicator = self.exit_indicator1.value
        exit_crossed_indicator = self.exit_crossed_indicator1.value
        exit_operator = self.exit_operator1.value
        exit_real_num = self.exit_real_num1.value
        condition, dataframe = condition_generator(dataframe, exit_operator, exit_indicator, exit_crossed_indicator, exit_real_num)
        conditions.append(condition)
        exit_indicator = self.exit_indicator2.value
        exit_crossed_indicator = self.exit_crossed_indicator2.value
        exit_operator = self.exit_operator2.value
        exit_real_num = self.exit_real_num2.value
        condition, dataframe = condition_generator(dataframe, exit_operator, exit_indicator, exit_crossed_indicator, exit_real_num)
        conditions.append(condition)
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'exit_long'] = 1
        return dataframe