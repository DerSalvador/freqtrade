# --- Do not remove these libs ---
import talib.abstract as ta
from pandas import DataFrame
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy.interface import IStrategy
# --------------------------------

class Babico_SMA5xBBmid(IStrategy):
    INTERFACE_VERSION = 3
    minimal_roi = {'0': 99999999}
    stoploss = -0.99
    # Trailing stoploss (not used)
    trailing_stop = False
    trailing_only_offset_is_reached = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.03
    use_exit_signal = True
    exit_profit_only = True
    process_only_new_candles = True
    # Optional order type mapping.
    order_types = {'entry': 'limit', 'exit': 'limit', 'trailing_stop_loss': 'limit', 'stoploss': 'limit', 'stoploss_on_exchange': False}
    # Optimal timeframe for the strategy
    timeframe = '1d'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_low'] = bb['lower']
        dataframe['bb_mid'] = bb['mid']
        dataframe['bb_upp'] = bb['upper']
        dataframe['ema5'] = ta.EMA(dataframe, timeperiod=5)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[qtpylib.crossed_above(dataframe['ema5'], dataframe['bb_mid']), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[qtpylib.crossed_above(dataframe['bb_mid'], dataframe['ema5']), 'exit_long'] = 1
        return dataframe