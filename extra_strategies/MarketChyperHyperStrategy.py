# --- Do not remove these libs ----------------------------------------------------------------------
import numpy as np  # noqa
import pandas as pd  # noqa
import talib.abstract as ta
from pandas import DataFrame
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import CategoricalParameter, DecimalParameter, IntParameter, RealParameter
# ^ TA-Lib Autofill mostly broken in JetBrains Products,
# ta._ta_lib.<function_name> can temporarily be used while writing as a workaround
# Then change back to ta.<function_name> so IDE won't nag about accessing a protected member of TA-Lib
# ----------------------------------------------------------------------------------------------------
# podriamos ver la tendencia y calcular cada valor por tendencia como hace manigomoney

class MarketChyperHyperStrategy(IStrategy):
    INTERFACE_VERSION = 3
    # If enabled all Weighted Signal results will be added to the dataframe for easy debugging with BreakPoints
    # Warning: Disable this for anything else then debugging in an IDE! (Integrated Development Environment)
    debuggable_weighted_signal_dataframe = False
    # Ps: Documentation has been moved to the Buy/Sell HyperOpt Space Parameters sections below this copy-paste section
    ####################################################################################################################
    #                                    START OF HYPEROPT RESULTS COPY-PASTE SECTION                                  #
    ####################################################################################################################
    # Buy hyperspace params:
    entry_params = {'entry_downtrend_oslevel': -37, 'entry_downtrend_rsi_div_value': 79, 'entry_downtrend_rsi_divergence_weight': 50, 'entry_downtrend_total_signal_needed': 70, 'entry_downtrend_wavetrend_weight': 96, 'entry_sideways_oslevel': -28, 'entry_sideways_rsi_div_value': 45, 'entry_sideways_rsi_divergence_weight': 35, 'entry_sideways_total_signal_needed': 80, 'entry_sideways_wavetrend_weight': 5, 'entry_uptrend_oslevel': -43, 'entry_uptrend_rsi_div_value': 93, 'entry_uptrend_rsi_divergence_weight': 84, 'entry_uptrend_total_signal_needed': 25, 'entry_uptrend_wavetrend_weight': 91}
    # Sell hyperspace params:
    exit_params = {'exit_downtrend_oblevel': 75.67481, 'exit_downtrend_rsi_divergence_weight': 90, 'exit_downtrend_total_signal_needed': 51, 'exit_downtrend_wavetrend_weight': 30, 'exit_sideways_oblevel': 1.93351, 'exit_sideways_rsi_divergence_weight': 59, 'exit_sideways_total_signal_needed': 36, 'exit_sideways_wavetrend_weight': 83, 'exit_uptrend_oblevel': 37.98512, 'exit_uptrend_rsi_divergence_weight': 99, 'exit_uptrend_total_signal_needed': 93, 'exit_uptrend_wavetrend_weight': 43}
    # ROI table:
    minimal_roi = {'0': 0.23733, '238': 0.20624, '846': 0.08939, '1834': 0}
    # Stoploss:
    stoploss = -0.12447
    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.01658
    trailing_stop_positive_offset = 0.10224
    trailing_only_offset_is_reached = True
    ####################################################################################################################
    #                                     END OF HYPEROPT RESULTS COPY-PASTE SECTION                                   #
    ####################################################################################################################
    # Optimal timeframe for the strategy.
    timeframe = '1h'
    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False
    # These values can be overridden in the "ask_strategy" section in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 400
    # SMA200 needs 200 candles before producing valid signals
    # EMA200 needs an extra 200 candles of SMA200 before producing valid signals
    # Optional order type mapping.
    order_types = {'entry': 'limit', 'exit': 'limit', 'stoploss': 'market', 'stoploss_on_exchange': False}
    # Optional order time in force.
    order_time_in_force = {'entry': 'gtc', 'exit': 'gtc'}
    # Uptrend Trend Buy
    # -------------------
    # Total Buy Signal Percentage needed for a signal to be positive
    # im testing number of signals * 50 / 2
    entry___trades_when_downwards = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry___trades_when_sideways = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry___trades_when_upwards = CategoricalParameter([True, False], default=True, space='entry', optimize=False, load=True)
    entry_uptrend_total_signal_needed = IntParameter(0, 100, default=65, space='entry', optimize=True, load=True)
    #wave trend
    entry_uptrend_wavetrend_weight = IntParameter(0, 100, default=0, space='entry', optimize=True, load=True)
    #rsi divs
    entry_uptrend_rsi_divergence_weight = IntParameter(0, 100, default=0, space='entry', optimize=True, load=True)
    # entry_rsi_div_value (rsi used in condition of bullish div)
    entry_uptrend_rsi_div_value = IntParameter(0, 100, default=0, space='entry', optimize=True, load=True)
    entry_uptrend_oslevel = IntParameter(-100, 0, default=0, space='entry', optimize=True, load=True)
    # Sideways Trend Buy
    # -------------------
    entry_sideways_total_signal_needed = IntParameter(0, 100, default=65, space='entry', optimize=True, load=True)
    #wave trend
    entry_sideways_wavetrend_weight = IntParameter(0, 100, default=0, space='entry', optimize=True, load=True)
    #rsi divs
    entry_sideways_rsi_divergence_weight = IntParameter(0, 100, default=0, space='entry', optimize=True, load=True)
    # entry_rsi_div_value (rsi used in condition of bullish div)
    entry_sideways_rsi_div_value = IntParameter(0, 100, default=0, space='entry', optimize=True, load=True)
    entry_sideways_oslevel = IntParameter(-100, 0, default=0, space='entry', optimize=True, load=True)
    # Downtrend Trend Buy
    # -------------------
    entry_downtrend_total_signal_needed = IntParameter(0, 100, default=65, space='entry', optimize=True, load=True)
    #wave trend
    entry_downtrend_wavetrend_weight = IntParameter(0, 100, default=0, space='entry', optimize=True, load=True)
    #rsi divs
    entry_downtrend_rsi_divergence_weight = IntParameter(0, 100, default=0, space='entry', optimize=True, load=True)
    # entry_rsi_div_value (rsi used in condition of bullish div)
    entry_downtrend_rsi_div_value = IntParameter(0, 100, default=0, space='entry', optimize=True, load=True)
    entry_downtrend_oslevel = IntParameter(-100, 0, default=0, space='entry', optimize=True, load=True)
    #exit??
    exit___trades_when_downwards = CategoricalParameter([True, False], default=True, space='exit', optimize=True, load=True)
    exit___trades_when_sideways = CategoricalParameter([True, False], default=True, space='exit', optimize=True, load=True)
    exit___trades_when_upwards = CategoricalParameter([True, False], default=True, space='exit', optimize=True, load=True)
    # Uptrend Trend Sell
    # --------------------
    # Total Sell Signal Percentage needed for a signal to be positive
    exit_uptrend_total_signal_needed = IntParameter(0, 100, default=65, space='exit', optimize=True, load=True)
    #wave trend
    exit_uptrend_wavetrend_weight = IntParameter(0, 100, default=0, space='exit', optimize=True, load=True)
    #rsi divs
    exit_uptrend_rsi_divergence_weight = IntParameter(0, 100, default=0, space='exit', optimize=True, load=True)
    exit_uptrend_oblevel = RealParameter(0, 100, default=0, space='exit', optimize=True, load=True)
    # Sidewyas Trend Sell
    # --------------------
    # Total Sell Signal Percentage needed for a signal to be positive
    exit_sideways_total_signal_needed = IntParameter(0, 100, default=65, space='exit', optimize=True, load=True)
    #wave trend
    exit_sideways_wavetrend_weight = IntParameter(0, 100, default=0, space='exit', optimize=True, load=True)
    #rsi divs
    exit_sideways_rsi_divergence_weight = IntParameter(0, 100, default=0, space='exit', optimize=True, load=True)
    exit_sideways_oblevel = RealParameter(0, 100, default=0, space='exit', optimize=True, load=True)
    # Downtrend Trend Sell
    # --------------------
    exit_downtrend_total_signal_needed = IntParameter(0, 100, default=65, space='exit', optimize=True, load=True)
    #wave trend
    exit_downtrend_wavetrend_weight = IntParameter(0, 100, default=0, space='exit', optimize=True, load=True)
    #rsi divs
    exit_downtrend_rsi_divergence_weight = IntParameter(0, 100, default=0, space='exit', optimize=True, load=True)
    exit_downtrend_oblevel = RealParameter(0, 100, default=0, space='exit', optimize=True, load=True)
    # ---------------------------------------------------------------- #
    #                 Custom HyperOpt Space Parameters                 #
    # ---------------------------------------------------------------- #
    # class HyperOpt:
    #     # Define a custom stoploss space.
    #     @staticmethod
    #     def stoploss_space():
    #         return [Real(-0.01, -0.35, name='stoploss')]

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        :param dataframe: Dataframe with data from the exchange
        :param metadata: Additional information, like the currently traded pair
        :return: a Dataframe with all mandatory indicators for the strategies
        """
        # Momentum Indicators (timeperiod is expressed in candles)
        # -------------------
        # ADX - Average Directional Index (The Trend Strength Indicator)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)  # 14 timeperiods is usually used for ADX
        # +DM (Positive Directional Indicator) = current high - previous high
        dataframe['plus_di'] = ta.PLUS_DI(dataframe, timeperiod=25)
        # -DM (Negative Directional Indicator) = previous low - current low
        dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=25)
        # RSI - Relative Strength Index (Under bought / Over sold & Over bought / Under sold indicator Indicator)
        dataframe['rsi'] = ta.RSI(dataframe)
        # MACD - Moving Average Convergence Divergence
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']  # MACD - Blue TradingView Line (Bullish if on top)
        dataframe['macdsignal'] = macd['macdsignal']  # Signal - Orange TradingView Line (Bearish if on top)
        # Initialize total signal variables (should be 0 = false by default)
        dataframe['total_entry_signal_strength'] = dataframe['total_exit_signal_strength'] = 0
        #divergences
        dataframe = self.divergences(dataframe)
        #get trend
        dataframe.loc[(dataframe['adx'] > 20) & (dataframe['plus_di'] < dataframe['minus_di']), 'trend'] = 'downwards'
        dataframe.loc[dataframe['adx'] < 20, 'trend'] = 'sideways'
        dataframe.loc[(dataframe['adx'] > 20) & (dataframe['plus_di'] > dataframe['minus_di']), 'trend'] = 'upwards'
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame populated with indicators
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry column
        """
        dataframe = self.market_cipher(dataframe)
        #CALCULATE WT OVERSOLD
        dataframe.loc[dataframe['trend'] == 'downwards', 'wtOversold'] = dataframe['wt2'] <= self.entry_downtrend_oslevel.value
        dataframe.loc[dataframe['trend'] == 'sideways', 'wtOversold'] = dataframe['wt2'] <= self.entry_sideways_oslevel.value
        dataframe.loc[dataframe['trend'] == 'upwards', 'wtOversold'] = dataframe['wt2'] <= self.entry_uptrend_oslevel.value
        #SUM
        dataframe.loc[(dataframe['trend'] == 'downwards') & (dataframe['wtCrossUp'] & dataframe['wtOversold']), 'entry_wavetrend_weight'] = self.entry_downtrend_wavetrend_weight.value
        dataframe.loc[(dataframe['trend'] == 'sideways') & (dataframe['wtCrossUp'] & dataframe['wtOversold']), 'entry_wavetrend_weight'] = self.entry_sideways_wavetrend_weight.value
        dataframe.loc[(dataframe['trend'] == 'upwards') & (dataframe['wtCrossUp'] & dataframe['wtOversold']), 'entry_wavetrend_weight'] = self.entry_uptrend_wavetrend_weight.value
        dataframe['total_entry_signal_strength'] += dataframe['entry_wavetrend_weight']
        #rsi div and rsi vañur entry_rsi_div entry_rsi_div_weight
        dataframe.loc[(dataframe['trend'] == 'downwards') & (dataframe['bullish_div'] & (dataframe['rsi'] <= self.entry_downtrend_rsi_div_value.value)), 'entry_rsi_divergence_weight'] = self.entry_downtrend_rsi_divergence_weight.value
        dataframe.loc[(dataframe['trend'] == 'sideways') & (dataframe['bullish_div'] & (dataframe['rsi'] <= self.entry_sideways_rsi_div_value.value)), 'entry_rsi_divergence_weight'] = self.entry_sideways_rsi_divergence_weight.value
        dataframe.loc[(dataframe['trend'] == 'upwards') & (dataframe['bullish_div'] & (dataframe['rsi'] <= self.entry_uptrend_rsi_div_value.value)), 'entry_rsi_divergence_weight'] = self.entry_uptrend_rsi_divergence_weight.value
        dataframe['total_entry_signal_strength'] += dataframe['entry_rsi_divergence_weight']
        # Check if entry signal should be sent depending on the current trend
        # Check if entry signal should be sent depending on the current trend
        dataframe.loc[(dataframe['trend'] == 'downwards') & (dataframe['total_entry_signal_strength'] >= self.entry_downtrend_total_signal_needed.value) | (dataframe['trend'] == 'sideways') & (dataframe['total_entry_signal_strength'] >= self.entry_sideways_total_signal_needed.value) | (dataframe['trend'] == 'upwards') & (dataframe['total_entry_signal_strength'] >= self.entry_uptrend_total_signal_needed.value), 'enter_long'] = 1
        # Override Buy Signal: When configured entry signals can be completely turned off for each kind of trend
        if not self.entry___trades_when_downwards.value:
            dataframe.loc[dataframe['trend'] == 'downwards', 'enter_long'] = 0
        if not self.entry___trades_when_sideways.value:
            dataframe.loc[dataframe['trend'] == 'sideways', 'enter_long'] = 0
        if not self.entry___trades_when_upwards.value:
            dataframe.loc[dataframe['trend'] == 'upwards', 'enter_long'] = 0
        return dataframe
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.market_cipher(dataframe)
        #CALCULATE WT OVERSOLD
        dataframe.loc[dataframe['trend'] == 'downwards', 'wtOverbought'] = dataframe['wt2'] >= self.exit_downtrend_oblevel.value
        dataframe.loc[dataframe['trend'] == 'sideways', 'wtOverbought'] = dataframe['wt2'] >= self.exit_sideways_oblevel.value
        dataframe.loc[dataframe['trend'] == 'upwards', 'wtOverbought'] = dataframe['wt2'] >= self.exit_uptrend_oblevel.value
        #SUM
        dataframe.loc[(dataframe['trend'] == 'downwards') & (dataframe['wtCrossDown'] & dataframe['wtOverbought']), 'exit_wavetrend_weight'] = self.exit_downtrend_wavetrend_weight.value
        dataframe.loc[(dataframe['trend'] == 'sideways') & (dataframe['wtCrossDown'] & dataframe['wtOverbought']), 'exit_wavetrend_weight'] = self.exit_sideways_wavetrend_weight.value
        dataframe.loc[(dataframe['trend'] == 'upwards') & (dataframe['wtCrossDown'] & dataframe['wtOverbought']), 'exit_wavetrend_weight'] = self.exit_uptrend_wavetrend_weight.value
        dataframe['total_exit_signal_strength'] += dataframe['exit_wavetrend_weight']
        #rsi div and rsi vañur entry_rsi_div entry_rsi_div_weight
        dataframe.loc[(dataframe['trend'] == 'downwards') & dataframe['bearish_div'], 'exit_rsi_divergence_weight'] = self.exit_downtrend_rsi_divergence_weight.value
        dataframe.loc[(dataframe['trend'] == 'sideways') & dataframe['bearish_div'], 'exit_rsi_divergence_weight'] = self.exit_sideways_rsi_divergence_weight.value
        dataframe.loc[(dataframe['trend'] == 'upwards') & dataframe['bearish_div'], 'exit_rsi_divergence_weight'] = self.exit_uptrend_rsi_divergence_weight.value
        dataframe['total_exit_signal_strength'] += dataframe['exit_rsi_divergence_weight']
        # Check if entry signal should be sent depending on the current trend
        # Check if entry signal should be sent depending on the current trend
        dataframe.loc[(dataframe['trend'] == 'downwards') & (dataframe['total_exit_signal_strength'] >= self.exit_downtrend_total_signal_needed.value) | (dataframe['trend'] == 'sideways') & (dataframe['total_exit_signal_strength'] >= self.exit_sideways_total_signal_needed.value) | (dataframe['trend'] == 'upwards') & (dataframe['total_exit_signal_strength'] >= self.exit_uptrend_total_signal_needed.value), 'exit_long'] = 1
        return dataframe
    #wavetrend, market cypher

    def market_cipher(self, dataframe) -> DataFrame:
        self.n1 = 10  #WT Channel Length
        self.n2 = 21  #WT Average Length
        dataframe['ap'] = (dataframe['high'] + dataframe['low'] + dataframe['close']) / 3
        dataframe['esa'] = ta.EMA(dataframe['ap'], self.n1)
        dataframe['d'] = ta.EMA((dataframe['ap'] - dataframe['esa']).abs(), self.n1)
        dataframe['ci'] = (dataframe['ap'] - dataframe['esa']) / (0.015 * dataframe['d'])
        dataframe['tci'] = ta.EMA(dataframe['ci'], self.n2)
        dataframe['wt1'] = dataframe['tci']
        dataframe['wt2'] = ta.SMA(dataframe['wt1'], 4)
        dataframe['wtVwap'] = dataframe['wt1'] - dataframe['wt2']
        dataframe['wtCrossUp'] = dataframe['wt2'] - dataframe['wt1'] <= 0
        dataframe['wtCrossDown'] = dataframe['wt2'] - dataframe['wt1'] >= 0
        dataframe['crossed_above'] = qtpylib.crossed_above(dataframe['wt2'], dataframe['wt1'])
        dataframe['crossed_below'] = qtpylib.crossed_below(dataframe['wt2'], dataframe['wt1'])
        return dataframe
    #rsi divergences  dataframe['bullish_div'] dataframe['bearish_div']

    def divergences(self, dataframe) -> DataFrame:
        dataframe['bullish_div'] = (dataframe['close'].shift(4) > dataframe['close'].shift(2)) & (dataframe['close'].shift(3) > dataframe['close'].shift(2)) & (dataframe['close'].shift(2) < dataframe['close'].shift(1)) & (dataframe['close'].shift(2) < dataframe['close'])
        dataframe['bearish_div'] = (dataframe['close'].shift(4) < dataframe['close'].shift(2)) & (dataframe['close'].shift(3) < dataframe['close'].shift(2)) & (dataframe['close'].shift(2) > dataframe['close'].shift(1)) & (dataframe['close'].shift(2) > dataframe['close'])
        return dataframe