# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
from freqtrade.strategy import DecimalParameter, IntParameter, BooleanParameter, CategoricalParameter, stoploss_from_open
from datetime import datetime
# --------------------------------

def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['close'] * 100
    return emadif
'\n======================================================= SELL REASON STATS ========================================================\n|        Sell Reason |   Sells |   Win  Draws  Loss  Win% |   Avg Profit % |   Cum Profit % |   Tot Profit USDT |   Tot Profit % |\n|--------------------+---------+--------------------------+----------------+----------------+-------------------+----------------|\n|        exit_signal |     392 |    159     0   233  40.6 |          -0.45 |        -178.25 |          -892.121 |         -59.42 |\n| trailing_stop_loss |     187 |    187     0     0   100 |           3.53 |         659.86 |          3302.61  |         219.95 |\n====================================================== LEFT OPEN TRADES REPORT ======================================================\n|   Pair |   Buys |   Avg Profit % |   Cum Profit % |   Tot Profit USDT |   Tot Profit % |   Avg Duration |   Win  Draw  Loss  Win% |\n|--------+--------+----------------+----------------+-------------------+----------------+----------------+-------------------------|\n|  TOTAL |      0 |           0.00 |           0.00 |             0.000 |           0.00 |           0:00 |     0     0     0     0 |\n=============== SUMMARY METRICS ================\n| Metric                 | Value               |\n|------------------------+---------------------|\n| Backtesting from       | 2021-10-12 00:00:00 |\n| Backtesting to         | 2021-11-12 00:00:00 |\n| Max open trades        | 3                   |\n|                        |                     |\n| Total/Daily Avg Trades | 579 / 18.68         |\n| Starting balance       | 1000.000 USDT       |\n| Final balance          | 3410.494 USDT       |\n| Absolute profit        | 2410.494 USDT       |\n| Total profit %         | 241.05%             |\n| Trades per day         | 18.68               |\n| Avg. daily profit %    | 7.78%               |\n| Avg. stake amount      | 500.000 USDT        |\n| Total trade volume     | 289500.000 USDT     |\n|                        |                     |\n| Best Pair              | QRDO/USDT 35.47%    |\n| Worst Pair             | DAG/USDT -12.07%    |\n| Best trade             | ARX/USDT 8.93%      |\n| Worst trade            | ATOM/USDT -11.35%   |\n| Best day               | 235.119 USDT        |\n| Worst day              | -36.114 USDT        |\n| Days win/draw/lose     | 26 / 0 / 5          |\n| Avg. Duration Winners  | 1:41:00             |\n| Avg. Duration Loser    | 3:10:00             |\n| Rejected Buy signals   | 217074              |\n|                        |                     |\n| Min balance            | 955.214 USDT        |\n| Max balance            | 3410.494 USDT       |\n| Drawdown               | 22.67%              |\n| Drawdown               | 113.471 USDT        |\n| Drawdown high          | 2385.361 USDT       |\n| Drawdown low           | 2271.890 USDT       |\n| Drawdown Start         | 2021-11-10 17:55:00 |\n| Drawdown End           | 2021-11-10 23:05:00 |\n| Market change          | 0%                  |\n================================================\n\n\nEpoch details:\n\n*    5/90:    579 trades. 346/0/233 Wins/Draws/Losses. Avg profit   0.83%. Median profit   0.54%. Total profit  2410.49362831 USDT ( 241.05%). Avg duration 2:17:00 min. Objective: -112.66357\n\n\n    # Buy hyperspace params:\n    entry_params = {\n        "ADX_thresold": 40,\n        "BB_length": 20,\n        "BB_multifactor": 2,\n        "KC_length": 25,\n        "KC_multifactor": 1.5,\n        "RSI_overbought": 45,\n        "use_true_range": True,\n    }\n\n    # Sell hyperspace params:\n    exit_params = {\n        "pHSL": -0.08,  # value loaded from strategy\n        "pPF_1": 0.016,  # value loaded from strategy\n        "pPF_2": 0.08,  # value loaded from strategy\n        "pSL_1": 0.011,  # value loaded from strategy\n        "pSL_2": 0.04,  # value loaded from strategy\n    }\n\n    # ROI table:  # value loaded from strategy\n    minimal_roi = {\n        "0": 0.3\n    }\n\n    # Stoploss:\n    stoploss = -0.99  # value loaded from strategy\n\n    # Trailing stop:\n    trailing_stop = True  # value loaded from strategy\n    trailing_stop_positive = 0.005  # value loaded from strategy\n    trailing_stop_positive_offset = 0.03  # value loaded from strategy\n    trailing_only_offset_is_reached = True  # value loaded from strategy\n    '
'\n======================================================= SELL REASON STATS ========================================================\n|        Sell Reason |   Sells |   Win  Draws  Loss  Win% |   Avg Profit % |   Cum Profit % |   Tot Profit USDT |   Tot Profit % |\n|--------------------+---------+--------------------------+----------------+----------------+-------------------+----------------|\n|        exit_signal |     457 |    196     0   261  42.9 |          -0.57 |        -258.56 |         -1294.08  |         -86.19 |\n| trailing_stop_loss |     261 |    261     0     0   100 |           3.57 |         931.7  |          4663.14  |         310.57 |\n|         force_exit |       2 |      0     0     2     0 |          -0.64 |          -1.28 |            -6.389 |          -0.43 |\n======================================================= LEFT OPEN TRADES REPORT =======================================================\n|     Pair |   Buys |   Avg Profit % |   Cum Profit % |   Tot Profit USDT |   Tot Profit % |   Avg Duration |   Win  Draw  Loss  Win% |\n|----------+--------+----------------+----------------+-------------------+----------------+----------------+-------------------------|\n| MHC/USDT |      1 |          -0.36 |          -0.36 |            -1.801 |          -0.18 |        1:30:00 |     0     0     1     0 |\n| XLM/USDT |      1 |          -0.92 |          -0.92 |            -4.588 |          -0.46 |        1:05:00 |     0     0     1     0 |\n|    TOTAL |      2 |          -0.64 |          -1.28 |            -6.389 |          -0.64 |        1:18:00 |     0     0     2     0 |\n=============== SUMMARY METRICS ================\n| Metric                 | Value               |\n|------------------------+---------------------|\n| Backtesting from       | 2021-10-12 00:00:00 |\n| Backtesting to         | 2021-11-12 00:00:00 |\n| Max open trades        | 3                   |\n|                        |                     |\n| Total/Daily Avg Trades | 720 / 23.23         |\n| Starting balance       | 1000.000 USDT       |\n| Final balance          | 4362.668 USDT       |\n| Absolute profit        | 3362.668 USDT       |\n| Total profit %         | 336.27%             |\n| Trades per day         | 23.23               |\n| Avg. daily profit %    | 10.85%              |\n| Avg. stake amount      | 500.000 USDT        |\n| Total trade volume     | 360000.000 USDT     |\n|                        |                     |\n| Best Pair              | XNL/USDT 45.69%     |\n| Worst Pair             | DAG/USDT -8.3%      |\n| Best trade             | XNL/USDT 19.72%     |\n| Worst trade            | DAPPT/USDT -9.72%   |\n| Best day               | 229.122 USDT        |\n| Worst day              | -8.923 USDT         |\n| Days win/draw/lose     | 29 / 0 / 3          |\n| Avg. Duration Winners  | 1:43:00             |\n| Avg. Duration Loser    | 3:23:00             |\n| Rejected Buy signals   | 377484              |\n|                        |                     |\n| Min balance            | 968.162 USDT        |\n| Max balance            | 4376.206 USDT       |\n| Drawdown               | 18.82%              |\n| Drawdown               | 94.205 USDT         |\n| Drawdown high          | 3312.883 USDT       |\n| Drawdown low           | 3218.678 USDT       |\n| Drawdown Start         | 2021-11-10 15:55:00 |\n| Drawdown End           | 2021-11-10 23:40:00 |\n| Market change          | 0%                  |\n================================================\n\n\nEpoch details:\n\n   462/684:    720 trades. 457/0/263 Wins/Draws/Losses. Avg profit   0.93%. Median profit   0.69%. Total profit  3362.66761261 USDT ( 336.27%). Avg duration 2:19:00 min. Objective: -147.06218\n\n\n    # Buy hyperspace params:\n    entry_params = {\n        "ADX_thresold": 33,\n        "BB_length": 22,\n        "BB_multifactor": 1.5,\n        "KC_length": 28,\n        "KC_multifactor": 1,\n        "RSI_overbought": 45,\n        "use_true_range": False,\n    }\n\n    # Sell hyperspace params:\n    exit_params = {\n        "pHSL": -0.08,  # value loaded from strategy\n        "pPF_1": 0.016,  # value loaded from strategy\n        "pPF_2": 0.08,  # value loaded from strategy\n        "pSL_1": 0.011,  # value loaded from strategy\n        "pSL_2": 0.04,  # value loaded from strategy\n    }\n\n    # ROI table:  # value loaded from strategy\n    minimal_roi = {\n        "0": 0.3\n    }\n\n    # Stoploss:\n    stoploss = -0.99  # value loaded from strategy\n\n    # Trailing stop:\n    trailing_stop = True  # value loaded from strategy\n    trailing_stop_positive = 0.005  # value loaded from strategy\n    trailing_stop_positive_offset = 0.03  # value loaded from strategy\n    trailing_only_offset_is_reached = True  # value loaded from strategy\n    '

class SqueezeMomentum(IStrategy):
    INTERFACE_VERSION = 3  # Buy hyperspace params:
    entry_params = {'BB_length': 20, 'BB_multifactor': 2.0, 'KC_length': 11, 'KC_multifactor': 1.5, 'use_true_range': True, 'RSI_overbought': 60, 'ADX_thresold': 33}  # Sell hyperspace params:
    exit_params = {}  # ROI table:  # value loaded from strategy
    minimal_roi = {'0': 0.3}  # Stoploss:
    stoploss = -0.99  # value loaded from strategy
    # Trailing stop:
    trailing_stop = True  # value loaded from strategy
    trailing_stop_positive = 0.005  # value loaded from strategy
    trailing_stop_positive_offset = 0.03  # value loaded from strategy
    trailing_only_offset_is_reached = True  # value loaded from strategy
    use_custom_stoploss = False  # Sell signal
    use_exit_signal = True
    exit_profit_only = False
    exit_profit_offset = 0.01
    ignore_roi_if_entry_signal = False
    process_only_new_candles = True
    startup_candle_count = 30  # Parameters
    BB_length = IntParameter(10, 30, default=entry_params['BB_length'], space='entry', optimize=True)
    BB_multifactor = CategoricalParameter([0.5, 1, 1.5, 2, 2.5, 3, 3.5], default=entry_params['BB_multifactor'], space='entry', optimize=True)
    KC_length = IntParameter(10, 30, default=entry_params['KC_length'], space='entry', optimize=True)
    KC_multifactor = CategoricalParameter([0.5, 1, 1.5, 2, 2.5, 3, 3.5], default=entry_params['KC_multifactor'], space='entry', optimize=True)
    use_true_range = BooleanParameter(default=entry_params['use_true_range'], space='entry', optimize=True)  # Guards
    RSI_overbought = CategoricalParameter([45, 50, 55, 60, 65], default=entry_params['RSI_overbought'], space='entry', optimize=True)
    ADX_thresold = CategoricalParameter([15, 20, 25, 30, 33, 35, 40, 45, 50], default=entry_params['ADX_thresold'], space='entry', optimize=True)  ## Trailing params
    # hard stoploss profit
    pHSL = DecimalParameter(-0.2, -0.04, default=-0.08, decimals=3, space='exit', load=True)  # profit threshold 1, trigger point, SL_1 is used
    pPF_1 = DecimalParameter(0.008, 0.02, default=0.016, decimals=3, space='exit', load=True)
    pSL_1 = DecimalParameter(0.008, 0.02, default=0.011, decimals=3, space='exit', load=True)  # profit threshold 2, SL_2 is used
    pPF_2 = DecimalParameter(0.04, 0.1, default=0.08, decimals=3, space='exit', load=True)
    pSL_2 = DecimalParameter(0.02, 0.07, default=0.04, decimals=3, space='exit', load=True)  # Optimal timeframe for the strategy
    timeframe = '5m'  ## Custom Trailing stoploss ( credit to Perkmeister for this custom stoploss to help the strategy ride a green candle )

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> float:  # hard stoploss profit
        HSL = self.pHSL.value
        PF_1 = self.pPF_1.value
        SL_1 = self.pSL_1.value
        PF_2 = self.pPF_2.value
        SL_2 = self.pSL_2.value  # For profits between PF_1 and PF_2 the stoploss (sl_profit) used is linearly interpolated
        # between the values of SL_1 and SL_2. For all profits above PL_2 the sl_profit value
        # rises linearly with current profit, for profits below PF_1 the hard stoploss profit is used.
        if current_profit > PF_2:
            sl_profit = SL_2 + (current_profit - PF_2)
        elif current_profit > PF_1:
            sl_profit = SL_1 + (current_profit - PF_1) * (SL_2 - SL_1) / (PF_2 - PF_1)
        else:
            sl_profit = HSL  # Only for hyperopt invalid return
        if sl_profit >= current_profit:
            return -0.99
        return stoploss_from_open(sl_profit, current_profit)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        //
        // @author LazyBear
        // List of all my indicators: https://www.tradingview.com/v/4IneGo8h/
        //

        // Calculate BB
        source = close
        basis = sma(source, length)
        dev = multKC * stdev(source, length)
        upperBB = basis + dev
        lowerBB = basis - dev

        // Calculate KC
        ma = sma(source, lengthKC)
        range = useTrueRange ? tr : (high - low)
        rangema = sma(range, lengthKC)
        upperKC = ma + rangema * multKC
        lowerKC = ma - rangema * multKC

        sqzOn  = (lowerBB > lowerKC) and (upperBB < upperKC)
        sqzOff = (lowerBB < lowerKC) and (upperBB > upperKC)
        noSqz  = (sqzOn == false) and (sqzOff == false)

        val = linreg(source  -  avg(avg(highest(high, lengthKC), lowest(low, lengthKC)),sma(close,lengthKC)),
                    lengthKC,0)

        bcolor = iff( val > 0,
                    iff( val > nz(val[1]), lime, green),
                    iff( val < nz(val[1]), red, maroon))
        scolor = noSqz ? blue : sqzOn ? black : gray
        plot(val, color=bcolor, style=histogram, linewidth=4)
        plot(0, color=scolor, style=cross, linewidth=2)
        """
        if self.use_true_range.value:
            dataframe[f'range'] = ta.TRANGE(dataframe)
        else:
            dataframe[f'range'] = dataframe['high'] - dataframe['low']
        for val in self.BB_length.range:  # BB
            dataframe[f'ma_{val}'] = ta.SMA(dataframe, val)
            dataframe[f'stdev_{val}'] = ta.STDDEV(dataframe, val)  # KC
            dataframe[f'rangema_{val}'] = ta.SMA(dataframe[f'range'], val)  # Linreg
            dataframe[f'hh_close_{val}'] = ta.MAX(dataframe['high'], val)
            dataframe[f'll_close_{val}'] = ta.MIN(dataframe['low'], val)
            dataframe[f'avg_hh_ll_{val}'] = (dataframe[f'hh_close_{val}'] + dataframe[f'll_close_{val}']) / 2
            dataframe[f'avg_close_{val}'] = ta.SMA(dataframe['close'], val)
            dataframe[f'avg_{val}'] = (dataframe[f'avg_hh_ll_{val}'] + dataframe[f'avg_close_{val}']) / 2
            dataframe[f'val_{val}'] = ta.LINEARREG(dataframe['close'] - dataframe[f'avg_{val}'], val, 0)  # min val
            dataframe[f'val_min_{val}'] = ta.MIN(dataframe[f'val_{val}'], 50)  # max val
            dataframe[f'val_max_{val}'] = ta.MAX(dataframe[f'val_{val}'], 50)  # stdev val
            dataframe[f'val_stdev_{val}'] = ta.STDDEV(dataframe[f'val_{val}'], 50)  # average val
            dataframe[f'val_avg_{val}'] = ta.SMA(dataframe[f'val_{val}'], 50)
        for val in self.KC_length.range:  # BB
            dataframe[f'ma_{val}'] = ta.SMA(dataframe, val)
            dataframe[f'stdev_{val}'] = ta.STDDEV(dataframe, val)  # KC
            dataframe[f'rangema_{val}'] = ta.SMA(dataframe[f'range'], val)  # RSI
        dataframe['rsi'] = ta.RSI(dataframe)  # EMA
        dataframe['ema_50'] = ta.EMA(dataframe, 50)
        dataframe['ema_200'] = ta.EMA(dataframe, 200)  # ADX
        dataframe['adx'] = ta.ADX(dataframe, 14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb_length = self.BB_length.value
        mult = self.BB_multifactor.value
        kc = self.KC_multifactor.value
        kc_length = self.KC_length.value
        is_sqzOn = (dataframe[f'ma_{bb_length}'] - dataframe[f'stdev_{bb_length}'] * mult > dataframe[f'ma_{kc_length}'] - dataframe[f'rangema_{kc_length}'] * kc) & (dataframe[f'ma_{bb_length}'] + dataframe[f'stdev_{bb_length}'] * mult < dataframe[f'ma_{kc_length}'] + dataframe[f'rangema_{kc_length}'] * kc)
        is_sqzOff = (dataframe[f'ma_{bb_length}'] - dataframe[f'stdev_{bb_length}'] * mult < dataframe[f'ma_{kc_length}'] - dataframe[f'rangema_{kc_length}'] * kc) & (dataframe[f'ma_{bb_length}'] + dataframe[f'stdev_{bb_length}'] * mult > dataframe[f'ma_{kc_length}'] + dataframe[f'rangema_{kc_length}'] * kc)  # is_noSqz = (
        #        ((not is_sqzOn) & (not is_sqzOff))
        # )
        # (dataframe[f'sqzOn_{self.KC_length.value}_{self.KC_multifactor.value}'] == 1) &
        # (dataframe[f'val_{self.BB_length.value}'] > 0) &
        # (dataframe[f'val_{self.BB_length.value}'].shift(1) < 0) &
        # (dataframe[f'sqzOn_{self.KC_length.value}_{self.KC_multifactor.value}'].shift(1) == 1) &
        # (dataframe[f'val_{self.BB_length.value}'].shift(1) == dataframe[f'val_min_{self.BB_length.value}']) &
        # (dataframe[f'val_{self.BB_length.value}'].shift(1) < dataframe[f'val_avg_{self.BB_length.value}'] -  dataframe[f'val_stdev_{self.BB_length.value}']) &
        # (dataframe[f'sqzOn_{self.KC_length.value}_{self.KC_multifactor.value}'].rolling(10).sum() < 3) &
        # (dataframe['close'] > dataframe['ema_50']) &
        # (dataframe['ema_50'] > dataframe['ema_200']) &
        dataframe.loc[is_sqzOff & (dataframe[f'val_{self.BB_length.value}'].shift(2) > dataframe[f'val_{self.BB_length.value}'].shift(1)) & (dataframe[f'val_{self.BB_length.value}'].shift(1) < dataframe[f'val_{self.BB_length.value}']) & (dataframe[f'val_{self.BB_length.value}'] < 0) & (dataframe['adx'] > self.ADX_thresold.value) & (dataframe['rsi'] < self.RSI_overbought.value) & (dataframe['volume'] > 0), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe[f'val_{self.BB_length.value}'].shift(2) < dataframe[f'val_{self.BB_length.value}'].shift(1)) & (dataframe[f'val_{self.BB_length.value}'].shift(1) > dataframe[f'val_{self.BB_length.value}']) & (dataframe[f'val_{self.BB_length.value}'].shift(1) == dataframe[f'val_max_{self.BB_length.value}']) & (dataframe[f'val_{self.BB_length.value}'] > 0) & (dataframe['volume'] > 0), 'exit_long'] = 1
        dataframe.to_csv('user_data/csvs/%s_%s.csv' % (self.__class__.__name__, metadata['pair'].replace('/', '_')))
        return dataframe