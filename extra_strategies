# DevilStra Strategy
# 𝔇𝔢𝔳𝔦𝔩 𝔦𝔰 𝔞𝔩𝔴𝔞𝔶𝔰 𝔰𝔱𝔯𝔬𝔫𝔤𝔢𝔯 𝔱𝔥𝔞𝔫 𝔊𝔬𝔡.
# 𝔅𝔲𝔱 𝔱𝔥𝔢 𝔬𝔫𝔩𝔶 𝔬𝔫𝔢 𝔴𝔥𝔬 𝔥𝔞𝔰 𝔱𝔥𝔢 𝔞𝔟𝔦𝔩𝔦𝔱𝔶
# 𝔗𝔬 𝔠𝔯𝔢𝔞𝔱𝔢 𝔫𝔢𝔴 𝔠𝔯𝔢𝔞𝔱𝔲𝔯𝔢𝔰 𝔦𝔰 𝔊𝔬𝔡.
# 𝔄𝔫𝔡 𝔱𝔥𝔢 𝔇𝔢𝔳𝔦𝔩 𝔪𝔞𝔨𝔢𝔰 𝔭𝔬𝔴𝔢𝔯𝔣𝔲𝔩 𝔰𝔭𝔢𝔩𝔩𝔰
# 𝔉𝔯𝔬𝔪 𝔱𝔥𝔦𝔰 𝔰𝔪𝔞𝔩𝔩 𝔠𝔯𝔢𝔞𝔱𝔲𝔯𝔢𝔰 (𝔩𝔦𝔨𝔢 𝔣𝔯𝔬𝔤𝔰, 𝔢𝔱𝔠.)
# 𝔚𝔦𝔱𝔥 𝔣𝔯𝔞𝔤𝔪𝔢𝔫𝔱𝔞𝔱𝔦𝔬𝔫 𝔞𝔫𝔡 𝔪𝔦𝔵𝔦𝔫𝔤 𝔱𝔥𝔢𝔪.
# Author: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/
# * IMPORTANT: You Need An "STATIC" Pairlist On Your Config.json !
# * IMPORTANT: First set PAIR_LIST_LENGHT={pair_whitelist size}
# * And re-hyperopt the Sell strategy And paste result in exact
# * place(lines 535~564)
# freqtrade hyperopt --hyperopt-loss SharpeHyperOptLoss --spaces entry exit -s 𝕯𝖊𝖛𝖎𝖑𝕾𝖙𝖗𝖆
# --- Do not remove these libs ---
import numpy as np
from functools import reduce
import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
import random
from freqtrade.strategy import CategoricalParameter, DecimalParameter, IntParameter
from numpy.lib import math
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
# ########################## SETTINGS ##############################
# pairlist lenght(use exact count of pairs you used in whitelist size+1):
PAIR_LIST_LENGHT = 269
# you can find exact value of this inside GodStraNew
TREND_CHECK_CANDLES = 4
# Set the pain range of devil(2~9999)
PAIN_RANGE = 1000
# Add "GodStraNew" Generated Results As spells inside SPELLS.
# Set them unic phonemes like 'Zi' 'Gu' or 'Lu'!
# * Use below replacement on GodStraNew results to
# * Change God Generated Creatures to Spells:
# +-----------------------------+----------------------+
# | GodStraNew Hyperopt Results |   DevilStra Spells   |
# +-----------------------------+----------------------+
# |                             | "phonem" : {         |
# |    entry_params =  {          |    "entry_params" : {  |
# |      ...                    |      ...             |
# |    }                        |    },                |
# |    exit_params = {          |    "exit_params" : { |
# |      ...                    |      ...             |
# |    }                        |    }                 |
# |                             | },                   |
# +-----------------------------+----------------------+
SPELLS = {'Zi': {'entry_params': {'entry_crossed_indicator0': 'BOP-4', 'entry_crossed_indicator1': 'MACD-0-50', 'entry_crossed_indicator2': 'DEMA-52', 'entry_indicator0': 'MINUS_DI-50', 'entry_indicator1': 'HT_TRENDMODE-50', 'entry_indicator2': 'CORREL-128', 'entry_operator0': '/>R', 'entry_operator1': 'CA', 'entry_operator2': 'CDT', 'entry_real_num0': 0.1763, 'entry_real_num1': 0.6891, 'entry_real_num2': 0.0509}, 'exit_params': {'exit_crossed_indicator0': 'WCLPRICE-52', 'exit_crossed_indicator1': 'AROONOSC-15', 'exit_crossed_indicator2': 'CDLRISEFALL3METHODS-52', 'exit_indicator0': 'COS-50', 'exit_indicator1': 'CDLCLOSINGMARUBOZU-30', 'exit_indicator2': 'CDL2CROWS-130', 'exit_operator0': 'DT', 'exit_operator1': '>R', 'exit_operator2': '/>R', 'exit_real_num0': 0.0678, 'exit_real_num1': 0.8698, 'exit_real_num2': 0.3917}}, 'Gu': {'entry_params': {'entry_crossed_indicator0': 'SMA-20', 'entry_crossed_indicator1': 'CDLLADDERBOTTOM-20', 'entry_crossed_indicator2': 'OBV-50', 'entry_indicator0': 'MAMA-1-50', 'entry_indicator1': 'SUM-40', 'entry_indicator2': 'VAR-30', 'entry_operator0': '<R', 'entry_operator1': 'D', 'entry_operator2': 'D', 'entry_real_num0': 0.2644, 'entry_real_num1': 0.0736, 'entry_real_num2': 0.8954}, 'exit_params': {'exit_crossed_indicator0': 'CDLLADDERBOTTOM-50', 'exit_crossed_indicator1': 'CDLHARAMICROSS-50', 'exit_crossed_indicator2': 'CDLDARKCLOUDCOVER-30', 'exit_indicator0': 'CDLLADDERBOTTOM-10', 'exit_indicator1': 'MAMA-1-40', 'exit_indicator2': 'OBV-30', 'exit_operator0': 'UT', 'exit_operator1': '>R', 'exit_operator2': 'CUT', 'exit_real_num0': 0.2707, 'exit_real_num1': 0.7987, 'exit_real_num2': 0.6891}}, 'Lu': {'entry_params': {'entry_crossed_indicator0': 'HT_SINE-0-28', 'entry_crossed_indicator1': 'ADD-130', 'entry_crossed_indicator2': 'ADD-12', 'entry_indicator0': 'ADD-28', 'entry_indicator1': 'AVGPRICE-15', 'entry_indicator2': 'AVGPRICE-12', 'entry_operator0': 'DT', 'entry_operator1': 'D', 'entry_operator2': 'C', 'entry_real_num0': 0.3676, 'entry_real_num1': 0.4284, 'entry_real_num2': 0.372}, 'exit_params': {'exit_crossed_indicator0': 'HT_SINE-0-5', 'exit_crossed_indicator1': 'HT_SINE-0-4', 'exit_crossed_indicator2': 'HT_SINE-0-28', 'exit_indicator0': 'ADD-30', 'exit_indicator1': 'AVGPRICE-28', 'exit_indicator2': 'ADD-50', 'exit_operator0': 'CUT', 'exit_operator1': 'DT', 'exit_operator2': '=R', 'exit_real_num0': 0.3205, 'exit_real_num1': 0.2055, 'exit_real_num2': 0.8467}}, 'La': {'entry_params': {'entry_crossed_indicator0': 'WMA-14', 'entry_crossed_indicator1': 'MAMA-1-14', 'entry_crossed_indicator2': 'CDLHIKKAKE-14', 'entry_indicator0': 'T3-14', 'entry_indicator1': 'BETA-14', 'entry_indicator2': 'HT_PHASOR-1-14', 'entry_operator0': '/>R', 'entry_operator1': '>', 'entry_operator2': '>R', 'entry_real_num0': 0.0551, 'entry_real_num1': 0.3469, 'entry_real_num2': 0.3871}, 'exit_params': {'exit_crossed_indicator0': 'HT_TRENDLINE-14', 'exit_crossed_indicator1': 'LINEARREG-14', 'exit_crossed_indicator2': 'STOCHRSI-1-14', 'exit_indicator0': 'CDLDARKCLOUDCOVER-14', 'exit_indicator1': 'AD-14', 'exit_indicator2': 'CDLSTALLEDPATTERN-14', 'exit_operator0': '/=R', 'exit_operator1': 'COT', 'exit_operator2': 'OT', 'exit_real_num0': 0.3992, 'exit_real_num1': 0.7747, 'exit_real_num2': 0.7415}}, 'Si': {'entry_params': {'entry_crossed_indicator0': 'MACDEXT-2-14', 'entry_crossed_indicator1': 'CORREL-14', 'entry_crossed_indicator2': 'CMO-14', 'entry_indicator0': 'MA-14', 'entry_indicator1': 'ADXR-14', 'entry_indicator2': 'CDLMARUBOZU-14', 'entry_operator0': '<', 'entry_operator1': '/<R', 'entry_operator2': '<R', 'entry_real_num0': 0.7883, 'entry_real_num1': 0.8286, 'entry_real_num2': 0.6512}, 'exit_params': {'exit_crossed_indicator0': 'AROON-1-14', 'exit_crossed_indicator1': 'STOCHRSI-0-14', 'exit_crossed_indicator2': 'SMA-14', 'exit_indicator0': 'T3-14', 'exit_indicator1': 'AROONOSC-14', 'exit_indicator2': 'MIDPOINT-14', 'exit_operator0': 'C', 'exit_operator1': 'CA', 'exit_operator2': 'CB', 'exit_real_num0': 0.372, 'exit_real_num1': 0.5948, 'exit_real_num2': 0.9872}}, 'Pa': {'entry_params': {'entry_crossed_indicator0': 'AROON-0-60', 'entry_crossed_indicator1': 'APO-60', 'entry_crossed_indicator2': 'BBANDS-0-60', 'entry_indicator0': 'WILLR-12', 'entry_indicator1': 'AD-15', 'entry_indicator2': 'MINUS_DI-12', 'entry_operator0': 'D', 'entry_operator1': '>', 'entry_operator2': 'CA', 'entry_real_num0': 0.2208, 'entry_real_num1': 0.1371, 'entry_real_num2': 0.6389}, 'exit_params': {'exit_crossed_indicator0': 'MACDEXT-0-15', 'exit_crossed_indicator1': 'BBANDS-2-15', 'exit_crossed_indicator2': 'DEMA-15', 'exit_indicator0': 'ULTOSC-15', 'exit_indicator1': 'MIDPOINT-12', 'exit_indicator2': 'PLUS_DI-12', 'exit_operator0': '<', 'exit_operator1': 'DT', 'exit_operator2': 'COT', 'exit_real_num0': 0.278, 'exit_real_num1': 0.0643, 'exit_real_num2': 0.7065}}, 'De': {'entry_params': {'entry_crossed_indicator0': 'HT_DCPERIOD-12', 'entry_crossed_indicator1': 'HT_PHASOR-0-12', 'entry_crossed_indicator2': 'MACDFIX-1-15', 'entry_indicator0': 'CMO-12', 'entry_indicator1': 'TRIMA-12', 'entry_indicator2': 'MACDEXT-0-15', 'entry_operator0': '<', 'entry_operator1': 'D', 'entry_operator2': '<', 'entry_real_num0': 0.3924, 'entry_real_num1': 0.5546, 'entry_real_num2': 0.7648}, 'exit_params': {'exit_crossed_indicator0': 'MACDFIX-1-15', 'exit_crossed_indicator1': 'MACD-1-15', 'exit_crossed_indicator2': 'WMA-15', 'exit_indicator0': 'ROC-15', 'exit_indicator1': 'MACD-2-15', 'exit_indicator2': 'CCI-60', 'exit_operator0': 'CA', 'exit_operator1': '<R', 'exit_operator2': '/<R', 'exit_real_num0': 0.4989, 'exit_real_num1': 0.4131, 'exit_real_num2': 0.8904}}, 'Ra': {'entry_params': {'entry_crossed_indicator0': 'EMA-110', 'entry_crossed_indicator1': 'SMA-5', 'entry_crossed_indicator2': 'SMA-6', 'entry_indicator0': 'SMA-6', 'entry_indicator1': 'EMA-12', 'entry_indicator2': 'EMA-5', 'entry_operator0': 'D', 'entry_operator1': '<', 'entry_operator2': '/<R', 'entry_real_num0': 0.9814, 'entry_real_num1': 0.5528, 'entry_real_num2': 0.0541}, 'exit_params': {'exit_crossed_indicator0': 'SMA-50', 'exit_crossed_indicator1': 'EMA-12', 'exit_crossed_indicator2': 'SMA-100', 'exit_indicator0': 'EMA-110', 'exit_indicator1': 'EMA-50', 'exit_indicator2': 'EMA-15', 'exit_operator0': '<', 'exit_operator1': 'COT', 'exit_operator2': '/=R', 'exit_real_num0': 0.3506, 'exit_real_num1': 0.8767, 'exit_real_num2': 0.0614}}, 'Cu': {'entry_params': {'entry_crossed_indicator0': 'SMA-110', 'entry_crossed_indicator1': 'SMA-110', 'entry_crossed_indicator2': 'SMA-5', 'entry_indicator0': 'SMA-110', 'entry_indicator1': 'SMA-55', 'entry_indicator2': 'SMA-15', 'entry_operator0': '<R', 'entry_operator1': '<', 'entry_operator2': 'CA', 'entry_real_num0': 0.5, 'entry_real_num1': 0.7, 'entry_real_num2': 0.9}, 'exit_params': {'exit_crossed_indicator0': 'SMA-55', 'exit_crossed_indicator1': 'SMA-50', 'exit_crossed_indicator2': 'SMA-100', 'exit_indicator0': 'SMA-5', 'exit_indicator1': 'SMA-50', 'exit_indicator2': 'SMA-50', 'exit_operator0': '/=R', 'exit_operator1': 'CUT', 'exit_operator2': 'DT', 'exit_real_num0': 0.4, 'exit_real_num1': 0.2, 'exit_real_num2': 0.7}}}
# ######################## END SETTINGS ############################

def spell_finder(index, space):
    return SPELLS[index][space + '_params']

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

class DevilStra(IStrategy):
    INTERFACE_VERSION = 3
    # #################### RESULT PASTE PLACE ####################
    # 16/16:    108 trades. 75/18/15 Wins/Draws/Losses. Avg profit   7.77%. Median profit   8.89%. Total profit  0.08404983 BTC (  84.05Σ%). Avg duration 3 days, 6:49:00 min. Objective: -11.22849
    # Buy hyperspace params:
    entry_params = {'entry_spell': 'Zi,Lu,Ra,Ra,La,Si,Pa,Si,Cu,La,De,Lu,De,La,Zi,Zi,Zi,Zi,Zi,Lu,Lu,Lu,Si,La,Ra,Pa,La,Zi,Zi,Gu,Ra,De,Gu,Zi,Ra,Ra,Ra,Cu,Pa,De,De,La,Lu,Lu,Lu,La,Zi,Cu,Ra,Gu,Pa,La,Zi,Zi,Si,Lu,Ra,Cu,Cu,Pa,Si,Gu,De,De,Lu,Gu,Zi,Pa,Lu,Pa,Ra,Gu,Cu,La,Pa,Lu,Zi,La,Zi,Gu,Zi,De,Cu,Ra,Lu,Ra,Gu,Si,Ra,La,La,Lu,Gu,Zi,Si,La,Pa,Pa,Cu,Cu,Zi,Gu,Pa,Zi,Pa,Cu,Lu,Pa,Si,De,Gu,Lu,Lu,Cu,Ra,Si,Pa,Gu,Si,Cu,Pa,Zi,Pa,Zi,Gu,Lu,Ra,Pa,Ra,De,Ra,Pa,Zi,La,Pa,De,Pa,Cu,Gu,De,Lu,La,Ra,Zi,Si,Zi,Zi,Cu,Cu,De,Pa,Pa,Zi,De,Ra,La,Lu,De,Lu,Gu,Cu,Cu,La,De,Gu,Lu,Ra,Pa,Lu,Cu,Pa,Pa,De,Si,Zi,Cu,De,De,De,Lu,Si,Zi,Gu,Si,Si,Ra,Pa,Si,La,La,Lu,Lu,De,Gu,Gu,Zi,Ra,La,Lu,Lu,La,Si,Zi,Si,Zi,Si,Lu,Cu,Zi,Lu,De,La,Ra,Ra,Lu,De,Pa,Zi,Gu,Cu,Zi,Pa,De,Si,Lu,De,Cu,De,Zi,Ra,Gu,De,Si,Lu,Lu,Ra,De,Gu,Cu,Gu,La,De,Lu,Lu,Si,Cu,Lu,Zi,Lu,Cu,Gu,Lu,Lu,Ra,Si,Ra,Pa,Lu,De,Ra,Zi,Gu,Gu,Zi,Lu,Cu,Cu,Cu,Lu'}
    # Sell hyperspace params:
    exit_params = {'exit_spell': 'La,Pa,De,De,La,Si,Si,La,La,La,Si,Pa,Pa,Lu,De,Cu,Cu,Gu,Lu,Ra,Lu,Si,Ra,De,La,Cu,La,La,Gu,La,De,Ra,Ra,Ra,Gu,Lu,Si,Si,Zi,Zi,La,Pa,Pa,Zi,Cu,Gu,Gu,Pa,Gu,Cu,Si,Ra,Ra,La,Gu,De,Si,La,Ra,Pa,Si,Lu,Pa,De,Zi,De,Lu,Si,Gu,De,Lu,De,Ra,Ra,Zi,De,Cu,Zi,Gu,Pa,Ra,De,Pa,De,Pa,Ra,Si,Si,Zi,Cu,Lu,Zi,Ra,De,Ra,Zi,Zi,Pa,Lu,Zi,Cu,Pa,Gu,Pa,Cu,De,Zi,De,De,Pa,Pa,Zi,Lu,Ra,Pa,Ra,Lu,Zi,Gu,Zi,Si,Lu,Ra,Ra,Zi,Lu,Pa,Lu,Si,Pa,Pa,Pa,Si,Zi,La,La,Lu,De,Zi,Gu,Ra,Ra,Ra,Zi,Pa,Zi,Cu,Lu,Gu,Cu,De,Lu,Gu,Lu,Gu,Si,Pa,Pa,Si,La,Gu,Ra,Pa,Si,Si,Si,Cu,Cu,Cu,Si,De,Lu,Gu,Gu,Lu,De,Ra,Gu,Gu,Gu,Cu,La,De,Cu,Zi,Pa,Si,De,Pa,Pa,Pa,La,De,Gu,Zi,La,De,Cu,La,Pa,Ra,Si,Si,Zi,Cu,Ra,Pa,Gu,Pa,Ra,Zi,De,Zi,Gu,Gu,Pa,Cu,Lu,Gu,De,Si,Pa,La,Cu,Zi,Gu,De,Gu,La,Cu,Gu,De,Cu,Cu,Gu,Ra,Lu,Zi,De,La,Ra,Pa,Pa,Si,La,Lu,La,De,De,Ra,De,La,La,Pa,Cu,Lu,Pa,Ra,Pa,Pa,Cu,Zi,Gu,Cu,Gu,La,Si,Ra,Pa'}
    # ROI table:
    minimal_roi = {'0': 0.574, '1757': 0.158, '3804': 0.089, '6585': 0}
    # Stoploss:
    stoploss = -0.28
    # #################### END OF RESULT PLACE ####################
    # 𝖂𝖔𝖗𝖘𝖙, 𝖀𝖓𝖎𝖉𝖊𝖆𝖑, 𝕾𝖚𝖇𝖔𝖕𝖙𝖎𝖒𝖆𝖑, 𝕸𝖆𝖑𝖆𝖕𝖗𝖔𝖕𝖔𝖘 𝕬𝖓𝖉 𝕯𝖎𝖘𝖒𝖆𝖑 𝖙𝖎𝖒𝖊𝖋𝖗𝖆𝖒𝖊 𝖋𝖔𝖗 𝖙𝖍𝖎𝖘 𝖘𝖙𝖗𝖆𝖙𝖊𝖌𝖞:
    timeframe = '4h'
    # TODO: k will be change to len(pairlist)
    spell_pot = [','.join(tuple(random.choices(list(SPELLS.keys()), k=PAIR_LIST_LENGHT))) for i in range(PAIN_RANGE)]
    entry_spell = CategoricalParameter(spell_pot, default=spell_pot[0], space='entry')
    exit_spell = CategoricalParameter(spell_pot, default=spell_pot[0], space='exit')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pairs = self.dp.current_whitelist()
        pairs_len = len(pairs)
        pair_index = pairs.index(metadata['pair'])
        entry_spells = self.entry_spell.value.split(',')
        entry_spells_len = len(entry_spells)
        if pairs_len > entry_spells_len:
            print(f'First set PAIR_LIST_LENGHT={pairs_len + 1} And re-hyperopt the')
            print('Buy strategy And paste result in exact place(lines 535~564)')
            print("IMPORTANT: You Need An 'STATIC' Pairlist On Your Config.json !!!")
            exit()
        entry_params_index = entry_spells[pair_index]
        params = spell_finder(entry_params_index, 'entry')
        conditions = list()
        # TODO: Its not dry code!
        entry_indicator = params['entry_indicator0']
        entry_crossed_indicator = params['entry_crossed_indicator0']
        entry_operator = params['entry_operator0']
        entry_real_num = params['entry_real_num0']
        condition, dataframe = condition_generator(dataframe, entry_operator, entry_indicator, entry_crossed_indicator, entry_real_num)
        conditions.append(condition)
        # backup
        entry_indicator = params['entry_indicator1']
        entry_crossed_indicator = params['entry_crossed_indicator1']
        entry_operator = params['entry_operator1']
        entry_real_num = params['entry_real_num1']
        condition, dataframe = condition_generator(dataframe, entry_operator, entry_indicator, entry_crossed_indicator, entry_real_num)
        conditions.append(condition)
        entry_indicator = params['entry_indicator2']
        entry_crossed_indicator = params['entry_crossed_indicator2']
        entry_operator = params['entry_operator2']
        entry_real_num = params['entry_real_num2']
        condition, dataframe = condition_generator(dataframe, entry_operator, entry_indicator, entry_crossed_indicator, entry_real_num)
        conditions.append(condition)
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'entry'] = 1
        # print(len(dataframe.keys()))
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pairs = self.dp.current_whitelist()
        pairs_len = len(pairs)
        pair_index = pairs.index(metadata['pair'])
        exit_spells = self.exit_spell.value.split(',')
        exit_spells_len = len(exit_spells)
        if pairs_len > exit_spells_len:
            print(f'First set PAIR_LIST_LENGHT={pairs_len + 1} And re-hyperopt the')
            print('Sell strategy And paste result in exact place(lines 535~564)')
            print("IMPORTANT: You Need An 'STATIC' Pairlist On Your Config.json !!!")
            exit()
        exit_params_index = exit_spells[pair_index]
        params = spell_finder(exit_params_index, 'exit')
        conditions = list()
        # TODO: Its not dry code!
        exit_indicator = params['exit_indicator0']
        exit_crossed_indicator = params['exit_crossed_indicator0']
        exit_operator = params['exit_operator0']
        exit_real_num = params['exit_real_num0']
        condition, dataframe = condition_generator(dataframe, exit_operator, exit_indicator, exit_crossed_indicator, exit_real_num)
        conditions.append(condition)
        exit_indicator = params['exit_indicator1']
        exit_crossed_indicator = params['exit_crossed_indicator1']
        exit_operator = params['exit_operator1']
        exit_real_num = params['exit_real_num1']
        condition, dataframe = condition_generator(dataframe, exit_operator, exit_indicator, exit_crossed_indicator, exit_real_num)
        conditions.append(condition)
        exit_indicator = params['exit_indicator2']
        exit_crossed_indicator = params['exit_crossed_indicator2']
        exit_operator = params['exit_operator2']
        exit_real_num = params['exit_real_num2']
        condition, dataframe = condition_generator(dataframe, exit_operator, exit_indicator, exit_crossed_indicator, exit_real_num)
        conditions.append(condition)
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'exit'] = 1
        return dataframe