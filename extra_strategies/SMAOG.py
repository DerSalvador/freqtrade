from datetime import datetime, timedelta
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import CategoricalParameter
from freqtrade.strategy import DecimalParameter, IntParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
# og        @tirail
# author    @Jooopieeert#0239
ma_types = {'SMA': ta.SMA, 'EMA': ta.EMA}

class SMAOG(IStrategy):
    INTERFACE_VERSION = 3
    entry_params = {'base_nb_candles_entry': 26, 'entry_trigger': 'SMA', 'low_offset': 0.968, 'pair_is_bad_0_threshold': 0.555, 'pair_is_bad_1_threshold': 0.172, 'pair_is_bad_2_threshold': 0.198}
    exit_params = {'base_nb_candles_exit': 28, 'high_offset': 0.985, 'exit_trigger': 'EMA'}
    base_nb_candles_entry = IntParameter(16, 45, default=entry_params['base_nb_candles_entry'], space='entry', optimize=False, load=True)
    base_nb_candles_exit = IntParameter(16, 45, default=exit_params['base_nb_candles_exit'], space='exit', optimize=False, load=True)
    low_offset = DecimalParameter(0.8, 0.99, default=entry_params['low_offset'], space='entry', optimize=False, load=True)
    high_offset = DecimalParameter(0.8, 1.1, default=exit_params['high_offset'], space='exit', optimize=False, load=True)
    entry_trigger = CategoricalParameter(ma_types.keys(), default=entry_params['entry_trigger'], space='entry', optimize=False, load=True)
    exit_trigger = CategoricalParameter(ma_types.keys(), default=exit_params['exit_trigger'], space='exit', optimize=False, load=True)
    pair_is_bad_0_threshold = DecimalParameter(0.0, 0.6, default=0.22, space='entry', optimize=True, load=True)
    pair_is_bad_1_threshold = DecimalParameter(0.0, 0.35, default=0.09, space='entry', optimize=True, load=True)
    pair_is_bad_2_threshold = DecimalParameter(0.0, 0.2, default=0.06, space='entry', optimize=True, load=True)
    timeframe = '5m'
    stoploss = -0.23
    minimal_roi = {'0': 10}
    trailing_stop = True
    trailing_only_offset_is_reached = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    process_only_new_candles = True
    startup_candle_count = 400

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if not self.config['runmode'].value == 'hyperopt':
            dataframe['ma_offset_entry'] = ma_types[self.entry_trigger.value](dataframe, int(self.base_nb_candles_entry.value)) * self.low_offset.value
            dataframe['ma_offset_exit'] = ma_types[self.exit_trigger.value](dataframe, int(self.base_nb_candles_exit.value)) * self.high_offset.value
            dataframe['pair_is_bad'] = (((dataframe['open'].rolling(144).min() - dataframe['close']) / dataframe['close'] >= self.pair_is_bad_0_threshold.value) | ((dataframe['open'].rolling(12).min() - dataframe['close']) / dataframe['close'] >= self.pair_is_bad_1_threshold.value) | ((dataframe['open'].rolling(2).min() - dataframe['close']) / dataframe['close'] >= self.pair_is_bad_2_threshold.value)).astype('int')
            dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
            dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
            dataframe['rsi_exit'] = ta.RSI(dataframe, timeperiod=2)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if self.config['runmode'].value == 'hyperopt':
            dataframe['ma_offset_entry'] = ma_types[self.entry_trigger.value](dataframe, int(self.base_nb_candles_entry.value)) * self.low_offset.value
            dataframe['pair_is_bad'] = (((dataframe['open'].rolling(144).min() - dataframe['close']) / dataframe['close'] >= self.pair_is_bad_0_threshold.value) | ((dataframe['open'].rolling(12).min() - dataframe['close']) / dataframe['close'] >= self.pair_is_bad_1_threshold.value) | ((dataframe['open'].rolling(2).min() - dataframe['close']) / dataframe['close'] >= self.pair_is_bad_2_threshold.value)).astype('int')
            dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
            dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe.loc[(dataframe['ema_50'] > dataframe['ema_200']) & (dataframe['close'] > dataframe['ema_200']) & (dataframe['pair_is_bad'] < 1) & (dataframe['close'] < dataframe['ma_offset_entry']) & (dataframe['volume'] > 0), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if self.config['runmode'].value == 'hyperopt':
            dataframe['ma_offset_exit'] = ta.EMA(dataframe, int(self.base_nb_candles_exit.value)) * self.high_offset.value
        dataframe.loc[(dataframe['close'] > dataframe['ma_offset_exit']) & ((dataframe['open'] < dataframe['open'].shift(1)) | (dataframe['rsi_exit'] < 50) | (dataframe['rsi_exit'] < dataframe['rsi_exit'].shift(1))) & (dataframe['volume'] > 0), 'exit_long'] = 1
        return dataframe