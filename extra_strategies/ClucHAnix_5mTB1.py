import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import merge_informative_pair, DecimalParameter, stoploss_from_open, RealParameter
from pandas import DataFrame, Series
from datetime import datetime
from typing import Dict, List
from datetime import datetime, timezone
from freqtrade.persistence import Trade
import logging
logger = logging.getLogger(__name__)

def bollinger_bands(stock_price, window_size, num_of_std):
    rolling_mean = stock_price.rolling(window=window_size).mean()
    rolling_std = stock_price.rolling(window=window_size).std()
    lower_band = rolling_mean - rolling_std * num_of_std
    return (np.nan_to_num(rolling_mean), np.nan_to_num(lower_band))

def ha_typical_price(bars):
    res = (bars['ha_high'] + bars['ha_low'] + bars['ha_close']) / 3.0
    return Series(index=bars.index, data=res)

class ClucHAnix_5m1(IStrategy):
    INTERFACE_VERSION = 3
    '\n    PASTE OUTPUT FROM HYPEROPT HERE\n    Can be overridden for specific sub-strategies (stake currencies) at the bottom.\n    '
    #hypered params
    entry_params = {'bbdelta_close': 0.01889, 'bbdelta_tail': 0.72235, 'close_bblower': 0.0127, 'closedelta_close': 0.00916, 'rocr_1h': 0.79492}
    # Sell hyperspace params:
    # custom stoploss params, come from BB_RPB_TSL
    # exit signal params
    exit_params = {'pHSL': -0.1, 'pPF_1': 0.011, 'pPF_2': 0.064, 'pSL_1': 0.011, 'pSL_2': 0.062, 'exit_fisher': 0.39075, 'exit_bbmiddle_close': 0.99754}
    # ROI table:
    minimal_roi = {'0': 100}
    # Stoploss:
    stoploss = -0.99  # use custom stoploss
    # Trailing stop:
    trailing_stop = False
    trailing_stop_positive = 0.001
    trailing_stop_positive_offset = 0.012
    trailing_only_offset_is_reached = False
    '\n    END HYPEROPT\n    '
    timeframe = '5m'
    # Make sure these match or are not overridden in config
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    # Custom stoploss
    use_custom_stoploss = True
    process_only_new_candles = True
    startup_candle_count = 168
    order_types = {'entry': 'market', 'exit': 'market', 'emergencyexit': 'market', 'forceentry': 'market', 'forceexit': 'market', 'stoploss': 'market', 'stoploss_on_exchange': False, 'stoploss_on_exchange_interval': 60, 'stoploss_on_exchange_limit_ratio': 0.99}
    # entry params
    rocr_1h = RealParameter(0.5, 1.0, default=0.54904, space='entry', optimize=True)
    bbdelta_close = RealParameter(0.0005, 0.02, default=0.01965, space='entry', optimize=True)
    closedelta_close = RealParameter(0.0005, 0.02, default=0.00556, space='entry', optimize=True)
    bbdelta_tail = RealParameter(0.7, 1.0, default=0.95089, space='entry', optimize=True)
    close_bblower = RealParameter(0.0005, 0.02, default=0.00799, space='entry', optimize=True)
    # exit params
    exit_fisher = RealParameter(0.1, 0.5, default=0.38414, space='exit', optimize=True)
    exit_bbmiddle_close = RealParameter(0.97, 1.1, default=1.07634, space='exit', optimize=True)
    # hard stoploss profit
    pHSL = DecimalParameter(-0.5, -0.04, default=-0.08, decimals=3, space='exit', load=True)
    # profit threshold 1, trigger point, SL_1 is used
    pPF_1 = DecimalParameter(0.008, 0.02, default=0.016, decimals=3, space='exit', load=True)
    pSL_1 = DecimalParameter(0.008, 0.02, default=0.011, decimals=3, space='exit', load=True)
    # profit threshold 2, SL_2 is used
    pPF_2 = DecimalParameter(0.04, 0.1, default=0.08, decimals=3, space='exit', load=True)
    pSL_2 = DecimalParameter(0.02, 0.07, default=0.04, decimals=3, space='exit', load=True)

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, '1h') for pair in pairs]
        return informative_pairs
    # come from BB_RPB_TSL

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
        # Only for hyperopt invalid return
        if sl_profit >= current_profit:
            return -0.99
        return stoploss_from_open(sl_profit, current_profit)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # # Heikin Ashi Candles
        heikinashi = qtpylib.heikinashi(dataframe)
        dataframe['ha_open'] = heikinashi['open']
        dataframe['ha_close'] = heikinashi['close']
        dataframe['ha_high'] = heikinashi['high']
        dataframe['ha_low'] = heikinashi['low']
        # Set Up Bollinger Bands
        mid, lower = bollinger_bands(ha_typical_price(dataframe), window_size=40, num_of_std=2)
        dataframe['lower'] = lower
        dataframe['mid'] = mid
        dataframe['bbdelta'] = (mid - dataframe['lower']).abs()
        dataframe['closedelta'] = (dataframe['ha_close'] - dataframe['ha_close'].shift()).abs()
        dataframe['tail'] = (dataframe['ha_close'] - dataframe['ha_low']).abs()
        dataframe['bb_lowerband'] = dataframe['lower']
        dataframe['bb_middleband'] = dataframe['mid']
        dataframe['ema_fast'] = ta.EMA(dataframe['ha_close'], timeperiod=3)
        dataframe['ema_slow'] = ta.EMA(dataframe['ha_close'], timeperiod=50)
        dataframe['volume_mean_slow'] = dataframe['volume'].rolling(window=30).mean()
        dataframe['rocr'] = ta.ROCR(dataframe['ha_close'], timeperiod=28)
        rsi = ta.RSI(dataframe)
        dataframe['rsi'] = rsi
        rsi = 0.1 * (rsi - 50)
        dataframe['fisher'] = (np.exp(2 * rsi) - 1) / (np.exp(2 * rsi) + 1)
        inf_tf = '1h'
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=inf_tf)
        inf_heikinashi = qtpylib.heikinashi(informative)
        informative['ha_close'] = inf_heikinashi['close']
        informative['rocr'] = ta.ROCR(informative['ha_close'], timeperiod=168)
        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, inf_tf, ffill=True)
        #NOTE: dynamic offset
        dataframe['perc'] = (dataframe['high'] - dataframe['low']) / dataframe['low'] * 100
        dataframe['avg3_perc'] = ta.EMA(dataframe['perc'], 3)
        dataframe['norm_perc'] = (dataframe['perc'] - dataframe['perc'].rolling(50).min()) / (dataframe['perc'].rolling(50).max() - dataframe['perc'].rolling(50).min())
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe['rocr_1h'].gt(self.rocr_1h.value) & (dataframe['lower'].shift().gt(0) & dataframe['bbdelta'].gt(dataframe['ha_close'] * self.bbdelta_close.value) & dataframe['closedelta'].gt(dataframe['ha_close'] * self.closedelta_close.value) & dataframe['tail'].lt(dataframe['bbdelta'] * self.bbdelta_tail.value) & dataframe['ha_close'].lt(dataframe['lower'].shift()) & dataframe['ha_close'].le(dataframe['ha_close'].shift()) | (dataframe['ha_close'] < dataframe['ema_slow']) & (dataframe['ha_close'] < self.close_bblower.value * dataframe['bb_lowerband'])), 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(dataframe['fisher'] > self.exit_fisher.value) & dataframe['ha_high'].le(dataframe['ha_high'].shift(1)) & dataframe['ha_high'].shift(1).le(dataframe['ha_high'].shift(2)) & dataframe['ha_close'].le(dataframe['ha_close'].shift(1)) & (dataframe['ema_fast'] > dataframe['ha_close']) & (dataframe['ha_close'] * self.exit_bbmiddle_close.value > dataframe['bb_middleband']) & (dataframe['volume'] > 0), 'exit_long'] = 1
        return dataframe

class ClucHAnix_5mTB1(ClucHAnix_5m1):
    process_only_new_candles = True
    custom_info_trail_entry = dict()
    # Trailing entry parameters
    trailing_entry_order_enabled = True
    trailing_expire_seconds = 300
    # If the current candle goes above min_uptrend_trailing_profit % before trailing_expire_seconds_uptrend seconds, entry the coin
    trailing_entry_uptrend_enabled = True
    trailing_expire_seconds_uptrend = 90
    min_uptrend_trailing_profit = 0.02
    debug_mode = True
    trailing_entry_max_stop = 0.01  # stop trailing entry if current_price > starting_price * (1+trailing_entry_max_stop)
    trailing_entry_max_entry = 0.002  # entry if price between uplimit (=min of serie (current_price * (1 + trailing_entry_offset())) and (start_price * 1+trailing_entry_max_entry))
    init_trailing_dict = {'trailing_entry_order_started': False, 'trailing_entry_order_uplimit': 0, 'start_trailing_price': 0, 'enter_tag': None, 'start_trailing_time': None, 'offset': 0, 'allow_trailing': False}

    def trailing_entry(self, pair, reinit=False):
        # returns trailing entry info for pair (init if necessary)
        if not pair in self.custom_info_trail_entry:
            self.custom_info_trail_entry[pair] = dict()
        if reinit or not 'trailing_entry' in self.custom_info_trail_entry[pair]:
            self.custom_info_trail_entry[pair]['trailing_entry'] = self.init_trailing_dict.copy()
        return self.custom_info_trail_entry[pair]['trailing_entry']

    def trailing_entry_info(self, pair: str, current_price: float):
        # current_time live, dry run
        current_time = datetime.now(timezone.utc)
        if not self.debug_mode:
            return
        trailing_entry = self.trailing_entry(pair)
        duration = 0
        try:
            duration = current_time - trailing_entry['start_trailing_time']
        except TypeError:
            duration = 0
        finally:
            logger.info(f"pair: {pair} : start: {trailing_entry['start_trailing_price']:.4f}, duration: {duration}, current: {current_price:.4f}, uplimit: {trailing_entry['trailing_entry_order_uplimit']:.4f}, profit: {self.current_trailing_profit_ratio(pair, current_price) * 100:.2f}%, offset: {trailing_entry['offset']}")

    def current_trailing_profit_ratio(self, pair: str, current_price: float) -> float:
        trailing_entry = self.trailing_entry(pair)
        if trailing_entry['trailing_entry_order_started']:
            return (trailing_entry['start_trailing_price'] - current_price) / trailing_entry['start_trailing_price']
        else:
            return 0

    def trailing_entry_offset(self, dataframe, pair: str, current_price: float):
        # return rebound limit before a entry in % of initial price, function of current price
        # return None to stop trailing entry (will start again at next entry signal)
        # return 'forceentry' to force immediate entry
        # (example with 0.5%. initial price : 100 (uplimit is 100.5), 2nd price : 99 (no entry, uplimit updated to 99.5), 3price 98 (no entry uplimit updated to 98.5), 4th price 99 -> BUY
        current_trailing_profit_ratio = self.current_trailing_profit_ratio(pair, current_price)
        last_candle = dataframe.iloc[-1]
        adapt = abs(last_candle['perc_norm'])
        default_offset = 0.003 * (1 + adapt)  #NOTE: default_offset 0.003 <--> 0.006
        #default_offset = adapt*0.01
        trailing_entry = self.trailing_entry(pair)
        if not trailing_entry['trailing_entry_order_started']:
            return default_offset
        # example with duration and indicators
        # dry run, live only
        last_candle = dataframe.iloc[-1]
        current_time = datetime.now(timezone.utc)
        trailing_duration = current_time - trailing_entry['start_trailing_time']
        if trailing_duration.total_seconds() > self.trailing_expire_seconds:
            if current_trailing_profit_ratio > 0 and last_candle['enter_long'] == 1:
                # more than 1h, price under first signal, entry signal still active -> entry
                return 'forceentry'
            else:
                # wait for next signal
                return None
        elif self.trailing_entry_uptrend_enabled and trailing_duration.total_seconds() < self.trailing_expire_seconds_uptrend and (current_trailing_profit_ratio < -1 * self.min_uptrend_trailing_profit):
            # less than 90s and price is rising, entry
            return 'forceentry'
        if current_trailing_profit_ratio < 0:
            # current price is higher than initial price
            return default_offset
        trailing_entry_offset = {0.06: 0.02, 0.03: 0.01, 0: default_offset}
        for key in trailing_entry_offset:
            if current_trailing_profit_ratio > key:
                return trailing_entry_offset[key]
        return default_offset
    # end of trailing entry parameters
    # -----------------------------------------------------

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        self.trailing_entry(metadata['pair'])
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float, time_in_force: str, **kwargs) -> bool:
        val = super().confirm_trade_entry(pair, order_type, amount, rate, time_in_force, **kwargs)
        if val:
            if self.trailing_entry_order_enabled and self.config['runmode'].value in ('live', 'dry_run'):
                val = False
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                if len(dataframe) >= 1:
                    last_candle = dataframe.iloc[-1].squeeze()
                    current_price = rate
                    trailing_entry = self.trailing_entry(pair)
                    trailing_entry_offset = self.trailing_entry_offset(dataframe, pair, current_price)
                    if trailing_entry['allow_trailing']:
                        if not trailing_entry['trailing_entry_order_started'] and last_candle['enter_long'] == 1:
                            # start trailing entry
                            trailing_entry['trailing_entry_order_started'] = True
                            trailing_entry['trailing_entry_order_uplimit'] = last_candle['close']
                            trailing_entry['start_trailing_price'] = last_candle['close']
                            trailing_entry['enter_tag'] = last_candle['enter_tag']
                            trailing_entry['start_trailing_time'] = datetime.now(timezone.utc)
                            trailing_entry['offset'] = 0
                            self.trailing_entry_info(pair, current_price)
                            logger.info(f"start trailing entry for {pair} at {last_candle['close']}")
                        elif trailing_entry['trailing_entry_order_started']:
                            if trailing_entry_offset == 'forceentry':
                                # entry in custom conditions
                                val = True
                                ratio = '%.2f' % (self.current_trailing_profit_ratio(pair, current_price) * 100)
                                self.trailing_entry_info(pair, current_price)
                                logger.info(f'price OK for {pair} ({ratio} %, {current_price}), order may not be triggered if all slots are full')
                            elif trailing_entry_offset is None:
                                # stop trailing entry custom conditions
                                self.trailing_entry(pair, reinit=True)
                                logger.info(f'STOP trailing entry for {pair} because "trailing entry offset" returned None')
                            elif current_price < trailing_entry['trailing_entry_order_uplimit']:
                                # update uplimit
                                old_uplimit = trailing_entry['trailing_entry_order_uplimit']
                                self.custom_info_trail_entry[pair]['trailing_entry']['trailing_entry_order_uplimit'] = min(current_price * (1 + trailing_entry_offset), self.custom_info_trail_entry[pair]['trailing_entry']['trailing_entry_order_uplimit'])
                                self.custom_info_trail_entry[pair]['trailing_entry']['offset'] = trailing_entry_offset
                                self.trailing_entry_info(pair, current_price)
                                logger.info(f"update trailing entry for {pair} at {old_uplimit} -> {self.custom_info_trail_entry[pair]['trailing_entry']['trailing_entry_order_uplimit']}")
                            elif current_price < trailing_entry['start_trailing_price'] * (1 + self.trailing_entry_max_entry):
                                # entry ! current price > uplimit && lower thant starting price
                                val = True
                                ratio = '%.2f' % (self.current_trailing_profit_ratio(pair, current_price) * 100)
                                self.trailing_entry_info(pair, current_price)
                                logger.info(f"current price ({current_price}) > uplimit ({trailing_entry['trailing_entry_order_uplimit']}) and lower than starting price price ({trailing_entry['start_trailing_price'] * (1 + self.trailing_entry_max_entry)}). OK for {pair} ({ratio} %), order may not be triggered if all slots are full")
                            elif current_price > trailing_entry['start_trailing_price'] * (1 + self.trailing_entry_max_stop):
                                # stop trailing entry because price is too high
                                self.trailing_entry(pair, reinit=True)
                                self.trailing_entry_info(pair, current_price)
                                logger.info(f'STOP trailing entry for {pair} because of the price is higher than starting price * {1 + self.trailing_entry_max_stop}')
                            else:
                                # uplimit > current_price > max_price, continue trailing and wait for the price to go down
                                self.trailing_entry_info(pair, current_price)
                                logger.info(f'price too high for {pair} !')
                    else:
                        logger.info(f'Wait for next entry signal for {pair}')
                if val == True:
                    self.trailing_entry_info(pair, rate)
                    self.trailing_entry(pair, reinit=True)
                    logger.info(f'STOP trailing entry for {pair} because I entry it')
        return val

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        if self.trailing_entry_order_enabled and self.config['runmode'].value in ('live', 'dry_run'):
            last_candle = dataframe.iloc[-1].squeeze()
            trailing_entry = self.trailing_entry(metadata['pair'])
            if last_candle['enter_long'] == 1:
                if not trailing_entry['trailing_entry_order_started']:
                    open_trades = Trade.get_trades([Trade.pair == metadata['pair'], Trade.is_open.is_(True)]).all()
                    if not open_trades:
                        logger.info(f"Set 'allow_trailing' to True for {metadata['pair']} to start trailing!!!")
                        # self.custom_info_trail_entry[metadata['pair']]['trailing_entry']['allow_trailing'] = True
                        trailing_entry['allow_trailing'] = True
                        initial_entry_tag = last_candle['enter_tag'] if 'enter_tag' in last_candle else 'entry signal'
                        dataframe.loc[:, 'enter_tag'] = f"{initial_entry_tag} (start trail price {last_candle['close']})"
            elif trailing_entry['trailing_entry_order_started'] == True:
                logger.info(f"Continue trailing for {metadata['pair']}. Manually trigger entry signal!!")
                dataframe.loc[:, 'enter_long'] = 1
                dataframe.loc[:, 'enter_tag'] = trailing_entry['enter_tag']
        # dataframe['entry'] = 1
        return dataframe