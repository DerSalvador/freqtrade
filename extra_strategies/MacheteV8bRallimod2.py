from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from cachetools import TTLCache
from pandas import DataFrame, Series
import numpy as np
## Indicator libs
import talib.abstract as ta
from finta import TA as fta
import technical.indicators as ftt
from technical.indicators import hull_moving_average
from technical.indicators import PMAX, zema
from technical.indicators import cmf
## FT stuffs
from freqtrade.strategy import IStrategy, merge_informative_pair, stoploss_from_open, IntParameter, DecimalParameter, CategoricalParameter
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.exchange import timeframe_to_minutes
from freqtrade.persistence import Trade
from skopt.space import Dimension
###   @Rallipanos mod
'\nNOTE:\ndocker-compose run --rm freqtrade hyperopt -c user_data/config-backtesting.json --strategy IchimokuHaulingV8a --hyperopt-loss SortinoHyperOptLossDaily --spaces roi entry exit --timerange=1624940400-1630447200 -j 4 -e 1000\n'

class MacheteV8bRallimod2(IStrategy):
    INTERFACE_VERSION = 3
    # Buy hyperspace params:
    entry_params = {'entry_should_use_get_entry_signal_offset_strategy': True, 'entry_should_use_get_entry_signal_bbrsi_strategy': False, 'ewo_high': 2.327, 'rsi_entry': 45, 'base_nb_candles_entry': 14, 'low_offset': 0.965}
    # Sell hyperspace params:
    exit_params = {'cstp_bail_how': 'roc', 'cstp_bail_roc': -0.032, 'cstp_bail_time': 1108, 'cstp_bb_trailing_input': 'bb_lowerband_neutral_inf', 'cstp_threshold': -0.036, 'cstp_trailing_max_stoploss': 0.054, 'cstp_trailing_only_offset_is_reached': 0.09, 'cstp_trailing_stop_profit_devider': 2, 'droi_pullback': True, 'droi_pullback_amount': 0.01, 'droi_pullback_respect_table': False, 'droi_trend_type': 'any', 'base_nb_candles_exit': 24, 'high_offset': 0.991, 'high_offset_2': 0.995}
    # ROI table:
    minimal_roi = {'0': 0.279, '92': 0.109, '245': 0.059, '561': 0.02}
    # Stoploss:
    stoploss = -0.05  #-0.046
    # Trailing stop:
    trailing_stop = False
    #trailing_stop_positive = 0.0247
    #trailing_stop_positive_offset = 0.0248
    #trailing_only_offset_is_reached = True
    use_custom_stoploss = False
    # entry signal
    entry_should_use_get_entry_signal_offset_strategy = CategoricalParameter([True, False], default=entry_params['entry_should_use_get_entry_signal_offset_strategy'], space='entry', optimize=True)
    entry_should_use_get_entry_signal_bbrsi_strategy = CategoricalParameter([True, False], default=entry_params['entry_should_use_get_entry_signal_bbrsi_strategy'], space='entry', optimize=True)
    # Dynamic ROI
    droi_trend_type = CategoricalParameter(['rmi', 'ssl', 'candle', 'any'], default=exit_params['droi_trend_type'], space='exit', optimize=True)
    droi_pullback = CategoricalParameter([True, False], default=exit_params['droi_pullback'], space='exit', optimize=True)
    droi_pullback_amount = DecimalParameter(0.005, 0.02, default=exit_params['droi_pullback_amount'], space='exit')
    droi_pullback_respect_table = CategoricalParameter([True, False], default=exit_params['droi_pullback_respect_table'], space='exit', optimize=True)
    # Custom Stoploss
    cstp_threshold = DecimalParameter(-0.05, 0, default=exit_params['cstp_threshold'], space='exit')
    cstp_bail_how = CategoricalParameter(['roc', 'time', 'any'], default=exit_params['cstp_bail_how'], space='exit', optimize=True)
    cstp_bail_roc = DecimalParameter(-0.05, -0.01, default=exit_params['cstp_bail_roc'], space='exit')
    cstp_bail_time = IntParameter(720, 1440, default=exit_params['cstp_bail_time'], space='exit')
    cstp_trailing_only_offset_is_reached = DecimalParameter(0.01, 0.06, default=exit_params['cstp_trailing_only_offset_is_reached'], space='exit')
    cstp_trailing_stop_profit_devider = IntParameter(2, 4, default=exit_params['cstp_trailing_stop_profit_devider'], space='exit')
    cstp_trailing_max_stoploss = DecimalParameter(0.02, 0.08, default=exit_params['cstp_trailing_max_stoploss'], space='exit')
    cstp_bb_trailing_input = CategoricalParameter(['bb_lowerband_trend', 'bb_lowerband_trend_inf', 'bb_lowerband_neutral', 'bb_lowerband_neutral_inf', 'bb_upperband_neutral_inf'], default=exit_params['cstp_bb_trailing_input'], space='exit', optimize=True)
    fast_ewo = 50
    slow_ewo = 200
    ewo_high = DecimalParameter(2.0, 12.0, default=entry_params['ewo_high'], space='entry', optimize=True)
    rsi_entry = IntParameter(30, 70, default=entry_params['rsi_entry'], space='entry', optimize=True)
    base_nb_candles_entry = IntParameter(5, 80, default=entry_params['base_nb_candles_entry'], space='entry', optimize=True)
    base_nb_candles_exit = IntParameter(5, 80, default=exit_params['base_nb_candles_exit'], space='exit', optimize=True)
    high_offset = DecimalParameter(0.95, 1.1, default=exit_params['high_offset'], space='exit', optimize=True)
    high_offset_2 = DecimalParameter(0.99, 1.5, default=exit_params['high_offset_2'], space='exit', optimize=True)
    # nested hyperopt class

    class HyperOpt:
        # defining as dummy, so that no error is thrown about missing
        # exit indicator space when hyperopting for all spaces

        @staticmethod
        def indicator_space() -> List[Dimension]:
            return []
    custom_trade_info = {}
    custom_current_price_cache: TTLCache = TTLCache(maxsize=100, ttl=300)  # 5 minutes
    # run "populate_indicators" only for new candle
    process_only_new_candles = False
    # Experimental settings (configuration will overide these if set)
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 200  #149
    use_dynamic_roi = True
    timeframe = '5m'
    informative_timeframe = '1h'
    # Optional order type mapping
    order_types = {'entry': 'limit', 'exit': 'limit', 'stoploss': 'market', 'stoploss_on_exchange': False}

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, self.informative_timeframe) for pair in pairs]
        return informative_pairs
    #
    # Processing indicators
    #

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self.custom_trade_info[metadata['pair']] = self.populate_trades(metadata['pair'])
        if not self.dp:
            return dataframe
        dataframe = self.get_entry_signal_indicators(dataframe, metadata)
        informative_tmp = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=self.informative_timeframe)
        informative = self.get_market_condition_indicators(informative_tmp.copy(), metadata)
        informative = self.get_custom_stoploss_indicators(informative, metadata)
        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, self.informative_timeframe, ffill=True)
        dataframe.rename(columns=lambda s: s.replace('_{}'.format(self.informative_timeframe), '_inf'), inplace=True)
        # Slam some indicators into the trade_info dict so we can dynamic roi and custom stoploss in backtest
        if self.dp.runmode.value in ('backtest', 'hyperopt'):
            self.custom_trade_info[metadata['pair']]['roc_inf'] = dataframe[['date', 'roc_inf']].copy().set_index('date')
            self.custom_trade_info[metadata['pair']]['atr_inf'] = dataframe[['date', 'atr_inf']].copy().set_index('date')
            self.custom_trade_info[metadata['pair']]['sroc_inf'] = dataframe[['date', 'sroc_inf']].copy().set_index('date')
            self.custom_trade_info[metadata['pair']]['ssl-dir_inf'] = dataframe[['date', 'ssl-dir_inf']].copy().set_index('date')
            self.custom_trade_info[metadata['pair']]['rmi-up-trend_inf'] = dataframe[['date', 'rmi-up-trend_inf']].copy().set_index('date')
            self.custom_trade_info[metadata['pair']]['candle-up-trend_inf'] = dataframe[['date', 'candle-up-trend_inf']].copy().set_index('date')
            self.custom_trade_info[metadata['pair']]['bb_lowerband_trend_inf'] = dataframe[['date', 'bb_lowerband_trend_inf']].copy().set_index('date')
            self.custom_trade_info[metadata['pair']]['bb_lowerband_trend_inf'] = dataframe[['date', 'bb_lowerband_trend_inf']].copy().set_index('date')
            self.custom_trade_info[metadata['pair']]['bb_lowerband_neutral_inf'] = dataframe[['date', 'bb_lowerband_neutral_inf']].copy().set_index('date')
            self.custom_trade_info[metadata['pair']]['bb_lowerband_neutral_inf'] = dataframe[['date', 'bb_lowerband_neutral_inf']].copy().set_index('date')
            self.custom_trade_info[metadata['pair']]['bb_upperband_neutral_inf'] = dataframe[['date', 'bb_upperband_neutral_inf']].copy().set_index('date')
        return dataframe

    def get_entry_signal_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['sma_9'] = ta.SMA(dataframe, timeperiod=9)
        dataframe['EWO'] = EWO(dataframe, self.fast_ewo, self.slow_ewo)
        for val in self.base_nb_candles_entry.range:
            dataframe[f'ma_entry_{val}'] = ta.EMA(dataframe, timeperiod=val)
        for val in self.base_nb_candles_exit.range:
            dataframe[f'ma_exit_{val}'] = ta.EMA(dataframe, timeperiod=val)
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=4)
        dataframe['rsi_slow'] = ta.RSI(dataframe, timeperiod=20)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['hma_5'] = hull_moving_average(dataframe, 5, 'close')
        dataframe['ema_25'] = ta.EMA(dataframe, timeperiod=25)
        dataframe['ema_60'] = ta.EMA(dataframe, timeperiod=60)
        dataframe['uptrend_5m'] = dataframe['ema_25'] > dataframe['ema_60']
        return dataframe

    def get_market_condition_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        displacement = 30
        ichimoku = ftt.ichimoku(dataframe, conversion_line_period=20, base_line_periods=60, laggin_span=120, displacement=displacement)
        dataframe['chikou_span'] = ichimoku['chikou_span']
        dataframe['tenkan_sen'] = ichimoku['tenkan_sen']
        dataframe['kijun_sen'] = ichimoku['kijun_sen']
        dataframe['senkou_a'] = ichimoku['senkou_span_a']
        dataframe['senkou_b'] = ichimoku['senkou_span_b']
        dataframe['leading_senkou_span_a'] = ichimoku['leading_senkou_span_a']
        dataframe['leading_senkou_span_b'] = ichimoku['leading_senkou_span_b']
        dataframe['cloud_green'] = ichimoku['cloud_green'] * 1
        dataframe['cloud_red'] = ichimoku['cloud_red'] * -1
        ssl = SSLChannels_ATR(dataframe, 10)
        dataframe['sslDown'] = ssl[0]
        dataframe['sslUp'] = ssl[1]
        #dataframe['vfi'] = fta.VFI(dataframe, period=14)
        # Summary indicators
        dataframe['future_green'] = ichimoku['cloud_green'].shift(displacement).fillna(0).astype('int') * 2
        dataframe['chikou_high'] = ((dataframe['chikou_span'] > dataframe['senkou_a']) & (dataframe['chikou_span'] > dataframe['senkou_b'])).shift(displacement).fillna(0).astype('int')
        dataframe['go_long'] = ((dataframe['tenkan_sen'] > dataframe['kijun_sen']) & (dataframe['close'] > dataframe['leading_senkou_span_a']) & (dataframe['close'] > dataframe['leading_senkou_span_b']) & (dataframe['future_green'] > 0) & (dataframe['chikou_high'] > 0)).fillna(0).astype('int') * 3
        dataframe['max'] = dataframe['high'].rolling(3).max()
        dataframe['min'] = dataframe['low'].rolling(6).min()
        dataframe['upper'] = np.where(dataframe['max'] > dataframe['max'].shift(), 1, 0)
        dataframe['lower'] = np.where(dataframe['min'] < dataframe['min'].shift(), 1, 0)
        dataframe['up_trend'] = np.where(dataframe['upper'].rolling(5, min_periods=1).sum() != 0, 1, 0)
        dataframe['dn_trend'] = np.where(dataframe['lower'].rolling(5, min_periods=1).sum() != 0, 1, 0)
        return dataframe

    def get_custom_stoploss_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bollinger_neutral = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=1)
        dataframe['bb_lowerband_neutral'] = bollinger_neutral['lower']
        dataframe['bb_middleband_neutral'] = bollinger_neutral['mid']
        dataframe['bb_upperband_neutral'] = bollinger_neutral['upper']
        bollinger_trend = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband_trend'] = bollinger_trend['lower']
        dataframe['bb_middleband_trend'] = bollinger_trend['mid']
        dataframe['bb_upperband_trend'] = bollinger_trend['upper']
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['roc'] = ta.ROC(dataframe, timeperiod=9)
        dataframe['rmi'] = RMI(dataframe, length=24, mom=5)
        ssldown, sslup = SSLChannels_ATR(dataframe, length=21)
        dataframe['sroc'] = SROC(dataframe, roclen=21, emalen=13, smooth=21)
        dataframe['ssl-dir'] = np.where(sslup > ssldown, 'up', 'down')
        dataframe['rmi-up'] = np.where(dataframe['rmi'] >= dataframe['rmi'].shift(), 1, 0)
        dataframe['rmi-up-trend'] = np.where(dataframe['rmi-up'].rolling(5).sum() >= 3, 1, 0)
        dataframe['candle-up'] = np.where(dataframe['close'] >= dataframe['close'].shift(), 1, 0)
        dataframe['candle-up-trend'] = np.where(dataframe['candle-up'].rolling(5).sum() >= 3, 1, 0)
        return dataframe
    #
    # Processing entry signals
    #

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        #(dataframe['sslUp_inf'] > dataframe['sslDown_inf'])
        dataframe.loc[(self.get_entry_signal_offset_strategy(dataframe) == True) | (self.get_entry_signal_bbrsi_strategy(dataframe) == True), 'enter_long'] = 1
        return dataframe

    def get_entry_signal_offset_strategy(self, dataframe: DataFrame):
        signal = (self.entry_should_use_get_entry_signal_offset_strategy.value == True) & (dataframe['sma_9'] < dataframe[f'ma_entry_{self.base_nb_candles_entry.value}']) & (dataframe['rsi_fast'] < dataframe['rsi_slow']) & (dataframe['rsi_fast'] < 35) & (dataframe['rsi_fast'] > 4) & (dataframe['EWO'] > self.ewo_high.value) & (dataframe['close'] < ta.EMA(dataframe['close'], timeperiod=14) * 0.97) & (dataframe['rsi'] < self.rsi_entry.value) & (dataframe['volume'] > 0)
        return signal

    def get_entry_signal_bbrsi_strategy(self, dataframe: DataFrame):
        signal = (self.entry_should_use_get_entry_signal_bbrsi_strategy.value == True) & (dataframe['sslUp_inf'] > dataframe['sslDown_inf']) & (dataframe['uptrend_5m'] == 0) & (dataframe['rsi'] < 40) & (dataframe['rsi_fast'] < dataframe['rsi_slow']) & (dataframe['close'].shift(1) < dataframe['bb_lowerband'] * 1) & (dataframe['EWO'] > self.ewo_high.value) & (dataframe['volume'] > 0)
        return signal
    #
    # Processing exit signals
    #

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        #(dataframe['rsi']>150)&
        #&
        # NOTE: I keep the volume checks of feels like it has not much benifit when trading leverage tokens, maybe im wrong!?
        #(dataframe['vfi'] < 0.0) &
        #(dataframe['volume'] > 0)
        dataframe.loc[qtpylib.crossed_above(dataframe['sslDown_inf'], dataframe['sslUp_inf']) & (qtpylib.crossed_below(dataframe['tenkan_sen_inf'], dataframe['kijun_sen_inf']) | qtpylib.crossed_below(dataframe['close_inf'], dataframe['kijun_sen_inf']) | (dataframe['close'] > dataframe['sma_9']) & (dataframe['close'] > dataframe[f'ma_exit_{self.base_nb_candles_exit.value}'] * self.high_offset_2.value) & (dataframe['volume'] > 0) & (dataframe['rsi_fast'] > dataframe['rsi_slow'])), 'exit_long'] = 1
        return dataframe
    #
    # Custom Stoploss
    #

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> float:
        trade_dur = int((current_time.timestamp() - trade.open_date_utc.timestamp()) // 60)
        if self.config['runmode'].value in ('live', 'dry_run'):
            dataframe, last_updated = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            sroc = dataframe['sroc_inf'].iat[-1]
            bb_trailing = dataframe[self.cstp_bb_trailing_input.value].iat[-1]
        else:
            # If in backtest or hyperopt, get the indicator values out of the trades dict (Thanks @JoeSchr!)
            sroc = self.custom_trade_info[trade.pair]['sroc_inf'].loc[current_time]['sroc_inf']
            bb_trailing = self.custom_trade_info[trade.pair][self.cstp_bb_trailing_input.value].loc[current_time][self.cstp_bb_trailing_input.value]
        if current_profit < self.cstp_threshold.value:
            if self.cstp_bail_how.value == 'roc' or self.cstp_bail_how.value == 'any':
                # Dynamic bailout based on rate of change
                if sroc / 100 <= self.cstp_bail_roc.value:
                    return 0.001
            if self.cstp_bail_how.value == 'time' or self.cstp_bail_how.value == 'any':
                # Dynamic bailout based on time
                if trade_dur > self.cstp_bail_time.value:
                    return 0.001
        if current_profit < self.cstp_trailing_only_offset_is_reached.value:
            if current_rate <= bb_trailing:
                return 0.001
            else:
                return -1
        desired_stoploss = current_profit / self.cstp_trailing_stop_profit_devider.value
        return max(min(desired_stoploss, self.cstp_trailing_max_stoploss.value), 0.025)
    #
    # Dynamic ROI
    #

    def min_roi_reached_dynamic(self, trade: Trade, current_profit: float, current_time: datetime, trade_dur: int) -> Tuple[Optional[int], Optional[float]]:
        minimal_roi = self.minimal_roi
        _, table_roi = self.min_roi_reached_entry(trade_dur)
        # see if we have the data we need to do this, otherwise fall back to the standard table
        if self.custom_trade_info and trade and (trade.pair in self.custom_trade_info):
            if self.config['runmode'].value in ('live', 'dry_run'):
                dataframe, last_updated = self.dp.get_analyzed_dataframe(pair=trade.pair, timeframe=self.timeframe)
                rmi_trend = dataframe['rmi-up-trend_inf'].iat[-1]
                candle_trend = dataframe['candle-up-trend_inf'].iat[-1]
                ssl_dir = dataframe['ssl-dir_inf'].iat[-1]
            else:
                # If in backtest or hyperopt, get the indicator values out of the trades dict (Thanks @JoeSchr!)
                rmi_trend = self.custom_trade_info[trade.pair]['rmi-up-trend_inf'].loc[current_time]['rmi-up-trend_inf']
                candle_trend = self.custom_trade_info[trade.pair]['candle-up-trend_inf'].loc[current_time]['candle-up-trend_inf']
                ssl_dir = self.custom_trade_info[trade.pair]['ssl-dir_inf'].loc[current_time]['ssl-dir_inf']
            min_roi = table_roi
            max_profit = trade.calc_profit_ratio(trade.max_rate)
            pullback_value = max_profit - self.droi_pullback_amount.value
            in_trend = False
            if self.droi_trend_type.value == 'rmi' or self.droi_trend_type.value == 'any':
                if rmi_trend == 1:
                    in_trend = True
            if self.droi_trend_type.value == 'ssl' or self.droi_trend_type.value == 'any':
                if ssl_dir == 'up':
                    in_trend = True
            if self.droi_trend_type.value == 'candle' or self.droi_trend_type.value == 'any':
                if candle_trend == 1:
                    in_trend = True
            # Force the ROI value high if in trend
            if in_trend == True:
                min_roi = 100
                # If pullback is enabled, allow to exit if a pullback from peak has happened regardless of trend
                if self.droi_pullback.value == True and current_profit < pullback_value:
                    if self.droi_pullback_respect_table.value == True:
                        min_roi = table_roi
                    else:
                        min_roi = current_profit / 1.5
        else:
            min_roi = table_roi
        return (trade_dur, min_roi)
    # Change here to allow loading of the dynamic_roi settings

    def min_roi_reached(self, trade: Trade, current_profit: float, current_time: datetime) -> bool:
        trade_dur = int((current_time.timestamp() - trade.open_date_utc.timestamp()) // 120)
        if self.use_dynamic_roi:
            _, roi = self.min_roi_reached_dynamic(trade, current_profit, current_time, trade_dur)
        else:
            _, roi = self.min_roi_reached_entry(trade_dur)
        if roi is None:
            return False
        else:
            return current_profit > roi
    # Get the current price from the exchange (or local cache)

    def get_current_price(self, pair: str, refresh: bool) -> float:
        if not refresh:
            rate = self.custom_current_price_cache.get(pair)
            # Check if cache has been invalidated
            if rate:
                return rate
        ask_strategy = self.config.get('ask_strategy', {})
        if ask_strategy.get('use_order_book', False):
            ob = self.dp.orderbook(pair, 1)
            rate = ob[f"{ask_strategy['price_side']}s"][0][0]
        else:
            ticker = self.dp.ticker(pair)
            rate = ticker['last']
        self.custom_current_price_cache[pair] = rate
        return rate
    #
    # Custom trade info
    #

    def populate_trades(self, pair: str) -> dict:
        # Initialize the trades dict if it doesn't exist, persist it otherwise
        if not pair in self.custom_trade_info:
            self.custom_trade_info[pair] = {}
        # init the temp dicts and set the trade stuff to false
        trade_data = {}
        trade_data['active_trade'] = False
        # active trade stuff only works in live and dry, not backtest
        if self.config['runmode'].value in ('live', 'dry_run'):
            # find out if we have an open trade for this pair
            active_trade = Trade.get_trades([Trade.pair == pair, Trade.is_open.is_(True)]).all()
            # if so, get some information
            if active_trade:
                # get current price and update the min/max rate
                current_rate = self.get_current_price(pair, True)
                active_trade[0].adjust_min_max_rates(current_rate, current_rate)
        return trade_data
#
# Custom indicators
#

def RMI(dataframe, *, length=20, mom=5):
    """
    Source: https://github.com/freqtrade/technical/blob/master/technical/indicators/indicators.py#L912
    """
    df = dataframe.copy()
    df['maxup'] = (df['close'] - df['close'].shift(mom)).clip(lower=0)
    df['maxdown'] = (df['close'].shift(mom) - df['close']).clip(lower=0)
    df.fillna(0, inplace=True)
    df['emaInc'] = ta.EMA(df, price='maxup', timeperiod=length)
    df['emaDec'] = ta.EMA(df, price='maxdown', timeperiod=length)
    df['RMI'] = np.where(df['emaDec'] == 0, 0, 100 - 100 / (1 + df['emaInc'] / df['emaDec']))
    return df['RMI']

def SSLChannels_ATR(dataframe, length=7):
    """
    SSL Channels with ATR: https://www.tradingview.com/script/SKHqWzql-SSL-ATR-channel/
    Credit to @JimmyNixx for python
    """
    df = dataframe.copy()
    df['ATR'] = ta.ATR(df, timeperiod=14)
    df['smaHigh'] = df['high'].rolling(length).mean() + df['ATR']
    df['smaLow'] = df['low'].rolling(length).mean() - df['ATR']
    df['hlv'] = np.where(df['close'] > df['smaHigh'], 1, np.where(df['close'] < df['smaLow'], -1, np.NAN))
    df['hlv'] = df['hlv'].ffill()
    df['sslDown'] = np.where(df['hlv'] < 0, df['smaHigh'], df['smaLow'])
    df['sslUp'] = np.where(df['hlv'] < 0, df['smaLow'], df['smaHigh'])
    return (df['sslDown'], df['sslUp'])

def SROC(dataframe, roclen=21, emalen=13, smooth=21):
    df = dataframe.copy()
    roc = ta.ROC(df, timeperiod=roclen)
    ema = ta.EMA(df, timeperiod=emalen)
    sroc = ta.ROC(ema, timeperiod=smooth)
    return sroc

def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df['low'] * 100
    return emadif