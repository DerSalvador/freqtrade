# GodStra Strategy
# Author: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/
# IMPORTANT:Add to your pairlists inside config.json (Under StaticPairList):
#   {
#       "method": "AgeFilter",
#       "min_days_listed": 30
#   },
# IMPORTANT: INSTALL TA BEFOUR RUN(pip install ta)
# IMPORTANT: Use Smallest "max_open_trades" for getting best results inside config.json
# --- Do not remove these libs ---
import logging
from numpy.lib import math
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
# --------------------------------
# Add your lib to import here
# import talib.abstract as ta
import pandas as pd
# import talib.abstract as ta
from ta import add_all_ta_features
from ta.utils import dropna
import freqtrade.vendor.qtpylib.indicators as qtpylib
from functools import reduce
import numpy as np

class GodStra(IStrategy):
    INTERFACE_VERSION = 3
    # 5/66:      9 trades. 8/0/1 Wins/Draws/Losses. Avg profit  21.83%. Median profit  35.52%. Total profit  1060.11476586 USDT ( 196.50Σ%). Avg duration 3440.0 min. Objective: -7.06960
    # +--------+---------+----------+------------------+--------------+-------------------------------+----------------+-------------+
    # |   Best |   Epoch |   Trades |    Win Draw Loss |   Avg profit |                        Profit |   Avg duration |   Objective |
    # |--------+---------+----------+------------------+--------------+-------------------------------+----------------+-------------|
    # | * Best |   1/500 |       11 |      2    1    8 |        5.22% |  280.74230393 USDT   (57.40%) |      2,421.8 m |    -2.85206 |
    # | * Best |   2/500 |       10 |      7    0    3 |       18.76% |  983.46414442 USDT  (187.58%) |        360.0 m |    -4.32665 |
    # | * Best |   5/500 |        9 |      8    0    1 |       21.83% | 1,060.11476586 USDT  (196.50%) |      3,440.0 m |     -7.0696 |
    # Buy hyperspace params:
    entry_params = {'entry-cross-0': 'volatility_kcc', 'entry-indicator-0': 'trend_ichimoku_base', 'entry-int-0': 42, 'entry-oper-0': '<R', 'entry-real-0': 0.06295}
    # Sell hyperspace params:
    exit_params = {'exit-cross-0': 'volume_mfi', 'exit-indicator-0': 'trend_kst_diff', 'exit-int-0': 98, 'exit-oper-0': '=R', 'exit-real-0': 0.8779}
    # ROI table:
    minimal_roi = {'0': 0.3556, '4818': 0.21275, '6395': 0.09024, '22372': 0}
    # Stoploss:
    stoploss = -0.34549
    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.22673
    trailing_stop_positive_offset = 0.2684
    trailing_only_offset_is_reached = True
    # Buy hypers
    timeframe = '5m'
    print('Add {\n\t"method": "AgeFilter",\n\t"min_days_listed": 30\n},\n to your pairlists in config (Under StaticPairList)')

    def dna_size(dct: dict):

        def int_from_str(st: str):
            str_int = ''.join([d for d in st if d.isdigit()])
            if str_int:
                return int(str_int)
            return -1  # in case if the parameter somehow doesn't have index
        return len({int_from_str(digit) for digit in dct.keys()})

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Add all ta features
        dataframe = dropna(dataframe)
        dataframe = add_all_ta_features(dataframe, open='open', high='high', low='low', close='close', volume='volume', fillna=True)
        # dataframe.to_csv("df.csv", index=True)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = list()
        # /5: Cuz We have 5 Group of variables inside entry_param
        for i in range(self.dna_size(self.entry_params)):
            OPR = self.entry_params[f'entry-oper-{i}']
            IND = self.entry_params[f'entry-indicator-{i}']
            CRS = self.entry_params[f'entry-cross-{i}']
            INT = self.entry_params[f'entry-int-{i}']
            REAL = self.entry_params[f'entry-real-{i}']
            DFIND = dataframe[IND]
            DFCRS = dataframe[CRS]
            if OPR == '>':
                conditions.append(DFIND > DFCRS)
            elif OPR == '=':
                conditions.append(np.isclose(DFIND, DFCRS))
            elif OPR == '<':
                conditions.append(DFIND < DFCRS)
            elif OPR == 'CA':
                conditions.append(qtpylib.crossed_above(DFIND, DFCRS))
            elif OPR == 'CB':
                conditions.append(qtpylib.crossed_below(DFIND, DFCRS))
            elif OPR == '>I':
                conditions.append(DFIND > INT)
            elif OPR == '=I':
                conditions.append(DFIND == INT)
            elif OPR == '<I':
                conditions.append(DFIND < INT)
            elif OPR == '>R':
                conditions.append(DFIND > REAL)
            elif OPR == '=R':
                conditions.append(np.isclose(DFIND, REAL))
            elif OPR == '<R':
                conditions.append(DFIND < REAL)
        print(conditions)
        dataframe.loc[reduce(lambda x, y: x & y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = list()
        for i in range(self.dna_size(self.exit_params)):
            OPR = self.exit_params[f'exit-oper-{i}']
            IND = self.exit_params[f'exit-indicator-{i}']
            CRS = self.exit_params[f'exit-cross-{i}']
            INT = self.exit_params[f'exit-int-{i}']
            REAL = self.exit_params[f'exit-real-{i}']
            DFIND = dataframe[IND]
            DFCRS = dataframe[CRS]
            if OPR == '>':
                conditions.append(DFIND > DFCRS)
            elif OPR == '=':
                conditions.append(np.isclose(DFIND, DFCRS))
            elif OPR == '<':
                conditions.append(DFIND < DFCRS)
            elif OPR == 'CA':
                conditions.append(qtpylib.crossed_above(DFIND, DFCRS))
            elif OPR == 'CB':
                conditions.append(qtpylib.crossed_below(DFIND, DFCRS))
            elif OPR == '>I':
                conditions.append(DFIND > INT)
            elif OPR == '=I':
                conditions.append(DFIND == INT)
            elif OPR == '<I':
                conditions.append(DFIND < INT)
            elif OPR == '>R':
                conditions.append(DFIND > REAL)
            elif OPR == '=R':
                conditions.append(np.isclose(DFIND, REAL))
            elif OPR == '<R':
                conditions.append(DFIND < REAL)
        dataframe.loc[reduce(lambda x, y: x & y, conditions), 'exit_long'] = 1
        return dataframe