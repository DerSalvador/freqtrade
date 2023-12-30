# --- Do not remove these libs ---
from datetime import datetime, timedelta
from functools import reduce
import talib.abstract as ta
from pandas import DataFrame
import freqtrade.vendor.qtpylib.indicators as qtpylib
# --------------------------------
from freqtrade.persistence import Trade
from freqtrade.strategy.interface import IStrategy
#

class BBRSIv2(IStrategy):
    INTERFACE_VERSION = 3
    '\n    author@: Gert Wohlgemuth\n    converted from:\n    https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/BbandRsi.cs\n    Customized by StrongManBR\n    '
    # Minimal ROI designed for the strategy.
    # adjust based on market conditions. We would recommend to keep it low for quick turn arounds
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = {'0': 0.3}
    # Optimal stoploss designed for the strategy
    stoploss = -0.33
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = True
    exit_profit_offset = 0.01
    ignore_roi_if_entry_signal = False
    use_custom_stoploss = True
    startup_candle_count: int = 144
    # Optimal timeframe for the strategy
    timeframe = '15m'
    plot_config = {'main_plot': {'bb_lowerband': {}, 'bb_middleband': {}, 'bb_upperband': {}, 'tema': {}}, 'subplots': {'RSI': {'rsi': {'color': 'blue'}}, 'MARKET': {'close_max': {'color': 'green', 'type': 'bar'}, 'close_min': {'color': 'red', 'type': 'bar'}, 'dropped_by_percent': {'color': 'blue', 'type': 'bar'}, 'pumped_by_percent': {'color': 'orange', 'type': 'bar'}}}}

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> float:
        sl_new = 1
        if self.config['runmode'].value in ('live', 'dry_run'):
            sl_new = 0.001
        if current_profit > 0.2:
            sl_new = 0.05
        elif current_profit > 0.1:
            sl_new = 0.03
        elif current_profit > 0.06:
            sl_new = 0.02
        elif current_profit > 0.03:
            sl_new = 0.01
        return sl_new

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        # Bollinger bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        # Custom
        # TEMA - Triple Exponential Moving Average
        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9, price='close')
        dataframe['close_max'] = dataframe['close'].rolling(window=60).max()  #5h
        dataframe['dropped_by_percent'] = 1 - dataframe['close'] / dataframe['close_max']
        dataframe['close_min'] = dataframe['close'].rolling(window=60).min()  #5h
        dataframe['pumped_by_percent'] = (dataframe['high'] - dataframe['close_min']) / dataframe['high']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'enter_tag'] = ''
        conditions = []
        #        dont_entry_conditions = []
        # Signal: RSI crosses above 35
        RB1 = qtpylib.crossed_above(dataframe['rsi'], 35) & (dataframe['close'] < dataframe['bb_lowerband'])
        dataframe.loc[RB1, 'enter_tag'] += 'RB1:BB_LOWER '
        conditions.append(RB1)  # Make sure Volume is not 0
        RB2 = (dataframe['rsi'] < 23) & (dataframe['tema'] < dataframe['bb_lowerband']) & (dataframe['tema'] > dataframe['tema'].shift(1)) & (dataframe['volume'] > 0)
        dataframe.loc[RB2, 'enter_tag'] += 'RB2:RSI<23_ '
        conditions.append(RB2)
        if conditions:
            #is_bull &
            #is_additional_check &
            #can_entry &
            #is_live_data &
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        dataframe.loc[:, 'exit_tag'] = ''
        #exit_now = []
        RS1 = dataframe['rsi'] > 70
        dataframe.loc[RS1, 'exit_tag'] += 'RS1:RSI>70 '
        conditions.append(RS1)
        RS2 = dataframe['high'] > dataframe['close_max']
        dataframe.loc[RS2, 'exit_tag'] += 'RS2:>CLOSE_MAX '
        conditions.append(RS2)
        if conditions:
            #can_exit &
            #is_live_data &
            dataframe.loc[reduce(lambda x, y: x | y, conditions), 'exit_long'] = 1
        return dataframe