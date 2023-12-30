# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame, Series
# --------------------------------
import logging
import pandas as pd
import numpy as np
import datetime
from freqtrade.persistence import Trade
logger = logging.getLogger(__name__)

class YourStrat(IStrategy):
    INTERFACE_VERSION = 3
    # replace this by your strategy
    pass

class TrailingBuyStrat(YourStrat):
    # This class is designed to heritate from yours and starts trailing entry with your entry signals
    # Trailing entry starts at any entry signal
    # Trailing entry stops  with BUY if : price decreases and rises again more than trailing_entry_offset
    # Trailing entry stops with NO BUY : current price is > intial price * (1 +  trailing_entry_max) OR custom_exit tag
    # IT IS NOT COMPATIBLE WITH BACKTEST/HYPEROPT
    #
    # if process_only_new_candles = True, then you need to use 1m timeframe (and normal strat timeframe as informative)
    # if process_only_new_candles = False, it will use ticker data and you won't need to change anything
    trailing_entry_order_enabled = True
    trailing_entry_offset = 0.005  # rebound limit before a entry in % of initial price
    # (example with 0.5%. initial price : 100 (uplimit is 100.5), 2nd price : 99 (no entry, uplimit updated to 99.5), 3price 98 (no entry uplimit updated to 98.5), 4th price 99 -> BUY
    trailing_entry_max = 0.1  # stop trailing entry if current_price > starting_price * (1+trailing_entry_max)
    process_only_new_candles = False
    custom_info = dict()
    init_trailing_dict = {'trailing_entry_order_started': False, 'trailing_entry_order_uplimit': 0, 'start_trailing_price': 0, 'enter_tag': None}

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs):
        tag = super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)
        if tag:
            self.custom_info[pair]['trailing_entry'] = self.init_trailing_dict
            logger.info(f'STOP trailing entry for {pair} because of {tag}')
        return tag

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        if not metadata['pair'] in self.custom_info:
            self.custom_info[metadata['pair']] = dict()
        if not 'trailing_entry' in self.custom_info[metadata['pair']]:
            self.custom_info[metadata['pair']]['trailing_entry'] = self.init_trailing_dict
        return dataframe

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float, rate: float, time_in_force: str, exit_reason: str, **kwargs) -> bool:
        val = super().confirm_trade_exit(pair, trade, order_type, amount, rate, time_in_force, exit_reason, **kwargs)
        self.custom_info[pair]['trailing_entry'] = self.init_trailing_dict
        return val

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        def get_local_min(x):
            win = dataframe.loc[:, 'barssince_last_entry'].iloc[x.shape[0] - 1].astype('int')
            win = max(win, 0)
            return pd.Series(x).rolling(window=win).min().iloc[-1]
        dataframe = super().populate_entry_trend(dataframe, metadata)
        dataframe = dataframe.rename(columns={'entry': 'pre_entry'})
        if self.trailing_entry_order_enabled and self.config['runmode'].value in ('live', 'dry_run'):  # trailing live dry ticker, 1m
            last_candle = dataframe.iloc[-1].squeeze()
            if not self.process_only_new_candles:
                current_price = self.get_current_price(metadata['pair'])
            else:
                current_price = last_candle['close']
            dataframe['enter_long'] = 0
            if not self.custom_info[metadata['pair']]['trailing_entry']['trailing_entry_order_started'] and last_candle['pre_entry'] == 1:
                self.custom_info[metadata['pair']]['trailing_entry'] = {'trailing_entry_order_started': True, 'trailing_entry_order_uplimit': last_candle['close'], 'start_trailing_price': last_candle['close'], 'enter_tag': last_candle['enter_tag'] if 'enter_tag' in last_candle else 'entry signal'}
                logger.info(f"start trailing entry for {metadata['pair']} at {last_candle['close']}")
            elif self.custom_info[metadata['pair']]['trailing_entry']['trailing_entry_order_started']:
                if current_price < self.custom_info[metadata['pair']]['trailing_entry']['trailing_entry_order_uplimit']:
                    # update uplimit
                    self.custom_info[metadata['pair']]['trailing_entry']['trailing_entry_order_uplimit'] = min(current_price * (1 + self.trailing_entry_offset), self.custom_info[metadata['pair']]['trailing_entry']['trailing_entry_order_uplimit'])
                    logger.info(f"update trailing entry for {metadata['pair']} at {self.custom_info[metadata['pair']]['trailing_entry']['trailing_entry_order_uplimit']}")
                elif current_price < self.custom_info[metadata['pair']]['trailing_entry']['start_trailing_price']:
                    # entry ! current price > uplimit but lower thant starting price
                    dataframe.iloc[-1, dataframe.columns.get_loc('enter_long')] = 1
                    ratio = '%.2f' % ((1 - current_price / self.custom_info[metadata['pair']]['trailing_entry']['start_trailing_price']) * 100)
                    if 'enter_tag' in dataframe.columns:
                        dataframe.iloc[-1, dataframe.columns.get_loc('enter_tag')] = f"{self.custom_info[metadata['pair']]['trailing_entry']['enter_tag']} ({ratio} %)"
                    # stop trailing when entry signal ! prevent from entrying much higher price when slot is free
                    self.custom_info[metadata['pair']]['trailing_entry'] = self.init_trailing_dict
                    logger.info(f"STOP trailing entry for {metadata['pair']} because I entry it {ratio}")
                elif current_price > self.custom_info[metadata['pair']]['trailing_entry']['start_trailing_price'] * (1 + self.trailing_entry_max):
                    self.custom_info[metadata['pair']]['trailing_entry'] = self.init_trailing_dict
                    logger.info(f"STOP trailing entry for {metadata['pair']} because of the price is higher than starting prix * {1 + self.trailing_entry_max}")
                else:
                    logger.info(f"price to high for {metadata['pair']} at {current_price} vs {self.custom_info[metadata['pair']]['trailing_entry']['trailing_entry_order_uplimit']}")
        elif self.trailing_entry_order_enabled:
            # FOR BACKTEST
            # NOT WORKING
            dataframe.loc[(dataframe['pre_entry'] == 1) & (dataframe['pre_entry'].shift() == 0), 'pre_entry_switch'] = 1
            dataframe['pre_entry_switch'] = dataframe['pre_entry_switch'].fillna(0)
            dataframe['barssince_last_entry'] = dataframe['pre_entry_switch'].groupby(dataframe['pre_entry_switch'].cumsum()).cumcount()
            # Create integer positions of each row
            idx_positions = np.arange(len(dataframe))
            # "shift" those integer positions by the amount in shift col
            shifted_idx_positions = idx_positions - dataframe['barssince_last_entry']
            # get the label based index from our DatetimeIndex
            shifted_loc_index = dataframe.index[shifted_idx_positions]
            # Retrieve the "shifted" values and assign them as a new column
            dataframe['close_5m_last_entry'] = dataframe.loc[shifted_loc_index, 'close_5m'].values
            dataframe.loc[:, 'close_lower'] = dataframe.loc[:, 'close'].expanding().apply(get_local_min)
            dataframe['close_lower'] = np.where(dataframe['close_lower'].isna() == True, dataframe['close'], dataframe['close_lower'])
            dataframe['close_lower_offset'] = dataframe['close_lower'] * (1 + self.trailing_entry_offset)
            dataframe['trailing_entry_order_uplimit'] = np.where(dataframe['barssince_last_entry'] < 20, pd.DataFrame([dataframe['close_5m_last_entry'], dataframe['close_lower_offset']]).min(), np.nan)  # must entry within last 20 candles after signal
            dataframe.loc[(dataframe['barssince_last_entry'] < 20) & (dataframe['close'] > dataframe['trailing_entry_order_uplimit']), 'trailing_entry'] = 1
            dataframe['trailing_entry_count'] = dataframe['trailing_entry'].rolling(20).sum()
            dataframe.log[(dataframe['trailing_entry'] == 1) & (dataframe['trailing_entry_count'] == 1), 'enter_long'] = 1
        else:  # No entry trailing
            dataframe.loc[dataframe['pre_entry'] == 1, 'enter_long'] = 1
        return dataframe

    def get_current_price(self, pair: str) -> float:
        ticker = self.dp.ticker(pair)
        current_price = ticker['last']
        return current_price