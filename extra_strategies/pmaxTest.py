# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
import numpy as np
from functools import reduce
from pandas import DataFrame, Series
from technical.indicators import zema, VIDYA, RMI
from datetime import datetime, timedelta
from freqtrade.strategy import merge_informative_pair, CategoricalParameter, DecimalParameter, IntParameter, stoploss_from_open
# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class pmaxTest(IStrategy):
    INTERFACE_VERSION = 3
    '\n\n    author@: Gert Wohlgemuth\n\n    just a skeleton\n\n    '
    # Minimal ROI designed for the strategy.
    # adjust based on market conditions. We would recommend to keep it low for quick turn arounds
    # This attribute will be overridden if the config file contains "minimal_roi"
    #"0": 0.053,
    #"23": 0.039,
    #"62": 0.022,
    #"186": 0
    minimal_roi = {'0': 100}
    # exit space
    exit_params = {'pHSL': -0.04, 'pPF_1': 0.011, 'pPF_2': 0.069, 'pSL_1': 0.011, 'pSL_2': 0.068}
    # Optimal stoploss designed for the strategy
    stoploss = -0.99
    use_custom_stoploss = True
    # Optimal timeframe for the strategy
    timeframe = '5m'
    ## Trailing params
    # hard stoploss profit
    pHSL = DecimalParameter(-0.2, -0.04, default=-0.08, decimals=3, space='exit', load=True)
    # profit threshold 1, trigger point, SL_1 is used
    pPF_1 = DecimalParameter(0.008, 0.02, default=0.016, decimals=3, space='exit', load=True)
    pSL_1 = DecimalParameter(0.008, 0.02, default=0.011, decimals=3, space='exit', load=True)
    # profit threshold 2, SL_2 is used
    pPF_2 = DecimalParameter(0.04, 0.1, default=0.08, decimals=3, space='exit', load=True)
    pSL_2 = DecimalParameter(0.02, 0.07, default=0.04, decimals=3, space='exit', load=True)
    ## Custom Trailing stoploss ( credit to Perkmeister for this custom stoploss to help the strategy ride a green candle )

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> float:
        # hard stoploss profit
        HSL = self.pHSL.value
        PF_1 = self.pPF_1.value
        SL_1 = self.pSL_1.value
        PF_2 = self.pPF_2.value
        SL_2 = self.pSL_2.value
        # For profits between PF_1 and PF_2 the stoploss (sl_profit) used is linearly interpolated
        # between the values of SL_1 and SL_2. For all profits above PL_2 the sl_profit value
        # rises linearly with current profit, for profits below PF_1 the hard stoploss profit is used.
        if current_profit > PF_2:
            sl_profit = SL_2 + (current_profit - PF_2)
        elif current_profit > PF_1:
            sl_profit = SL_1 + (current_profit - PF_1) * (SL_2 - SL_1) / (PF_2 - PF_1)
        else:
            sl_profit = HSL
        # For hyperopt only
        if sl_profit >= current_profit:
            return -0.99
        return stoploss_from_open(sl_profit, current_profit)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Heiken Ashi
        heikinashi = qtpylib.heikinashi(dataframe)
        heikinashi['volume'] = dataframe['volume']
        # Profit Maximizer - PMAX
        dataframe['pm'], dataframe['pmx'] = pmax(heikinashi, MAtype=1, length=9, multiplier=27, period=10, src=3)
        dataframe['source'] = (dataframe['high'] + dataframe['low'] + dataframe['open'] + dataframe['close']) / 4
        dataframe['pmax_thresh'] = ta.EMA(dataframe['source'], timeperiod=9)
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_84'] = ta.RSI(dataframe, timeperiod=84)
        dataframe['rsi_112'] = ta.RSI(dataframe, timeperiod=112)
        # trima
        dataframe['trima_entry'] = ta.TRIMA(dataframe, 10)
        # zema
        dataframe['zema_entry'] = zema(dataframe, 30)
        dataframe['rmi'] = RMI(dataframe, length=9, mom=4)
        dataframe['cci'] = ta.CCI(dataframe, 46)
        stoch = ta.STOCHRSI(dataframe, 15, 20, 2, 2)
        dataframe['srsi_fk'] = stoch['fastk']
        dataframe['srsi_fd'] = stoch['fastd']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # add check
        dataframe.loc[qtpylib.crossed_above(dataframe['trima_entry'], dataframe['zema_entry']) & (dataframe['trima_entry'] > dataframe['pm']) & (dataframe['zema_entry'] > dataframe['pm']) & (dataframe['rmi'] < 50) & (dataframe['cci'] <= -91) & (dataframe['srsi_fk'] < 41) & (dataframe['close'].rolling(288).max() >= dataframe['close'] * 1.1) & (dataframe['rsi_fast'] < 35) & (dataframe['rsi_84'] < 60) & (dataframe['rsi_112'] < 60) & (dataframe['volume'] > 0), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # Make sure Volume is not 0
        dataframe.loc[dataframe['volume'] > 0, 'exit_long'] = 0
        return dataframe
# PMAX

def pmax(df, period, multiplier, length, MAtype, src):
    period = int(period)
    multiplier = int(multiplier)
    length = int(length)
    MAtype = int(MAtype)
    src = int(src)
    mavalue = f'MA_{MAtype}_{length}'
    atr = f'ATR_{period}'
    pm = f'pm_{period}_{multiplier}_{length}_{MAtype}'
    pmx = f'pmX_{period}_{multiplier}_{length}_{MAtype}'
    # MAtype==1 --> EMA
    # MAtype==2 --> DEMA
    # MAtype==3 --> T3
    # MAtype==4 --> SMA
    # MAtype==5 --> VIDYA
    # MAtype==6 --> TEMA
    # MAtype==7 --> WMA
    # MAtype==8 --> VWMA
    # MAtype==9 --> zema
    if src == 1:
        masrc = df['close']
    elif src == 2:
        masrc = (df['high'] + df['low']) / 2
    elif src == 3:
        masrc = (df['high'] + df['low'] + df['close'] + df['open']) / 4
    if MAtype == 1:
        mavalue = ta.EMA(masrc, timeperiod=length)
    elif MAtype == 2:
        mavalue = ta.DEMA(masrc, timeperiod=length)
    elif MAtype == 3:
        mavalue = ta.T3(masrc, timeperiod=length)
    elif MAtype == 4:
        mavalue = ta.SMA(masrc, timeperiod=length)
    elif MAtype == 5:
        mavalue = VIDYA(df, length=length)
    elif MAtype == 6:
        mavalue = ta.TEMA(masrc, timeperiod=length)
    elif MAtype == 7:
        mavalue = ta.WMA(df, timeperiod=length)
    elif MAtype == 8:
        mavalue = vwma(df, length)
    elif MAtype == 9:
        mavalue = zema(df, period=length)
    df[atr] = ta.ATR(df, timeperiod=period)
    df['basic_ub'] = mavalue + multiplier / 10 * df[atr]
    df['basic_lb'] = mavalue - multiplier / 10 * df[atr]
    basic_ub = df['basic_ub'].values
    final_ub = np.full(len(df), 0.0)
    basic_lb = df['basic_lb'].values
    final_lb = np.full(len(df), 0.0)
    for i in range(period, len(df)):
        final_ub[i] = basic_ub[i] if basic_ub[i] < final_ub[i - 1] or mavalue[i - 1] > final_ub[i - 1] else final_ub[i - 1]
        final_lb[i] = basic_lb[i] if basic_lb[i] > final_lb[i - 1] or mavalue[i - 1] < final_lb[i - 1] else final_lb[i - 1]
    df['final_ub'] = final_ub
    df['final_lb'] = final_lb
    pm_arr = np.full(len(df), 0.0)
    for i in range(period, len(df)):
        pm_arr[i] = final_ub[i] if pm_arr[i - 1] == final_ub[i - 1] and mavalue[i] <= final_ub[i] else final_lb[i] if pm_arr[i - 1] == final_ub[i - 1] and mavalue[i] > final_ub[i] else final_lb[i] if pm_arr[i - 1] == final_lb[i - 1] and mavalue[i] >= final_lb[i] else final_ub[i] if pm_arr[i - 1] == final_lb[i - 1] and mavalue[i] < final_lb[i] else 0.0
    pm = Series(pm_arr)
    # Mark the trend direction up/down
    pmx = np.where(pm_arr > 0.0, np.where(mavalue < pm_arr, 'down', 'up'), np.NaN)
    return (pm, pmx)