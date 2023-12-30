# WTC Strategy: WTC(World Trade Center Tabriz)
# is the biggest skyscraper of Tabriz, city of Iran
# (What you want?it not enough for you?that's just it!)
# No, no, I'm kidding. It's also mean Wave Trend with Crosses
# algo by LazyBare(in TradingView) that I reduce it
# signals noise with dividing it to Stoch-RSI indicator.
# Also thanks from discord: @aurax for his/him
# request to making this strategy.
# hope you enjoy and get profit
# Author: @Mablue (Masoud Azizi)
# IMPORTANT: install sklearn befoure you run this strategy:
# pip install sklearn
# github: https://github.com/mablue/
# freqtrade hyperopt --hyperopt-loss SharpeHyperOptLoss --spaces entry exit --strategy wtc
import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.strategy import DecimalParameter
from freqtrade.strategy import IStrategy
from pandas import DataFrame
#
# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from sklearn import preprocessing
# --------------------------------
# Add your lib to import here

class wtc(IStrategy):
    INTERFACE_VERSION = 3
    ################################ SETTINGS ################################
    # 61 trades. 16/0/45 Wins/Draws/Losses.
    # * Avg profit: 132.53%.
    # Median profit: -12.97%.
    # Total profit: 0.80921449 BTC ( 809.21Σ%).
    # Avg duration 4 days, 7:47:00 min.
    # Objective: -15.73417
    # Config:
    # "max_open_trades": 10,
    # "stake_currency": "BTC",
    # "stake_amount": 0.01,
    # "tradable_balance_ratio": 0.99,
    # "timeframe": "30m",
    # "dry_run_wallet": 0.1,
    # Buy hyperspace params:
    entry_params = {'entry_max': 0.9609, 'entry_max0': 0.8633, 'entry_max1': 0.9133, 'entry_min': 0.0019, 'entry_min0': 0.0102, 'entry_min1': 0.6864}
    # Sell hyperspace params:
    exit_params = {'exit_max': -0.7979, 'exit_max0': 0.82, 'exit_max1': 0.9821, 'exit_min': -0.5377, 'exit_min0': 0.0628, 'exit_min1': 0.4461}
    minimal_roi = {'0': 0.30873, '569': 0.16689, '3211': 0.06473, '7617': 0}
    stoploss = -0.128
    ############################## END SETTINGS ##############################
    timeframe = '30m'
    entry_max = DecimalParameter(-1, 1, decimals=4, default=0.4393, space='entry')
    entry_min = DecimalParameter(-1, 1, decimals=4, default=-0.4676, space='entry')
    exit_max = DecimalParameter(-1, 1, decimals=4, default=-0.9512, space='exit')
    exit_min = DecimalParameter(-1, 1, decimals=4, default=0.6519, space='exit')
    entry_max0 = DecimalParameter(0, 1, decimals=4, default=0.4393, space='entry')
    entry_min0 = DecimalParameter(0, 1, decimals=4, default=-0.4676, space='entry')
    exit_max0 = DecimalParameter(0, 1, decimals=4, default=-0.9512, space='exit')
    exit_min0 = DecimalParameter(0, 1, decimals=4, default=0.6519, space='exit')
    entry_max1 = DecimalParameter(0, 1, decimals=4, default=0.4393, space='entry')
    entry_min1 = DecimalParameter(0, 1, decimals=4, default=-0.4676, space='entry')
    exit_max1 = DecimalParameter(0, 1, decimals=4, default=-0.9512, space='exit')
    exit_min1 = DecimalParameter(0, 1, decimals=4, default=0.6519, space='exit')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # WAVETREND
        try:
            ap = (dataframe['high'] + dataframe['low'] + dataframe['close']) / 3
            esa = ta.EMA(ap, 10)
            d = ta.EMA((ap - esa).abs(), 10)
            ci = (ap - esa).div(0.0015 * d)
            tci = ta.EMA(ci, 21)
            wt1 = tci
            wt2 = ta.SMA(np.nan_to_num(wt1), 4)
            dataframe['wt1'], dataframe['wt2'] = (wt1, wt2)
            stoch = ta.STOCH(dataframe, 14)
            slowk = stoch['slowk']
            dataframe['slowk'] = slowk
            # print(dataframe.iloc[:, 6:].keys())
            x = dataframe.iloc[:, 6:].values  # returns a numpy array
            min_max_scaler = preprocessing.MinMaxScaler()
            x_scaled = min_max_scaler.fit_transform(x)
            dataframe.iloc[:, 6:] = pd.DataFrame(x_scaled)
            # print('wt:\t', dataframe['wt'].min(), dataframe['wt'].max())
            # print('stoch:\t', dataframe['stoch'].min(), dataframe['stoch'].max())
            dataframe['def'] = dataframe['slowk'] - dataframe['wt1']
        # print('def:\t', dataframe['def'].min(), "\t", dataframe['def'].max())
        except:
            dataframe['wt1'], dataframe['wt2'], dataframe['def'], dataframe['slowk'] = (0, 10, 100, 1000)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[qtpylib.crossed_above(dataframe['wt1'], dataframe['wt2']) & dataframe['wt1'].between(self.entry_min0.value, self.entry_max0.value) & dataframe['slowk'].between(self.entry_min1.value, self.entry_max1.value) & dataframe['def'].between(self.entry_min.value, self.entry_max.value), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # print(dataframe['slowk']/dataframe['wt1'])
        dataframe.loc[qtpylib.crossed_below(dataframe['wt1'], dataframe['wt2']) & dataframe['wt1'].between(self.exit_min0.value, self.exit_max0.value) & dataframe['slowk'].between(self.exit_min1.value, self.exit_max1.value) & dataframe['def'].between(self.exit_min.value, self.exit_max.value), 'exit_long'] = 1
        return dataframe