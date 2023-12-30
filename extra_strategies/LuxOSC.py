# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.strategy import CategoricalParameter, DecimalParameter, IntParameter
# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

def LUX_SuperTrendOscillator(dtloc, source='close', length=6, mult=9, smooth=72):
    """
    // This work is licensed under a Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) https://creativecommons.org/licenses/by-nc-sa/4.0/
    // © LuxAlgo
      https://www.tradingview.com/script/dVau7zqn-LUX-SuperTrend-Oscillator/
     :return: List of tuples in the format (osc, signal, histogram)   
     translated for freqtrade: viksal1982  viktors.s@gmail.com
    """
    def_proc_name = '_LUX_SuperTrendOscillator'
    atrcol = 'atr' + def_proc_name
    hl2col = 'hl2' + def_proc_name
    upcol = 'up' + def_proc_name
    dncol = 'dn' + def_proc_name
    uppercol = 'upper' + def_proc_name
    lowercol = 'lower' + def_proc_name
    trendcol = 'trend' + def_proc_name
    sptcol = 'spt' + def_proc_name
    osc1col = 'osc1' + def_proc_name
    osc2col = 'osc2' + def_proc_name
    osccol = 'osc' + def_proc_name
    alphacol = 'alpha' + def_proc_name
    amacol = 'ama' + def_proc_name
    histcol = 'hist' + def_proc_name
    dtS = dtloc.copy().fillna(0)
    dtS[atrcol] = ta.ATR(dtloc, timeperiod=length) * mult
    dtS[hl2col] = (dtS['high'] + dtS['low']) / 2
    dtS[upcol] = dtS[hl2col] + dtS[atrcol]
    dtS[dncol] = dtS[hl2col] - dtS[atrcol]

    def calc_upper(dfr, init=0):
        global calc_Lux_STO_upper
        global calc_Lux_STO_src
        if init == 1:
            calc_Lux_STO_upper = 0.0
            calc_Lux_STO_src = 0.0
            return
        if calc_Lux_STO_src < calc_Lux_STO_upper:
            calc_Lux_STO_upper = min(dfr[upcol], calc_Lux_STO_upper)
        else:
            calc_Lux_STO_upper = dfr[upcol]
        calc_Lux_STO_src = dfr[source]
        return calc_Lux_STO_upper
    calc_upper(None, init=1)
    dtS[uppercol] = dtS.apply(calc_upper, axis=1)

    def calc_lower(dfr, init=0):
        global calc_Lux_STO_lower
        global calc_Lux_STO_src
        if init == 1:
            calc_Lux_STO_lower = 0.0
            calc_Lux_STO_src = 0.0
            return
        if calc_Lux_STO_src > calc_Lux_STO_lower:
            calc_Lux_STO_lower = max(dfr[dncol], calc_Lux_STO_lower)
        else:
            calc_Lux_STO_lower = dfr[dncol]
        calc_Lux_STO_src = dfr[source]
        return calc_Lux_STO_lower
    calc_lower(None, init=1)
    dtS[lowercol] = dtS.apply(calc_lower, axis=1)

    def calc_trend(dfr, init=0):
        global calc_Lux_STO_trend
        global calc_Lux_STO_lower
        global calc_Lux_STO_upper
        if init == 1:
            calc_Lux_STO_trend = 0.0
            calc_Lux_STO_lower = 0.0
            calc_Lux_STO_upper = 0.0
            return
        if dfr[source] > calc_Lux_STO_upper:
            calc_Lux_STO_trend = 1
        elif dfr[source] < calc_Lux_STO_lower:
            calc_Lux_STO_trend = 0
        calc_Lux_STO_upper = dfr[uppercol]
        calc_Lux_STO_lower = dfr[lowercol]
        return calc_Lux_STO_trend
    calc_trend(None, init=1)
    dtS[trendcol] = dtS.apply(calc_trend, axis=1)
    dtS[sptcol] = dtS[trendcol] * dtS[lowercol] + (1 - dtS[trendcol]) * dtS[uppercol]
    dtS[osc1col] = (dtS[source] - dtS[sptcol]) / (dtS[uppercol] - dtS[lowercol])
    dtS[osc2col] = np.where(dtS[osc1col] < 1, dtS[osc1col], 1)
    dtS[osccol] = np.where(dtS[osc2col] > -1, dtS[osc2col], -1)
    dtS[alphacol] = dtS[osccol].pow(2) / length

    def calc_ama(dfr, init=0):
        global calc_Lux_STO_ama
        if init == 1:
            calc_Lux_STO_ama = 0.0
            return
        calc_Lux_STO_ama = calc_Lux_STO_ama + dfr[alphacol] * (dfr[osccol] - calc_Lux_STO_ama)
        return calc_Lux_STO_ama
    calc_ama(None, init=1)
    dtS[amacol] = dtS.apply(calc_ama, axis=1)
    dtS[histcol] = ta.EMA(dtS[osccol] - dtS[amacol], timeperiod=smooth)
    return (dtS[osccol] * 100, dtS[amacol] * 100, dtS[histcol] * 100, dtS[sptcol])

class LuxOSC(IStrategy):
    INTERFACE_VERSION = 3
    # Buy hyperspace params:
    entry_params = {'cross_entry': -100, 'length_entry': 6, 'mult_entry': 9, 'smooth_entry': 72}
    # Sell hyperspace params:
    exit_params = {'cross_exit': 50}
    length_entry = IntParameter(2, 100, default=int(entry_params['length_entry']), space='entry')
    mult_entry = IntParameter(2, 100, default=int(entry_params['mult_entry']), space='entry')
    smooth_entry = IntParameter(2, 100, default=int(entry_params['smooth_entry']), space='entry')
    cross_entry = IntParameter(-100, 100, default=int(entry_params['cross_entry']), space='entry')
    cross_exit = IntParameter(-100, 100, default=int(exit_params['cross_exit']), space='exit')
    stoploss = -0.99
    # Trailing stoploss
    trailing_stop = False
    timeframe = '5m'
    custom_info = {}
    process_only_new_candles = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count: int = 30
    # Optional order type mapping.
    order_types = {'entry': 'limit', 'exit': 'limit', 'stoploss': 'market', 'stoploss_on_exchange': False}
    # Optional order time in force.
    order_time_in_force = {'entry': 'gtc', 'exit': 'gtc'}
    # Main plot indicators (Moving averages, ...)
    # Subplots - each dict defines one additional plot
    plot_config = {'main_plot': {'supertrend': {'color': 'green'}}, 'subplots': {'OSC': {'osc': {'color': 'blue'}, 'signal': {'color': 'orange'}, 'histogram': {'color': 'green'}}}}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['osc'], dataframe['signal'], dataframe['histogram'], dataframe['supertrend'] = LUX_SuperTrendOscillator(dataframe, length=int(self.length_entry.value), mult=int(self.mult_entry.value), smooth=int(self.smooth_entry.value))
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[qtpylib.crossed_above(dataframe['osc'], int(self.cross_entry.value)) & (dataframe['supertrend'] > dataframe['close']) & (dataframe['volume'] > 0), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[qtpylib.crossed_below(dataframe['osc'], int(self.cross_exit.value)) & (dataframe['volume'] > 0), 'exit_long'] = 1
        return dataframe