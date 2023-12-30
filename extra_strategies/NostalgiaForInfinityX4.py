import copy
import logging
import pathlib
import rapidjson
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
import pandas as pd
import pandas_ta as pta
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import merge_informative_pair
from freqtrade.strategy import DecimalParameter, CategoricalParameter
from pandas import DataFrame, Series
from functools import reduce
from freqtrade.persistence import Trade, LocalTrade
from datetime import datetime, timedelta
import time
from typing import Optional
import warnings

log = logging.getLogger(__name__)
# log.setLevel(logging.DEBUG)
warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)

#############################################################################################################
##                NostalgiaForInfinityX4 by iterativ                                                       ##
##           https://github.com/iterativv/NostalgiaForInfinity                                             ##
##                                                                                                         ##
##    Strategy for Freqtrade https://github.com/freqtrade/freqtrade                                        ##
##                                                                                                         ##
#############################################################################################################
##               GENERAL RECOMMENDATIONS                                                                   ##
##                                                                                                         ##
##   For optimal performance, suggested to use between 4 and 6 open trades, with unlimited stake.          ##
##   A pairlist with 40 to 80 pairs. Volume pairlist works well.                                           ##
##   Prefer stable coin (USDT, BUSDT etc) pairs, instead of BTC or ETH pairs.                              ##
##   Highly recommended to blacklist leveraged tokens (*BULL, *BEAR, *UP, *DOWN etc).                      ##
##   Ensure that you don't override any variables in you config.json. Especially                           ##
##   the timeframe (must be 5m).                                                                           ##
##     use_exit_signal must set to true (or not set at all).                                               ##
##     exit_profit_only must set to false (or not set at all).                                             ##
##     ignore_roi_if_entry_signal must set to true (or not set at all).                                    ##
##                                                                                                         ##
#############################################################################################################
##               DONATIONS                                                                                 ##
##                                                                                                         ##
##   BTC: bc1qvflsvddkmxh7eqhc4jyu5z5k6xcw3ay8jl49sk                                                       ##
##   ETH (ERC20): 0x83D3cFb8001BDC5d2211cBeBB8cB3461E5f7Ec91                                               ##
##   BEP20/BSC (USDT, ETH, BNB, ...): 0x86A0B21a20b39d16424B7c8003E4A7e12d78ABEe                           ##
##   TRC20/TRON (USDT, TRON, ...): TTAa9MX6zMLXNgWMhg7tkNormVHWCoq8Xk                                      ##
##                                                                                                         ##
##               REFERRAL LINKS                                                                            ##
##                                                                                                         ##
##  Binance: https://accounts.binance.com/en/register?ref=C68K26A9 (20% discount on trading fees)          ##
##  Kucoin: https://www.kucoin.com/r/af/QBSSS5J2 (20% lifetime discount on trading fees)                   ##
##  Gate.io: https://www.gate.io/signup/UAARUlhf/20pct?ref_type=103 (20% discount on trading fees)         ##
##  OKX: https://www.okx.com/join/11749725931 (20% discount on trading fees)                               ##
##  MEXC: https://promote.mexc.com/a/nfi  (10% discount on trading fees)                                   ##
##  ByBit: https://partner.bybit.com/b/nfi                                                                 ##
##  Bitget: https://bonus.bitget.com/nfi (lifetime 20% rebate all & 10% discount on spot fees)             ##
##  HTX: https://www.htx.com/invite/en-us/1f?invite_code=ubpt2223                                          ##
##         (Welcome Bonus worth 241 USDT upon completion of a deposit and trade)                           ##
##  Bitvavo: https://account.bitvavo.com/create?a=D22103A4BC (no fees for the first € 1000)                ##
#############################################################################################################


class NostalgiaForInfinityX4(IStrategy):
  INTERFACE_VERSION = 3

  def version(self) -> str:
    return "v14.0.709"

  # ROI table:
  minimal_roi = {
    "0": 100.0,
  }

  stoploss = -0.99

  # Trailing stoploss (not used)
  trailing_stop = False
  trailing_only_offset_is_reached = True
  trailing_stop_positive = 0.01
  trailing_stop_positive_offset = 0.03

  use_custom_stoploss = False

  # Optimal timeframe for the strategy.
  timeframe = "5m"
  info_timeframes = ["15m", "1h", "4h", "1d"]

  # BTC informatives
  btc_info_timeframes = ["5m", "15m", "1h", "4h", "1d"]

  # Backtest Age Filter emulation
  has_bt_agefilter = False
  bt_min_age_days = 3

  # Exchange Downtime protection
  has_downtime_protection = False

  # Do you want to use the hold feature? (with hold-trades.json)
  hold_support_enabled = True

  # Run "populate_indicators()" only for new candle.
  process_only_new_candles = True

  # These values can be overridden in the "ask_strategy" section in the config.
  use_exit_signal = True
  exit_profit_only = False
  ignore_roi_if_entry_signal = True

  # Number of candles the strategy requires before producing valid signals
  startup_candle_count: int = 800

  # Normal mode tags
  normal_mode_tags = ["force_entry", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
  # Pump mode tags
  pump_mode_tags = ["21", "22", "23"]
  # Quick mode tags
  quick_mode_tags = ["41", "42", "43", "44", "45"]
  # Long rebuy mode tags
  long_rebuy_mode_tags = ["61"]
  # Long mode tags
  long_mode_tags = ["81", "82"]
  # Long rapid mode tags
  long_rapid_mode_tags = ["101", "102", "103", "104", "105"]

  normal_mode_name = "normal"
  pump_mode_name = "pump"
  quick_mode_name = "quick"
  long_rebuy_mode_name = "long_rebuy"
  long_mode_name = "long"
  long_rapid_mode_name = "long_rapid"

  # Shorting

  # Short normal mode tags
  short_normal_mode_tags = ["500"]

  short_normal_mode_name = "short_normal"

  is_futures_mode = False
  futures_mode_leverage = 3.0
  futures_mode_leverage_rebuy_mode = 3.0

  # Stop thesholds. 0: Doom Bull, 1: Doom Bear, 2: u_e Bull, 3: u_e Bear, 4: u_e mins Bull, 5: u_e mins Bear.
  # 6: u_e ema % Bull, 7: u_e ema % Bear, 8: u_e RSI diff Bull, 9: u_e RSI diff Bear.
  # 10: enable Doom Bull, 11: enable Doom Bear, 12: enable u_e Bull, 13: enable u_e Bear.
  stop_thresholds = [-0.2, -0.2, -0.025, -0.025, 720, 720, 0.016, 0.016, 24.0, 24.0, False, False, True, True]
  # Based on the the first entry (regardless of rebuys)
  stop_threshold = 0.60
  stop_threshold_futures = 0.50
  stop_threshold_futures_rapid = 0.50
  stop_threshold_spot_rapid = 0.60
  stop_threshold_futures_rebuy = 0.9
  stop_threshold_spot_rebuy = 0.9

  # Rebuy mode minimum number of free slots
  rebuy_mode_min_free_slots = 2

  # Position adjust feature
  position_adjustment_enable = True

  # Grinding feature
  grinding_enable = True
  grinding_mode = 2
  stake_grinding_mode_multiplier = 1.0
  stake_grinding_mode_multiplier_alt_1 = 1.0
  stake_grinding_mode_multiplier_alt_2 = 1.0
  # Grinding stop thresholds
  grinding_stop_init = -0.12
  grinding_stop_grinds = -0.16
  # Grinding take profit threshold
  grinding_profit_threshold = 0.012
  # Grinding stakes
  grinding_stakes = [0.25, 0.25, 0.25, 0.25, 0.25]
  grinding_stakes_alt_1 = [0.5, 0.5, 0.5]
  grinding_stakes_alt_2 = [0.75, 0.75]
  # Current total profit
  grinding_thresholds = [-0.04, -0.08, -0.1, -0.12, -0.14]
  grinding_thresholds_alt_1 = [-0.06, -0.12, -0.18]
  grinding_thresholds_alt_2 = [-0.08, -0.18]

  # Grinding mode 1
  grinding_mode_1_stop_grinds = -0.16
  grinding_mode_1_profit_threshold = 0.018
  grinding_mode_1_thresholds = [-0.0, -0.06]
  grinding_mode_1_stakes = [0.2, 0.2, 0.2, 0.2, 0.2]
  grinding_mode_1_sub_thresholds = [-0.06, -0.065, -0.07, -0.075, -0.08]
  grinding_mode_1_stakes_alt_1 = [0.25, 0.25, 0.25, 0.25]
  grinding_mode_1_sub_thresholds_alt_1 = [-0.06, -0.065, -0.07, -0.085]
  grinding_mode_1_stakes_alt_2 = [0.3, 0.3, 0.3, 0.3]
  grinding_mode_1_sub_thresholds_alt_2 = [-0.06, -0.07, -0.09, -0.1]
  grinding_mode_1_stakes_alt_3 = [0.35, 0.35, 0.35]
  grinding_mode_1_sub_thresholds_alt_3 = [-0.06, -0.075, -0.1]
  grinding_mode_1_stakes_alt_4 = [0.45, 0.45, 0.45]
  grinding_mode_1_sub_thresholds_alt_4 = [-0.06, -0.08, -0.11]

  # Grinding mode 2
  grinding_mode_2_stop_init_grinds_spot = -0.20
  grinding_mode_2_stop_grinds_spot = -0.16
  grinding_mode_2_stop_init_grinds_futures = -0.90
  grinding_mode_2_stop_grinds_futures = -0.26
  grinding_mode_2_profit_threshold_spot = 0.018
  grinding_mode_2_profit_threshold_futures = 0.018
  grinding_mode_2_stakes_spot = [
    [0.2, 0.2, 0.2, 0.2, 0.2],
    [0.25, 0.25, 0.25, 0.25, 0.25],
    [0.3, 0.3, 0.3, 0.3],
    [0.35, 0.35, 0.35, 0.35],
    [0.4, 0.4, 0.4],
    [0.45, 0.45, 0.45],
    [0.5, 0.5, 0.5],
    [0.75, 0.75],
  ]
  grinding_mode_2_stakes_futures = [
    [0.2, 0.2, 0.2, 0.2, 0.2],
    [0.25, 0.25, 0.25, 0.25, 0.25],
    [0.3, 0.3, 0.3, 0.3],
    [0.35, 0.35, 0.35, 0.35],
    [0.4, 0.4, 0.4],
    [0.45, 0.45, 0.45],
    [0.5, 0.5, 0.5],
    [0.75, 0.75],
  ]
  grinding_mode_2_sub_thresholds_spot = [
    [-0.0, -0.04, -0.05, -0.06, -0.07, -0.08],
    [-0.0, -0.04, -0.05, -0.06, -0.07, -0.08],
    [-0.0, -0.05, -0.06, -0.07, -0.08],
    [-0.0, -0.05, -0.07, -0.09, -0.1],
    [-0.0, -0.06, -0.08, -0.1],
    [-0.0, -0.06, -0.08, -0.1],
    [-0.0, -0.06, -0.08, -0.1],
    [-0.0, -0.06, -0.09],
  ]
  grinding_mode_2_sub_thresholds_futures = [
    [-0.0, -0.04, -0.05, -0.06, -0.07, -0.08],
    [-0.0, -0.04, -0.05, -0.06, -0.07, -0.08],
    [-0.0, -0.05, -0.06, -0.07, -0.08],
    [-0.0, -0.05, -0.07, -0.09, -0.1],
    [-0.0, -0.06, -0.08, -0.1],
    [-0.0, -0.06, -0.08, -0.1],
    [-0.0, -0.06, -0.08, -0.1],
    [-0.0, -0.06, -0.09],
  ]

  # Rebuy mode
  rebuy_mode_stake_multiplier = 0.2
  rebuy_mode_stake_multiplier_alt = 0.3
  rebuy_mode_max = 3
  rebuy_mode_stakes_spot = [1.0, 2.0, 4.0]
  rebuy_mode_stakes_futures = [1.0, 2.0, 4.0]
  rebuy_mode_thresholds_spot = [-0.06, -0.08, -0.10]
  rebuy_mode_thresholds_futures = [-0.03, -0.06, -0.08]

  # Profit max thresholds
  profit_max_thresholds = [0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.05, 0.05]

  # Max allowed buy "slippage", how high to buy on the candle
  max_slippage = 0.012

  # BTC/ETH stakes
  btc_stakes = ["BTC", "ETH"]

  #############################################################
  # Buy side configuration

  entry_long_params = {
    # Enable/Disable conditions
    # -------------------------------------------------------
    "buy_condition_1_enable": True,
    "buy_condition_2_enable": True,
    "buy_condition_3_enable": True,
    "buy_condition_4_enable": True,
    "buy_condition_5_enable": True,
    "buy_condition_6_enable": True,
    "buy_condition_7_enable": True,
    "buy_condition_8_enable": True,
    "buy_condition_9_enable": True,
    "buy_condition_21_enable": True,
    "buy_condition_22_enable": True,
    "buy_condition_23_enable": True,
    "buy_condition_41_enable": True,
    "buy_condition_42_enable": True,
    "buy_condition_43_enable": True,
    "buy_condition_44_enable": True,
    "buy_condition_45_enable": False,
    "buy_condition_61_enable": True,
    # "buy_condition_81_enable": True,
    # "buy_condition_82_enable": True,
    "buy_condition_101_enable": True,
    "buy_condition_102_enable": True,
    "buy_condition_103_enable": True,
    "buy_condition_104_enable": True,
    "buy_condition_105_enable": True,
  }

  entry_short_params = {
    # Enable/Disable conditions
    # -------------------------------------------------------
    "entry_condition_500_enable": False,
  }

  buy_protection_params = {}

  #############################################################
  # Buy hyperspace params:
  buy_params = {
    "entry_45_close_max_12": 0.76,
    "entry_45_close_max_24": 0.78,
    "entry_45_close_max_48": 0.80,
    "entry_45_cti_20_1d_max": 0.92,
    "entry_45_cti_20_1h_max": 0.92,
    "entry_45_cti_20_4h_max": 0.92,
    "entry_45_cti_20_max": -0.54,
    "entry_45_high_max_24_1h": 0.82,
    "entry_45_high_max_24_4h": 0.86,
    "entry_45_high_max_6_1d": 0.90,
    "entry_45_hl_pct_change_12_1h": 0.86,
    "entry_45_hl_pct_change_24_1h": 0.90,
    "entry_45_hl_pct_change_48_1h": 1.36,
    "entry_45_hl_pct_change_6_1h": 0.56,
    "entry_45_rsi_14_1d_max": 80.0,
    "entry_45_rsi_14_1h_max": 80.0,
    "entry_45_rsi_14_4h_max": 80.0,
    "entry_45_rsi_14_max": 46.0,
    "entry_45_rsi_14_min": 26.0,
    "entry_45_rsi_3_15m_min": 2.0,
    "entry_45_rsi_3_1d_min": 2.0,
    "entry_45_rsi_3_1h_min": 2.0,
    "entry_45_rsi_3_4h_min": 2.0,
    "entry_45_rsi_3_max": 46.0,
    "entry_45_rsi_3_min": 2.0,
    "entry_45_sma_offset": 0.960,
    "entry_45_res_level_1d_enabled": False,
    "entry_45_res_level_1h_enabled": False,
    "entry_45_res_level_4h_enabled": False,
    "entry_45_sup_level_1d_enabled": False,
    "entry_45_sup_level_1h_enabled": True,
    "entry_45_sup_level_4h_enabled": True,
  }

  entry_45_close_max_12 = DecimalParameter(00.50, 0.95, default=0.75, decimals=2, space="buy", optimize=True)
  entry_45_close_max_24 = DecimalParameter(00.50, 0.95, default=0.65, decimals=2, space="buy", optimize=True)
  entry_45_close_max_48 = DecimalParameter(00.50, 0.95, default=0.60, decimals=2, space="buy", optimize=True)
  entry_45_high_max_24_1h = DecimalParameter(00.40, 0.95, default=0.55, decimals=2, space="buy", optimize=True)
  entry_45_high_max_24_4h = DecimalParameter(00.40, 0.95, default=0.5, decimals=2, space="buy", optimize=True)
  entry_45_high_max_6_1d = DecimalParameter(00.30, 0.95, default=0.45, decimals=2, space="buy", optimize=True)
  entry_45_hl_pct_change_6_1h = DecimalParameter(00.30, 0.90, default=0.5, decimals=2, space="buy", optimize=True)
  entry_45_hl_pct_change_12_1h = DecimalParameter(00.40, 1.00, default=0.75, decimals=2, space="buy", optimize=True)
  entry_45_hl_pct_change_24_1h = DecimalParameter(00.50, 1.20, default=0.90, decimals=2, space="buy", optimize=True)
  entry_45_hl_pct_change_48_1h = DecimalParameter(00.60, 1.60, default=1.00, decimals=2, space="buy", optimize=True)
  entry_45_sup_level_1h_enabled = CategoricalParameter([True, False], default=False, space="buy", optimize=True)
  entry_45_res_level_1h_enabled = CategoricalParameter([True, False], default=False, space="buy", optimize=True)
  entry_45_sup_level_4h_enabled = CategoricalParameter([True, False], default=False, space="buy", optimize=True)
  entry_45_res_level_4h_enabled = CategoricalParameter([True, False], default=False, space="buy", optimize=True)
  entry_45_sup_level_1d_enabled = CategoricalParameter([True, False], default=False, space="buy", optimize=True)
  entry_45_res_level_1d_enabled = CategoricalParameter([True, False], default=False, space="buy", optimize=True)
  entry_45_rsi_3_min = DecimalParameter(00.0, 30.0, default=6.0, decimals=0, space="buy", optimize=True)
  entry_45_rsi_3_max = DecimalParameter(30.0, 60.0, default=46.0, decimals=0, space="buy", optimize=True)
  entry_45_rsi_3_15m_min = DecimalParameter(00.0, 30.0, default=16.0, decimals=0, space="buy", optimize=True)
  entry_45_rsi_3_1h_min = DecimalParameter(00.0, 30.0, default=16.0, decimals=0, space="buy", optimize=True)
  entry_45_rsi_3_4h_min = DecimalParameter(00.0, 30.0, default=16.0, decimals=0, space="buy", optimize=True)
  entry_45_rsi_3_1d_min = DecimalParameter(00.0, 30.0, default=6.0, decimals=0, space="buy", optimize=True)
  entry_45_cti_20_1h_max = DecimalParameter(0.0, 0.99, default=0.9, decimals=2, space="buy", optimize=True)
  entry_45_rsi_14_1h_max = DecimalParameter(50.0, 90.0, default=80.0, decimals=0, space="buy", optimize=True)
  entry_45_cti_20_4h_max = DecimalParameter(0.0, 0.99, default=0.9, decimals=2, space="buy", optimize=True)
  entry_45_rsi_14_4h_max = DecimalParameter(50.0, 90.0, default=80.0, decimals=0, space="buy", optimize=True)
  entry_45_cti_20_1d_max = DecimalParameter(0.0, 0.99, default=0.9, decimals=2, space="buy", optimize=True)
  entry_45_rsi_14_1d_max = DecimalParameter(50.0, 90.0, default=80.0, decimals=0, space="buy", optimize=True)
  entry_45_rsi_14_min = DecimalParameter(10.0, 40.0, default=30.0, decimals=0, space="buy", optimize=True)
  entry_45_rsi_14_max = DecimalParameter(20.0, 60.0, default=46.0, decimals=0, space="buy", optimize=True)
  entry_45_cti_20_max = DecimalParameter(-0.99, -0.50, default=-0.70, decimals=2, space="buy", optimize=True)
  entry_45_sma_offset = DecimalParameter(0.940, 0.984, default=0.972, decimals=3, space="buy", optimize=True)
  #############################################################
  # CACHES

  hold_trades_cache = None
  target_profit_cache = None
  #############################################################

  def __init__(self, config: dict) -> None:
    if "ccxt_config" not in config["exchange"]:
      config["exchange"]["ccxt_config"] = {}
    if "ccxt_async_config" not in config["exchange"]:
      config["exchange"]["ccxt_async_config"] = {}

    options = {
      "brokerId": None,
      "broker": {"spot": None, "margin": None, "future": None, "delivery": None},
      "partner": {
        "spot": {"id": None, "key": None},
        "future": {"id": None, "key": None},
        "id": None,
        "key": None,
      },
    }

    config["exchange"]["ccxt_config"]["options"] = options
    config["exchange"]["ccxt_async_config"]["options"] = options
    super().__init__(config)
    if ("exit_profit_only" in self.config and self.config["exit_profit_only"]) or (
      "sell_profit_only" in self.config and self.config["sell_profit_only"]
    ):
      self.exit_profit_only = True
    if "stop_threshold" in self.config:
      self.stop_threshold = self.config["stop_threshold"]
    if "profit_max_thresholds" in self.config:
      self.profit_max_thresholds = self.config["profit_max_thresholds"]
    if "grinding_enable" in self.config:
      self.grinding_enable = self.config["grinding_enable"]
    if "grinding_mode" in self.config:
      self.grinding_mode = self.config["grinding_mode"]
    if "grinding_stakes" in self.config:
      self.grinding_stakes = self.config["grinding_stakes"]
    if "grinding_thresholds" in self.config:
      self.grinding_thresholds = self.config["grinding_thresholds"]
    if "grinding_stakes_alt_1" in self.config:
      self.grinding_stakes_alt_1 = self.config["grinding_stakes_alt_1"]
    if "grinding_thresholds_alt_1" in self.config:
      self.grinding_thresholds_alt_1 = self.config["grinding_thresholds_alt_1"]
    if "grinding_stakes_alt_2" in self.config:
      self.grinding_stakes_alt_2 = self.config["grinding_stakes_alt_2"]
    if "grinding_thresholds_alt_2" in self.config:
      self.grinding_thresholds_alt_2 = self.config["grinding_thresholds_alt_2"]
    if "grinding_stop_init" in self.config:
      self.grinding_stop_init = self.config["grinding_stop_init"]
    if "grinding_stop_grinds" in self.config:
      self.grinding_stop_grinds = self.config["grinding_stop_grinds"]
    if "grinding_profit_threshold" in self.config:
      self.grinding_profit_threshold = self.config["grinding_profit_threshold"]
    if "max_slippage" in self.config:
      self.max_slippage = self.config["max_slippage"]
    if self.target_profit_cache is None:
      bot_name = ""
      if "bot_name" in self.config:
        bot_name = self.config["bot_name"] + "-"
      self.target_profit_cache = Cache(
        self.config["user_data_dir"]
        / (
          "nfix4-profit_max-"
          + bot_name
          + self.config["exchange"]["name"]
          + "-"
          + self.config["stake_currency"]
          + ("-(backtest)" if (self.config["runmode"].value == "backtest") else "")
          + ".json"
        )
      )

    # OKX, Kraken provides a lower number of candle data per API call
    if self.config["exchange"]["name"] in ["okx", "okex"]:
      self.startup_candle_count = 480
    elif self.config["exchange"]["name"] in ["kraken"]:
      self.startup_candle_count = 710
    elif self.config["exchange"]["name"] in ["bybit"]:
      self.startup_candle_count = 199

    if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
      self.is_futures_mode = True

    # If the cached data hasn't changed, it's a no-op
    self.target_profit_cache.save()

  def get_ticker_indicator(self):
    return int(self.timeframe[:-1])

  def exit_normal(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.exit_signals(
      self.normal_mode_name,
      profit_current_stake_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.exit_main(
        self.normal_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.exit_r(
        self.normal_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.exit_long_dec(
        self.normal_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.exit_stoploss(
        self.normal_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.normal_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.normal_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.normal_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_current_stake_ratio > (previous_profit + 0.005)) and (
        previous_sell_reason not in [f"exit_{self.normal_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.normal_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.normal_mode_name}_stoploss_doom",
        f"exit_{self.normal_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.normal_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.normal_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_current_stake_ratio >= self.profit_max_thresholds[0]:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
          mark_signal = f"exit_profit_{self.normal_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.normal_mode_name}_max",
      f"exit_{self.normal_mode_name}_stoploss_doom",
      f"exit_{self.normal_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  def exit_pump(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.exit_signals(
      self.pump_mode_name,
      profit_current_stake_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.exit_main(
        self.pump_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.exit_r(
        self.pump_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.exit_long_dec(
        self.normal_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.exit_stoploss(
        self.pump_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.pump_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.pump_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.pump_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_current_stake_ratio > (previous_profit + 0.005)) and (
        previous_sell_reason not in [f"exit_{self.pump_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.pump_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.pump_mode_name}_stoploss_doom",
        f"exit_{self.pump_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.pump_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.pump_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_current_stake_ratio >= self.profit_max_thresholds[2]:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
          mark_signal = f"exit_profit_{self.pump_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.pump_mode_name}_max",
      f"exit_{self.pump_mode_name}_stoploss_doom",
      f"exit_{self.pump_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  def exit_quick(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.exit_signals(
      self.quick_mode_name,
      profit_current_stake_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.exit_main(
        self.quick_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.exit_r(
        self.quick_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.exit_long_dec(
        self.normal_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.exit_stoploss(
        self.quick_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Extra sell logic
    if not sell:
      if (0.09 >= profit_current_stake_ratio > 0.02) and (last_candle["rsi_14"] > 78.0):
        sell, signal_name = True, f"exit_{self.quick_mode_name}_q_1"

      if (0.09 >= profit_current_stake_ratio > 0.02) and (last_candle["cti_20"] > 0.95):
        sell, signal_name = True, f"exit_{self.quick_mode_name}_q_2"

      if (0.09 >= profit_current_stake_ratio > 0.02) and (last_candle["r_14"] >= -0.1):
        sell, signal_name = True, f"exit_{self.quick_mode_name}_q_3"

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.quick_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.quick_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.quick_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_current_stake_ratio > (previous_profit + 0.005)) and (
        previous_sell_reason not in [f"exit_{self.quick_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.quick_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.quick_mode_name}_stoploss_doom",
        f"exit_{self.quick_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.quick_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.quick_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_current_stake_ratio >= self.profit_max_thresholds[4]:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
          mark_signal = f"exit_profit_{self.quick_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.quick_mode_name}_max",
      f"exit_{self.quick_mode_name}_stoploss_doom",
      f"exit_{self.quick_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  def long_exit_rebuy(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.exit_signals(
      self.long_rebuy_mode_name,
      profit_current_stake_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.exit_main(
        self.long_rebuy_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.exit_r(
        self.long_rebuy_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.exit_long_dec(
        self.normal_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      if profit_stake < -(
        filled_entries[0].cost
        * (self.stop_threshold_futures_rebuy if self.is_futures_mode else self.stop_threshold_spot_rebuy)
        / (trade.leverage if self.is_futures_mode else 1.0)
      ):
        sell, signal_name = True, f"exit_{self.long_rebuy_mode_name}_stoploss_doom"

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.long_rebuy_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.long_rebuy_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.long_rebuy_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_current_stake_ratio > (previous_profit + 0.005)) and (
        previous_sell_reason not in [f"exit_{self.long_rebuy_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rebuy_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.long_rebuy_mode_name}_stoploss_doom",
        f"exit_{self.long_rebuy_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rebuy_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rebuy_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_current_stake_ratio >= self.profit_max_thresholds[6]:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
          mark_signal = f"exit_profit_{self.long_rebuy_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    if signal_name not in [f"exit_profit_{self.long_rebuy_mode_name}_max"]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  def exit_long(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.exit_signals(
      self.long_mode_name,
      profit_current_stake_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.exit_main(
        self.long_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.exit_r(
        self.long_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.exit_stoploss(
        self.long_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.long_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.long_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.long_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_current_stake_ratio > (previous_profit + 0.005)) and (
        previous_sell_reason not in [f"exit_{self.long_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.long_mode_name}_stoploss_doom",
        f"exit_{self.long_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_current_stake_ratio >= self.profit_max_thresholds[8]:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
          mark_signal = f"exit_profit_{self.long_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.long_mode_name}_max",
      f"exit_{self.long_mode_name}_stoploss_doom",
      f"exit_{self.long_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  def long_exit_rapid(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.exit_signals(
      self.long_rapid_mode_name,
      profit_current_stake_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.exit_main(
        self.long_rapid_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.exit_r(
        self.long_rapid_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.exit_long_dec(
        self.normal_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.exit_stoploss(
        self.long_rapid_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Extra sell logic
    if not sell:
      if (0.09 >= profit_current_stake_ratio > 0.01) and (last_candle["rsi_14"] > 78.0):
        sell, signal_name = True, f"exit_{self.long_rapid_mode_name}_rpd_1"

      if (0.09 >= profit_current_stake_ratio > 0.01) and (last_candle["cti_20"] > 0.95):
        sell, signal_name = True, f"exit_{self.long_rapid_mode_name}_rpd_2"

      if (0.09 >= profit_current_stake_ratio > 0.01) and (last_candle["r_14"] >= -0.1):
        sell, signal_name = True, f"exit_{self.long_rapid_mode_name}_rpd_3"

      # Stoplosses
      if profit_stake < -(
        filled_entries[0].cost
        * (self.stop_threshold_futures_rapid if self.is_futures_mode else self.stop_threshold_spot_rapid)
        / (trade.leverage if self.is_futures_mode else 1.0)
      ):
        sell, signal_name = True, f"exit_{self.long_rapid_mode_name}_stoploss_doom"

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.long_rapid_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.long_rapid_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.long_rapid_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_current_stake_ratio > (previous_profit + 0.005)) and (
        previous_sell_reason not in [f"exit_{self.long_rapid_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rapid_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.long_rapid_mode_name}_stoploss_doom",
        f"exit_{self.long_rapid_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rapid_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rapid_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_current_stake_ratio >= 0.01:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
          mark_signal = f"exit_profit_{self.long_rapid_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    if signal_name not in [f"exit_profit_{self.long_rapid_mode_name}_max"]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  def mark_profit_target(
    self,
    mode_name: str,
    pair: str,
    sell: bool,
    signal_name: str,
    trade: Trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    last_candle,
    previous_candle_1,
  ) -> tuple:
    if sell and (signal_name is not None):
      return pair, signal_name

    return None, None

  def exit_profit_target(
    self,
    mode_name: str,
    pair: str,
    trade: Trade,
    current_time: datetime,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    last_candle,
    previous_candle_1,
    previous_rate,
    previous_profit,
    previous_sell_reason,
    previous_time_profit_reached,
    enter_tags,
  ) -> tuple:
    if previous_sell_reason in [f"exit_{mode_name}_stoploss_doom", f"exit_{mode_name}_stoploss"]:
      if profit_ratio > 0.04:
        # profit is over the threshold, don't exit
        self._remove_profit_target(pair)
        return False, None
      if profit_ratio < -0.18:
        if profit_ratio < (previous_profit - 0.04):
          return True, previous_sell_reason
      elif profit_ratio < -0.1:
        if profit_ratio < (previous_profit - 0.04):
          return True, previous_sell_reason
      elif profit_ratio < -0.04:
        if profit_ratio < (previous_profit - 0.04):
          return True, previous_sell_reason
      else:
        if profit_ratio < (previous_profit - 0.04):
          return True, previous_sell_reason
    elif previous_sell_reason in [f"exit_{mode_name}_stoploss_u_e"]:
      if profit_current_stake_ratio > 0.04:
        # profit is over the threshold, don't exit
        self._remove_profit_target(pair)
        return False, None
      if profit_ratio < (previous_profit - (0.20 if trade.realized_profit == 0.0 else 0.26)):
        return True, previous_sell_reason
    elif previous_sell_reason in [f"exit_profit_{mode_name}_max"]:
      if profit_current_stake_ratio < -0.08:
        # profit is under the threshold, cancel it
        self._remove_profit_target(pair)
        return False, None
      if self.is_futures_mode:
        if 0.01 <= profit_current_stake_ratio < 0.02:
          if profit_current_stake_ratio < (previous_profit * 0.5):
            return True, previous_sell_reason
        elif 0.02 <= profit_current_stake_ratio < 0.03:
          if profit_current_stake_ratio < (previous_profit * 0.6):
            return True, previous_sell_reason
        elif 0.03 <= profit_current_stake_ratio < 0.04:
          if profit_current_stake_ratio < (previous_profit * 0.7):
            return True, previous_sell_reason
        elif 0.04 <= profit_current_stake_ratio < 0.08:
          if profit_current_stake_ratio < (previous_profit * 0.8):
            return True, previous_sell_reason
        elif 0.08 <= profit_current_stake_ratio < 0.16:
          if profit_current_stake_ratio < (previous_profit * 0.9):
            return True, previous_sell_reason
        elif 0.16 <= profit_current_stake_ratio:
          if profit_current_stake_ratio < (previous_profit * 0.95):
            return True, previous_sell_reason
      else:
        if 0.01 <= profit_current_stake_ratio < 0.03:
          if profit_current_stake_ratio < (previous_profit * 0.6):
            return True, previous_sell_reason
        elif 0.03 <= profit_current_stake_ratio < 0.08:
          if profit_current_stake_ratio < (previous_profit * 0.65):
            return True, previous_sell_reason
        elif 0.08 <= profit_current_stake_ratio < 0.16:
          if profit_current_stake_ratio < (previous_profit * 0.7):
            return True, previous_sell_reason
        elif 0.16 <= profit_current_stake_ratio:
          if profit_current_stake_ratio < (previous_profit * 0.75):
            return True, previous_sell_reason
    else:
      return False, None

    return False, None

  def exit_signals(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    # Sell signal 1
    if (
      (last_candle["rsi_14"] > 79.0)
      and (last_candle["close"] > last_candle["bb20_2_upp"])
      and (previous_candle_1["close"] > previous_candle_1["bb20_2_upp"])
      and (previous_candle_2["close"] > previous_candle_2["bb20_2_upp"])
      and (previous_candle_3["close"] > previous_candle_3["bb20_2_upp"])
      and (previous_candle_4["close"] > previous_candle_4["bb20_2_upp"])
    ):
      if last_candle["close"] > last_candle["ema_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_1_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_1_2_1"

    # Sell signal 2
    elif (
      (last_candle["rsi_14"] > 80.0)
      and (last_candle["close"] > last_candle["bb20_2_upp"])
      and (previous_candle_1["close"] > previous_candle_1["bb20_2_upp"])
      and (previous_candle_2["close"] > previous_candle_2["bb20_2_upp"])
    ):
      if last_candle["close"] > last_candle["ema_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_2_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_2_2_1"

    # Sell signal 3
    elif last_candle["rsi_14"] > 85.0:
      if last_candle["close"] > last_candle["ema_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_3_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_3_2_1"

    # Sell signal 4
    elif (last_candle["rsi_14"] > 80.0) and (last_candle["rsi_14_1h"] > 78.0):
      if last_candle["close"] > last_candle["ema_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_4_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_4_2_1"

    # Sell signal 6
    elif (
      (last_candle["close"] < last_candle["ema_200"])
      and (last_candle["close"] > last_candle["ema_50"])
      and (last_candle["rsi_14"] > 79.0)
    ):
      if current_profit > 0.01:
        return True, f"exit_{mode_name}_6_1"

    # Sell signal 7
    elif (last_candle["rsi_14_1h"] > 79.0) and (last_candle["crossed_below_ema_12_26"]):
      if last_candle["close"] > last_candle["ema_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_7_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_7_2_1"

    # Sell signal 8
    elif last_candle["close"] > last_candle["bb20_2_upp_1h"] * 1.08:
      if last_candle["close"] > last_candle["ema_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_8_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_8_2_1"

    return False, None

  def exit_main(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    if last_candle["close"] > last_candle["sma_200_1h"]:
      if 0.01 > current_profit >= 0.001:
        if last_candle["rsi_14"] < 10.0:
          return True, f"exit_{mode_name}_o_0"
      elif 0.02 > current_profit >= 0.01:
        if last_candle["rsi_14"] < 28.0:
          return True, f"exit_{mode_name}_o_1"
      elif 0.03 > current_profit >= 0.02:
        if last_candle["rsi_14"] < 30.0:
          return True, f"exit_{mode_name}_o_2"
      elif 0.04 > current_profit >= 0.03:
        if last_candle["rsi_14"] < 32.0:
          return True, f"exit_{mode_name}_o_3"
      elif 0.05 > current_profit >= 0.04:
        if last_candle["rsi_14"] < 34.0:
          return True, f"exit_{mode_name}_o_4"
      elif 0.06 > current_profit >= 0.05:
        if last_candle["rsi_14"] < 36.0:
          return True, f"exit_{mode_name}_o_5"
      elif 0.07 > current_profit >= 0.06:
        if last_candle["rsi_14"] < 38.0:
          return True, f"exit_{mode_name}_o_6"
      elif 0.08 > current_profit >= 0.07:
        if last_candle["rsi_14"] < 40.0:
          return True, f"exit_{mode_name}_o_7"
      elif 0.09 > current_profit >= 0.08:
        if last_candle["rsi_14"] < 42.0:
          return True, f"exit_{mode_name}_o_8"
      elif 0.1 > current_profit >= 0.09:
        if last_candle["rsi_14"] < 44.0:
          return True, f"exit_{mode_name}_o_9"
      elif 0.12 > current_profit >= 0.1:
        if last_candle["rsi_14"] < 46.0:
          return True, f"exit_{mode_name}_o_10"
      elif 0.2 > current_profit >= 0.12:
        if last_candle["rsi_14"] < 44.0:
          return True, f"exit_{mode_name}_o_11"
      elif current_profit >= 0.2:
        if last_candle["rsi_14"] < 42.0:
          return True, f"exit_{mode_name}_o_12"
    elif last_candle["close"] < last_candle["sma_200_1h"]:
      if 0.01 > current_profit >= 0.001:
        if last_candle["rsi_14"] < 12.0:
          return True, f"exit_{mode_name}_u_0"
      elif 0.02 > current_profit >= 0.01:
        if last_candle["rsi_14"] < 30.0:
          return True, f"exit_{mode_name}_u_1"
      elif 0.03 > current_profit >= 0.02:
        if last_candle["rsi_14"] < 32.0:
          return True, f"exit_{mode_name}_u_2"
      elif 0.04 > current_profit >= 0.03:
        if last_candle["rsi_14"] < 34.0:
          return True, f"exit_{mode_name}_u_3"
      elif 0.05 > current_profit >= 0.04:
        if last_candle["rsi_14"] < 36.0:
          return True, f"exit_{mode_name}_u_4"
      elif 0.06 > current_profit >= 0.05:
        if last_candle["rsi_14"] < 38.0:
          return True, f"exit_{mode_name}_u_5"
      elif 0.07 > current_profit >= 0.06:
        if last_candle["rsi_14"] < 40.0:
          return True, f"exit_{mode_name}_u_6"
      elif 0.08 > current_profit >= 0.07:
        if last_candle["rsi_14"] < 42.0:
          return True, f"exit_{mode_name}_u_7"
      elif 0.09 > current_profit >= 0.08:
        if last_candle["rsi_14"] < 44.0:
          return True, f"exit_{mode_name}_u_8"
      elif 0.1 > current_profit >= 0.09:
        if last_candle["rsi_14"] < 46.0:
          return True, f"exit_{mode_name}_u_9"
      elif 0.12 > current_profit >= 0.1:
        if last_candle["rsi_14"] < 48.0:
          return True, f"exit_{mode_name}_u_10"
      elif 0.2 > current_profit >= 0.12:
        if last_candle["rsi_14"] < 46.0:
          return True, f"exit_{mode_name}_u_11"
      elif current_profit >= 0.2:
        if last_candle["rsi_14"] < 44.0:
          return True, f"exit_{mode_name}_u_12"

    return False, None

  def exit_r(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    if 0.01 > current_profit >= 0.001:
      if last_candle["r_480"] > -0.1:
        return True, f"exit_{mode_name}_w_0_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 82.0):
        return True, f"exit_{mode_name}_w_0_2"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] < 40.0):
        return True, f"exit_{mode_name}_w_0_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 75.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_0_4"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["cti_20"] > 0.97):
        return True, f"exit_{mode_name}_w_0_5"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] > 75.0)
        and (last_candle["r_480_1h"] > -5.0)
        and (last_candle["r_480_4h"] > -5.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_0_6"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] > 75.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_0_7"
    elif 0.02 > current_profit >= 0.01:
      if last_candle["r_480"] > -0.2:
        return True, f"exit_{mode_name}_w_1_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 78.0):
        return True, f"exit_{mode_name}_w_1_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 46.0):
        return True, f"exit_{mode_name}_w_1_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 74.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_1_4"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_1_5"
      elif (
        (last_candle["r_14"] >= -6.0)
        and (last_candle["rsi_14"] > 70.0)
        and (last_candle["r_480_1h"] > -10.0)
        and (last_candle["r_480_4h"] > -15.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_1_6"
      elif (
        (last_candle["r_14"] >= -10.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_1_7"
    elif 0.03 > current_profit >= 0.02:
      if last_candle["r_480"] > -0.3:
        return True, f"exit_{mode_name}_w_2_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 77.0):
        return True, f"exit_{mode_name}_w_2_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 48.0):
        return True, f"exit_{mode_name}_w_2_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 73.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_2_4"
      elif (last_candle["r_14"] >= -3.0) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_2_5"
      elif (
        (last_candle["r_14"] >= -10.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -20.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_2_6"
      elif (
        (last_candle["r_14"] >= -10.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_2_7"
    elif 0.04 > current_profit >= 0.03:
      if last_candle["r_480"] > -0.4:
        return True, f"exit_{mode_name}_w_3_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 76.0):
        return True, f"exit_{mode_name}_w_3_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 50.0):
        return True, f"exit_{mode_name}_w_3_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 72.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_3_4"
      elif (last_candle["r_14"] >= -4.0) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_3_5"
      elif (
        (last_candle["r_14"] >= -10.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -20.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_3_6"
      elif (
        (last_candle["r_14"] >= -10.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_3_7"
    elif 0.05 > current_profit >= 0.04:
      if last_candle["r_480"] > -0.5:
        return True, f"exit_{mode_name}_w_4_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 75.0):
        return True, f"exit_{mode_name}_w_4_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 52.0):
        return True, f"exit_{mode_name}_w_4_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 71.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_4_4"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_4_5"
      elif (
        (last_candle["r_14"] >= -10.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -20.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_4_6"
      elif (
        (last_candle["r_14"] >= -10.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_4_7"
    elif 0.06 > current_profit >= 0.05:
      if last_candle["r_480"] > -0.6:
        return True, f"exit_{mode_name}_w_5_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 74.0):
        return True, f"exit_{mode_name}_w_5_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 54.0):
        return True, f"exit_{mode_name}_w_5_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 70.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_5_4"
      elif (last_candle["r_14"] >= -6.0) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_5_5"
      elif (
        (last_candle["r_14"] >= -10.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -20.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_5_6"
      elif (
        (last_candle["r_14"] >= -10.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_5_7"
    elif 0.07 > current_profit >= 0.06:
      if last_candle["r_480"] > -0.7:
        return True, f"exit_{mode_name}_w_6_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 75.0):
        return True, f"exit_{mode_name}_w_6_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 52.0):
        return True, f"exit_{mode_name}_w_6_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 71.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_6_4"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_6_5"
      elif (
        (last_candle["r_14"] >= -8.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -20.0)
        and (last_candle["r_480_4h"] > -15.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_6_6"
      elif (
        (last_candle["r_14"] >= -8.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_6_7"
    elif 0.08 > current_profit >= 0.07:
      if last_candle["r_480"] > -0.8:
        return True, f"exit_{mode_name}_w_7_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 76.0):
        return True, f"exit_{mode_name}_w_7_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 50.0):
        return True, f"exit_{mode_name}_w_7_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 72.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_7_4"
      elif (last_candle["r_14"] >= -4.0) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_7_5"
      elif (
        (last_candle["r_14"] >= -6.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -15.0)
        and (last_candle["r_480_4h"] > -10.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_7_6"
      elif (
        (last_candle["r_14"] >= -6.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_7_7"
    elif 0.09 > current_profit >= 0.08:
      if last_candle["r_480"] > -0.9:
        return True, f"exit_{mode_name}_w_8_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 77.0):
        return True, f"exit_{mode_name}_w_8_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 48.0):
        return True, f"exit_{mode_name}_w_8_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 73.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_8_4"
      elif (last_candle["r_14"] >= -3.0) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_8_5"
      elif (
        (last_candle["r_14"] >= -4.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -15.0)
        and (last_candle["r_480_4h"] > -10.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_8_6"
      elif (
        (last_candle["r_14"] >= -4.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_8_7"
    elif 0.1 > current_profit >= 0.09:
      if last_candle["r_480"] > -1.0:
        return True, f"exit_{mode_name}_w_9_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 78.0):
        return True, f"exit_{mode_name}_w_9_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 46.0):
        return True, f"exit_{mode_name}_w_9_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 74.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_9_4"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_9_5"
      elif (
        (last_candle["r_14"] >= -2.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -15.0)
        and (last_candle["r_480_4h"] > -10.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_9_6"
      elif (
        (last_candle["r_14"] >= -2.0)
        and (last_candle["rsi_14"] > 60.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_9_7"
    elif 0.12 > current_profit >= 0.1:
      if last_candle["r_480"] > -1.1:
        return True, f"exit_{mode_name}_w_10_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 79.0):
        return True, f"exit_{mode_name}_w_10_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 44.0):
        return True, f"exit_{mode_name}_w_10_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 75.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_10_4"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_10_5"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] > 65.0)
        and (last_candle["r_480_1h"] > -10.0)
        and (last_candle["r_480_4h"] > -5.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_10_6"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] > 65.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_10_7"
    elif 0.2 > current_profit >= 0.12:
      if last_candle["r_480"] > -0.4:
        return True, f"exit_{mode_name}_w_11_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 80.0):
        return True, f"exit_{mode_name}_w_11_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 42.0):
        return True, f"exit_{mode_name}_w_11_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 76.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_11_4"
      elif (last_candle["r_14"] >= -0.5) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_11_5"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] > 70.0)
        and (last_candle["r_480_1h"] > -10.0)
        and (last_candle["r_480_4h"] > -5.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_11_6"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] > 70.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_11_7"
    elif current_profit >= 0.2:
      if last_candle["r_480"] > -0.2:
        return True, f"exit_{mode_name}_w_12_1"
      elif (last_candle["r_14"] >= -1.0) and (last_candle["rsi_14"] > 81.0):
        return True, f"exit_{mode_name}_w_12_2"
      elif (last_candle["r_14"] >= -2.0) and (last_candle["rsi_14"] < 40.0):
        return True, f"exit_{mode_name}_w_12_3"
      elif (last_candle["r_14"] >= -5.0) and (last_candle["rsi_14"] > 77.0) and (last_candle["r_480_1h"] > -25.0):
        return True, f"exit_{mode_name}_w_12_4"
      elif (last_candle["r_14"] >= -0.1) and (last_candle["cti_20"] > 0.95):
        return True, f"exit_{mode_name}_w_12_5"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] > 75.0)
        and (last_candle["r_480_1h"] > -5.0)
        and (last_candle["r_480_4h"] > -5.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 60.0)
        and (last_candle["cti_20_1d"] > 0.80)
      ):
        return True, f"exit_{mode_name}_w_12_6"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] > 75.0)
        and (last_candle["r_480_1h"] > -25.0)
        and (last_candle["r_480_4h"] > -25.0)
        and (last_candle["rsi_14_1h"] > 50.0)
        and (last_candle["rsi_14_4h"] > 50.0)
        and (last_candle["rsi_14_1d"] > 50.0)
        and (last_candle["change_pct_4h"] < -0.01)
      ):
        return True, f"exit_{mode_name}_w_12_7"

    return False, None

  def exit_long_dec(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    if 0.01 > current_profit >= 0.001:
      if (
        (last_candle["r_14"] > -1.0)
        and (last_candle["rsi_14"] > 70.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_0_1"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_0_2"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_3"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_3"] >= 90.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_4"
    elif 0.02 > current_profit >= 0.01:
      if (
        (last_candle["r_14"] > -10.0)
        and (last_candle["rsi_14"] > 66.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_1_1"
      elif (
        (last_candle["r_14"] >= -30.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_1_2"
      elif (
        (last_candle["r_14"] >= -30.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_3"
      elif (
        (last_candle["r_14"] >= -40.0)
        and (last_candle["rsi_3"] >= 80.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_4"
    elif 0.03 > current_profit >= 0.02:
      if (
        (last_candle["r_14"] > -16.0)
        and (last_candle["rsi_14"] > 56.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_2_1"
      elif (
        (last_candle["r_14"] >= -30.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_2_2"
      elif (
        (last_candle["r_14"] >= -30.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_3"
      elif (
        (last_candle["r_14"] >= -40.0)
        and (last_candle["rsi_3"] >= 80.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_4"
    elif 0.04 > current_profit >= 0.03:
      if (
        (last_candle["r_14"] > -16.0)
        and (last_candle["rsi_14"] > 54.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_3_1"
      elif (
        (last_candle["r_14"] >= -30.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_3_2"
      elif (
        (last_candle["r_14"] >= -30.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_3"
      elif (
        (last_candle["r_14"] >= -40.0)
        and (last_candle["rsi_3"] >= 80.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_4"
    elif 0.05 > current_profit >= 0.04:
      if (
        (last_candle["r_14"] > -16.0)
        and (last_candle["rsi_14"] > 52.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_4_1"
      elif (
        (last_candle["r_14"] >= -30.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_4_2"
      elif (
        (last_candle["r_14"] >= -30.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_3"
      elif (
        (last_candle["r_14"] >= -40.0)
        and (last_candle["rsi_3"] >= 80.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_4"
    elif 0.06 > current_profit >= 0.05:
      if (
        (last_candle["r_14"] > -16.0)
        and (last_candle["rsi_14"] > 50.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_5_1"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_5_2"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_3"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_3"] >= 90.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_4"
    elif 0.07 > current_profit >= 0.06:
      if (
        (last_candle["r_14"] > -16.0)
        and (last_candle["rsi_14"] > 50.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_6_1"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_6_2"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_3"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_3"] >= 90.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_4"
    elif 0.08 > current_profit >= 0.07:
      if (
        (last_candle["r_14"] > -16.0)
        and (last_candle["rsi_14"] > 50.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_7_1"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_7_2"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_3"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_3"] >= 90.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_4"
    elif 0.09 > current_profit >= 0.08:
      if (
        (last_candle["r_14"] > -16.0)
        and (last_candle["rsi_14"] > 50.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_8_1"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_8_2"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_3"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_3"] >= 90.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_4"
    elif 0.1 > current_profit >= 0.09:
      if (
        (last_candle["r_14"] > -16.0)
        and (last_candle["rsi_14"] > 52.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_9_1"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_9_2"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_3"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_3"] >= 90.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_4"
    elif 0.12 > current_profit >= 0.1:
      if (
        (last_candle["r_14"] > -16.0)
        and (last_candle["rsi_14"] > 54.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_10_1"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_10_2"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_3"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_3"] >= 90.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_4"
    elif 0.2 > current_profit >= 0.12:
      if (
        (last_candle["r_14"] > -16.0)
        and (last_candle["rsi_14"] > 56.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_11_1"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_11_2"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_3"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_3"] >= 90.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 60.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_4"
    elif current_profit >= 0.2:
      if (
        (last_candle["r_14"] > -10.0)
        and (last_candle["rsi_14"] > 66.0)
        and (last_candle["not_downtrend_1h"] == False)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_12_1"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 50.0)
        and (last_candle["ema_200_dec_4_1d"] == True)
        and (last_candle["change_pct_4h"] < -0.03)
      ):
        return True, f"exit_{mode_name}_d_12_2"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["rsi_14_4h"] >= 50.0)
        and (last_candle["cti_20_1d"] >= 0.50)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_4h"] <= -0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_3"
      elif (
        (last_candle["r_14"] >= -1.0)
        and (last_candle["rsi_3"] >= 90.0)
        and (last_candle["rsi_14"] <= 50.0)
        and (last_candle["rsi_14_15m"] <= 50.0)
        and (last_candle["r_480_4h"] < -75.0)
        and (last_candle["cti_20_1d"] > 0.5)
        and (last_candle["rsi_14_1d"] >= 70.0)
        and (last_candle["change_pct_1h"] < -0.03)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_4"

    return False, None

  def exit_stoploss(
    self,
    mode_name: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    is_backtest = self.dp.runmode.value == "backtest"
    # Stoploss doom
    if (
      self.is_futures_mode is False
      and profit_stake
      < -(filled_entries[0].cost * self.stop_threshold / (trade.leverage if self.is_futures_mode else 1.0))
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2023, 6, 13) or is_backtest)
    ):
      return True, f"exit_{mode_name}_stoploss"

    if (
      self.is_futures_mode is True
      and profit_stake
      < -(filled_entries[0].cost * self.stop_threshold_futures / (trade.leverage if self.is_futures_mode else 1.0))
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2023, 10, 17) or is_backtest)
    ):
      return True, f"exit_{mode_name}_stoploss"

    return False, None

  def exit_short_normal(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.exit_short_signals(
      self.short_normal_mode_name,
      profit_current_stake_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # # Main sell signals
    # if not sell:
    #     sell, signal_name = self.exit_short_main(self.short_normal_mode_name, profit_current_stake_ratio, max_profit, max_loss, last_candle, previous_candle_1, previous_candle_2, previous_candle_3, previous_candle_4, previous_candle_5, trade, current_time, enter_tags)

    # # Williams %R based sells
    # if not sell:
    #     sell, signal_name = self.exit_short_r(self.short_normal_mode_name, profit_current_stake_ratio, max_profit, max_loss, last_candle, previous_candle_1, previous_candle_2, previous_candle_3, previous_candle_4, previous_candle_5, trade, current_time, enter_tags)

    # # Stoplosses
    # if not sell:
    #     sell, signal_name = self.exit_short_stoploss(self.short_normal_mode_name, current_rate, profit_stake, profit_ratio, profit_current_stake_ratio, profit_init_ratio, max_profit, max_loss, filled_entries, filled_exits, last_candle, previous_candle_1, previous_candle_2, previous_candle_3, previous_candle_4, previous_candle_5, trade, current_time, enter_tags)

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.short_normal_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.short_normal_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.short_normal_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_current_stake_ratio > (previous_profit + 0.005)) and (
        previous_sell_reason not in [f"exit_{self.short_normal_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_normal_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.short_normal_mode_name}_stoploss_doom",
        f"exit_{self.short_normal_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_normal_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_normal_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_current_stake_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_current_stake_ratio >= self.profit_max_thresholds[0]:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_current_stake_ratio):
          mark_signal = f"exit_profit_{self.short_normal_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_current_stake_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.short_normal_mode_name}_max",
      f"exit_{self.short_normal_mode_name}_stoploss_doom",
      f"exit_{self.short_normal_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  def exit_short_signals(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    # Sell signal 1
    if (
      (last_candle["rsi_14"] < 30.0)
      and (last_candle["close"] < last_candle["bb20_2_low"])
      and (previous_candle_1["close"] < previous_candle_1["bb20_2_low"])
      and (previous_candle_2["close"] < previous_candle_2["bb20_2_low"])
      and (previous_candle_3["close"] < previous_candle_3["bb20_2_low"])
      and (previous_candle_4["close"] < previous_candle_4["bb20_2_low"])
    ):
      if last_candle["close"] < last_candle["ema_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_1_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_1_2_1"

    # Sell signal 2
    elif (
      (last_candle["rsi_14"] < 26.0)
      and (last_candle["close"] < last_candle["bb20_2_low"])
      and (previous_candle_1["close"] < previous_candle_1["bb20_2_low"])
      and (previous_candle_2["close"] < previous_candle_2["bb20_2_low"])
    ):
      if last_candle["close"] < last_candle["ema_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_2_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_2_2_1"

    # Sell signal 3
    elif last_candle["rsi_14"] < 16.0:
      if last_candle["close"] < last_candle["ema_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_3_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_3_2_1"

    # # Sell signal 4
    # elif (last_candle['rsi_14'] > 80.0) and (last_candle['rsi_14_1h'] > 78.0):
    #     if (last_candle['close'] > last_candle['ema_200']):
    #         if (current_profit > 0.01):
    #             return True, f'exit_{mode_name}_4_1_1'
    #     else:
    #         if (current_profit > 0.01):
    #             return True, f'exit_{mode_name}_4_2_1'

    # # Sell signal 6
    # elif (last_candle['close'] < last_candle['ema_200']) and (last_candle['close'] > last_candle['ema_50']) and (last_candle['rsi_14'] > 79.0):
    #     if (current_profit > 0.01):
    #         return True, f'exit_{mode_name}_6_1'

    # # Sell signal 7
    # elif (last_candle['rsi_14_1h'] > 79.0) and (last_candle['crossed_below_ema_12_26']):
    #     if (last_candle['close'] > last_candle['ema_200']):
    #         if (current_profit > 0.01):
    #             return True, f'exit_{mode_name}_7_1_1'
    #     else:
    #         if (current_profit > 0.01):
    #             return True, f'exit_{mode_name}_7_2_1'

    # # Sell signal 8
    # elif (last_candle['close'] > last_candle['bb20_2_upp_1h'] * 1.08):
    #     if (last_candle['close'] > last_candle['ema_200']):
    #         if (current_profit > 0.01):
    #             return True, f'exit_{mode_name}_8_1_1'
    #     else:
    #         if (current_profit > 0.01):
    #             return True, f'exit_{mode_name}_8_2_1'

    return False, None

  def calc_total_profit(
    self, trade: "Trade", filled_entries: "Orders", filled_exits: "Orders", exit_rate: float
  ) -> tuple:
    """
    Calculates the absolute profit for open trades.

    :param trade: trade object.
    :param filled_entries: Filled entries list.
    :param filled_exits: Filled exits list.
    :param exit_rate: The exit rate.
    :return tuple: The total profit in stake, ratio, ratio based on current stake, and ratio based on the first entry stake.
    """
    total_stake = 0.0
    total_profit = 0.0
    for entry in filled_entries:
      entry_stake = entry.safe_filled * entry.safe_price * (1 + trade.fee_open)
      total_stake += entry_stake
      total_profit -= entry_stake
    for exit in filled_exits:
      exit_stake = exit.safe_filled * exit.safe_price * (1 - trade.fee_close)
      total_profit += exit_stake
    current_stake = trade.amount * exit_rate * (1 - trade.fee_close)
    total_profit += current_stake
    total_profit_ratio = total_profit / total_stake
    current_profit_ratio = total_profit / current_stake
    init_profit_ratio = total_profit / filled_entries[0].cost
    return total_profit, total_profit_ratio, current_profit_ratio, init_profit_ratio

  def custom_exit(
    self, pair: str, trade: "Trade", current_time: "datetime", current_rate: float, current_profit: float, **kwargs
  ):
    dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    last_candle = dataframe.iloc[-1].squeeze()
    previous_candle_1 = dataframe.iloc[-2].squeeze()
    previous_candle_2 = dataframe.iloc[-3].squeeze()
    previous_candle_3 = dataframe.iloc[-4].squeeze()
    previous_candle_4 = dataframe.iloc[-5].squeeze()
    previous_candle_5 = dataframe.iloc[-6].squeeze()

    enter_tag = "empty"
    if hasattr(trade, "enter_tag") and trade.enter_tag is not None:
      enter_tag = trade.enter_tag
    enter_tags = enter_tag.split()

    filled_entries = trade.select_filled_orders(trade.entry_side)
    filled_exits = trade.select_filled_orders(trade.exit_side)

    profit_stake = 0.0
    profit_ratio = 0.0
    profit_current_stake_ratio = 0.0
    profit_init_ratio = 0.0
    profit_stake, profit_ratio, profit_current_stake_ratio, profit_init_ratio = self.calc_total_profit(
      trade, filled_entries, filled_exits, current_rate
    )

    max_profit = (trade.max_rate - trade.open_rate) / trade.open_rate
    max_loss = (trade.open_rate - trade.min_rate) / trade.min_rate

    count_of_entries = len(filled_entries)
    if count_of_entries > 1:
      initial_entry = filled_entries[0]
      if initial_entry is not None and initial_entry.average is not None:
        max_profit = (trade.max_rate - initial_entry.average) / initial_entry.average
        max_loss = (initial_entry.average - trade.min_rate) / trade.min_rate

    # Normal mode
    if any(c in self.normal_mode_tags for c in enter_tags):
      sell, signal_name = self.exit_normal(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Pump mode
    if any(c in self.pump_mode_tags for c in enter_tags):
      sell, signal_name = self.exit_pump(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Quick mode
    if any(c in self.quick_mode_tags for c in enter_tags):
      sell, signal_name = self.exit_quick(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Long Rebuy mode
    if all(c in self.long_rebuy_mode_tags for c in enter_tags):
      sell, signal_name = self.long_exit_rebuy(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Long mode
    if any(c in self.long_mode_tags for c in enter_tags):
      sell, signal_name = self.exit_long(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Long rapid mode
    if any(c in self.long_rapid_mode_tags for c in enter_tags):
      sell, signal_name = self.long_exit_rapid(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Short normal mode
    if any(c in self.short_normal_mode_tags for c in enter_tags):
      sell, signal_name = self.exit_short_normal(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Trades not opened by X4
    if not any(
      c
      in (
        self.normal_mode_tags
        + self.pump_mode_tags
        + self.quick_mode_tags
        + self.long_rebuy_mode_tags
        + self.long_mode_tags
        + self.long_rapid_mode_tags
        + self.short_normal_mode_tags
      )
      for c in enter_tags
    ):
      # use normal mode for such trades
      sell, signal_name = self.exit_normal(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    return None

  def custom_stake_amount(
    self,
    pair: str,
    current_time: datetime,
    current_rate: float,
    proposed_stake: float,
    min_stake: Optional[float],
    max_stake: float,
    leverage: float,
    entry_tag: Optional[str],
    side: str,
    **kwargs,
  ) -> float:
    if self.position_adjustment_enable == True:
      enter_tags = entry_tag.split()
      # For grinding
      if self.grinding_enable:
        if any(
          c in (self.normal_mode_tags + self.pump_mode_tags + self.quick_mode_tags + self.long_mode_tags)
          for c in enter_tags
        ):
          stake = proposed_stake * self.stake_grinding_mode_multiplier
          if stake < min_stake:
            stake = proposed_stake * self.stake_grinding_mode_multiplier_alt_1
          if stake < min_stake:
            stake = proposed_stake * self.stake_grinding_mode_multiplier_alt_2
          return stake
      # Rebuy mode
      if all(c in self.long_rebuy_mode_tags for c in enter_tags):
        stake_multiplier = self.rebuy_mode_stake_multiplier
        # Low stakes, on Binance mostly
        if (proposed_stake * self.rebuy_mode_stake_multiplier) < min_stake:
          stake_multiplier = self.rebuy_mode_stake_multiplier_alt
        return proposed_stake * stake_multiplier

    return proposed_stake

  def adjust_trade_position(
    self,
    trade: Trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    min_stake: Optional[float],
    max_stake: float,
    current_entry_rate: float,
    current_exit_rate: float,
    current_entry_profit: float,
    current_exit_profit: float,
    **kwargs,
  ) -> Optional[float]:
    if self.position_adjustment_enable == False:
      return None

    enter_tag = "empty"
    if hasattr(trade, "enter_tag") and trade.enter_tag is not None:
      enter_tag = trade.enter_tag
    enter_tags = enter_tag.split()

    # Grinding
    if any(
      c
      in (
        self.normal_mode_tags
        + self.pump_mode_tags
        + self.quick_mode_tags
        + self.long_mode_tags
        + self.long_rapid_mode_tags
      )
      for c in enter_tags
    ) or not any(
      c
      in (
        self.normal_mode_tags
        + self.pump_mode_tags
        + self.quick_mode_tags
        + self.long_rebuy_mode_tags
        + self.long_mode_tags
        + self.long_rapid_mode_tags
      )
      for c in enter_tags
    ):
      return self.long_grind_adjust_trade_position(
        trade,
        current_time,
        current_rate,
        current_profit,
        min_stake,
        max_stake,
        current_entry_rate,
        current_exit_rate,
        current_entry_profit,
        current_exit_profit,
      )

    # Rebuy mode
    if all(c in self.long_rebuy_mode_tags for c in enter_tags):
      return self.long_rebuy_adjust_trade_position(
        trade,
        current_time,
        current_rate,
        current_profit,
        min_stake,
        max_stake,
        current_entry_rate,
        current_exit_rate,
        current_entry_profit,
        current_exit_profit,
      )

    return None

  def long_grind_adjust_trade_position(
    self,
    trade: Trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    min_stake: Optional[float],
    max_stake: float,
    current_entry_rate: float,
    current_exit_rate: float,
    current_entry_profit: float,
    current_exit_profit: float,
    **kwargs,
  ) -> Optional[float]:
    is_backtest = self.dp.runmode.value == "backtest"
    if self.grinding_enable:
      dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
      if len(dataframe) < 2:
        return None
      last_candle = dataframe.iloc[-1].squeeze()
      previous_candle = dataframe.iloc[-2].squeeze()

      filled_orders = trade.select_filled_orders()
      filled_entries = trade.select_filled_orders(trade.entry_side)
      filled_exits = trade.select_filled_orders(trade.exit_side)
      count_of_entries = trade.nr_of_successful_entries
      count_of_exits = trade.nr_of_successful_exits

      if count_of_entries == 0:
        return None

      exit_rate = current_rate
      if self.dp.runmode.value in ("live", "dry_run"):
        ticker = self.dp.ticker(trade.pair)
        if ("bid" in ticker) and ("ask" in ticker):
          if trade.is_short:
            if self.config["exit_pricing"]["price_side"] in ["ask", "other"]:
              if ticker["ask"] is not None:
                exit_rate = ticker["ask"]
          else:
            if self.config["exit_pricing"]["price_side"] in ["bid", "other"]:
              if ticker["bid"] is not None:
                exit_rate = ticker["bid"]

      profit_stake, profit_ratio, profit_current_stake_ratio, profit_init_ratio = self.calc_total_profit(
        trade, filled_entries, filled_exits, exit_rate
      )

      slice_amount = filled_entries[0].cost
      slice_profit = (exit_rate - filled_orders[-1].safe_price) / filled_orders[-1].safe_price
      slice_profit_entry = (exit_rate - filled_entries[-1].safe_price) / filled_entries[-1].safe_price
      slice_profit_exit = (
        ((exit_rate - filled_exits[-1].safe_price) / filled_exits[-1].safe_price) if count_of_exits > 0 else 0.0
      )

      current_stake_amount = trade.amount * current_rate

      current_grind_mode = self.grinding_mode
      if (current_grind_mode == 1) and (
        (slice_amount * self.grinding_mode_1_stakes_alt_4[0] / (trade.leverage if self.is_futures_mode else 1.0))
        < min_stake
      ):
        current_grind_mode = 0

      is_x3_trade = len(filled_orders) >= 2 and filled_orders[1].ft_order_side == "sell"

      # mode 0
      if current_grind_mode == 0:
        # Buy
        grinding_parts = len(self.grinding_stakes)
        grinding_thresholds = self.grinding_thresholds
        grinding_stakes = self.grinding_stakes
        # Low stakes, on Binance mostly
        if (slice_amount * self.grinding_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
          if (
            slice_amount * self.grinding_stakes_alt_1[0] / (trade.leverage if self.is_futures_mode else 1.0)
          ) < min_stake:
            grinding_parts = len(self.grinding_stakes_alt_2)
            grinding_thresholds = self.grinding_thresholds_alt_2
            grinding_stakes = self.grinding_stakes_alt_2
          else:
            grinding_parts = len(self.grinding_stakes_alt_1)
            grinding_thresholds = self.grinding_thresholds_alt_1
            grinding_stakes = self.grinding_stakes_alt_1

        stake_amount_threshold = slice_amount * grinding_stakes[0]
        for i in range(grinding_parts):
          if current_stake_amount < stake_amount_threshold:
            if (
              (
                profit_current_stake_ratio
                < (
                  (0.0 if (i == 0 and is_x3_trade) else grinding_thresholds[i])
                  * (trade.leverage if self.is_futures_mode else 1.0)
                )
              )
              and (last_candle["protections_long_global"] == True)
              and (
                (last_candle["close_max_12"] < (last_candle["close"] * 1.12))
                and (last_candle["close_max_24"] < (last_candle["close"] * 1.18))
                and (last_candle["close_max_48"] < (last_candle["close"] * 1.24))
                and (last_candle["btc_pct_close_max_72_5m"] < 0.04)
                and (last_candle["btc_pct_close_max_24_5m"] < 0.03)
              )
              and (
                (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
                or (slice_profit_entry < -0.02)
              )
              and (
                (
                  (last_candle["enter_long"] == True)
                  and (current_time - timedelta(minutes=30) > filled_entries[-1].order_filled_utc)
                  and (slice_profit_entry < -0.06)
                )
                or (
                  (last_candle["rsi_14"] < 36.0)
                  and (last_candle["r_14"] < -90.0)
                  and (previous_candle["rsi_3"] > 16.0)
                  and (last_candle["ema_26"] > last_candle["ema_12"])
                  and ((last_candle["ema_26"] - last_candle["ema_12"]) > (last_candle["open"] * 0.012))
                  and ((previous_candle["ema_26"] - previous_candle["ema_12"]) > (last_candle["open"] / 100.0))
                  and (last_candle["rsi_3_15m"] > 26.0)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["rsi_3_4h"] > 26.0)
                )
                or (
                  (last_candle["rsi_14"] < 32.0)
                  and (last_candle["rsi_14"] > previous_candle["rsi_14"])
                  and (previous_candle["rsi_3"] > 16.0)
                  and (last_candle["rsi_3_15m"] > 26.0)
                  and (last_candle["cti_20_1h"] < 0.7)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["rsi_3_4h"] > 20.0)
                  and (last_candle["ema_200_dec_24"] == False)
                )
                or (
                  (last_candle["rsi_14"] < 36.0)
                  and (last_candle["rsi_3"] > 8.0)
                  and (last_candle["close"] < (last_candle["bb20_2_low"] * 1.0))
                  and (last_candle["ema_12"] < (last_candle["ema_26"] * 0.990))
                  and (last_candle["rsi_3_15m"] > 26.0)
                  and (last_candle["cti_20_1h"] < 0.5)
                  and (last_candle["rsi_3_1h"] > 25.0)
                  and (last_candle["rsi_3_4h"] > 30.0)
                  and (last_candle["rsi_14_4h"] < 70.0)
                )
                or (
                  (last_candle["rsi_14"] < 35.0)
                  and (last_candle["rsi_3"] > 26.0)
                  and (last_candle["ha_close"] > last_candle["ha_open"])
                  and (last_candle["rsi_3_15m"] > 26.0)
                  and (last_candle["cti_20_1h"] < 0.8)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["cti_20_4h"] < 0.8)
                  and (last_candle["rsi_3_4h"] > 26.0)
                  and (last_candle["ema_200_dec_24"] == False)
                  and (last_candle["ema_200_dec_24_15m"] == False)
                  and (last_candle["ema_200_dec_48_1h"] == False)
                )
                or (
                  (last_candle["rsi_14"] < 36.0)
                  and (last_candle["rsi_3"] > 5.0)
                  and (last_candle["tsi"] < -20.0)
                  and (last_candle["tsi"] > last_candle["tsi_signal"])
                  and (previous_candle["tsi"] < previous_candle["tsi_signal"])
                  and (last_candle["rsi_3_15m"] > 5.0)
                  and (last_candle["rsi_3_1h"] > 30.0)
                  and (last_candle["rsi_3_4h"] > 30.0)
                )
                or (
                  (last_candle["rsi_14"] < 35.0)
                  and (last_candle["rsi_3"] > 10.0)
                  and (last_candle["high_max_6_1h"] > (last_candle["close"] * 1.10))
                  and (last_candle["rsi_14"] > previous_candle["rsi_14"])
                  and (last_candle["rsi_3_15m"] > 20.0)
                  and (last_candle["cti_20_1h"] < 0.5)
                  and (last_candle["rsi_3_1h"] > 30.0)
                  and (last_candle["rsi_3_4h"] > 30.0)
                )
                or (
                  (last_candle["rsi_14"] < 36.0)
                  and (last_candle["close"] > (last_candle["sar"] * 1.000))
                  and (previous_candle["close"] < previous_candle["sar"])
                  and (last_candle["rsi_3_15m"] > 20.0)
                  and (last_candle["cti_20_1h"] < 0.8)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["rsi_3_4h"] > 26.0)
                  and (last_candle["ema_200_dec_24"] == False)
                  and (last_candle["ema_200_dec_24_15m"] == False)
                )
                or (
                  (last_candle["rsi_14"] < 36.0)
                  and (last_candle["cti_20"] < -0.5)
                  and (last_candle["rsi_3"] > 5.0)
                  and (last_candle["cci_20"] < -160.0)
                  and (last_candle["cci_20"] > previous_candle["cci_20"])
                  and (last_candle["ema_12"] < (last_candle["ema_26"] * 0.996))
                  and (last_candle["rsi_3_15m"] > 26.0)
                  and (last_candle["cti_20_1h"] < 0.5)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["rsi_3_4h"] > 26.0)
                )
                or (
                  (last_candle["rsi_14"] < 36.0)
                  and (last_candle["rsi_14_15m"] < 36.0)
                  and (last_candle["rsi_3"] > 5.0)
                  and (last_candle["ema_26_15m"] > last_candle["ema_12_15m"])
                  and ((last_candle["ema_26_15m"] - last_candle["ema_12_15m"]) > (last_candle["open_15m"] * 0.012))
                  and (
                    (previous_candle["ema_26_15m"] - previous_candle["ema_12_15m"]) > (last_candle["open_15m"] / 100.0)
                  )
                  and (last_candle["rsi_3_15m"] > 10.0)
                  and (last_candle["cti_20_1h"] < 0.8)
                  and (last_candle["rsi_3_1h"] > 30.0)
                  and (last_candle["rsi_3_4h"] > 30.0)
                )
                or (
                  (last_candle["rsi_14"] < 46.0)
                  and (last_candle["rsi_14_15m"] < 34.0)
                  and (last_candle["rsi_14_15m"] > previous_candle["rsi_14_15m"])
                  and (last_candle["rsi_3_15m"] > 20.0)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["rsi_3_4h"] > 26.0)
                  and (last_candle["not_downtrend_1h"])
                )
                or (
                  (last_candle["rsi_14"] < 34.0)
                  and (previous_candle["rsi_3_15m"] > 20.0)
                  and (last_candle["rsi_14_15m"] < 40.0)
                  and (last_candle["rsi_14_15m"] > previous_candle["rsi_14_15m"])
                  and (last_candle["ema_12_15m"] < (last_candle["ema_26_15m"] * 0.998))
                  and (last_candle["rsi_3_15m"] > 10.0)
                  and (last_candle["cti_20_1h"] < 0.5)
                  and (last_candle["rsi_3_1h"] > 20.0)
                  and (last_candle["rsi_3_4h"] > 20.0)
                )
                or (
                  (last_candle["close"] > (last_candle["low_min_3_1h"] * 1.04))
                  and (last_candle["close"] > (last_candle["low_min_12_1h"] * 1.08))
                  and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.18))
                  and (previous_candle["rsi_3"] > 16.0)
                  and (last_candle["rsi_14"] < 42.0)
                  and (last_candle["ha_close"] > last_candle["ha_open"])
                  and (last_candle["rsi_3_15m"] > 10.0)
                  and (last_candle["rsi_3_1h"] > 20.0)
                  and (last_candle["rsi_3_4h"] > 5.0)
                  and (last_candle["rsi_14_4h"] < 66.0)
                  and (last_candle["ema_200_dec_48_1h"] == False)
                )
                or (
                  (last_candle["rsi_14"] < 36.0)
                  and (last_candle["ewo_50_200"] > 2.4)
                  and (last_candle["rsi_14"] > previous_candle["rsi_14"])
                  and (last_candle["close"] < (last_candle["ema_12"] * 0.998))
                  and (last_candle["rsi_3_15m"] > 12.0)
                  and (last_candle["cti_20_1h"] < 0.8)
                  and (last_candle["rsi_3_1h"] > 16.0)
                  and (last_candle["rsi_3_4h"] > 16.0)
                  and (last_candle["rsi_14_4h"] < 66.0)
                  and (last_candle["ema_200_dec_24"] == False)
                  and (last_candle["ema_200_dec_24_15m"] == False)
                  and (last_candle["ema_200_dec_48_1h"] == False)
                )
                or (
                  (last_candle["rsi_14"] < 36.0)
                  and (last_candle["rsi_3"] > 10.0)
                  and (last_candle["rsi_3"] < 36.0)
                  and (last_candle["ewo_50_200"] > 3.2)
                  and (last_candle["close"] < (last_candle["ema_12"] * 1.014))
                  and (last_candle["close"] < (last_candle["ema_16"] * 0.976))
                  and (last_candle["rsi_3_15m"] > 16.0)
                  and (last_candle["cti_20_1h"] < 0.7)
                  and (last_candle["rsi_3_1h"] > 16.0)
                  and (last_candle["rsi_3_4h"] > 16.0)
                )
                or (
                  (last_candle["close"] > (last_candle["close_min_12"] * 1.034))
                  and (previous_candle["rsi_3"] > 10.0)
                  and (last_candle["rsi_14"] < 46.0)
                  and (last_candle["rsi_3_15m"] > 16.0)
                  and (last_candle["rsi_3_1h"] > 20.0)
                  and (last_candle["rsi_3_4h"] > 20.0)
                  and (last_candle["not_downtrend_1h"])
                )
                or (
                  (last_candle["rsi_14"] < 34.0)
                  and (last_candle["rsi_3"] > 14.0)
                  and (last_candle["close"] < (last_candle["ema_26"] * 0.968))
                  and (last_candle["rsi_3_15m"] > 26.0)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["cti_20_4h"] < 0.8)
                  and (last_candle["rsi_3_4h"] > 26.0)
                )
                or (
                  (last_candle["high_max_24_1h"] < (last_candle["close"] * 1.18))
                  and (last_candle["high_max_12_1h"] < (last_candle["close"] * 1.14))
                  and (last_candle["close_max_12"] < (last_candle["close"] * 1.06))
                  and (last_candle["rsi_3"] > 26.0)
                  and (last_candle["rsi_14"] < 34.0)
                  and (last_candle["rsi_14"] > previous_candle["rsi_14"])
                  and (last_candle["ha_close"] > last_candle["ha_open"])
                  and (last_candle["ema_12"] < (last_candle["ema_26"] * 0.994))
                  and (last_candle["rsi_3_15m"] > 26.0)
                  and (last_candle["cti_20_1h"] < 0.8)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["rsi_3_4h"] > 26.0)
                )
                or (
                  (last_candle["close"] > (last_candle["close_min_12"] * 1.04))
                  and (last_candle["close"] > (last_candle["close_min_24"] * 1.08))
                  and (previous_candle["close"] < previous_candle["ema_200"])
                  and (last_candle["close"] > last_candle["ema_200"])
                  and (last_candle["rsi_14"] < 56.0)
                  and (last_candle["ema_200_dec_24_15m"] == False)
                  and (last_candle["ema_200_dec_48_1h"] == False)
                )
                or (
                  (last_candle["rsi_14"] < 36.0)
                  and (last_candle["rsi_3"] > 20.0)
                  and (last_candle["close"] > (last_candle["ema_200"] * 1.0))
                  and (last_candle["close"] < (last_candle["ema_200"] * 1.05))
                  and (last_candle["rsi_3_15m"] > 26.0)
                  and (last_candle["cti_20_1h"] < 0.7)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["rsi_3_4h"] > 26.0)
                  and (last_candle["ema_200_dec_24_15m"] == False)
                  and (last_candle["ema_200_dec_48_1h"] == False)
                )
                or (
                  (last_candle["rsi_14"] < 30.0)
                  and (last_candle["rsi_3"] > 12.0)
                  and (last_candle["rsi_14"] > previous_candle["rsi_14"])
                  and (last_candle["rsi_3_15m"] > 14.0)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["cti_20_4h"] < 0.7)
                  and (last_candle["rsi_3_4h"] > 26.0)
                  and (last_candle["ema_200_dec_24_15m"] == False)
                  and (last_candle["ema_200_dec_48_1h"] == False)
                )
                or (
                  (last_candle["rsi_14"] < 46.0)
                  and (previous_candle["rsi_3"] > 12.0)
                  and (last_candle["rsi_3"] > 12.0)
                  and (last_candle["rsi_14"] > previous_candle["rsi_14"])
                  and (last_candle["ha_close"] > last_candle["ha_open"])
                  and (last_candle["rsi_3_15m"] > 26.0)
                  and (last_candle["cti_20_1h"] < 0.5)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["rsi_3_4h"] > 26.0)
                  and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
                  and (last_candle["close"] > (last_candle["close_min_24"] * 1.04))
                  and (last_candle["ema_200_dec_24"] == False)
                )
                or (
                  (count_of_exits > 0)
                  and (slice_profit < -0.08)
                  and (previous_candle["rsi_3"] > 16.0)
                  and (last_candle["rsi_14"] < 35.0)
                  and (last_candle["rsi_14"] > previous_candle["rsi_14"])
                  and (last_candle["ha_close"] > last_candle["ha_open"])
                  and (last_candle["rsi_3"] > 10.0)
                  and (last_candle["rsi_3_15m"] > 16.0)
                  and (last_candle["cti_20_1h"] < 0.5)
                  and (last_candle["rsi_3_1h"] > 30.0)
                  and (last_candle["rsi_3_4h"] > 30.0)
                )
                or (
                  (count_of_exits > 0)
                  and (slice_profit_entry < -0.08)
                  and (previous_candle["rsi_3"] > 16.0)
                  and (last_candle["rsi_14"] < 38.0)
                  and (last_candle["rsi_3"] > 16.0)
                  and (last_candle["close"] > (last_candle["sar"] * 1.000))
                  and (previous_candle["close"] < previous_candle["sar"])
                  and (last_candle["rsi_3_15m"] > 16.0)
                  and (last_candle["cti_20_1h"] < 0.5)
                  and (last_candle["rsi_3_1h"] > 30.0)
                  and (last_candle["rsi_3_4h"] > 30.0)
                )
                or (
                  (count_of_exits > 0)
                  and (slice_profit_entry < -0.04)
                  and (previous_candle["rsi_3"] > 10.0)
                  and (last_candle["rsi_14"] < 32.0)
                  and (last_candle["rsi_3"] > 10.0)
                  and (last_candle["rsi_14"] > previous_candle["rsi_14"])
                  and (last_candle["rsi_3_15m"] > 10.0)
                  and (last_candle["cti_20_1h"] < -0.5)
                  and (last_candle["rsi_3_1h"] > 26.0)
                  and (last_candle["cti_20_4h"] < -0.5)
                  and (last_candle["rsi_3_4h"] > 26.0)
                )
              )
            ):
              buy_amount = slice_amount * grinding_stakes[i] / (trade.leverage if self.is_futures_mode else 1.0)
              if buy_amount > max_stake:
                buy_amount = max_stake
              if buy_amount < min_stake:
                return None
              self.dp.send_msg(
                f"Grinding entry [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
              )
              return buy_amount
          stake_amount_threshold += slice_amount * grinding_stakes[i]

        # Sell

        if count_of_entries > 1:
          count_of_full_exits = 0
          for exit_order in filled_exits:
            if (exit_order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
              count_of_full_exits += 1
          num_buys = 0
          num_sells = 0
          for order in reversed(filled_orders):
            if order.ft_order_side == "buy":
              num_buys += 1
            elif order.ft_order_side == "sell":
              if (order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
                num_sells += 1
            # patial fills on exits
            if (num_buys == num_sells) and (order.ft_order_side == "sell"):
              sell_amount = order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)
              grind_profit = (exit_rate - order.safe_price) / order.safe_price
              if sell_amount > min_stake:
                # Test if it's the last exit. Normal exit with partial fill
                if (trade.stake_amount - sell_amount) > min_stake:
                  if grind_profit > 0.01:
                    self.dp.send_msg(
                      f"Grinding exit (remaining) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {order.safe_remaining} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
                    )
                    return -sell_amount
                  else:
                    # Current order is sell partial fill
                    return None
            elif (
              (count_of_entries > (count_of_full_exits + 1))
              and (order is not filled_orders[0])
              and (num_buys > num_sells)
              and (order.ft_order_side == "buy")
            ):
              buy_order = order
              grind_profit = (exit_rate - buy_order.safe_price) / buy_order.safe_price
              if grind_profit > self.grinding_profit_threshold:
                sell_amount = buy_order.safe_filled * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)
                if (current_stake_amount - sell_amount) < (min_stake * 1.7):
                  sell_amount = (trade.amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) - (
                    min_stake * 1.7
                  )
                if sell_amount > min_stake:
                  self.dp.send_msg(
                    f"Grinding exit [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount}| Coin amount: {buy_order.safe_filled} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
                  )
                  return -sell_amount
              # elif (
              #         (grind_profit < self.grinding_stop_grinds)
              #         # temporary
              #         and
              #         (
              #             (trade.open_date_utc.replace(tzinfo=None) >= datetime(2023, 5, 17) or is_backtest)
              #             or (buy_order.order_date_utc.replace(tzinfo=None) >= datetime(2023, 5, 27) or is_backtest)
              #         )
              # ):
              #     sell_amount = buy_order.safe_filled * exit_rate * 0.999
              #     if ((current_stake_amount - sell_amount) < (min_stake * 1.7)):
              #         sell_amount = (trade.amount * exit_rate) - (min_stake * 1.7)
              #     if (sell_amount > min_stake):
              #         self.dp.send_msg(f"Grinding stop exit [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount}| Coin amount: {buy_order.safe_filled} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%")
              #         return -sell_amount
              break

      # mode 1
      elif current_grind_mode == 1:
        max_sub_grinds = len(self.grinding_mode_1_stakes)
        grinding_mode_1_stakes = self.grinding_mode_1_stakes
        grinding_mode_1_sub_thresholds = self.grinding_mode_1_sub_thresholds
        # Low stakes, on Binance mostly
        if (
          slice_amount * self.grinding_mode_1_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)
        ) < min_stake:
          if (
            slice_amount * self.grinding_mode_1_stakes_alt_3[0] / (trade.leverage if self.is_futures_mode else 1.0)
          ) < min_stake:
            max_sub_grinds = len(self.grinding_mode_1_stakes_alt_4)
            grinding_mode_1_stakes = self.grinding_mode_1_stakes_alt_4
            grinding_mode_1_sub_thresholds = self.grinding_mode_1_sub_thresholds_alt_4
          elif (
            slice_amount * self.grinding_mode_1_stakes_alt_2[0] / (trade.leverage if self.is_futures_mode else 1.0)
          ) < min_stake:
            max_sub_grinds = len(self.grinding_mode_1_stakes_alt_3)
            grinding_mode_1_stakes = self.grinding_mode_1_stakes_alt_3
            grinding_mode_1_sub_thresholds = self.grinding_mode_1_sub_thresholds_alt_3
          elif (
            slice_amount * self.grinding_mode_1_stakes_alt_1[0] / (trade.leverage if self.is_futures_mode else 1.0)
          ) < min_stake:
            max_sub_grinds = len(self.grinding_mode_1_stakes_alt_2)
            grinding_mode_1_stakes = self.grinding_mode_1_stakes_alt_2
            grinding_mode_1_sub_thresholds = self.grinding_mode_1_sub_thresholds_alt_2
          else:
            max_sub_grinds = len(self.grinding_mode_1_stakes_alt_1)
            grinding_mode_1_stakes = self.grinding_mode_1_stakes_alt_1
            grinding_mode_1_sub_thresholds = self.grinding_mode_1_sub_thresholds_alt_1
        partial_sell = False
        sub_grind_count = 0
        total_amount = 0.0
        total_cost = 0.0
        current_open_rate = 0.0
        current_grind_stake = 0.0
        current_grind_stake_profit = 0.0
        for order in reversed(filled_orders):
          if (order.ft_order_side == "buy") and (order is not filled_orders[0]):
            sub_grind_count += 1
            total_amount += order.safe_filled
            total_cost += order.safe_filled * order.safe_price
          elif order.ft_order_side == "sell":
            if (order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) > min_stake:
              partial_sell = True
            break
        if sub_grind_count > 0:
          current_open_rate = total_cost / total_amount
          current_grind_stake = total_amount * exit_rate * (1 - trade.fee_close)
          current_grind_stake_profit = current_grind_stake - total_cost
        # Buy
        if (not partial_sell) and (sub_grind_count < max_sub_grinds):
          if (
            (
              (
                (sub_grind_count == 0)
                and (
                  profit_init_ratio
                  < (
                    (0.0 if is_x3_trade else grinding_mode_1_sub_thresholds[0])
                    * (trade.leverage if self.is_futures_mode else 1.0)
                  )
                )
              )
              or (
                (0 < sub_grind_count < max_sub_grinds)
                and (slice_profit_entry < grinding_mode_1_sub_thresholds[sub_grind_count])
              )
            )
            and (last_candle["protections_long_global"] == True)
            and (
              (last_candle["close_max_12"] < (last_candle["close"] * 1.12))
              and (last_candle["close_max_24"] < (last_candle["close"] * 1.18))
              and (last_candle["close_max_48"] < (last_candle["close"] * 1.24))
              and (last_candle["btc_pct_close_max_72_5m"] < 0.04)
              and (last_candle["btc_pct_close_max_24_5m"] < 0.03)
            )
            and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
            and (
              (last_candle["enter_long"] == True)
              or (
                (last_candle["rsi_14"] < 36.0)
                and (previous_candle["rsi_3"] > 6.0)
                and (last_candle["ema_26"] > last_candle["ema_12"])
                and ((last_candle["ema_26"] - last_candle["ema_12"]) > (last_candle["open"] * 0.010))
                and ((previous_candle["ema_26"] - previous_candle["ema_12"]) > (last_candle["open"] / 100.0))
                and (last_candle["rsi_3_15m"] > 6.0)
                and (last_candle["rsi_3_1h"] > 12.0)
                and (last_candle["rsi_3_4h"] > 12.0)
                and (
                  (last_candle["cti_20_4h"] < 0.5)
                  or (last_candle["rsi_14_4h"] < 50.0)
                  or (last_candle["ema_200_dec_24_4h"] == False)
                )
                and ((last_candle["cti_20_1d"] < 0.8) or (last_candle["rsi_14_1d"] < 60.0))
                and (
                  (last_candle["cti_20_1d"] < 0.5)
                  or (last_candle["rsi_14_1d"] < 50.0)
                  or (last_candle["ema_200_dec_4_1d"] == False)
                )
                and (last_candle["high_max_6_1d"] < (last_candle["close"] * 1.7))
              )
              or (
                (last_candle["rsi_14"] < 36.0)
                and (last_candle["rsi_3"] > 8.0)
                and (last_candle["rsi_14"] > previous_candle["rsi_14"])
                and (last_candle["ema_12"] < (last_candle["ema_26"] * 0.992))
                and (last_candle["rsi_3_15m"] > 8.0)
                and (last_candle["rsi_3_1h"] > 26.0)
                and (last_candle["rsi_3_4h"] > 26.0)
                and ((last_candle["cti_20_1d"] < 0.8) or (last_candle["rsi_14_1d"] < 60.0))
              )
              or (
                (previous_candle["rsi_3"] > 16.0)
                and (last_candle["rsi_3"] > 12.0)
                and (last_candle["rsi_14"] < 36.0)
                and (last_candle["rsi_14"] > previous_candle["rsi_14"])
                and (last_candle["ha_close"] > last_candle["ha_open"])
                and (last_candle["rsi_3_15m"] > 16.0)
                and (last_candle["rsi_3_1h"] > 26.0)
                and (last_candle["rsi_3_4h"] > 26.0)
                and (last_candle["cti_20_1h"] < 0.9)
                and (last_candle["cti_20_4h"] < 0.9)
                and (last_candle["cti_20_1d"] < 0.9)
              )
              or (
                (last_candle["rsi_14"] < 60.0)
                and (last_candle["hma_70_buy"])
                and (last_candle["ema_12"] < last_candle["ema_26"])
                and (last_candle["rsi_3_15m"] > 26.0)
                and (last_candle["rsi_3_1h"] > 26.0)
                and (last_candle["rsi_3_4h"] > 26.0)
                and (last_candle["cti_20_1h"] < 0.9)
                and (last_candle["cti_20_4h"] < 0.9)
                and (last_candle["cti_20_1d"] < 0.9)
                and (
                  (last_candle["cti_20_4h"] < 0.5)
                  or (last_candle["rsi_14_4h"] < 50.0)
                  or (last_candle["ema_200_dec_24_4h"] == False)
                )
                and ((last_candle["cti_20_1d"] < 0.8) or (last_candle["rsi_14_1d"] < 60.0))
                and (
                  (last_candle["cti_20_1d"] < 0.5)
                  or (last_candle["rsi_14_1d"] < 50.0)
                  or (last_candle["ema_200_dec_4_1d"] == False)
                )
                and (last_candle["close"] > last_candle["sup_level_1d"])
                and (last_candle["close"] < last_candle["res_hlevel_1d"])
              )
              or (
                (last_candle["rsi_14"] < 36.0)
                and (last_candle["rsi_3"] > 16.0)
                and (last_candle["change_pct"] > -0.01)
                and (last_candle["close"] < (last_candle["ema_26"] * 0.986))
                and (last_candle["rsi_3_15m"] > 16.0)
                and (last_candle["rsi_3_1h"] > 16.0)
                and (last_candle["rsi_3_4h"] > 16.0)
                and (last_candle["close"] < last_candle["res_hlevel_1d"])
                and (last_candle["close"] > last_candle["sup_level_1d"])
                and (last_candle["high_max_6_1d"] < (last_candle["close"] * 1.5))
                and (last_candle["hl_pct_change_24_1h"] < 0.75)
              )
              or (
                (last_candle["rsi_14"] < 46.0)
                and (previous_candle["rsi_3"] > 6.0)
                and (last_candle["bb20_2_width_1h"] > 0.132)
                and (last_candle["cti_20"] < -0.85)
                and (last_candle["r_14"] < -50.0)
                and (last_candle["rsi_3_15m"] > 16.0)
                and (last_candle["rsi_3_1h"] > 16.0)
                and (last_candle["rsi_3_4h"] > 16.0)
                and (last_candle["close"] < last_candle["res3_1d"])
                and (last_candle["high_max_6_1d"] < (last_candle["close"] * 1.5))
              )
              or (
                (last_candle["rsi_14"] < 60.0)
                and (last_candle["cti_20"] < -0.0)
                and (last_candle["hma_55_buy"])
                and (last_candle["rsi_3_15m"] > 16.0)
                and (last_candle["rsi_3_1h"] > 26.0)
                and (last_candle["rsi_3_4h"] > 26.0)
                and (last_candle["cti_20_15m"] < 0.8)
                and (last_candle["cti_20_1h"] < 0.8)
                and (last_candle["cti_20_4h"] < 0.8)
                and (last_candle["close"] < last_candle["res_hlevel_1d"])
                and (last_candle["close"] > last_candle["sup_level_1d"])
                and (last_candle["high_max_6_1d"] < (last_candle["close"] * 1.3))
                and (last_candle["hl_pct_change_24_1h"] < 0.75)
              )
            )
          ):
            buy_amount = (
              slice_amount
              * grinding_mode_1_stakes[sub_grind_count]
              / (trade.leverage if self.is_futures_mode else 1.0)
            )
            if buy_amount > max_stake:
              buy_amount = max_stake
            if buy_amount < min_stake:
              return None
            if buy_amount < (min_stake * 1.5):
              buy_amount = min_stake * 1.5
            self.dp.send_msg(
              f"Grinding entry [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
            )
            return buy_amount

        # Sell remaining if partial fill on exit
        if partial_sell:
          order = filled_exits[-1]
          sell_amount = order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)
          if (current_stake_amount - sell_amount) < (min_stake * 1.7):
            sell_amount = (trade.amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) - (
              min_stake * 1.7
            )
          grind_profit = (exit_rate - order.safe_price) / order.safe_price
          if sell_amount > min_stake:
            # Test if it's the last exit. Normal exit with partial fill
            if (trade.stake_amount - sell_amount) > min_stake:
              self.dp.send_msg(
                f"Grinding exit (remaining) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {order.safe_remaining} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
              )
              return -sell_amount

        # Sell
        elif sub_grind_count > 0:
          grind_profit = (exit_rate - current_open_rate) / current_open_rate
          if grind_profit > self.grinding_mode_1_profit_threshold:
            sell_amount = total_amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)
            if (current_stake_amount - sell_amount) < (min_stake * 1.5):
              sell_amount = (trade.amount * exit_rate) - (min_stake * 1.5)
            if sell_amount > min_stake:
              self.dp.send_msg(
                f"Grinding exit [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount}| Coin amount: {total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
              )
              return -sell_amount
          elif (
            (current_grind_stake_profit < (slice_amount * self.grinding_mode_1_stop_grinds))
            and is_x3_trade
            # temporary
            and (
              (trade.open_date_utc.replace(tzinfo=None) >= datetime(2023, 8, 28) or is_backtest)
              or (filled_entries[-1].order_date_utc.replace(tzinfo=None) >= datetime(2023, 8, 28) or is_backtest)
            )
          ):
            sell_amount = total_amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0) * 0.999
            if (current_stake_amount - sell_amount) < (min_stake * 1.7):
              sell_amount = (trade.amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) - (
                min_stake * 1.7
              )
            if sell_amount > min_stake:
              self.dp.send_msg(
                f"Grinding stop exit [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
              )
              return -sell_amount

      # mode 2
      elif current_grind_mode == 2:
        max_sub_grinds = 0
        grinding_mode_2_stakes = []
        grinding_mode_2_sub_thresholds = []
        for i, item in enumerate(
          self.grinding_mode_2_stakes_futures if self.is_futures_mode else self.grinding_mode_2_stakes_spot
        ):
          if (slice_amount * item[0] / (trade.leverage if self.is_futures_mode else 1.0)) > min_stake:
            grinding_mode_2_stakes = item
            grinding_mode_2_sub_thresholds = (
              self.grinding_mode_2_sub_thresholds_futures[i]
              if self.is_futures_mode
              else self.grinding_mode_2_sub_thresholds_spot[i]
            )
            max_sub_grinds = len(grinding_mode_2_stakes)
            break
        grinding_mode_2_stop_init_grinds = (
          self.grinding_mode_2_stop_init_grinds_futures
          if self.is_futures_mode
          else self.grinding_mode_2_stop_init_grinds_spot
        )
        grinding_mode_2_stop_grinds = (
          self.grinding_mode_2_stop_grinds_futures if self.is_futures_mode else self.grinding_mode_2_stop_grinds_spot
        )
        grinding_mode_2_profit_threshold = (
          self.grinding_mode_2_profit_threshold_futures
          if self.is_futures_mode
          else self.grinding_mode_2_profit_threshold_spot
        )
        partial_sell = False
        is_sell_found = False
        sub_grind_count = 0
        total_amount = 0.0
        total_cost = 0.0
        current_open_rate = 0.0
        current_grind_stake = 0.0
        current_grind_stake_profit = 0.0
        for order in reversed(filled_orders):
          if (order.ft_order_side == "buy") and (order is not filled_orders[0]):
            sub_grind_count += 1
            total_amount += order.safe_filled
            total_cost += order.safe_filled * order.safe_price
          elif order.ft_order_side == "sell":
            is_sell_found = True
            if (order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) > min_stake:
              partial_sell = True
            break
        if sub_grind_count > 0:
          current_open_rate = total_cost / total_amount
          current_grind_stake = total_amount * exit_rate * (1 - trade.fee_close)
          current_grind_stake_profit = current_grind_stake - total_cost

        # Buy
        if (not partial_sell) and (sub_grind_count < max_sub_grinds):
          if (
            (
              (slice_profit_entry if (sub_grind_count > 0) else profit_init_ratio)
              < grinding_mode_2_sub_thresholds[sub_grind_count + (0 if is_sell_found else 1)]
            )
            and (last_candle["protections_long_global"] == True)
            and (last_candle["protections_long_rebuy"] == True)
            and (
              (last_candle["close_max_12"] < (last_candle["close"] * 1.12))
              and (last_candle["close_max_24"] < (last_candle["close"] * 1.18))
              and (last_candle["close_max_48"] < (last_candle["close"] * 1.24))
              and (last_candle["btc_pct_close_max_72_5m"] < 0.03)
              and (last_candle["btc_pct_close_max_24_5m"] < 0.03)
            )
            and (
              (last_candle["enter_long"] == True)
              or (
                (last_candle["rsi_3"] > 10.0)
                and (last_candle["rsi_3_15m"] > 20.0)
                and (last_candle["rsi_3_1h"] > 20.0)
                and (last_candle["rsi_3_4h"] > 20.0)
                and (last_candle["rsi_14"] < 46.0)
                and (last_candle["ha_close"] > last_candle["ha_open"])
                and (last_candle["ema_12"] < (last_candle["ema_26"] * 0.990))
                and (last_candle["cti_20_1h"] < 0.8)
                and (last_candle["rsi_14_1h"] < 80.0)
              )
              or (
                (last_candle["rsi_14"] < 36.0)
                and (last_candle["close"] < (last_candle["sma_16"] * 0.998))
                and (last_candle["rsi_3"] > 16.0)
                and (last_candle["rsi_3_15m"] > 26.0)
                and (last_candle["rsi_3_1h"] > 26.0)
                and (last_candle["rsi_3_4h"] > 26.0)
              )
              or (
                (last_candle["rsi_14"] < 36.0)
                and (previous_candle["rsi_3"] > 6.0)
                and (last_candle["ema_26"] > last_candle["ema_12"])
                and ((last_candle["ema_26"] - last_candle["ema_12"]) > (last_candle["open"] * 0.010))
                and ((previous_candle["ema_26"] - previous_candle["ema_12"]) > (last_candle["open"] / 100.0))
                and (last_candle["rsi_3_1h"] > 20.0)
                and (last_candle["rsi_3_4h"] > 20.0)
                and (last_candle["cti_20_1h"] < 0.8)
                and (last_candle["rsi_14_1h"] < 80.0)
              )
              or (
                (last_candle["rsi_14"] > 30.0)
                and (last_candle["rsi_14"] < 60.0)
                and (last_candle["hma_70_buy"])
                and (last_candle["close"] > last_candle["zlma_50_1h"])
                and (last_candle["ema_26"] > last_candle["ema_12"])
                and (last_candle["cti_20_15m"] < 0.5)
                and (last_candle["rsi_14_15m"] < 50.0)
                and (last_candle["cti_20_1h"] < 0.8)
                and (last_candle["rsi_14_1h"] < 80.0)
              )
              or (
                (last_candle["rsi_3"] > 10.0)
                and (last_candle["rsi_3_15m"] > 20.0)
                and (last_candle["rsi_3_1h"] > 20.0)
                and (last_candle["rsi_3_4h"] > 20.0)
                and (last_candle["rsi_14"] < 36.0)
                and (last_candle["zlma_50_dec_15m"] == False)
                and (last_candle["zlma_50_dec_1h"] == False)
              )
              or (
                (last_candle["rsi_14"] < 40.0)
                and (last_candle["rsi_14_15m"] < 40.0)
                and (last_candle["rsi_3"] > 6.0)
                and (last_candle["ema_26_15m"] > last_candle["ema_12_15m"])
                and ((last_candle["ema_26_15m"] - last_candle["ema_12_15m"]) > (last_candle["open_15m"] * 0.006))
                and (
                  (previous_candle["ema_26_15m"] - previous_candle["ema_12_15m"]) > (last_candle["open_15m"] / 100.0)
                )
                and (last_candle["rsi_3_15m"] > 10.0)
                and (last_candle["rsi_3_1h"] > 26.0)
                and (last_candle["rsi_3_4h"] > 26.0)
                and (last_candle["cti_20_1h"] < 0.8)
                and (last_candle["rsi_14_1h"] < 80.0)
              )
              or (
                (last_candle["rsi_14"] > 35.0)
                and (last_candle["rsi_3"] > 4.0)
                and (last_candle["rsi_3"] < 46.0)
                and (last_candle["rsi_14"] < previous_candle["rsi_14"])
                and (last_candle["close"] < (last_candle["sma_16"] * 0.982))
                and (last_candle["cti_20"] < -0.6)
                and (last_candle["rsi_3_1h"] > 20.0)
                and (last_candle["rsi_3_4h"] > 20.0)
              )
              or (
                (last_candle["rsi_3"] > 12.0)
                and (last_candle["rsi_3_15m"] > 26.0)
                and (last_candle["rsi_3_1h"] > 26.0)
                and (last_candle["rsi_3_4h"] > 26.0)
                and (last_candle["rsi_14"] < 40.0)
                and (last_candle["cti_20_1h"] < 0.8)
                and (last_candle["rsi_14_1h"] < 80.0)
                and (last_candle["cti_20_4h"] < 0.8)
                and (last_candle["rsi_14_4h"] < 80.0)
                and (last_candle["ema_200_dec_48_1h"] == False)
              )
            )
          ):
            buy_amount = (
              slice_amount
              * grinding_mode_2_stakes[sub_grind_count]
              / (trade.leverage if self.is_futures_mode else 1.0)
            )
            if buy_amount > max_stake:
              buy_amount = max_stake
            if buy_amount < min_stake:
              return None
            if buy_amount < (min_stake * 1.5):
              buy_amount = min_stake * 1.5
            self.dp.send_msg(
              f"Grinding entry [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
            )
            return buy_amount

        # Sell remaining if partial fill on exit
        if partial_sell:
          order = filled_exits[-1]
          sell_amount = order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)
          if (current_stake_amount - sell_amount) < (min_stake * 1.5):
            sell_amount = (trade.amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) - (
              min_stake * 1.5
            )
          grind_profit = (exit_rate - order.safe_price) / order.safe_price
          if sell_amount > min_stake:
            # Test if it's the last exit. Normal exit with partial fill
            if (trade.stake_amount - sell_amount) > min_stake:
              self.dp.send_msg(
                f"Grinding exit (remaining) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {order.safe_remaining} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
              )
              return -sell_amount

        # Sell
        elif sub_grind_count > 0:
          grind_profit = (exit_rate - current_open_rate) / current_open_rate
          if grind_profit > grinding_mode_2_profit_threshold:
            sell_amount = total_amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)
            if (current_stake_amount - sell_amount) < (min_stake * 1.5):
              sell_amount = (trade.amount * exit_rate) - (min_stake * 1.5)
            if sell_amount > min_stake:
              self.dp.send_msg(
                f"Grinding exit [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount}| Coin amount: {total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
              )
              return -sell_amount

        # Grind stop
        if (
          (
            (
              (
                current_grind_stake_profit
                < (slice_amount * grinding_mode_2_stop_grinds / (trade.leverage if self.is_futures_mode else 1.0))
              )
              if is_sell_found
              else (
                profit_stake
                < (slice_amount * grinding_mode_2_stop_init_grinds / (trade.leverage if self.is_futures_mode else 1.0))
              )
            )
            or (
              (
                profit_stake
                < (slice_amount * grinding_mode_2_stop_init_grinds / (trade.leverage if self.is_futures_mode else 1.0))
              )
              and (
                (
                  (trade.amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0))
                  - (total_amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0))
                )
                > (min_stake * 3.0)
              )
              # temporary
              and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2023, 12, 19) or is_backtest)
            )
          )
          # temporary
          and (
            (trade.open_date_utc.replace(tzinfo=None) >= datetime(2023, 8, 28) or is_backtest)
            or (filled_entries[-1].order_date_utc.replace(tzinfo=None) >= datetime(2023, 8, 28) or is_backtest)
          )
        ):
          sell_amount = trade.amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0) * 0.999
          if (current_stake_amount / (trade.leverage if self.is_futures_mode else 1.0) - sell_amount) < (
            min_stake * 1.5
          ):
            sell_amount = (trade.amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) - (
              min_stake * 1.5
            )
          if sell_amount > min_stake:
            grind_profit = 0.0
            if current_open_rate > 0.0:
              grind_profit = ((exit_rate - current_open_rate) / current_open_rate) if is_sell_found else profit_ratio
            self.dp.send_msg(
              f"Grinding stop exit [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
            )
            return -sell_amount

    return None

  def long_rebuy_adjust_trade_position(
    self,
    trade: Trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    min_stake: Optional[float],
    max_stake: float,
    current_entry_rate: float,
    current_exit_rate: float,
    current_entry_profit: float,
    current_exit_profit: float,
    **kwargs,
  ) -> Optional[float]:
    dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
    if len(dataframe) < 2:
      return None
    last_candle = dataframe.iloc[-1].squeeze()
    previous_candle = dataframe.iloc[-2].squeeze()

    filled_orders = trade.select_filled_orders()
    filled_entries = trade.select_filled_orders(trade.entry_side)
    filled_exits = trade.select_filled_orders(trade.exit_side)
    count_of_entries = trade.nr_of_successful_entries
    count_of_exits = trade.nr_of_successful_exits

    if count_of_entries == 0:
      return None

    exit_rate = current_rate
    if self.dp.runmode.value in ("live", "dry_run"):
      ticker = self.dp.ticker(trade.pair)
      if ("bid" in ticker) and ("ask" in ticker):
        if trade.is_short:
          if self.config["exit_pricing"]["price_side"] in ["ask", "other"]:
            if ticker["ask"] is not None:
              exit_rate = ticker["ask"]
        else:
          if self.config["exit_pricing"]["price_side"] in ["bid", "other"]:
            if ticker["bid"] is not None:
              exit_rate = ticker["bid"]

    profit_stake, profit_ratio, profit_current_stake_ratio, profit_init_ratio = self.calc_total_profit(
      trade, filled_entries, filled_exits, exit_rate
    )

    slice_amount = filled_entries[0].cost
    slice_profit = (exit_rate - filled_orders[-1].safe_price) / filled_orders[-1].safe_price
    slice_profit_entry = (exit_rate - filled_entries[-1].safe_price) / filled_entries[-1].safe_price
    slice_profit_exit = (
      ((exit_rate - filled_exits[-1].safe_price) / filled_exits[-1].safe_price) if count_of_exits > 0 else 0.0
    )

    current_stake_amount = trade.amount * current_rate

    is_rebuy = False

    rebuy_mode_stakes = self.rebuy_mode_stakes_futures if self.is_futures_mode else self.rebuy_mode_stakes_spot
    max_sub_grinds = len(rebuy_mode_stakes)
    rebuy_mode_sub_thresholds = (
      self.rebuy_mode_thresholds_futures if self.is_futures_mode else self.rebuy_mode_thresholds_spot
    )
    partial_sell = False
    sub_grind_count = 0
    total_amount = 0.0
    total_cost = 0.0
    current_open_rate = 0.0
    current_grind_stake = 0.0
    current_grind_stake_profit = 0.0
    for order in reversed(filled_orders):
      if (order.ft_order_side == "buy") and (order is not filled_orders[0]):
        sub_grind_count += 1
        total_amount += order.safe_filled
        total_cost += order.safe_filled * order.safe_price
      elif order.ft_order_side == "sell":
        if (order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) > min_stake:
          partial_sell = True
        break
    if sub_grind_count > 0:
      current_open_rate = total_cost / total_amount
      current_grind_stake = total_amount * exit_rate * (1 - trade.fee_close)
      current_grind_stake_profit = current_grind_stake - total_cost

    if (not partial_sell) and (sub_grind_count < max_sub_grinds):
      if (
        ((0 <= sub_grind_count < max_sub_grinds) and (slice_profit_entry < rebuy_mode_sub_thresholds[sub_grind_count]))
        and (last_candle["protections_long_global"] == True)
        and (last_candle["protections_long_rebuy"] == True)
        and (
          (last_candle["close_max_12"] < (last_candle["close"] * 1.14))
          and (last_candle["close_max_24"] < (last_candle["close"] * 1.20))
          and (last_candle["close_max_48"] < (last_candle["close"] * 1.26))
          and (last_candle["btc_pct_close_max_72_5m"] < 0.03)
          and (last_candle["btc_pct_close_max_24_5m"] < 0.03)
        )
        and (
          (last_candle["rsi_3"] > 10.0)
          and (last_candle["rsi_3_15m"] > 10.0)
          and (last_candle["rsi_3_1h"] > 10.0)
          and (last_candle["rsi_3_4h"] > 10.0)
          and (last_candle["rsi_14"] < 46.0)
        )
      ):
        buy_amount = (
          slice_amount * rebuy_mode_stakes[sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount > max_stake:
          buy_amount = max_stake
        if buy_amount < min_stake:
          return None
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        self.dp.send_msg(
          f"Rebuy [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        return buy_amount

    return None

  def informative_pairs(self):
    # get access to all pairs available in whitelist.
    pairs = self.dp.current_whitelist()
    # Assign tf to each pair so they can be downloaded and cached for strategy.
    informative_pairs = []
    for info_timeframe in self.info_timeframes:
      informative_pairs.extend([(pair, info_timeframe) for pair in pairs])

    if self.config["stake_currency"] in ["USDT", "BUSD", "USDC", "DAI", "TUSD", "PAX", "USD", "EUR", "GBP"]:
      if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
        btc_info_pair = f"BTC/{self.config['stake_currency']}:{self.config['stake_currency']}"
      else:
        btc_info_pair = f"BTC/{self.config['stake_currency']}"
    else:
      if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
        btc_info_pair = "BTC/USDT:USDT"
      else:
        btc_info_pair = "BTC/USDT"

    informative_pairs.extend([(btc_info_pair, btc_info_timeframe) for btc_info_timeframe in self.btc_info_timeframes])

    return informative_pairs

  def informative_1d_indicators(self, metadata: dict, info_timeframe) -> DataFrame:
    tik = time.perf_counter()
    assert self.dp, "DataProvider is required for multiple timeframes."
    # Get the informative pair
    informative_1d = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=info_timeframe)

    # Indicators
    # -----------------------------------------------------------------------------------------
    # RSI
    informative_1d["rsi_3"] = ta.RSI(informative_1d, timeperiod=3, fillna=True)
    informative_1d["rsi_14"] = ta.RSI(informative_1d, timeperiod=14)

    # EMA
    informative_1d["ema_200"] = ta.EMA(informative_1d, timeperiod=200)

    informative_1d["ema_200_dec_4"] = (informative_1d["ema_200"].isnull()) | (
      informative_1d["ema_200"] <= informative_1d["ema_200"].shift(4)
    )

    # CTI
    informative_1d["cti_20"] = pta.cti(informative_1d["close"], length=20)

    # Pivots
    (
      informative_1d["pivot"],
      informative_1d["res1"],
      informative_1d["res2"],
      informative_1d["res3"],
      informative_1d["sup1"],
      informative_1d["sup2"],
      informative_1d["sup3"],
    ) = pivot_points(informative_1d, mode="fibonacci")

    # S/R
    res_series = (
      informative_1d["high"].rolling(window=5, center=True).apply(lambda row: is_resistance(row), raw=True).shift(2)
    )
    sup_series = (
      informative_1d["low"].rolling(window=5, center=True).apply(lambda row: is_support(row), raw=True).shift(2)
    )
    informative_1d["res_level"] = Series(
      np.where(
        res_series,
        np.where(informative_1d["close"] > informative_1d["open"], informative_1d["close"], informative_1d["open"]),
        float("NaN"),
      )
    ).ffill()
    informative_1d["res_hlevel"] = Series(np.where(res_series, informative_1d["high"], float("NaN"))).ffill()
    informative_1d["sup_level"] = Series(
      np.where(
        sup_series,
        np.where(informative_1d["close"] < informative_1d["open"], informative_1d["close"], informative_1d["open"]),
        float("NaN"),
      )
    ).ffill()

    # Downtrend checks
    informative_1d["not_downtrend"] = (informative_1d["close"] > informative_1d["close"].shift(2)) | (
      informative_1d["rsi_14"] > 50.0
    )

    informative_1d["is_downtrend_3"] = (
      (informative_1d["close"] < informative_1d["open"])
      & (informative_1d["close"].shift(1) < informative_1d["open"].shift(1))
      & (informative_1d["close"].shift(2) < informative_1d["open"].shift(2))
    )

    informative_1d["is_downtrend_5"] = (
      (informative_1d["close"] < informative_1d["open"])
      & (informative_1d["close"].shift(1) < informative_1d["open"].shift(1))
      & (informative_1d["close"].shift(2) < informative_1d["open"].shift(2))
      & (informative_1d["close"].shift(3) < informative_1d["open"].shift(3))
      & (informative_1d["close"].shift(4) < informative_1d["open"].shift(4))
    )

    # Wicks
    informative_1d["top_wick_pct"] = (
      informative_1d["high"] - np.maximum(informative_1d["open"], informative_1d["close"])
    ) / np.maximum(informative_1d["open"], informative_1d["close"])
    informative_1d["bot_wick_pct"] = abs(
      (informative_1d["low"] - np.minimum(informative_1d["open"], informative_1d["close"]))
      / np.minimum(informative_1d["open"], informative_1d["close"])
    )

    # Candle change
    informative_1d["change_pct"] = (informative_1d["close"] - informative_1d["open"]) / informative_1d["open"]

    # Pump protections
    informative_1d["hl_pct_change_3"] = range_percent_change(self, informative_1d, "HL", 3)
    informative_1d["hl_pct_change_6"] = range_percent_change(self, informative_1d, "HL", 6)

    # Max highs
    informative_1d["high_max_6"] = informative_1d["high"].rolling(6).max()
    informative_1d["high_max_12"] = informative_1d["high"].rolling(12).max()

    # Performance logging
    # -----------------------------------------------------------------------------------------
    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] informative_1d_indicators took: {tok - tik:0.4f} seconds.")

    return informative_1d

  def informative_4h_indicators(self, metadata: dict, info_timeframe) -> DataFrame:
    tik = time.perf_counter()
    assert self.dp, "DataProvider is required for multiple timeframes."
    # Get the informative pair
    informative_4h = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=info_timeframe)

    # Indicators
    # -----------------------------------------------------------------------------------------
    # RSI
    informative_4h["rsi_3"] = ta.RSI(informative_4h, timeperiod=3, fillna=True)
    informative_4h["rsi_14"] = ta.RSI(informative_4h, timeperiod=14, fillna=True)

    informative_4h["rsi_14_max_3"] = informative_4h["rsi_14"].rolling(3).max()
    informative_4h["rsi_14_max_6"] = informative_4h["rsi_14"].rolling(6).max()

    # EMA
    informative_4h["ema_12"] = ta.EMA(informative_4h, timeperiod=12)
    informative_4h["ema_26"] = ta.EMA(informative_4h, timeperiod=26)
    informative_4h["ema_50"] = ta.EMA(informative_4h, timeperiod=50)
    informative_4h["ema_100"] = ta.EMA(informative_4h, timeperiod=100)
    informative_4h["ema_200"] = ta.EMA(informative_4h, timeperiod=200)

    informative_4h["ema_200_dec_24"] = (informative_4h["ema_200"].isnull()) | (
      informative_4h["ema_200"] <= informative_4h["ema_200"].shift(24)
    )

    # SMA
    informative_4h["sma_12"] = ta.SMA(informative_4h, timeperiod=12)
    informative_4h["sma_26"] = ta.SMA(informative_4h, timeperiod=26)
    informative_4h["sma_50"] = ta.SMA(informative_4h, timeperiod=50)
    informative_4h["sma_200"] = ta.SMA(informative_4h, timeperiod=200)

    # Williams %R
    informative_4h["r_14"] = williams_r(informative_4h, period=14)
    informative_4h["r_480"] = williams_r(informative_4h, period=480)

    # CTI
    informative_4h["cti_20"] = pta.cti(informative_4h["close"], length=20)

    # S/R
    res_series = (
      informative_4h["high"].rolling(window=5, center=True).apply(lambda row: is_resistance(row), raw=True).shift(2)
    )
    sup_series = (
      informative_4h["low"].rolling(window=5, center=True).apply(lambda row: is_support(row), raw=True).shift(2)
    )
    informative_4h["res_level"] = Series(
      np.where(
        res_series,
        np.where(informative_4h["close"] > informative_4h["open"], informative_4h["close"], informative_4h["open"]),
        float("NaN"),
      )
    ).ffill()
    informative_4h["res_hlevel"] = Series(np.where(res_series, informative_4h["high"], float("NaN"))).ffill()
    informative_4h["sup_level"] = Series(
      np.where(
        sup_series,
        np.where(informative_4h["close"] < informative_4h["open"], informative_4h["close"], informative_4h["open"]),
        float("NaN"),
      )
    ).ffill()

    # Downtrend checks
    informative_4h["not_downtrend"] = (informative_4h["close"] > informative_4h["close"].shift(2)) | (
      informative_4h["rsi_14"] > 50.0
    )

    informative_4h["is_downtrend_3"] = (
      (informative_4h["close"] < informative_4h["open"])
      & (informative_4h["close"].shift(1) < informative_4h["open"].shift(1))
      & (informative_4h["close"].shift(2) < informative_4h["open"].shift(2))
    )

    # Wicks
    informative_4h["top_wick_pct"] = (
      informative_4h["high"] - np.maximum(informative_4h["open"], informative_4h["close"])
    ) / np.maximum(informative_4h["open"], informative_4h["close"])

    # Candle change
    informative_4h["change_pct"] = (informative_4h["close"] - informative_4h["open"]) / informative_4h["open"]

    # Max highs
    informative_4h["high_max_3"] = informative_4h["high"].rolling(3).max()
    informative_4h["high_max_12"] = informative_4h["high"].rolling(12).max()
    informative_4h["high_max_24"] = informative_4h["high"].rolling(24).max()
    informative_4h["high_max_36"] = informative_4h["high"].rolling(36).max()
    informative_4h["high_max_48"] = informative_4h["high"].rolling(48).max()

    # Volume
    informative_4h["volume_mean_factor_6"] = informative_4h["volume"] / informative_4h["volume"].rolling(6).mean()

    # Performance logging
    # -----------------------------------------------------------------------------------------
    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] informative_1d_indicators took: {tok - tik:0.4f} seconds.")

    return informative_4h

  def informative_1h_indicators(self, metadata: dict, info_timeframe) -> DataFrame:
    tik = time.perf_counter()
    assert self.dp, "DataProvider is required for multiple timeframes."
    # Get the informative pair
    informative_1h = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=info_timeframe)

    # Indicators
    # -----------------------------------------------------------------------------------------
    # RSI
    informative_1h["rsi_3"] = ta.RSI(informative_1h, timeperiod=3)
    informative_1h["rsi_14"] = ta.RSI(informative_1h, timeperiod=14)

    # EMA
    informative_1h["ema_12"] = ta.EMA(informative_1h, timeperiod=12)
    informative_1h["ema_26"] = ta.EMA(informative_1h, timeperiod=26)
    informative_1h["ema_50"] = ta.EMA(informative_1h, timeperiod=50)
    informative_1h["ema_100"] = ta.EMA(informative_1h, timeperiod=100)
    informative_1h["ema_200"] = ta.EMA(informative_1h, timeperiod=200)

    informative_1h["ema_200_dec_48"] = (informative_1h["ema_200"].isnull()) | (
      informative_1h["ema_200"] <= informative_1h["ema_200"].shift(48)
    )

    # SMA
    informative_1h["sma_12"] = ta.SMA(informative_1h, timeperiod=12)
    informative_1h["sma_26"] = ta.SMA(informative_1h, timeperiod=26)
    informative_1h["sma_50"] = ta.SMA(informative_1h, timeperiod=50)
    informative_1h["sma_100"] = ta.SMA(informative_1h, timeperiod=100)
    informative_1h["sma_200"] = ta.SMA(informative_1h, timeperiod=200)

    # ZL MA
    informative_1h["zlma_50"] = pta.zlma(informative_1h["close"], length=50, matype="linreg", offset=0)

    informative_1h["zlma_50_dec"] = (informative_1h["zlma_50"].isnull()) | (
      informative_1h["zlma_50"] <= informative_1h["zlma_50"].shift(1)
    )

    # BB
    bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(informative_1h), window=20, stds=2)
    informative_1h["bb20_2_low"] = bollinger["lower"]
    informative_1h["bb20_2_mid"] = bollinger["mid"]
    informative_1h["bb20_2_upp"] = bollinger["upper"]

    informative_1h["bb20_2_width"] = (informative_1h["bb20_2_upp"] - informative_1h["bb20_2_low"]) / informative_1h[
      "bb20_2_mid"
    ]

    # Williams %R
    informative_1h["r_14"] = williams_r(informative_1h, period=14)
    informative_1h["r_96"] = williams_r(informative_1h, period=96)
    informative_1h["r_480"] = williams_r(informative_1h, period=480)

    # CTI
    informative_1h["cti_20"] = pta.cti(informative_1h["close"], length=20)
    informative_1h["cti_40"] = pta.cti(informative_1h["close"], length=40)

    # SAR
    informative_1h["sar"] = ta.SAR(informative_1h)

    # S/R
    res_series = (
      informative_1h["high"].rolling(window=5, center=True).apply(lambda row: is_resistance(row), raw=True).shift(2)
    )
    sup_series = (
      informative_1h["low"].rolling(window=5, center=True).apply(lambda row: is_support(row), raw=True).shift(2)
    )
    informative_1h["res_level"] = Series(
      np.where(
        res_series,
        np.where(informative_1h["close"] > informative_1h["open"], informative_1h["close"], informative_1h["open"]),
        float("NaN"),
      )
    ).ffill()
    informative_1h["res_hlevel"] = Series(np.where(res_series, informative_1h["high"], float("NaN"))).ffill()
    informative_1h["sup_level"] = Series(
      np.where(
        sup_series,
        np.where(informative_1h["close"] < informative_1h["open"], informative_1h["close"], informative_1h["open"]),
        float("NaN"),
      )
    ).ffill()

    # Pump protections
    informative_1h["hl_pct_change_48"] = range_percent_change(self, informative_1h, "HL", 48)
    informative_1h["hl_pct_change_36"] = range_percent_change(self, informative_1h, "HL", 36)
    informative_1h["hl_pct_change_24"] = range_percent_change(self, informative_1h, "HL", 24)
    informative_1h["hl_pct_change_12"] = range_percent_change(self, informative_1h, "HL", 12)
    informative_1h["hl_pct_change_6"] = range_percent_change(self, informative_1h, "HL", 6)

    # Downtrend checks
    informative_1h["not_downtrend"] = (informative_1h["close"] > informative_1h["close"].shift(2)) | (
      informative_1h["rsi_14"] > 50.0
    )

    informative_1h["is_downtrend_3"] = (
      (informative_1h["close"] < informative_1h["open"])
      & (informative_1h["close"].shift(1) < informative_1h["open"].shift(1))
      & (informative_1h["close"].shift(2) < informative_1h["open"].shift(2))
    )

    informative_1h["is_downtrend_5"] = (
      (informative_1h["close"] < informative_1h["open"])
      & (informative_1h["close"].shift(1) < informative_1h["open"].shift(1))
      & (informative_1h["close"].shift(2) < informative_1h["open"].shift(2))
      & (informative_1h["close"].shift(3) < informative_1h["open"].shift(3))
      & (informative_1h["close"].shift(4) < informative_1h["open"].shift(4))
    )

    # Wicks
    informative_1h["top_wick_pct"] = (
      informative_1h["high"] - np.maximum(informative_1h["open"], informative_1h["close"])
    ) / np.maximum(informative_1h["open"], informative_1h["close"])

    # Candle change
    informative_1h["change_pct"] = (informative_1h["close"] - informative_1h["open"]) / informative_1h["open"]

    # Max highs
    informative_1h["high_max_3"] = informative_1h["high"].rolling(3).max()
    informative_1h["high_max_6"] = informative_1h["high"].rolling(6).max()
    informative_1h["high_max_12"] = informative_1h["high"].rolling(12).max()
    informative_1h["high_max_24"] = informative_1h["high"].rolling(24).max()
    informative_1h["high_max_36"] = informative_1h["high"].rolling(36).max()
    informative_1h["high_max_48"] = informative_1h["high"].rolling(48).max()

    # Max lows
    informative_1h["low_min_3"] = informative_1h["low"].rolling(3).min()
    informative_1h["low_min_12"] = informative_1h["low"].rolling(12).min()
    informative_1h["low_min_24"] = informative_1h["low"].rolling(24).min()

    # Volume
    informative_1h["volume_mean_factor_12"] = informative_1h["volume"] / informative_1h["volume"].rolling(12).mean()

    # Performance logging
    # -----------------------------------------------------------------------------------------
    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] informative_1h_indicators took: {tok - tik:0.4f} seconds.")

    return informative_1h

  def informative_15m_indicators(self, metadata: dict, info_timeframe) -> DataFrame:
    tik = time.perf_counter()
    assert self.dp, "DataProvider is required for multiple timeframes."

    # Get the informative pair
    informative_15m = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=info_timeframe)

    # Indicators
    # -----------------------------------------------------------------------------------------

    # RSI
    informative_15m["rsi_3"] = ta.RSI(informative_15m, timeperiod=3)
    informative_15m["rsi_14"] = ta.RSI(informative_15m, timeperiod=14)

    # EMA
    informative_15m["ema_12"] = ta.EMA(informative_15m, timeperiod=12)
    informative_15m["ema_26"] = ta.EMA(informative_15m, timeperiod=26)
    informative_15m["ema_200"] = ta.EMA(informative_15m, timeperiod=200)

    informative_15m["ema_200_dec_24"] = (informative_15m["ema_200"].isnull()) | (
      informative_15m["ema_200"] <= informative_15m["ema_200"].shift(24)
    )

    # SMA
    informative_15m["sma_200"] = ta.SMA(informative_15m, timeperiod=200)

    # ZL MA
    informative_15m["zlma_50"] = pta.zlma(informative_15m["close"], length=50, matype="linreg", offset=0)

    informative_15m["zlma_50_dec"] = (informative_15m["zlma_50"].isnull()) | (
      informative_15m["zlma_50"] <= informative_15m["zlma_50"].shift(1)
    )

    # BB - 20 STD2
    bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(informative_15m), window=20, stds=2)
    informative_15m["bb20_2_low"] = bollinger["lower"]
    informative_15m["bb20_2_mid"] = bollinger["mid"]
    informative_15m["bb20_2_upp"] = bollinger["upper"]

    # CTI
    informative_15m["cti_20"] = pta.cti(informative_15m["close"], length=20)

    # EWO
    informative_15m["ewo_50_200"] = ewo(informative_15m, 50, 200)

    # Downtrend check
    informative_15m["not_downtrend"] = (
      (informative_15m["close"] > informative_15m["open"])
      | (informative_15m["close"].shift(1) > informative_15m["open"].shift(1))
      | (informative_15m["close"].shift(2) > informative_15m["open"].shift(2))
      | (informative_15m["rsi_14"] > 50.0)
      | (informative_15m["rsi_3"] > 25.0)
    )

    # Volume
    informative_15m["volume_mean_factor_12"] = informative_15m["volume"] / informative_15m["volume"].rolling(12).mean()

    # Performance logging
    # -----------------------------------------------------------------------------------------
    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] informative_15m_indicators took: {tok - tik:0.4f} seconds.")

    return informative_15m

  # Coin Pair Base Timeframe Indicators
  # ---------------------------------------------------------------------------------------------
  def base_tf_5m_indicators(self, metadata: dict, dataframe: DataFrame) -> DataFrame:
    tik = time.perf_counter()

    # Indicators
    # -----------------------------------------------------------------------------------------
    # RSI
    dataframe["rsi_3"] = ta.RSI(dataframe, timeperiod=3)
    dataframe["rsi_14"] = ta.RSI(dataframe, timeperiod=14)
    dataframe["rsi_20"] = ta.RSI(dataframe, timeperiod=20)

    # EMA
    dataframe["ema_12"] = ta.EMA(dataframe, timeperiod=12)
    dataframe["ema_16"] = ta.EMA(dataframe, timeperiod=16)
    dataframe["ema_26"] = ta.EMA(dataframe, timeperiod=26)
    dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
    dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)

    dataframe["ema_200_dec_24"] = (dataframe["ema_200"].isnull()) | (
      dataframe["ema_200"] <= dataframe["ema_200"].shift(24)
    )

    dataframe["ema_200_pct_change_144"] = (dataframe["ema_200"] - dataframe["ema_200"].shift(144)) / dataframe[
      "ema_200"
    ].shift(144)
    dataframe["ema_200_pct_change_288"] = (dataframe["ema_200"] - dataframe["ema_200"].shift(288)) / dataframe[
      "ema_200"
    ].shift(288)

    # SMA
    dataframe["sma_16"] = ta.SMA(dataframe, timeperiod=16)
    dataframe["sma_50"] = ta.SMA(dataframe, timeperiod=50)
    dataframe["sma_200"] = ta.SMA(dataframe, timeperiod=200)

    # BB 20 - STD2
    bb_20_std2 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
    dataframe["bb20_2_low"] = bb_20_std2["lower"]
    dataframe["bb20_2_mid"] = bb_20_std2["mid"]
    dataframe["bb20_2_upp"] = bb_20_std2["upper"]

    # BB 40 - STD2
    bb_40_std2 = qtpylib.bollinger_bands(dataframe["close"], window=40, stds=2)
    dataframe["bb40_2_low"] = bb_40_std2["lower"]
    dataframe["bb40_2_mid"] = bb_40_std2["mid"]
    dataframe["bb40_2_delta"] = (bb_40_std2["mid"] - dataframe["bb40_2_low"]).abs()
    dataframe["bb40_2_tail"] = (dataframe["close"] - dataframe["bb40_2_low"]).abs()

    # Williams %R
    dataframe["r_14"] = williams_r(dataframe, period=14)
    dataframe["r_480"] = williams_r(dataframe, period=480)

    # CTI
    dataframe["cti_20"] = pta.cti(dataframe["close"], length=20)

    # SAR
    dataframe["sar"] = ta.SAR(dataframe)

    # CCI
    dataframe["cci_20"] = ta.CCI(dataframe, source="hlc3", timeperiod=20)

    # TSI
    tsi = pta.tsi(dataframe["close"])
    dataframe["tsi"] = tsi.iloc[:, 0]
    dataframe["tsi_signal"] = tsi.iloc[:, 1]

    # EWO
    dataframe["ewo_50_200"] = ewo(dataframe, 50, 200)

    # Hull Moving Average
    dataframe["hma_55"] = pta.hma(dataframe["close"], length=55)
    dataframe["hma_70"] = pta.hma(dataframe["close"], length=70)

    dataframe["hma_55_buy"] = (dataframe["hma_55"] > dataframe["hma_55"].shift(1)) & (
      dataframe["hma_55"].shift(1) < dataframe["hma_55"].shift(2)
    )
    dataframe["hma_70_buy"] = (dataframe["hma_70"] > dataframe["hma_70"].shift(1)) & (
      dataframe["hma_70"].shift(1) < dataframe["hma_70"].shift(2)
    )

    # Heiken Ashi
    heikinashi = qtpylib.heikinashi(dataframe)
    dataframe["ha_open"] = heikinashi["open"]
    dataframe["ha_close"] = heikinashi["close"]
    dataframe["ha_high"] = heikinashi["high"]
    dataframe["ha_low"] = heikinashi["low"]

    # Dip protection
    dataframe["tpct_change_0"] = top_percent_change(self, dataframe, 0)
    dataframe["tpct_change_2"] = top_percent_change(self, dataframe, 2)

    # Candle change
    dataframe["change_pct"] = (dataframe["close"] - dataframe["open"]) / dataframe["open"]

    # Close max
    dataframe["close_max_12"] = dataframe["close"].rolling(12).max()
    dataframe["close_max_24"] = dataframe["close"].rolling(24).max()
    dataframe["close_max_48"] = dataframe["close"].rolling(48).max()

    # Close min
    dataframe["close_min_12"] = dataframe["close"].rolling(12).min()
    dataframe["close_min_24"] = dataframe["close"].rolling(24).min()

    # Close delta
    dataframe["close_delta"] = (dataframe["close"] - dataframe["close"].shift()).abs()

    # Number of empty candles in the last 288
    dataframe["num_empty_288"] = (dataframe["volume"] <= 0).rolling(window=288, min_periods=288).sum()

    # For sell checks
    dataframe["crossed_below_ema_12_26"] = qtpylib.crossed_below(dataframe["ema_12"], dataframe["ema_26"])

    # Global protections
    # -----------------------------------------------------------------------------------------
    if not self.config["runmode"].value in ("live", "dry_run"):
      # Backtest age filter
      dataframe["bt_agefilter_ok"] = False
      dataframe.loc[dataframe.index > (12 * 24 * self.bt_min_age_days), "bt_agefilter_ok"] = True
    else:
      # Exchange downtime protection
      dataframe["live_data_ok"] = dataframe["volume"].rolling(window=72, min_periods=72).min() > 0

    # Performance logging
    # -----------------------------------------------------------------------------------------
    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] base_tf_5m_indicators took: {tok - tik:0.4f} seconds.")

    return dataframe

  # Coin Pair Indicator Switch Case
  # ---------------------------------------------------------------------------------------------
  def info_switcher(self, metadata: dict, info_timeframe) -> DataFrame:
    if info_timeframe == "1d":
      return self.informative_1d_indicators(metadata, info_timeframe)
    elif info_timeframe == "4h":
      return self.informative_4h_indicators(metadata, info_timeframe)
    elif info_timeframe == "1h":
      return self.informative_1h_indicators(metadata, info_timeframe)
    elif info_timeframe == "15m":
      return self.informative_15m_indicators(metadata, info_timeframe)
    else:
      raise RuntimeError(f"{info_timeframe} not supported as informative timeframe for BTC pair.")

  # BTC 1D Indicators
  # ---------------------------------------------------------------------------------------------
  def btc_info_1d_indicators(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    btc_info_1d = self.dp.get_pair_dataframe(btc_info_pair, btc_info_timeframe)
    # Indicators
    # -----------------------------------------------------------------------------------------
    btc_info_1d["rsi_14"] = ta.RSI(btc_info_1d, timeperiod=14)
    # btc_info_1d['pivot'], btc_info_1d['res1'], btc_info_1d['res2'], btc_info_1d['res3'], btc_info_1d['sup1'], btc_info_1d['sup2'], btc_info_1d['sup3'] = pivot_points(btc_info_1d, mode='fibonacci')

    # Add prefix
    # -----------------------------------------------------------------------------------------
    ignore_columns = ["date"]
    btc_info_1d.rename(columns=lambda s: f"btc_{s}" if s not in ignore_columns else s, inplace=True)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] btc_info_1d_indicators took: {tok - tik:0.4f} seconds.")

    return btc_info_1d

  # BTC 4h Indicators
  # ---------------------------------------------------------------------------------------------
  def btc_info_4h_indicators(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    btc_info_4h = self.dp.get_pair_dataframe(btc_info_pair, btc_info_timeframe)
    # Indicators
    # -----------------------------------------------------------------------------------------
    # RSI
    btc_info_4h["rsi_14"] = ta.RSI(btc_info_4h, timeperiod=14)

    # SMA
    btc_info_4h["sma_200"] = ta.SMA(btc_info_4h, timeperiod=200)

    # Bull market or not
    btc_info_4h["is_bull"] = btc_info_4h["close"] > btc_info_4h["sma_200"]

    # Add prefix
    # -----------------------------------------------------------------------------------------
    ignore_columns = ["date"]
    btc_info_4h.rename(columns=lambda s: f"btc_{s}" if s not in ignore_columns else s, inplace=True)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] btc_info_4h_indicators took: {tok - tik:0.4f} seconds.")

    return btc_info_4h

  # BTC 1h Indicators
  # ---------------------------------------------------------------------------------------------
  def btc_info_1h_indicators(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    btc_info_1h = self.dp.get_pair_dataframe(btc_info_pair, btc_info_timeframe)
    # Indicators
    # -----------------------------------------------------------------------------------------
    # RSI
    btc_info_1h["rsi_14"] = ta.RSI(btc_info_1h, timeperiod=14)

    btc_info_1h["not_downtrend"] = (btc_info_1h["close"] > btc_info_1h["close"].shift(2)) | (
      btc_info_1h["rsi_14"] > 50
    )

    # Add prefix
    # -----------------------------------------------------------------------------------------
    ignore_columns = ["date"]
    btc_info_1h.rename(columns=lambda s: f"btc_{s}" if s not in ignore_columns else s, inplace=True)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] btc_info_1h_indicators took: {tok - tik:0.4f} seconds.")

    return btc_info_1h

  # BTC 15m Indicators
  # ---------------------------------------------------------------------------------------------
  def btc_info_15m_indicators(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    btc_info_15m = self.dp.get_pair_dataframe(btc_info_pair, btc_info_timeframe)
    # Indicators
    # -----------------------------------------------------------------------------------------
    btc_info_15m["rsi_14"] = ta.RSI(btc_info_15m, timeperiod=14)

    # Add prefix
    # -----------------------------------------------------------------------------------------
    ignore_columns = ["date"]
    btc_info_15m.rename(columns=lambda s: f"btc_{s}" if s not in ignore_columns else s, inplace=True)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] btc_info_15m_indicators took: {tok - tik:0.4f} seconds.")

    return btc_info_15m

  # BTC 5m Indicators
  # ---------------------------------------------------------------------------------------------
  def btc_info_5m_indicators(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    btc_info_5m = self.dp.get_pair_dataframe(btc_info_pair, btc_info_timeframe)
    # Indicators
    # -----------------------------------------------------------------------------------------

    # RSI
    btc_info_5m["rsi_14"] = ta.RSI(btc_info_5m, timeperiod=14)

    # Close max
    btc_info_5m["close_max_24"] = btc_info_5m["close"].rolling(24).max()
    btc_info_5m["close_max_72"] = btc_info_5m["close"].rolling(72).max()

    btc_info_5m["pct_close_max_24"] = (btc_info_5m["close_max_24"] - btc_info_5m["close"]) / btc_info_5m["close"]
    btc_info_5m["pct_close_max_72"] = (btc_info_5m["close_max_72"] - btc_info_5m["close"]) / btc_info_5m["close"]

    # Add prefix
    # -----------------------------------------------------------------------------------------
    ignore_columns = ["date"]
    btc_info_5m.rename(columns=lambda s: f"btc_{s}" if s not in ignore_columns else s, inplace=True)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] btc_info_5m_indicators took: {tok - tik:0.4f} seconds.")

    return btc_info_5m

  # BTC Indicator Switch Case
  # ---------------------------------------------------------------------------------------------
  def btc_info_switcher(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    if btc_info_timeframe == "1d":
      return self.btc_info_1d_indicators(btc_info_pair, btc_info_timeframe, metadata)
    elif btc_info_timeframe == "4h":
      return self.btc_info_4h_indicators(btc_info_pair, btc_info_timeframe, metadata)
    elif btc_info_timeframe == "1h":
      return self.btc_info_1h_indicators(btc_info_pair, btc_info_timeframe, metadata)
    elif btc_info_timeframe == "15m":
      return self.btc_info_15m_indicators(btc_info_pair, btc_info_timeframe, metadata)
    elif btc_info_timeframe == "5m":
      return self.btc_info_5m_indicators(btc_info_pair, btc_info_timeframe, metadata)
    else:
      raise RuntimeError(f"{btc_info_timeframe} not supported as informative timeframe for BTC pair.")

  def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    """
        --> BTC informative indicators
        ___________________________________________________________________________________________
        """
    if self.config["stake_currency"] in ["USDT", "BUSD", "USDC", "DAI", "TUSD", "PAX", "USD", "EUR", "GBP"]:
      if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
        btc_info_pair = f"BTC/{self.config['stake_currency']}:{self.config['stake_currency']}"
      else:
        btc_info_pair = f"BTC/{self.config['stake_currency']}"
    else:
      if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
        btc_info_pair = "BTC/USDT:USDT"
      else:
        btc_info_pair = "BTC/USDT"

    for btc_info_timeframe in self.btc_info_timeframes:
      btc_informative = self.btc_info_switcher(btc_info_pair, btc_info_timeframe, metadata)
      dataframe = merge_informative_pair(dataframe, btc_informative, self.timeframe, btc_info_timeframe, ffill=True)
      # Customize what we drop - in case we need to maintain some BTC informative ohlcv data
      # Default drop all
      drop_columns = {
        "1d": [f"btc_{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "4h": [f"btc_{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "1h": [f"btc_{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "15m": [f"btc_{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "5m": [f"btc_{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
      }.get(
        btc_info_timeframe,
        [f"{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
      )
      drop_columns.append(f"date_{btc_info_timeframe}")
      dataframe.drop(columns=dataframe.columns.intersection(drop_columns), inplace=True)

    """
        --> Indicators on informative timeframes
        ___________________________________________________________________________________________
        """
    for info_timeframe in self.info_timeframes:
      info_indicators = self.info_switcher(metadata, info_timeframe)
      dataframe = merge_informative_pair(dataframe, info_indicators, self.timeframe, info_timeframe, ffill=True)
      # Customize what we drop - in case we need to maintain some informative timeframe ohlcv data
      # Default drop all except base timeframe ohlcv data
      drop_columns = {
        "1d": [f"{s}_{info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "4h": [f"{s}_{info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "1h": [f"{s}_{info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "15m": [f"{s}_{info_timeframe}" for s in ["date", "high", "low", "volume"]],
      }.get(info_timeframe, [f"{s}_{info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]])
      dataframe.drop(columns=dataframe.columns.intersection(drop_columns), inplace=True)

    """
        --> The indicators for the base timeframe  (5m)
        ___________________________________________________________________________________________
        """
    dataframe = self.base_tf_5m_indicators(metadata, dataframe)

    # Global protections
    dataframe["protections_long_global"] = (
      # current 4h red with top wick, previous 4h red, 4h overbought
      (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["top_wick_pct_4h"] < 0.04)
        | (dataframe["change_pct_4h"].shift(48) > -0.04)
        | (dataframe["cti_20_4h"] < 0.8)
      )
      &
      # current 1h red, current 4h green, 4h overbought
      (
        (dataframe["change_pct_1h"] > -0.04)
        | (dataframe["change_pct_4h"] < 0.08)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 70.0)
      )
      &
      # current 4h red, previous 4h green, 4h overbought
      (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["change_pct_4h"].shift(48) < 0.04)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 70.0)
      )
      &
      # current 4h red, previous 4h red, 2nd previous 4h long green, 4h overbought
      (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["change_pct_4h"].shift(48) > -0.04)
        | (dataframe["change_pct_4h"].shift(96) < 0.16)
        | (dataframe["cti_20_4h"] < 0.5)
      )
      &
      # current 4h red, overbought 4h, sudden rise 4h (and now coming down)
      (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["rsi_14_max_6_4h"] < 80.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (((dataframe["ema_12_4h"] - dataframe["ema_26_4h"]) / dataframe["ema_26_4h"]) < 0.08)
      )
      # current 4h red, previous 4h green with top wick, 4h overbought
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_4h"].shift(48) < 0.08)
        | (dataframe["top_wick_pct_4h"].shift(48) < 0.08)
        | (dataframe["cti_20_4h"] < 0.5)
      )
      # current 4h long red, previous 4h red, 2nd previous 4h long green, 4h overbought
      & (
        (dataframe["change_pct_4h"] > -0.08)
        | (dataframe["change_pct_4h"].shift(48) > -0.01)
        | (dataframe["change_pct_4h"].shift(96) < 0.08)
        | (dataframe["cti_20_4h"] < 0.5)
      )
      # current 1h red, current 4h long green with top wick, 1h overbought
      & (
        (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["change_pct_4h"] < 0.08)
        | (dataframe["top_wick_pct_4h"] < 0.04)
        | (dataframe["cti_20_1h"] < 0.7)
      )
      # current 1h red, 1h overbought, 1d overbought, 1h descending
      & (
        (dataframe["change_pct_1h"] > -0.04)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h overbought, 1d overbought, 1h descending
      & (
        (dataframe["rsi_14_1h"] < 70.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d green, 4h overbought, 4h descending
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["rsi_14_4h"] < 70.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 4h red, previous 4h green, 1d overbought
      & (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["change_pct_4h"].shift(48) < 0.04)
        | (dataframe["rsi_14_1d"] < 70.0)
        | (dataframe["cti_20_1d"] < 0.5)
      )
      # 1h overbought, 4h overbought, 1d overbought
      & (
        (dataframe["r_480_1h"] < -20.0)
        | (dataframe["r_480_4h"] < -20.0)
        | (dataframe["rsi_14_1d"] < 80.0)
        | (dataframe["cti_20_1d"] < 0.85)
      )
      # current 4h red, previous 4h red, 2nd previous 4h green with top wick, 4h overbought
      & (
        (dataframe["change_pct_4h"] > -0.0)
        | (dataframe["change_pct_4h"].shift(48) > -0.0)
        | (dataframe["change_pct_4h"].shift(96) < 0.06)
        | (dataframe["top_wick_pct_4h"].shift(96) < 0.06)
        | (dataframe["cti_20_4h"] < 0.7)
      )
      # current 4h red, previous 4h red, 2nd previous 4h green, 4h overbought
      & (
        (dataframe["change_pct_4h"] > -0.0)
        | (dataframe["change_pct_4h"].shift(48) > -0.0)
        | (dataframe["change_pct_4h"].shift(96) < 0.06)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_4h"] < 0.5)
      )
      # current 1d green with top wick, current & previous 4h red, 4h overbought
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["change_pct_4h"] > -0.0)
        | (dataframe["change_pct_4h"].shift(48) > -0.0)
        | (dataframe["cti_20_4h"] < 0.7)
      )
      # current 1h red, 1h downtrend, 15m move down, 1h move down, 1h downtrend, 4h downtrend
      & (
        (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 4h downtrend, 4h move down, 1d overbought
      & (
        (dataframe["is_downtrend_3_4h"] == False)
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_4h"] > 16.0)
        | (dataframe["cti_20_1d"] < 0.7)
      )
      # 4h red with top wick, 1h downtrend, 1d overbought
      & (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["top_wick_pct_4h"] < 0.04)
        | (dataframe["is_downtrend_3_1h"] == False)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # current 1h red, previous 1h red, 4h overbought
      & (
        (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["change_pct_1h"].shift(12) > -0.01)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_max_6_4h"] < 70.0)
      )
      # current 1d long green, current 4h red, 1h high, 4h high, 1h downtrend, 4h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.16)
        | (dataframe["change_pct_4h"] > -0.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 4h red, previous 4h red, 2nd previous 4h green with top wick, 4h overbought
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_4h"].shift(48) > -0.01)
        | (dataframe["change_pct_4h"].shift(96) < 0.04)
        | (dataframe["top_wick_pct_4h"].shift(96) < 0.04)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_max_6_4h"] < 70.0)
      )
      # 5m & 15m strond down move, 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["cti_20_15m"] < -0.8)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m downtrend, 5m & 15m strong down move, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 4.0)
        | (dataframe["rsi_3_15m"] > 4.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 4h strong down move, 1h & 4h downtrend
      & (
        (dataframe["rsi_3_4h"] > 4.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h downtrend, 1h strong down move, 1d overbought
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_14_1d"] < 70.0)
        | (dataframe["cti_20_1d"] < 0.8)
      )
      # 15m strong down move, 15m still dropping, 5m & 15m & 4h & 1d downtrend
      & (
        (dataframe["rsi_3_15m"] > 8.0)
        | (dataframe["cti_20_15m"] < -0.8)
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 15m still dropping, 1h & 4h down move, 5m & 15m & 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["cti_20_15m"] < -0.7)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m & 1h & 4h downtrend, 5m & 15m strong down move, 1h & 4h still dropping, 5m & 15m & 1h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_14_15m"] < 20.0)
        | (dataframe["cti_20_1h"] < -0.8)
        | (dataframe["cti_20_4h"] < -0.8)
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4h long top wick, current 1h red, 15m down move, 1h & 4h still high
      & (
        (dataframe["top_wick_pct_4h"] < 0.08)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["cti_20_4h"] < -0.0)
      )
      # 1h down move, 1h & 4h still high, 5m downtrend
      & (
        (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 70.0)
        | (dataframe["ema_200_dec_24"] == False)
      )
      # current 4h red, 1h & 4h still high, 1d overbought, 4h overbought
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_1d"] < 70.0)
        | (dataframe["rsi_14_max_3_4h"] < 70.0)
      )
      # current 1d long green, current 1h red, 1h still not low enough, 4h high
      & (
        (dataframe["change_pct_1d"] < 0.16)
        | (dataframe["change_pct_1h"] > -0.0)
        | (dataframe["cti_20_1h"] < -0.8)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_max_3_4h"] < 70.0)
      )
      # current 1d red, 1h & 4h downtrend, 15m & 1h & 4h down move, 4h still dropping, 1d high
      & (
        (dataframe["change_pct_1d"] > -0.06)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["cti_20_4h"] < -0.8)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["cti_20_1d"] < 0.5)
      )
      # current 4h long green, 1h downtrend, 15m down move, 1h still high
      & (
        (dataframe["change_pct_4h"] < 0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 15m & 1h downtrend, 15m & 1h strong down move, 15m & 1h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["ema_200_dec_24_15m"] == False)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # currend 1d green, 4h & 1d overbought
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["cti_20_4h"] < 0.9)
        | (dataframe["rsi_14_4h"] < 75.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 80.0)
      )
      # current 1d long red, previous 1d green, 1h & 4h downtrend, 5m & 15m & 1h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.16)
        | (dataframe["change_pct_1d"].shift(288) < 0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 15m & 1h & 4h downtrend, 15m & 1h & 4h down move
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_14_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_3_4h"] > 20.0)
      )
      # current 5m strong down move, 1h & 1d high, 5m & 15m downtrend
      & (
        (dataframe["rsi_3"] > 8.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["cti_20_1d"] < 0.9)
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
      )
      # 15m & 1h downtrend, 4h high, 4h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h downtrend, 1h dropping, 4h still high, 5m & 15m downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_1h"] < -0.8)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
      )
      # current 4h green with top wick, 15m still high, 4h overbought, 4h downtrend
      & (
        (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["top_wick_pct_4h"] < 0.04)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d red, 1h downtrend, 15m down move, 4h down move & still high, 1d overbought
      & (
        (dataframe["change_pct_1d"] > -0.06)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["cti_20_1d"] < 0.7)
      )
      # current 4h red, previous 4h green, 15m strong down move, 4h overbought
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_4h"].shift(48) < 0.01)
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_max_3_4h"] < 70.0)
      )
      # current 1d green, 15m & 1h down move, 1d overbought
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["cti_20_1d"] < 0.9)
      )
      # 15m & 1h downtrend, 15m strong down move, 4h overbought
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["cti_20_4h"] < 0.8)
      )
      # current 4h green with top wick, 15m down move, 4h overbought & high
      & (
        (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_max_3_4h"] < 70.0)
      )
      # 15m & 1h & 4h downtrend, 15m strong down move
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 3.0)
        | (dataframe["cti_20_1h"] < -0.7)
      )
      # 15m & 1h & 4h downtrend, 15m down move & still high, 1d overbought
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_14_15m"] < 26.0)
        | (dataframe["cti_20_1d"] < 0.9)
      )
      # 15m downtrend, 5m & 15m downmove, 15m still high, 1d overbought
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 4.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
      )
      # current 4h red, 1h downtrend, 4h overbought
      & (
        (dataframe["change_pct_4h"] > -0.06)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_max_6_4h"] < 80.0)
      )
      # 15m & 1h downtrend, 15m & 1h downmove, 1d high, 1d downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m down move, 15m & 4h still high, 1d overbought, 5m & 15m downtrend, drop in last 48h
      & (
        (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_1d"] < 65.0)
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
        | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.24))
      )
      # 1h & 4h downtrend, 5m & 15m downmove
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 4.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d green with top wick, 15m downtrend, 1h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["top_wick_pct_1d"] < 0.04)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["cti_20_1d"] < 0.7)
      )
      # current 1h long red, 1h downtrend, 4h still high, 4h & 1d downtrend
      & (
        (dataframe["change_pct_1h"] > -0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1d downtrend, 1h & 4h still low, 1d still high, drop in last 6 days
      & (
        (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # 15m downtrend, 15m downmove, 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
      )
      # current 4h red, previous 4h long green, 1h & 4h overbought
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_4h"].shift(48) < 0.08)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_max_3_4h"] < 70.0)
      )
      # current 1d red, 1d & 4h downtrend, 15m & 1h & 4h downmove
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_3_4h"] > 10.0)
      )
      # current 4h red with top wick, 1h downtrend, 15m & 1h downmove, 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 1d green with top wick, 15m & 1h downtrend, 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # current 15m & 1h downtrend, 4h overbought
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 70.0)
      )
      # current 1d red with top wick, previous 1d green with top wick, 1h & 4h & 1d still high, pump in last 6 days
      & (
        (dataframe["change_pct_1d"] > -0.04)
        | (dataframe["top_wick_pct_1d"] < 0.04)
        | (dataframe["change_pct_1d"].shift(288) < 0.04)
        | (dataframe["top_wick_pct_1d"].shift(288) < 0.04)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["hl_pct_change_6_1d"] < 0.5)
      )
      # 15m downtrend, 5m & 15m downmove, 1h & 4h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # 15m downtrend, 15m stil high, 1d overbought
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 15m downtrend, 15m stil high, 15m downmove, 1h & 4h overbought
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # current 1d red, 1h downtrend, 15m downmove, 1h & 4h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.12)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d green with top wick, current 4h red, 1h downtrend, 4h & 1d overbought
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["change_pct_4h"] > -0.0)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 1d green with top witck, current 4h red, 4h overbought
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["rsi_14_max_3_4h"] < 70.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d green with top wick, 15m downtrend, 15m downmove, 4h overbought
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # 1h & 4h downtrend, 15m downmove, 4h * 1d still high, 1h downtrend, drop in last 48 hours
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["high_max_48_4h"] < (dataframe["close"] * 1.4))
      )
      # current 1d long green, current 4h red, 1h downtrend, 4h & 1d overbought
      & (
        (dataframe["change_pct_1d"] < 0.16)
        | (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # current 1d green with top wick, current 4h green, 15m & 1h & 4h still high
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["top_wick_pct_1d"] < 0.06)
        | (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.7)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 40.0)
      )
      # current 1d red, 1h downtrend, 15m downmove, 1h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["cti_20_1h"] < 0.25)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
      )
      # 1h downtrend, 15m & 1h downmove, 4h & 1d still high, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < -0.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 5m & 15m & 1h & 4h downmove, 4h still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 30.0)
      )
      # 1h downtrend, 1h donwmove, 4h still high, 1d overbought
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # 1h downtrend, 1d still high, strong pump in last 6 days
      & ((dataframe["not_downtrend_1h"]) | (dataframe["cti_20_1d"] < 0.5) | (dataframe["hl_pct_change_6_1d"] < 3.0))
      # current 5m red, 1h & 4h downtrend, 15m still high, 5m & 1h & 4h downmove, 1h downtrend
      & (
        (dataframe["change_pct"] > -0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1d red, 1h downtrend, 15m & 1h & 4h still high
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
      )
      # current 1d red with top wick, previous 1d red, 14m downmove, 1h & 1d still high, pump in last 6 days
      & (
        (dataframe["change_pct_1d"] > -0.04)
        | (dataframe["top_wick_pct_1d"] < 0.04)
        | (dataframe["change_pct_1d"].shift(288) > -0.04)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["cti_20_1h"] < -0.7)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["hl_pct_change_6_1d"] < 0.5)
      )
      # current 1d red, 1h & 4h downtrend, 5m downmove, 15m still high, 4h downmove
      & (
        (dataframe["change_pct_1d"] > -0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["cti_20_15m"] < -0.8)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_3_4h"] > 20.0)
      )
      # current 4h red, 1h downtrend, 4m downmove, 15m & 1h & 4h * 1d still high, drop in last 6 days
      & (
        (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # current 1d long red, 5m downmove, 1h & 4h downtrend, drops in last 6 days
      & (
        (dataframe["change_pct_1d"] > -0.12)
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.7))
      )
      # current 1d red, previous 1d long green, 4h overbought, 1d still high, pump in last 6 days
      & (
        (dataframe["change_pct_1d"] > -0.01)
        | (dataframe["change_pct_1d"].shift(288) < 0.12)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_max_3_4h"] < 70.0)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["hl_pct_change_6_1d"] < 0.5)
      )
      # current 1d red, 1h downtrend, 15m & 1d still high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.12)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4h red, 1h & 4h downtrend, 15m & 1h & 4h downmove, 1d still high
      & (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 1d red, previous 1d long green with long top wick, 1h donwtremd, 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.01)
        | (dataframe["change_pct_1d"].shift(288) < 0.16)
        | (dataframe["top_wick_pct_1d"].shift(288) < 0.16)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
      )
      # current 1d long green with long top wick, 15m downmove, 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.16)
        | (dataframe["top_wick_pct_1d"] < 0.16)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # 5m & 15m downmove, 15m & 1h & 4h still high, 1h downtrend, drop in last 6 days
      & (
        (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # current 1d green with top wick, 1h downtrend, 15m & 1h donwmove, 4h & 1d still high, 4h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["top_wick_pct_1d"] < 0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h & 4h downtrend, 1h still high, 1h & 4h donwmove, 1d still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["cti_20_1h"] < -0.7)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 15m downtrend, 15m strong downmove, 1h & 4h high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 60.0)
      )
      # current 1d long red, 1h & 4h downtrend, 1h & 4h downmove
      & (
        (dataframe["change_pct_1d"] > -0.12)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_3_4h"] > 16.0)
      )
      # current 1d red, 1d & 1h & 4h donwtrend, 5m downmove, 15m & 1d still high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.04)
        | (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_14_15m"] < 26.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d green with top wick, 1h & 4h & 1d still high, drop in last 6 days
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["top_wick_pct_1d"] < 0.06)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # 15m & 1h & 4h downtrend, 15m & 1h & 4h downmove, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m downtrend, 15m downmove, 1h & 4h high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # current 5m red, 5m strong downmove
      & ((dataframe["change_pct"] > -0.03) | (dataframe["rsi_3"] > 4.0))
      # current 4h red, previous 4h green, 1h & 4h high, 4h downtrend
      & (
        (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["change_pct_4h"].shift(48) < 0.02)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1h red, 5m & 15 & 1h still high, 4h overbought, 4h downtrend
      & (
        (dataframe["change_pct_1h"] > -0.0)
        | (dataframe["rsi_14"] < 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 65.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d long green with long top wick, 4h red, 1h & 4h downtrend, 4h still high
      & (
        (dataframe["change_pct_1d"] < 0.16)
        | (dataframe["top_wick_pct_1d"] < 0.16)
        | (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["cti_20_4h"] < -0.0)
      )
      # current 4h red with top wick, 1h downtrend, 15m downmove, 1h & 4h still high
      & (
        (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["top_wick_pct_4h"] < 0.06)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 40.0)
      )
      # 5m downmove, 15m & 1h & 4h still high, drop in last 24 hours
      & (
        (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.26))
      )
      # 5m & 15m downmove, 15m & 1h & 4h & 1d high
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
      )
      # 1d very low, chance not finished drop, 1h & 4h & 1d downtrend
      & (
        (dataframe["cti_20_1d"] > -0.95)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green, previous 1d red with top wick, 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["change_pct_1d"].shift(288) > -0.04)
        | (dataframe["top_wick_pct_1d"].shift(288) < 0.08)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 5m downmove, 4h & 1d overbought, pump in last 6 days
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 70.0)
        | (dataframe["hl_pct_change_6_1d"] < 0.5)
      )
      # current 4h red, current 1h red, 15m downmove, 1h & 4h & 1d still high:w
      & (
        (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["change_pct_1h"] > -0.03)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
      )
      # current 1d long green, current 4h red, 1h downtrend, 15m downmove, 4h & 1d overbought
      & (
        (dataframe["change_pct_1d"] < 0.16)
        | (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 1h downtred, 5m strong downmove, 15m & 4h & 1d stil high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 5.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 4h & 1h downtrend, 15m downmove, 1d overbought
      & (
        (dataframe["is_downtrend_3_4h"] == False)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 4h red, current 1h red, 15m downmove, 1h & 4h still high
      & (
        (dataframe["change_pct_4h"] > -0.0)
        | (dataframe["change_pct_1h"] > -0.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # current 1d long top wick, current 4h red, current 1h red, 15m downmove, 1h & 4h still high, 1d overbought
      & (
        (dataframe["top_wick_pct_1d"] < 0.16)
        | (dataframe["change_pct_4h"] > -0.0)
        | (dataframe["change_pct_1h"] > -0.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # 15m downmove, 5m & 15m & 1h & 4h & 1d still high. 1h downtrend
      & (
        (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d green with top wick, current 4h red, 3 previous 4h green, 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["top_wick_pct_1d"] < 0.06)
        | (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_4h"].shift(48) < 0.01)
        | (dataframe["change_pct_4h"].shift(96) < 0.01)
        | (dataframe["change_pct_4h"].shift(144) < 0.01)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 1d green with top wick, 1h downtrend, 15m & 1h downmove, 1h  4h still high, 4h & 1d downtrend
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["top_wick_pct_1d"] < 0.06)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h downtrend, 5m & 4h downmove, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_4h"] > 10.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 15m & 1h downtrend, 4h overbought
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # 1h downtrend, 15m downmove, 4h overbought
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # current 1d long green, 1h & 4h & 1d overbought
      & (
        (dataframe["change_pct_1d"] < 0.12)
        | (dataframe["rsi_14_1h"] < 65.0)
        | (dataframe["rsi_14_4h"] < 65.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 4h long green with long top wick, 4h overbought, pump in last 24h
      & (
        (dataframe["change_pct_4h"] < 0.1)
        | (dataframe["top_wick_pct_4h"] < 0.1)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["hl_pct_change_24_1h"] < 0.7)
      )
      # 15m & 1h & 4h high, drop in last 2 hours
      & (
        (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["close_max_24"] < (dataframe["close"] * 1.08))
      )
      # current 4h red, 1h downtrend, 4h overbought
      & (
        (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_max_6_4h"] < 70.0)
      )
      # 1h downtrend, 5m & 15m strong downmove, 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # current 4h long red, 1h & 4h downtrend, 1h & 4h downmove, 4h downtrend
      & (
        (dataframe["change_pct_4h"] > -0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d green, 15m downmove, 1h & 4h still high, 1d overbought
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # 4h downtrend, 15m & 1h & 4h still high, 1h & 4h downtrend, drop in last 2 hours
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["close_max_24"] < (dataframe["close"] * 1.08))
      )
      # 15m & 4h downtrend, 4h strong down move, 4h very low, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_4h"] > 16.0)
        | (dataframe["r_480_4h"] > -95.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d long green, current 4h red, previous 4h red, 1h downtrend, 4h still high, 4h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.12)
        | (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["change_pct_4h"].shift(48) > -0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h downtrend, 15m & 1h downmove, 4h still high, 1d overbought
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 5m & 15m downmove, 4h overbought, 1d still high
      & (
        (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_14_4h"] < 65.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 1h downtrend, 15m & 1h downmove, 4h high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 60.0)
      )
      # current 4h red, 1h downtrend, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1h"] > -0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
      )
      # 15m & 1h & 4h downtrend, 5m & 4h strong downmove, 4h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_4h"] > 16.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 4h red, 4h downtrend, 15m & 4h downmove, 1d overbought
      & (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["cti_20_1d"] < 0.7)
      )
      # current 5m long red or green 4h downtrend, 1h still high, 1h downtrend
      & (
        (abs(dataframe["change_pct"]) < 0.05)
        | (dataframe["not_downtrend_4h"])
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d long green, current 1h red, 1h still high, 1h downmove, 1h still high
      & (
        (dataframe["change_pct_1d"] < 0.26)
        | (dataframe["change_pct_1h"] > -0.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
      )
      # current 1d long greem, 1h downtrend, 1h downmove, 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.26)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["cti_20_1d"] < 0.5)
      )
      # current 5m red, current 4h red, 1h downtrend, 5m downmove, 1h still high, 1h downtrend
      & (
        (dataframe["change_pct_4h"] > -0.024)
        | (dataframe["change_pct_4h"] > -0.0)
        | (dataframe["is_downtrend_3_1h"] == False)
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["cti_20_1h"] < 0.8)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d red, 15m & 1h downtrend, 15m strong downmove, 1d still high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4h green with long top wick, 1h still not low enough, 4h & 1d overbought
      & (
        (dataframe["change_pct_4h"] < 0.01)
        | (dataframe["top_wick_pct_4h"] < 0.08)
        | (dataframe["cti_20_1h"] < -0.7)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # current 1d green with top wick, current 4h green with top wick, 15m & 1h downmove, 4h overbought
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["top_wick_pct_1d"] < 0.06)
        | (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["rsi_14_max_6_4h"] < 70.0)
      )
      # 15m downmove, 4h & 1d overbought, 1d downtrend
      & (
        (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_max_6_4h"] < 70.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 70.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h red, current 1h red, 1h & 4h downtrend, 1h & 4h downmove, 1h & 4h still not low enough
      & (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["change_pct_1h"] > -0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 36.0)
      )
      # current 1d red, 1h downtrend, 5m & 1h downmove, 4 h stil high, 1d overbought
      & (
        (dataframe["change_pct_1d"] > -0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # current 4h red, current 1h red, 1h & 4h downtrend, 1h & 4h strong downmove
      & (
        (dataframe["change_pct_4h"] > -0.06)
        | (dataframe["change_pct_1h"] > -0.03)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1h"] > 6.0)
        | (dataframe["rsi_3_4h"] > 10.0)
      )
      # current 1d long red, 1h & 4h downtrend, 15m still high, 1h & 4h downmove, 1d high
      & (
        (dataframe["change_pct_1d"] > -0.12)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 1h & 4h downtrend, 15m downmove, 15m still higher, 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.7))
      )
      # current 4h red with top wick, 1h & 4h downtrend, 5m downmove, 1h & 4h still high
      & (
        (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["top_wick_pct_4h"] < 0.03)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["cti_20_1h"] < -0.8)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
      )
      # 15m & 1h downtrend, 5m & 15m & 1h strong downmove
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_3_1h"] > 6.0)
      )
      # current 4h top wick, 15m & 1h still higher, 4h overbought
      & (
        (dataframe["top_wick_pct_4h"] < 0.03)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < 0.9)
        | (dataframe["rsi_14_4h"] < 70.0)
      )
      # current 1d long green, current 4h red, current 1h red, 1h downmove, 1h & 4h still high, 4h overbought
      & (
        (dataframe["change_pct_1d"] < 0.12)
        | (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["change_pct_1h"] > -0.03)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_max_6_4h"] < 70.0)
      )
      # 4h downtrend, 5m & 4h downmove, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["r_480_4h"] > -95.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h red, previous 4h green with top wick, 15m still high, 1h & 4h still high
      & (
        (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["change_pct_4h"].shift(48) < 0.03)
        | (dataframe["top_wick_pct_4h"].shift(48) < 0.03)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # current 1d green, 15m strong downmove, 1h & 4h still higher, 1d overbought
      & (
        (dataframe["change_pct_1d"] < 0.12)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 65.0)
      )
      # 1h downtrend, 5m & 15m & 1h downmove, 4h still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_4h"] < 46.0)
      )
      # current 1d red with top wick, 4h downtrend, 5m & 15m & 1h & 4h downmove, 15m & 1h & 4h still high
      & (
        (dataframe["change_pct_1d"] > -0.03)
        | (dataframe["top_wick_pct_1d"] < 0.03)
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 20.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 30.0)
      )
      # 5m downmove, 15m & 1h & 4h & 1d high
      & (
        (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 65.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 1h downtrend, 5m & 15m & 1h downmove, 1d overbought
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["cti_20_1d"] < 0.85)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # current 1d green with top wick, 1h downmove, 1h still high, 4h & 1d overbought
      & (
        (dataframe["change_pct_1d"] < 0.03)
        | (dataframe["top_wick_pct_1d"] < 0.03)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 65.0)
        | (dataframe["rsi_14_max_3_4h"] < 70.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # current 1d top wick, 4h downtrend, 15m downmove, 15m & 1h & 4h still high, 1d overbought
      & (
        (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 28.0)
        | (dataframe["cti_20_1h"] < -0.7)
        | (dataframe["cti_20_4h"] < -0.7)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # current 1d green, 15m downmove, 1h still high, 4h & 1d overbought, drop in last 2 hours
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close_max_24"] < (dataframe["close"] * 1.08))
      )
      # 1h downtrend, 5m & 15m & 1h strong downmove, 4h still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 8.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h downtrend, 5m downmove, 15m & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 15m downtrend, 14m & 1h downmove, 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # current 1d bot & top wick, 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["bot_wick_pct_1d"] < 0.04)
        | (dataframe["top_wick_pct_1d"] < 0.04)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # 1d downtrend, 5m & 15m downmove, 15m & 1h & 4h still high, 1h downtrend
      & (
        (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 5m downmove, 15m & 1h & 4h & 1d stil high, drop in last 2 days, pump in last 6 days
      & (
        (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.8)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.26))
        | (dataframe["hl_pct_change_6_1d"] < 0.7)
      )
      # current 1d top wick, 1h downtrend, 5m & 15m downmove, 1h & 4h still high, 4h downtrend
      & (
        (dataframe["top_wick_pct_1d"] < 0.1)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_14_15m"] > 30.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d green with top wick, 5m & 15m downmove, 1h still high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1d downtrend, current 1d red, 5m & 15m & 4h downmove, 1h downtrend
      & (
        (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_4h"] > 12.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4h green, current 1h red, 5m & 15m downmove, 15m  1h & 1d still high, 4h overbought
      & (
        (dataframe["change_pct_4h"] < 0.01)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # current 4h green, 1h downtrend, 5m & 15m & 1h strong downmove, 1h downtrend
      & (
        (dataframe["change_pct_4h"] < 0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d green, current 4h & 1h red, 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.12)
        | (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 65.0)
      )
      # current 4h & 1h red, 1h downtrend, 5m downmove, 15m & 1h & 4h & 1d still high, 1h downtrend, drop in last 6 days
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_14"] > 36.0)
        | (dataframe["rsi_14_15m"] < 26.0)
        | (dataframe["cti_20_1h"] < -0.8)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.4))
      )
      # current 4h green, current 1h red, 1h downtrend, 15m & 1h & 4h still high
      & (
        (dataframe["change_pct_4h"] < 0.01)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_15m"] < -0.7)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 46.0)
      )
      # current 4h top wick, 5m & 15m downmove, 1h & 4h still high, drop in last 6 days
      & (
        (dataframe["top_wick_pct_4h"] < 0.04)
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.7))
      )
      # current 4h green, current 1h red, 5m downmove, 15m & 1h & 4h still high
      & (
        (dataframe["change_pct_4h"] < 0.03)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < -0.7)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # current 4h long green, current 1h red, 15m & 1h & 4h still high
      & (
        (dataframe["change_pct_4h"] < 0.08)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 60.0)
      )
      # current 1h downtrend, 15m downmove, 15m & 1h & 4h still high, drop in last 2 hours
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["close_max_24"] < (dataframe["close"] * 1.08))
      )
      # 15m & 1h & 4h downtrend, 15m & 1h & 4h downmove, 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # current 4h red, 15m downtrend, 15m & 1h downmove, 4h overbought
      & (
        (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_max_6_4h"] < 70.0)
      )
      # 5m & 15m downmove, 15m & 1h still high
      & (
        (dataframe["rsi_3"] > 4.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
      )
      # current 1d green with top wick, 5m downmove, 15m & 1h & 4h still high
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
      )
      # current 4h red, current 1h red, 1h downtrend, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # 15m downtrend, 15m strong downmove, 1h & 4h stil high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3_15m"] > 8.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # current 1h red, 15m & 1h overbought, drop in last 6 days
      & (
        (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["cti_20_15m"] < 0.7)
        | (dataframe["rsi_14_15m"] < 50.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 60.0)
        | (dataframe["rsi_14_1h"].shift(12) < 70.0)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # 15m & 4h downtrend, 5m & 15m strong downmove, 4h still high, 4h downtrend, drop in the last 24 hours
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.2))
      )
      # 5m strong downmove, 15m & 1h & 4h & 1d high
      & (
        (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14_15m"] < 50.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 1h & 4h downtrend, 5m & 1h & 4h downmove, drop in last 48 hours
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.4))
      )
      # current 1h red, 5m & 15m downmove, 15m still high, 1h & 4h downtrend, drop in last 6 days
      & (
        (dataframe["change_pct_1h"] > -0.03)
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.4))
      )
      # current 4h green, current 1h red, 15m strong downmove, 1h & 4h still high
      & (
        (dataframe["change_pct_4h"] < 0.03)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
      )
      # current 1h long red, 1h downtrend, 1h strong downmove, 1h & 4h downtrend
      & (
        (dataframe["change_pct_1h"] > -0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1h long red, 1h downtrend, 4h overbought
      & (
        (dataframe["change_pct_1h"] > -0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 60.0)
      )
      # 5m & 15m downmove, 15m & 1h & 4h downtrend, drop in last 6 days
      & (
        (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["ema_200_dec_24_15m"] == False)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # current 1h top wick, 5m downmove, 1h & 4h still high, 1h & 4h downtrend
      & (
        (dataframe["top_wick_pct_1h"] < 0.04)
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d long green with long top wick, current 4h red, 15m downmove, 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.12)
        | (dataframe["top_wick_pct_1d"] < 0.12)
        | (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 4h green with top wick, 1h downtrend, 15m still high, 1h downmove, 1h & 4h still high
      & (
        (dataframe["change_pct_4h"] < 0.03)
        | (dataframe["top_wick_pct_4h"] < 0.03)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # current 1d red, 15m & 1h & 4h still high, pump in last 6 days, drop in last 6 days
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["hl_pct_change_6_1d"] < 0.7)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # 5m & 15m downmove, 15m still high, 1h overbought, 4h stil high
      & (
        (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 70.0)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # 5h downtrend, 4h strong downmove, pump in last 6 days, drop in last 6 days
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_4h"] > 10.0)
        | (dataframe["hl_pct_change_6_1d"] < 0.7)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # 15m strong downmove, 1h & 4h high, 1h & 4h & 1d downtrend
      & (
        (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 15m & 1h downmove, 1h & 4h still high, 1d overbought
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # 15m downmove, 15m & 1h & 4h & 1d still high, 1h downtrend, pump in last 24 hours, drop in last 4 hours
      & (
        (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 65.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["hl_pct_change_12_1h"] < 0.24)
        | (dataframe["close_max_48"] < (dataframe["close"] * 1.08))
      )
      # current 1d long top wick, 5m & 15m strong downmove, 4h & 1d downtrend
      & (
        (dataframe["top_wick_pct_1d"] < 0.16)
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h green with top wick, 1h downtrend, 5m & 15m downmove, 4h still high, 1d downtrend
      & (
        (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["top_wick_pct_4h"] < 0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m & 1h downtrend, 15m downmove, 15m & 4h still high, 1d overbought, drop in last 2 days
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.24))
      )
      # 1h & 4h downtrend, 1h downmove, 1h & 4h still high, 1d overbought
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 30.0)
        | (dataframe["cti_20_1d"] < 0.9)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # 1h downtrend, 15m & 1h strong downmove, 4h & 1d still high, 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 1h & 4h very down, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["r_480_1h"] > -90.0)
        | (dataframe["r_480_4h"] > -95.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red, previous 1d green with top wick, 15m downmove, 1h & 4h & 1d still high, drop in last 48 hours
      & (
        (dataframe["change_pct_1d"] > -0.04)
        | (dataframe["change_pct_1d"].shift(288) < 0.04)
        | (dataframe["top_wick_pct_1d"].shift(288) < 0.04)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.2))
      )
      # 1h downtrend, 5m & 15m & 1h downmove, 1h & 4h & 1d still high, drop in last 48 hours
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.3))
      )
      # current 4h long green, 5m & 15m downmove, 1h & 4h very down, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] < 0.08)
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["r_480_4h"] > -95.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green with top wick, 1h downtrend, 5m & 1h downmove, 1h very down, 4h stil high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.12)
        | (dataframe["top_wick_pct_1d"] < 0.12)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_1h"] > 12.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d green with top wick, current 4h red with top wick, 1h downtrend, 1h downmove, 4h still high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["top_wick_pct_1d"] < 0.06)
        | (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["top_wick_pct_4h"] < 0.03)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 12.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d green with top wick, 1h & 4h downtrend, 5m & 15m & 1h downmove, 4h & 1d stil high
      & (
        (dataframe["change_pct_1d"] < 0.03)
        | (dataframe["top_wick_pct_1d"] < 0.03)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 15m strond downmove, 1h & 4h & 1d high, 1h downtrend
      & (
        (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 15m downmove, 15m & 1h & 4h & 1d high, drop in last 6 hours
      & (
        (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["high_max_6_1h"] < (dataframe["close"] * 1.2))
      )
      # current 4h red, previous 4h long green with long top wick, current 1h red, 10 downmove, 15m & 1h & 4h high
      & (
        (dataframe["change_pct_4h"] > -0.0)
        | (dataframe["change_pct_4h"].shift(48) < 0.12)
        | (dataframe["top_wick_pct_4h"].shift(48) < 0.12)
        | (dataframe["change_pct_1h"] > -0.0)
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 65.0)
      )
      # 1h downtrend, 1h strong downmove, 4h still high, 1d overbought
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 8.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.9)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # current 4h red, previous 4h top wick, 1h & 4h & 1d still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["top_wick_pct_4h"].shift(48) < 0.04)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["rsi_14_max_3_4h"] < 70.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h red, 5m & 15m downmove, 4h high, 1d overbought
      & (
        (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # 1d & 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h still high, 1d overbought, drop in last 6 days
      & (
        (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.26))
      )
      # current 1d green, 15m strong downmove, 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["rsi_3_15m"] > 4.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # current 1d green, current 4h red, 1h & 3h downmove, 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # 15m & 1h downtrend, 5m & 15m & 1h downmove, 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # 1h downtrend, 15m & 1h downmove, 15m still high, 1h & 4h very low, 1h & 4h & 1d downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["r_480_4h"] > -90.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # 15m & 1h & 4h downtrend, 5m & 15m downmove, 1h & 4h very low, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["r_480_4h"] > -90.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 15m & 1h & 4h downmove, 1d high, drop in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # current 1d long green, 1h downtrend, 1h downmove, 4h & 1d high
      & (
        (dataframe["change_pct_1d"] < 0.12)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 5m & 15m downmove, 15m & 1h & 4h still high, 1d downtrend, drop in last 6 days
      & (
        (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # 1h downtrend, 5m downmove, 15m & 1h & 4h & 1d still high, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 5m & 15m & 1h & 4h downmove, 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] > 36.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 16.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.24))
      )
      # current 4h green with top wick, 5m downmove, 15m & 1h & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["top_wick_pct_4h"] < 0.04)
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d long red, 5m & 15m downmove, 1h & 4h still high, drop in last 6 days
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.24))
      )
      # 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 15m downtrend, 5m & 15m strong downmove, 1h still high, 1h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h downtrend, 1h downmove, 1h still high, 4h overbought, 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 65.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 5m & 15m strong downmove, 1h & 4h still high, 1d overbought
      & (
        (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # 4h downtrend, 5m downmove, 15m & 1h still high, 4h downmove, 1h downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_3_4h"] > 16.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d red, 1h & 4h downtrend, 15m & 1h & 4h downmove, 1h & 4h & 1d still high, drop in last 48 hours
      & (
        (dataframe["change_pct_1d"] > -0.0)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.26))
      )
      # 5m & 15m strong downmove, 1h & 4h downtrend
      & (
        (dataframe["rsi_3"] > 4.0)
        | (dataframe["rsi_3_15m"] > 4.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 15m downtrend, 5m & 15m strong downtrend, 1h & 4h still high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
      )
      # 1h & 4h downtrend, 5m & 15m & 1h downmove, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 15m downtrend, 5m downmove, 15m & 1h & 4h still high, 4h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d long top wick, 1h & 4h still high, 1h & 4h very low, 1h & 4h & 1d downtrend
      & (
        (dataframe["top_wick_pct_1d"] < 0.12)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m downtrend, 5m & 15m & 1h downmove, 1h & 4h & 1d still high, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1d downtrend, 15, & 1h downmove, 1h & 4h & 1d still high
      & (
        (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # current 1d long green, 5m & 15m downmove, 1h & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.16)
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 15m downtrend, 5m & 15m downmove, 1d still high, 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.3))
      )
      # 1h downtrend, 15m & 1h downmove, 1h & 4h still high, 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h downtrend, 5m & 15m & 1h downmove, 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.7))
      )
      # 1h downtrend, 5m & 15m & 1h downmove, 4h still high, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 15m & 1h & 4h downmove, 1h & 4h & 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
      )
      # 15m downtrend, 5m & 15m downmove, 1h & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 15m & 1h downmove, 1h & 4h & 1d high, 1d downtrend
      & (
        (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1d & 1h downtrend, 15m & 1h downmove, 1h & 4h & 1d still high
      & (
        (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 1h & 4h & 1d still high, 1d downtrend, big drop in last 12 days
      & (
        (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 65.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
        | (dataframe["high_max_12_1d"] < (dataframe["close"] * 2.5))
      )
      # 1h & 4h downtrend, 1d still high, big drop in last 12 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["high_max_12_1d"] < (dataframe["close"] * 5.0))
      )
      # current 1d red, 1h downtrend, 5m & 15h downmove, 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 8.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # current 4h green with top wick, 5m & 15m downmove, 1h & 4h high, 1h downtrend
      & (
        (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["top_wick_pct_4h"] < 0.08)
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h downtrend, 5m & 15m strong downmove, 1h & 4h downtrend, drop in last 12 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["high_max_12_1d"] < (dataframe["close"] * 1.9))
      )
      # 4h downtrend, 5m & 15m downmove, 1h & 4h very low, 1h & 4h & 1d downtrend, drop in last 12 days
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
        | (dataframe["high_max_12_1d"] < (dataframe["close"] * 1.5))
      )
      # current 4h top wick, 5m & 15m downmove, 1h & 4h high, 4h & 1d downtrend
      & (
        (dataframe["top_wick_pct_4h"] < 0.06)
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m & 4h downtrend, 5m & 15m downmove, 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["r_480_4h"] > -80.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtreend, 1h & 4h downmove, 1h & 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_3_4h"] > 16.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red, 1h & 4h downtrend, 15m downmove, 1h & 4h love, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_1d"] > -0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 1h & 4h downmove, 1h & 4h low, 1h & 4h * 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["r_480_4h"] > -90.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red, current 4h red, previous 4h green, 15m downtrend, 5m & 15m downmove, 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["change_pct_1d"] > -0.01)
        | (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_4h"].shift(48) < 0.06)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 15m downmove, 1h & 4h still high, 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["r_480_4h"] > -90.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 1h downmove, 4h still high, 1h & 4h low, 1h & 4h & 1d downtrend, drop in last 12 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["r_480_4h"] > -95.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
        | (dataframe["high_max_12_1d"] < (dataframe["close"] * 1.7))
      )
      # current 4h green, 5m downmove, 1h & 4h still high, 4h low, 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] < 0.06)
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["r_480_4h"] > -90.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green with top wick, 15m downtrend, 5m & 15m downmove, 1h & 4h stil high, 4h & 1d downtrend
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1d & 1hdowntrend, 5m & 15m & 1h downmove, 1h & 4h & 1d downtrend, drop in last 12 days
      & (
        (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
        | (dataframe["high_max_12_1d"] < (dataframe["close"] * 1.4))
      )
      # 4h downtrend, 5m & 4h downmove, 1h & 4h very low, 1h downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["r_480_1h"] > -97.0)
        | (dataframe["r_480_4h"] > -97.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current & previous 4h red, 2nd previous 4h long green, 1h % 4h high, 1d downtrend
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_4h"].shift(48) > -0.01)
        | (dataframe["change_pct_4h"].shift(96) < 0.16)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_max_6_4h"] < 70.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h red, previous 4h green, 5m & 15m downmove, 1d overbought
      & (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["change_pct_4h"].shift(48) < 0.04)
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 1h downtrend, 5m & 15m & 1h downmove, 4h very low, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["r_480_4h"] > -97.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m & 1h downtrend, 5m & 15m downmove, 5h still high, 1d overbought
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # current 4h long green, 5m strong downmove, 1h overbought, 4h still high
      & (
        (dataframe["change_pct_4h"] < 0.08)
        | (dataframe["rsi_3"] > 4.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 70.0)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # currend 1h red, current 4h top wick, current 1h red, 1h downtrend, 5m & 15m & 1h downmove, 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.03)
        | (dataframe["top_wick_pct_4h"] < 0.03)
        | (dataframe["change_pct_1h"] > -0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 1d green with top wick, current 4h red, 1h downtrend, 5m & 1h downmove, 4h stil high, 4h & 1d downmove
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h downtrend, 5m & 15m downmove, 1h stil high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green with top wick, current 4h red, previous 4h green with top wick, 1h downtrend, 4h overbought, 1d downtrend
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["change_pct_4h"].shift(48) < 0.04)
        | (dataframe["top_wick_pct_4h"].shift(48) < 0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14_max_3_4h"] < 70.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 5m & 15m & 1h & 4h downmove, 1d stil high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 6.0)
        | (dataframe["rsi_3_1h"] > 12.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # current 4h red, 15m & 1h & 4h & 1d still high, big drop in last 6 days
      & (
        (dataframe["change_pct_4h"] > -0.06)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["high_max_6_1d"] < (dataframe["close"] * 4.0))
      )
      # current 1d red, previous 1d green with top wick, 5m & 15m downmove, 15m still high, 1d overbought
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["change_pct_1d"].shift(288) < 0.03)
        | (dataframe["top_wick_pct_1d"].shift(288) < 0.03)
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["rsi_14_1d"].shift(288) < 65.0)
        | (dataframe["hl_pct_change_6_1d"] < 0.5)
      )
      # 5m & 15m downmove, 1h & 4h & 1d still high, 1d downtrend, pump in last 6 days
      & (
        (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
        | (dataframe["hl_pct_change_6_1d"] < 0.7)
      )
      # current 1d long green, 5m strong downmove, 15m & 1h & 1d still high, 1d overbought, pump in last 12 days
      & (
        (dataframe["change_pct_1d"] < 0.18)
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["high_max_12_1d"] < (dataframe["close"] * 0.9))
      )
      # 1h downtrend, 5m downmove, 1h & 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["r_480_1h"] > -70.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 5m & 15m & 1h & 4h downmove, 4h very low, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_3_4h"] > 36.0)
        | (dataframe["r_480_4h"] > -95.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 5m & 1h downmove, 15m still high, 1h & 4h low, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["r_480_1h"] > -75.0)
        | (dataframe["r_480_4h"] > -90.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red, 5m downmove, 15m still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h downtrend, 1d downmove, 15m still high, 1h & 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["r_480_4h"] > -95.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h downtrend, 1h & 4h downmove, 15m stil high, 1h & 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["r_480_1h"] > -70.0)
        | (dataframe["r_480_4h"] > -80.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1d downtrend, 5m & 15m downmove, 15m & 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m & 1h downtrend, 5m & 15m downmove, 15m & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 5m & 15m downmove, 15m & 1h & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 15m downmove, 15m & 1h & 4h & 1d stil high, 1d downtrend
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.8)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < -0.8)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h green with top wick, 5m & 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["top_wick_pct_4h"] < 0.04)
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 4h red with top wick, 5m & 1h downmove, 1h & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 5m & 15m & 1h downmove, 1h & 4h & 1d still high, 1h * 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 30.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red, previous 1d green, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["change_pct_1d"] > -0.03)
        | (dataframe["change_pct_1d"].shift(288) < 0.03)
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 5m & 1h downmove, 15m & 1h & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 4m & 15m downmove,15m & 1h & 4h & 1d still high
      & (
        (dataframe["rsi_3"] > 26.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["cti_20_1h"] < -0.8)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < -0.8)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # 1h downtrend, 5m & 15m & 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["close"] > dataframe["sup_level_1d"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.8)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
      )
      # 5m downmove, 15m  1h & 4h still high, 1h & 4h downtrend
      & (
        (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h downtrend, 5m & 15m & 1h downmove, 1h & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.8)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h downtrend, 5m & 15m & 1h & 4h downmove, 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.8)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # 1d top wick, 1h downtrend, 5m & 15m & 1h downmove, 1h & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["top_wick_pct_1d"] < 0.03)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["close"] > dataframe["sup_level_1d"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 30.0)
        | (dataframe["rsi_14_1d"] < 30.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 5m & 1d downmove, 15m & 1h & 4h still high, 1h & 4h very low, 1h & 4h downtrend
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_1d"] > 26.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["r_480_4h"] > -95.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h & 4h downtrend, 5m & 15m & 1h & 4h downmove, 4h & 1d still high, 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["close"] > dataframe["sup_level_1d"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_3_4h"] > 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h downtrend, 5m & 4h downmove, 15m & 1h & 4h & 1d still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red, previous 1d green, 15m & 1h & 4h downtrend, 1d still high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.03)
        | (dataframe["change_pct_1d"].shift(288) < 0.03)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 4h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 5m & 1h downmove, 15m & 1h & 1d stil high, 1h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["close"] > dataframe["sup_level_1d"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 44.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 5m % 15m & 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 1h & 4d downtrend, 5m & 15h & 1h downmove, 15m & 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m downtrend, 15m & 1h & 4h & 1d still high, 4h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 30.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d long green, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_1d"] < 0.16)
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m & 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h * 1d still high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # 1h & 4h downtrend, 5m & 1h & 4h downmove, 15m still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h & 1d downtrend, 5m & 1d downmove, 15m still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["rsi_3_1d"] > 12.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 15m downmove, 1h & 4h & 1d still high, 4h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.6)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h green with top wick, 5m & 1d downmove, 15m & 1h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["top_wick_pct_4h"] < 0.04)
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_1d"] > 10.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 5m & 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # 1h & 4h & 1d downtrend, 5, & 1h & 1d downmove, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_1d"] > 16.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 15m & 1h downmove, 1h & 4h still high, 1h & 4h downtrend
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h downtrend, 5m downmove, 15m & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 15m downmove, 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 16.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green with top wick, 5m downmove, 15m still high, 1h & 4h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["top_wick_pct_1d"] < 0.04)
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["close"] > dataframe["sup_level_1d"])
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h & 4h downtrend, 5m & 15m & 4h downmove, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_4h"] > 16.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h & 4h downtrend, 5m & 15m & 1h & 4h downmove
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_4h"] > 30.0)
      )
      # 5m & 15m downmove, 15m & 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h downtrend, 5m downmove, 15m & 1h & 4h & 1d still high, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["r_480_4h"] > -75.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 5m red, 5m & 15m downmove, 15m & 1d still high, 1h downtrend
      & (
        (dataframe["change_pct"] > -0.018)
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1d"] < -0.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4h red, 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < -0.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # 1h & 1d downtrend, 5m & 15m downmove, 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["close"] > dataframe["sup_level_1d"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h & 1d downtrend, 5m & 15m & 1d downmove, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1d"] > 20.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 5m & 1h downmove, 15m & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["close"] > dataframe["sup_level_1d"])
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < -0.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h & 1d downtrend, 5m & 15m & 1d downmove, 15m still high, 1h & dh downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1d"] > 16.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 5m & 15m downmove, 15m & 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green, 5m & 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # 1h & 4h & 1d downtrend, 15m & 4h & 1d downmove, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 1d downtrend, 5m & 15m downmove, 15m & 1h & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1d downtrend, 5m & 15m & 1d downmove, 15m sitll high, 1h & 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1d"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["r_480_4h"] > -90.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 15m downmove, 15m & 1h & 4h still high, 1h downtrend
      & (
        (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 4h & 1d downtrend, 15m & 1h & 4h still high, 5m low, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green with top wick, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_1d"] < 0.02)
        | (dataframe["top_wick_pct_1d"] < 0.02)
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 15m downmove, 15m & 4h & 1d still high, pump in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["hl_pct_change_6_1d"] < 0.7)
      )
      # 5m & 15m downmove, 15m & 1h & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < 0.8)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h green with top wick, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 15m downmove, 15m & 1h & 4h & 1d still high, 4h downtrend
      & (
        (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 5m downmove, 15m & 1h & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["rsi_3"] > 30.0)
        | (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 50.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d red with top wick, previous 1d green, 1h downtrend, 5m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.01)
        | (dataframe["top_wick_pct_1d"] < 0.02)
        | (dataframe["change_pct_1d"].shift(288) < 0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # 5m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["rsi_3"] > 26.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # current 1d green, current 4h green, current 1h green, 5m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["change_pct_1h"] < 0.02)
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 1d green with top wick, current 4h red, 5m & 15m downmove, 1h & 4h & 1d high, 1d downtrend
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_max_3_4h"] < 70.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h red, 5m & 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # current 1d green with top wick, 15m downmove, 15m & 1h & 4h & 1d still high, drop in last 12 days
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["top_wick_pct_1d"] < 0.04)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["high_max_12_1d"] < (dataframe["close"] * 0.9))
      )
      # 15m & 1d downtrend, 5m & 15m & 1d downmove, 15m & 1h & 4h still high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1d"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # current 1d red with top wick, previous 1d green, 1d downtrend, 5m downmove, 15m & 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["change_pct_1d"] > -0.02)
        | (dataframe["top_wick_pct_1d"] < 0.02)
        | (dataframe["change_pct_1d"].shift(288) < 0.04)
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 15m downmove, 15m & 1h & 4h still high, 1d downtrend
      & (
        (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red with top wick, previous 1d green, 4h downtrend, 5m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.02)
        | (dataframe["top_wick_pct_1d"] < 0.02)
        | (dataframe["change_pct_1d"].shift(288) < 0.02)
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < -0.7)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.7)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
      )
      # 1d downtrend, 15m & 1h & 1d still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 36.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red with top wick, previous 1d green, 5m downmove, 15m & 1h & 4h & 1d stil high, 4h & 1d downtrend
      & (
        (dataframe["change_pct_1d"] > -0.02)
        | (dataframe["top_wick_pct_1d"] < 0.02)
        | (dataframe["change_pct_1d"].shift(288) < 0.02)
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green with top wick, 5m downmove, 15m & 1h & 4h still high, 1d overbought
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["top_wick_pct_1d"] < 0.04)
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 4h red, previous 4h green, 15m downmove, 15m & 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_4h"].shift(48) < 0.02)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m & 4h & 1d downtrend, 5m & 15m & 1d downmove, 1h & 1d downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1d"] > 26.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h red, 15m downmove, 15m & 1h & 4h & 1d still high, 4h downtrend
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1d downtrend, 5m & 15m downmove, 15m & 1h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m downmove, 15m & 1h & 4h & 1d still high, 4h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 36.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < -0.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h green with top wick, 1h & 4h & 1d high
      & (
        (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # 15m downtrend, 5m & 15m downmove, 15m & 1h & 4d & 1d still high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # current 1d red, 15m & 1d downtrend, 1d downmove, 15m & 1h high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.02)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_1d"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d red, current 4h green, 15m downmove, 15m & 1h & 1d high
      & (
        (dataframe["change_pct_1d"] > -0.02)
        | (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 60.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 1d green, 1h & 4h downtrend, 4h downmove, 15m & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 1d green, current 4h green, 15m & 1h & 4h & 1d still high, pump in last 3 days
      & (
        (dataframe["change_pct_1d"] < 0.16)
        | (dataframe["change_pct_4h"] < 0.08)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["hl_pct_change_3_1d"] < 0.7)
      )
      # current 4h green, 5m downmove, 15m & 1h & 4h & 1d still high, 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1d downtrend, 15m & 1h & 4h & 1d still high, 4h & 1d downtrend
      & (
        (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["rsi_14_15m"] < 50.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 60.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1h green, 15m downtrend, 5m & 15m downmove, 15m & 1h & 4h still high, 24h downtrend
      & (
        (dataframe["change_pct_1h"] < 0.0)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # cuerrent 5m red, previous 5m green, 15m downmove, 15m & 1h & 4h still high, 1h downtrend
      & (
        (dataframe["change_pct"] > -0.016)
        | (dataframe["change_pct"].shift(1) < 0.016)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 4h downtrend
      & (
        (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 15m & 1h & 4h high, 1h & 4h & 1d downtrend
      & (
        (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1d downtrend, 5m downmove, 15m & 1h & 4h & 1h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 36.0)
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1h green, 15m downmove, 15m & 1h & 4h & 1d high
      & (
        (dataframe["change_pct_1h"] < 0.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < 0.8)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 1d top wick, 4h downtrend, 15m & 1h & 4h & 1d high, 4h downtrend, 1d downtrend
      & (
        (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["is_downtrend_3_4h"] == False)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1d downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m downmove, 15m & 1h & 4h high, 1h downtrend
      & (
        (dataframe["rsi_3"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 15m downtrend, 15m downmove, 15m & 1h & 4h high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # current 1d red, previous 1d green with top wick, current 4h green, current 1h green, 15m downmove, 15m & 1h & 4h & 1d syill high, 4h & 1d downtrend
      & (
        (dataframe["change_pct_1d"] > -0.04)
        | (dataframe["change_pct_1d"].shift(288) < 0.02)
        | (dataframe["top_wick_pct_1d"].shift(288) < 0.02)
        | (dataframe["change_pct_4h"] < 0.01)
        | (dataframe["change_pct_1h"] < 0.01)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m & 1h downtrend, 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
      )
      # 5m & 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
      )
      # 4h & 1d downtrend, 5m & 4h & 1d downmove, 15m still high, 1h & 4h low, 1h & 4h & 1d
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_4h"] > 36.0)
        | (dataframe["rsi_3_1d"] > 36.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["r_480_1h"] > -75.0)
        | (dataframe["r_480_4h"] > -75.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h & 1d downtrend, 5m & 4h & 1d downmove, 5m & 15m & 1d still high, 1h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["cti_20"] < -0.5)
        | (dataframe["rsi_14"] < 33.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h red, 1d downtrend, 5m & 1d downmove, 15m & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_1d"] > 12.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # current 1d green with top wick, 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 4h red, previous 4h green, 5m & 15m downmove, 1h & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["change_pct_4h"].shift(48) < 0.02)
        | (dataframe["rsi_14"] < 12.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrendm 5m & 15m & 1h downmove, 15m & 1h & 4h & 1d still high, 5m & 15m downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
      )
      # 1d & 1h downtrend, 5m downmove, 15m & 1h & 1d still high, 5m & 15m downtrend
      & (
        (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
      )
      # current 4h top wick, 15m downmove, 15m & 1h & 4h & 1d still high, drop in last 12 days
      & (
        (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["rsi_3_15m"] > 50.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 60.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["high_max_12_1d"] < (dataframe["close"] * 0.9))
      )
      # 1h downtrend, 5m & 1h downmove, 15m & 1h & 4h still high, 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h downtrend, 5m & 15m & 1h downmove, 15m & 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h & 1d downtrend, 5m & 15m & 1h downmove, 15m & 4h & 1d still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["rsi_14_1d"] < 36.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 15m downmove, 15m & 1h & 4h & 1d high, pump in last 12 days
      & (
        (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.9)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # 5m downmove, 15m & 1h & 4h & 1d still high, 4h downtrend
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 4h green with top wick, 1d downtrend, 5m downmove, 15m & 1h & 4h stil high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 60.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 15m downmove, 15m & 1h & 4h & 1d still high, 1h & 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["r_480_4h"] > -80.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h downtrend, 5m & 15h & 1d downmove, 15m & 1h still high, 1h & 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["r_480_4h"] > -75.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red, 15m downmove, 1h & 1d high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.04)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 70.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4m red, 4h downtrend, 5m & 4h downmove, 1d stil high, 1h & 4h downtrend
      & (
        (dataframe["change_pct"] > -0.018)
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 4h red, previous 4h green, 5m downmove, 15m & 1h & 4h & 1d high
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_4h"].shift(48) < 0.02)
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # 1h & 4h & 1d downtrend, 5m & 15m & 1d downmove, 1d stil high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1d"] > 20.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4h green with top wick, 15m downmove, 15m & 1h & 4h & 1d still high, 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] < 0.01)
        | (dataframe["top_wick_pct_4h"] < 0.04)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 15m downmove, 15m & 1h & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h & 1d downtrend, 5m & 4h downmove, 15m still high, 4h low, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d & 4h green with top wick, 5m downmove, 15m & 1h & 4h & 1d high
      & (
        (dataframe["change_pct_1d"] < 0.02)
        | (dataframe["top_wick_pct_1d"] < 0.02)
        | (dataframe["change_pct_4h"] < 0.01)
        | (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # current & previous 1d red, 5m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.0)
        | (dataframe["change_pct_1d"].shift(288) > -0.08)
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 50.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
      )
      # current 4h top wick, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["top_wick_pct_4h"] < 0.06)
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h red with top wick, 15m & 1h & 4h & 1d still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1h downtrend, drop in last 12 days
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["close"] > (dataframe["high_max_12_1d"] * 0.8))
      )
      # 1h downtrend, 5m & 1h downmove, 15m & 1h & 4h & 1d still high, 5m & 15m downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
      )
      # current 1d red, 15m & 1h & 4h downtrend, 5m & 15m & 4h downmove, 1d still high, 5m & 15m downtrend
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["cti_20_1d"] < -0.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
      )
      # current 4h green, current 1h red, 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] < 0.08)
        | (dataframe["change_pct_1h"] > -0.04)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 4h & current 1h green, 15m downmove, 15m & 1h & 4h still high, 1h & 4h downtrend
      & (
        (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["change_pct_1h"] < 0.01)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1h red, 5m downmove, 15m & 1h & 4h high
      & (
        (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
      )
      # current 4h red, 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
      )
      # current 1d green, 1h downtrend, 5m & 15m downmove, 4h & 1d overbought
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # 15m & 1h & 4h downtrend, 15m downmove, 15m still high, 1d overbought, 1h & 1d downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1d downtrend, 5m & 15m downmove, 15m & 1h & 4h still high, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 15m & 1h & 4h & 1d downtrend, 15m downmove, 15m & 1h & 4h & 1d still high, 1h & 1d downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 30.0)
        | (dataframe["rsi_14_1d"] < 30.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red, 1d downtrend, 5m downmove, 15m still high, 1h & 4h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 15m & 4h & 1d downtrend, 5m & 15m & 4h & 1d downmove, 1d still high, 1h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["rsi_3_1d"] > 20.0)
        | (dataframe["cti_20_1d"] < -0.7)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d top wick, 5m & 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["top_wick_pct_1d"] < 0.02)
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < -0.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
      )
      # 15m & 1h & 1d downtrend, 15m & 1h & 1d downmove, 1h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_1d"] > 26.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d red, 5m & 15m downmove, 1h & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.02)
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] < dataframe["res_hlevel_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4h green, 5m & 15m downmove, 15m & 1h & 4h & 1d high, pump in last 6 days
      & (
        (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 70.0)
        | (dataframe["hl_pct_change_6_1d"] < 0.9)
      )
      # current 1d red with top wick, 1h downtrend, 5m & 1h downmove, 15m & 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["change_pct_1d"] > -0.04)
        | (dataframe["top_wick_pct_1d"] < 0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h & 1d downtrend, 5m downmove, 15m & 1h & 4h & 1d still high, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < -0.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red, 4h downtrend, 5m & 15m & 1d downmove, 1h & 1d high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1d"] > 20.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 5m downmove, 15m & 1h & 4h still high, 4h low, 1h & 1d downtrend
      & (
        (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["r_480_4h"] > -80.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 1d downtrend, 5m downmove, 15m & 1h & 4h still high, 1h & 4h low, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d green, 1h downtrend, 15m & 1h downmove, 1h & 4h & 1d stil high, 4h low
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["r_480_4h"] > -75.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # 1h & 4h & 1d downtrend, 1d downmove, 15m & 1h & 1d still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 4h & 1d downtrend, 5m & 15m downmove, 15m & 1h still high, 1h & 4d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_4h"] > 16.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d red, 5m & 15m downmove, 15m & 1h & 4h high
      & (
        (dataframe["change_pct_1d"] > -0.12)
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["cti_20_15m"] < 0.5)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 50.0)
      )
      # current 1d & 4h red, 4h & 1d downtrend, 5m & 1h & 4h & 1d downmove, 1h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.04)
        | (dataframe["change_pct_4h"] > -0.08)
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["rsi_3_1d"] > 16.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # previous 5m red, 1d downtrend, 5m & 15m & 4h & 1d downmove, 1h low, 1h & 4h downtrend
      & (
        (dataframe["change_pct"].shift(1) > -0.02)
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_4h"] > 36.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 4h green, current 1h red, 15m & 1h & 4h still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["change_pct_1h"] > -0.02)
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 1d downtrend, 15m downmove, 1d still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["cti_20_1d"] < -0.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4h green with top wick, current 1d top wick, 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["top_wick_pct_1d"] < 0.06)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.7)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
      )
      # current 4h top wick, 15m & 1d downmove, 15m & 1h & 4h still high, 1h & 4h * 1d downtrend
      & (
        (dataframe["top_wick_pct_4h"] < 0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 5m red, 1h & 1d downtrend, 5m downmove, 15m & 1h & 4h & 1d stil high
      & (
        (dataframe["change_pct"] > -0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["rsi_14_1d"] < 36.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
      )
      # 15m & 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 1d downtrend, 5m & 15m & 4h & 1d downmove, 1d high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h downtrend, 5m & 15m downmove, 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h green with top wick, 5m & 15m downmove, 15m & 1h & 4h high, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["top_wick_pct_4h"] < 0.02)
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 60.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 5m & 1h & 4h downmove, 15m & 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 1d green, 1h downtrend, 15m downmove, 1h & 4h & 1d high
      & (
        (dataframe["change_pct_1d"] < 0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["r_480_4h"] < -20.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 1d green, 5m & 15m downmove, 1h & 4h & 1d high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 50.0)
        | (dataframe["rsi_14_1h"] < 60.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d green, 5m downmove, 5m & 1h & 4h & 1d high
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # 1h downtrend, 1h & 4h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 1h & 4h & 1d downtrend, 5m & 1h dowmove, 15m stil high, 1h & 4h low, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["r_480_1h"] > -75.0)
        | (dataframe["r_480_4h"] > -90.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 5m & 15m downmove, 1d still high, 1d downtrend
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 4.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h downtrend, 15m & 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 15m downtrend, 5m & 15m downmove, 15m & 1h & 4h still high, 4h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d red, previous 1d green, 1h downtrend, 15m & 1h & 4h still high, 4h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.06)
        | (dataframe["change_pct_1d"].shift(288) < 0.12)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h downtrend, 15m & 1h & 4h downmove, 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 8.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 5m & 1h downmove, 1h & 4h & 1d high
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 1d downtrend, 5m & 15m & 1d downmove, 15m still high, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1d"] > 20.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1h red, previous 1h green, 15m downmove, 1h & 4h high, 1h downtrend
      & (
        (dataframe["change_pct_1h"] > -0.06)
        | (dataframe["change_pct_1h"].shift(12) < 0.06)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d green with top wick, 5m downmove, 15m & 1h & 4h stil high, 4h low, 1h & 4h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["top_wick_pct_1d"] < 0.06)
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["r_480_4h"] > -75.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h & 4h & 1d downtrend, 5m & 1h downmove, 15m & 1h still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1h & 4h red, 1h & 4h downtrend, 15m & 1h & 4h downmove, 1d stil high
      & (
        (dataframe["change_pct_1h"] > -0.04)
        | (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 4h downtrend, 5m & 15m & 1h & 4h downmove, 1d still high, 5m low, 5m & 15m downtrend, drop in last 12 hours
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_3_4h"] > 36.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["r_480"] > -80.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
        | (dataframe["close"] > (dataframe["high_max_12_1h"] * 0.86))
      )
      # 1h & 1d downtrend, 5m & 15m & 1d downmove, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1d"] > 20.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green, current 4h red, 1h downtrend, 1h downmove, 5m & 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14"] < 36.0)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h downtrend, 4h & 1d downmove, 15m & 1d still high, 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["rsi_3_1d"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.6))
      )
      # current 4h red, 1h downtrend, 1h dowmove, 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # current 4h green with top wick, 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["top_wick_pct_4h"] < 0.08)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 70.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # 1h & 4h downtrend, 1h & 4h downmove, 4h & 1d stil high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 1d green, current 1h  red, 15m & 1h & 4h & 1d still high, 4h high
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["change_pct_1h"] > -0.02)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 65.0)
        | (dataframe["r_480_4h"] < -16.0)
      )
      # 1h & 4h & 1d downtrend, 15m & 1h & 4h & 1d downmove, 15m still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h downtrend, 5m & 15m downmove, 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 4h & 1d downtrend, 15m downmove, 15m & 1h & 4h & 1d still high, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 15m & 1d downtrend, 15m & 1d downmove, 1h high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1d"] > 10.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d long green, 1h downtrend, 15m & 1h downmove, 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.26)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 1d red, 15m downtrend, 15m downmove, 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.04)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3_15m"] > 8.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 1h & 4h & 1d downtrend, 1h & 1d downmove, 5m & 15m still high, 5h low, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["r_480_4h"] > -75.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 15m downmove, 15m & 1h & 4h & 1d high
      & (
        (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 70.0)
      )
      # current 1d red, 1h & 4h downtrend, 1h & 4h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # 1h downtrend, 1h downmove, 5m & 15m & 1h & 4h & 1d still high, 4h high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["r_480_4h"] < -20.0)
      )
      # current 4h red, previous 4h green, 15m & 1h downtrend, 15m & 1h downmove, 4h high, 1h downtrend
      & (
        (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["change_pct_4h"].shift(48) < 0.04)
        | (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 12.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 5m & 15m downmove, 15m & 1h & 4h & 1d high
      & (
        (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 1h & 4h downtrend, 1h & 4h downmove, 1h & 4h & 1d stil high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_3_4h"] > 36.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 5m & 15m downmove, 1h & 4h & 1d still high, 5m low, 1h downtrend
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["r_480"] > -90.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4h green, 1h downtrend, 15m & 1h downmove, 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] < 0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 1h downtrend, 1h downmove, 5m & 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 1d green, 1h downtrend, 1h downmove, 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["change_pct_1d"] < 0.12)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 12.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 4h green, 15m downmove, 15m & 1h & 4h still high, 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green with top wick, 1h downmove, 15m & 1h & 4h & 1d still high, drop in last 6 days
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.8))
      )
      # 15m & 1h & 4h downtrend, 15m & 1h & 4h downmove, 1h downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 4.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 4h & 1d downtrend, 5m downmove, 15m & 1h & 4h & 1d still high, 4h downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h downtrend, 5m downmove, 15m & 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h downtrend, 15m & 1h downmove, 4h & 1d stil high, 5m low
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["r_480"] > -80.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 1h downtrend 15m & 1h downmove, 4h & 1d still high, 4h low, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["r_480_4h"] > -75.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green, 15m & 1h downmove, 5m & 15m & 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["change_pct_1d"] < 0.04)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 1d downtrend, 15m & 1h & 4h & 1d downmove, 1d still high, 5m & 15m & 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_3_4h"] > 36.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h & 1d downtrend, 15m & 1h & 4h & 1d downmove, 1h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_3_1d"] > 10.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h & 1d downtrend, 15m & 1h & 4h & 1d downmove, 1d still high, 5m & 15m & 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["rsi_3_1d"] > 20.0)
        | (dataframe["cti_20_1d"] < -0.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_24"] == False)
        | (dataframe["ema_200_dec_24_15m"] == False)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.6))
      )
      # current 4h red, previous 4h greem, 1h downtrend, 15m & 1h downmove, 1h & 4h & 1d still high, drop in last 6 days
      & (
        (dataframe["change_pct_4h"] > -0.02)
        | (dataframe["change_pct_4h"].shift(48) < 0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.75))
      )
      # 1h downtrend, 15m & 1h & 4h downmove, 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 15m & 4h downtrend, 5m & 15m & 1h & 4h downmove, 4h & 1d still high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 70.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 1d green with top wick, 1h downtrend, 1h downmove, 5m & 15m & 1h & 4h & 1d still high, 5m downtrend
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14"] < 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["ema_200_dec_24"] == False)
      )
      # 1d downtrend, 5m & 15m & 1h & 4h & 1d still high, 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_14"] < 46.0)
        | (dataframe["rsi_14_15m"] < 50.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 30.0)
        | (dataframe["rsi_14_1d"] < 30.0)
        | (dataframe["r_480_4h"] > -90.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d red, previous 1d green, 1h & 4h downmove, 15m & 4h &1d still high
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["change_pct_1d"].shift(288) < 0.12)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 15m & 1h & 1d downtrend, 15m & 1h & 6h downmove
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_3_1d"] > 6.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 1h & 1d downtrend, 1d downmove, 15m stil high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_1d"] > 6.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # current 1d red with top wick, 1h & 4h downtrend, 15m & 1d downmove, 15m & 1h & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["change_pct_1d"] > -0.01)
        | (dataframe["top_wick_pct_1d"] < 0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1d"] > 36.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1d red, current 4h red, previous 4h green, 5m & 15m & 1h & 4h downmove, 1h & 4h & 1d stil high
      & (
        (dataframe["change_pct_1d"] > -0.01)
        | (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_4h"].shift(48) < 0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 1h & 1d downtrend, 15m & 1h & 1d downmove, 4h low, 1h & 4h & 1d dowqntrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_1d"] > 16.0)
        | (dataframe["r_480_4h"] > -90.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 1d downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["rsi_14_1d"] < 36.0)
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # current 1d green with top wick, current 4h red, 5m & 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.02)
        | (dataframe["top_wick_pct_1d"] < 0.02)
        | (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 1d red, previous 1d green, 15m downmove, 5m & 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.12)
        | (dataframe["change_pct_1d"].shift(288) < 0.12)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 1h downtrend, 5m & 15m downmove, 15m & 1d high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 4.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4h green, current 1h red, 5m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] < 0.01)
        | (dataframe["change_pct_1h"] > -0.00)
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 1d green, current 4h top wick, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, pump in last 6 days, drop in last 6 days
      & (
        (dataframe["change_pct_1d"] < 0.24)
        | (dataframe["top_wick_pct_4h"] < 0.08)
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["hl_pct_change_6_1d"] < 0.9)
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.70))
      )
      # 1h & 4h & 1d downtrend, 5m & 15m downmove, 1h low, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_14"] > 30.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["r_480_1h"] > -75.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d green with top wick, current 1h red, previous 1h greem, 15m & 1h & 4h & 1d stil high
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["change_pct_1h"] > -0.03)
        | (dataframe["change_pct_1h"].shift(12) < 0.03)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 1d green with top wick, previous 4h red, 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h still high, 4h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.03)
        | (dataframe["top_wick_pct_1d"] < 0.03)
        | (dataframe["change_pct_4h"].shift(48) > -0.04)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 1h downtrendm 5m & 1hm & 1h & 4h downmove, 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 1h & 1d downtrendm 1h & 1d downmove, 5m & 15m & 1h & 4h satill high, 4h low, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_1d"] > 26.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 15m downmove, 5m & 1h & 4h & 1d still high, 4h low, 4h & 1d downtrend
      & (
        (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < -0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["r_480_4h"] > -75.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 4h & 1d downtrend, 1h & 4h & 1d downmove, 1h & 4h low, 1h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_3_1d"] > 16.0)
        | (dataframe["r_480_1h"] > -75.0)
        | (dataframe["r_480_4h"] > -80.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1d green, current 1h red, 15m & 1h downmove, 15m & 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["rsi_3_15m"] > 40.0)
        | (dataframe["rsi_3_1h"] > 40.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 65.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 1d downtrend, 5m downmove, 15m & 1h still high, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 5m downmove, 15m & 1h & 4h & 1d still high, 4h high
      & (
        (dataframe["rsi_3"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 70.0)
        | (dataframe["r_480_4h"] < -30.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 1d red, 4h & 1d downtrend, 15m & 1d downmove, 5m & still high, 4h low, drop in last 6 days
      & (
        (dataframe["change_pct_1d"] > -0.08)
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_1d"] > 36.0)
        | (dataframe["rsi_14"] < 26.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.75))
      )
      # current 1d red, previous 1d green, 15m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.02)
        | (dataframe["change_pct_1d"].shift(288) < 0.08)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 1d red, previous 1d green, 1h downtrend, 5m & 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.01)
        | (dataframe["change_pct_1d"].shift(288) < 0.06)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14"] < 33.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 1h downtrend, 1h downmove, 5m & 15m & 1h & 4h & 1d stil high, 4h high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["r_480_4h"] < -30.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # 15m & 1h downtrend, 15m & 1h downmove, 5m & 15m & 1h & 4h still high, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 10.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h & 1d downtrend, 1d downmove, 5m & 15m & 1d still high, 1h low, drop in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["is_downtrend_3_1d"] == False)
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["r_480_1h"] > -75.0)
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.70))
      )
      # 1h & 1d downtrend, 15m & 1h & 1d downmove, 1h & 4h low, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_3_1d"] > 10.0)
        | (dataframe["r_480_1h"] > -90.0)
        | (dataframe["r_480_4h"] > -90.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 5m downmove, 15m & 1h & 4h still high, 4h love, 1h downtrend
      & (
        (dataframe["rsi_3"] > 4.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h downtrend, 1h downmove, 15m & 1h & 4h stil high, 4h low, 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 4h green with top wick, 1d downtrend, 15m & 1d downmove, 5m & 15m & 1h & 4h still high, 1h downtrend
      & (
        (dataframe["change_pct_4h"] < 0.03)
        | (dataframe["top_wick_pct_4h"] < 0.03)
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1d"] > 10.0)
        | (dataframe["rsi_14"] < 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1d downtrend, 5m & 15m & 1d downmove, 1h still high, 1h low, 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 6.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1d"] > 20.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.75))
      )
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 4h green, 1d downtrend, 15m & 1h & 4h still high, 1h & 4h downtrend
      & (
        (dataframe["change_pct_4h"] < 0.03)
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["r_14_1h"] < -20.0)
        | (dataframe["r_14_4h"] < -20.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 15m downtrend, 15m downmove, 5m & 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 5m downmove, 15m & 1h & 4h & 1d high
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < 0.8)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # current 4h red, previous 4h green, 5m & 1h downmove, 15m & 1h & 4h & 1d still high, drop in last 6 days
      & (
        (dataframe["change_pct_4h"] > -0.01)
        | (dataframe["change_pct_4h"].shift(48) < 0.01)
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.80))
      )
      # current 1d top wick, 1h downtrend, 5m & 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["top_wick_pct_1d"] < 0.08)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 5m & 15m downmove, 15m & 1h & 4h still high, 4h low, 1h downtrend
      & (
        (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["r_480_1h"] > -80.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 5m & 15m downmove, 1h & 4h & 1d still high, 1h high
      & (
        (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["r_480_1h"] < -30.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 1h downtrend, 5m downmove, 15m & 1h still high, 1h low, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h & 4h downtrend, 5m & 15m & 4h downmove, 15m & 1h & 4h still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_4h"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 30.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 4h & 1d downtrend, 5m & 4h & 1d downmove, 1h downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_3_1d"] > 6.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # curent 1d red, previous 1d green, 1h downtrend, 15m & 1h & 4h downmove, 4h still high
      & (
        (dataframe["change_pct_1d"] > -0.06)
        | (dataframe["change_pct_1d"].shift(288) < 0.06)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 1h downtrend, 1h downmove, 15m & 1h & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 12.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1d downtrend, 15m & 1d downmove, 15m & 1h & 4h still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1d"] > 36.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 1h red, previous 1h red, 5m & 15m & 1h & 4h still high, 1h & 4h downtrend
      & (
        (dataframe["change_pct_1h"] > -0.04)
        | (dataframe["change_pct_1h"].shift(12) < 0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 1d red, previous 1d green, current 4h green, 1h downtrend, 5m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.01)
        | (dataframe["change_pct_1d"].shift(288) < 0.01)
        | (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 4h downtrend, 15m & 4h & 1d downmove, 1h & 1d still high, 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["rsi_3_1d"] > 26.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.70))
      )
      # 1d downtrend, 1d downmove, 15m & 1h & 4h still high, 4h low, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_1d"] > 30.0)
        | (dataframe["cti_20_15m"] < -0.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["r_480_4h"] > -80.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 4h red with top wick, 1h downtrend, 1h downmove, 15m & 1h & 4h & 1d stil high, 1d downtrend, drop in last 6 days
      & (
        (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["top_wick_pct_4h"] < 0.03)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_4_1d"] == False)
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.70))
      )
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 36.0)
        | (dataframe["rsi_3_15m"] > 16.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.60))
      )
      # current 1d green, 15m & 1g downmove, 1h & 4h still high, 1h & 4h downtrend
      & (
        (dataframe["change_pct_1d"] < 0.06)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # 15m downmove, 1h & 4h & 1d high, 1h & 4h high
      & (
        (dataframe["rsi_3_15m"] > 40.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 70.0)
        | (dataframe["r_480_1h"] < -25.0)
        | (dataframe["r_480_4h"] < -20.0)
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # 4h downtrend, 5m downmove, 15m & 1h & 4h & 1d still high, 1h downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h downtrend, 5m & 15m & 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_14"] > 36.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 1h downtrend, 5m downmove, 5m & 15m & 1h still high, 1h low, 1h downtrend
      & (
        (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 1h & 4h downtrend, 5m & h downmove, 15m & 1h & 4h & 1d stil high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # current 1d red, previous 1d green, 1h & 4h downtrend, 15m & 1h downmove, 15m & 1n & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.02)
        | (dataframe["change_pct_1d"].shift(288) < 0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 1h downtrend, 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 5m & 15m & 1h downmove, 5m & 1h & 4h & 1d still high, 1d downtrend
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 1h downmove, 1h & 4h & 1d still high, 1h & 4h high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["r_480_1h"] < -20.0)
        | (dataframe["r_480_4h"] < -20.0)
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 1h & 4h downtrend, 5m & 15m & 1h & 4h downmove, 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_4h"] > 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 1h downtrend, 1h downmove, 5m & 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 12.0)
        | (dataframe["rsi_14"] < 40.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 1h & 1d downtrend, 15m & 1h downmove, 15m & 1h & 4h still high, 1h low, 1h & 4h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["r_480_1h"] > -85.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
      )
      # current 4h green, 1h downtrend, 15m & 1h downmove, 15m & 1h & 4h still high
      & (
        (dataframe["change_pct_4h"] < 0.02)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
      )
      # 1h & 1d downtrend, 15m & 1h downmove, 5m & 15m & 1h & 4h still high, 1h downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # current 4h red, previous 4h green, 1h downtrend, 1h downmove, 5m & 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] > -0.03)
        | (dataframe["change_pct_4h"].shift(48) < 0.03)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_max_6_4h"] < 70.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["zlma_50_1h"])
      )
      # 1h & 1d downtrend, 1h & 4h & 1d downmove, 15m still high, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_3_4h"] > 36.0)
        | (dataframe["rsi_3_1d"] > 36.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 5m & 1h & 4h & 1d still high, drop in last 6 days
      & (
        (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.8)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 70.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["hl_pct_change_6_1d"] < 0.9)
      )
      # 1h & 1d downtrend, 5m & 1h downmove, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # current 1h red with top wick, 1h downtrend, 15m & 1h downmove, 5m & 15m & 1h & 4h still high, 1h downtrend
      & (
        (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["top_wick_pct_1h"] < 0.01)
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
      )
      # 4h downtrend, 4h downmove, 5m & 15m & 1h & 4h & 1d still high, 1h high
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_4h"] > 30.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["r_480_1h"] < -30.0)
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 1h & qd downtrend, 5m & 15m & 1h downmove, 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_15m"] > 12.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_4h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 5m & 15m & 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 1d red, current 4h green, 1d downtrend, 15m downmove, 15m & 1h still high, 1h downtrend, drop in last 6 days
      & (
        (dataframe["change_pct_1d"] > -0.06)
        | (dataframe["change_pct_4h"] < 0.06)
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.85))
      )
      # 5m downmove, 5m & 15m & 1h & 4h & 1d still high, pump in last 6 days
      & (
        (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["cti_20_15m"] < -0.5)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < -0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["hl_pct_change_6_1d"] < 0.5)
      )
      # 1h & 4h & 1d downtrend, 5m & 15m & 1h downmove, 4h low, 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["r_480_4h"] > -85.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h & 1d still high, pump in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["hl_pct_change_6_1d"] < 0.8)
      )
      # 15m & 1h downmove, 5m & 15m & 1h & 4h & 1d still high, 1h & 4h high
      & (
        (dataframe["rsi_3_15m"] > 40.0)
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["r_480_1h"] < -30.0)
        | (dataframe["r_480_4h"] < -15.0)
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # current 4h red, previous 4h green, 5m & 1hm downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] > -0.00)
        | (dataframe["change_pct_4h"].shift(48) < 0.00)
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 46.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["bb20_2_low_1h"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # current & previous 1h red, 5m & 15m downmove, 15m & 1h & 4h still high, 4h high
      & (
        (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["change_pct_1h"].shift(12) > -0.01)
        | (dataframe["rsi_3"] > 26.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_14_15m"] < 40.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["r_480_4h"] < -30.0)
      )
      # current 1h red, previous 1h green, 5m & 15m downmove, 5m & 15m still high, 1h pumped
      & (
        (dataframe["change_pct_1h"] > -0.02)
        | (dataframe["change_pct_1h"].shift(12) < 0.02)
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < 0.7)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["rsi_14_1h"].shift(12) < 70.0)
      )
      # current 4h green, current 1h red, 15m & 1h downmove, 4h & 1d still high, 4h high
      & (
        (dataframe["change_pct_4h"] < 0.01)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1h"] > 26.0)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["r_480_4h"] < -5.0)
      )
      # 1h downtrend, 1h downmove, 4h & 1d still high, 4h high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 16.0)
        | (dataframe["rsi_14_4h"] < 60.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["r_480_4h"] < -5.0)
      )
      # 1h downtrend, 1h downmove, 15m & 1h & 4h & 1d stil high, 4h high, pump in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 70.0)
        | (dataframe["r_480_4h"] < -30.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["hl_pct_change_6_1d"] < 0.9)
      )
      # current 4h red, previous 4h green, current 1h red, 15m & 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_4h"] > -0.04)
        | (dataframe["change_pct_4h"].shift(48) < 0.04)
        | (dataframe["change_pct_1h"] > -0.02)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 60.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
        | (dataframe["close"] > dataframe["zlma_50_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
    )

    # Global protections
    dataframe["protections_long_rebuy"] = (
      # 1h & 4h downtrend, 15m & 1h & 4h downmove
      (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_3_4h"] > 20.0)
      )
      # current 1d red, 5m & 15m downmove, 1h & 4h & 1d still high, pump in last 6 days
      & (
        (dataframe["change_pct_1d"] > -0.01)
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 26.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["hl_pct_change_6_1d"] < 0.5)
      )
      # 1h & 1d downtrend, 5m & 1h & 1d downmove, 1h downtrend, drop in last 6 days
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 16.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_3_1d"] > 20.0)
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["close"] > (dataframe["high_max_6_1d"] * 0.75))
      )
      # 5m & 15m downmove, 15m & 4h & 1d still high, 5m low, 1d downtrend
      & (
        (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_14_15m"] < 26.0)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 40.0)
        | (dataframe["r_480"] > -90.0)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 5m & 15m & 1h downmove, 15m & 4h & 1d still high
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 10.0)
        | (dataframe["rsi_3_15m"] > 36.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.8)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # 15m downtrend, 5m & 15m & 1h downmove, 5m & 15m & 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_15m"] > 30.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14"] < 30.0)
        | (dataframe["rsi_14_15m"] < 33.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["rsi_14_1d"] < 36.0)
        | (dataframe["close"] > dataframe["bb20_2_low_15m"])
      )
      # current 1d red, previous 1d green, 5m downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] > -0.03)
        | (dataframe["change_pct_1d"].shift(288) < 0.03)
        | (dataframe["rsi_3"] > 12.0)
        | (dataframe["rsi_14_15m"] < 46.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < -0.0)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["cti_20_1d"] < 0.7)
        | (dataframe["rsi_14_1d"] < 50.0)
      )
      # current 1d green, current 1h red, 5m downmove, 15m & 1h & 4h & 1d high
      & (
        (dataframe["change_pct_1d"] < 0.08)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["cti_20_1h"] < 0.5)
        | (dataframe["rsi_14_1h"] < 50.0)
        | (dataframe["cti_20_4h"] < 0.5)
        | (dataframe["rsi_14_4h"] < 70.0)
        | (dataframe["rsi_14_1d"] < 46.0)
      )
      # current 1d green with top wick, current 1h red, 5m & 1h downmove, 15m & 1h & 4h & 1d still high
      & (
        (dataframe["change_pct_1d"] < 0.03)
        | (dataframe["top_wick_pct_1d"] < 0.03)
        | (dataframe["change_pct_1h"] > -0.01)
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 46.0)
        | (dataframe["cti_20_4h"] < 0.7)
        | (dataframe["rsi_14_4h"] < 50.0)
        | (dataframe["rsi_14_1d"] < 60.0)
      )
      # 15m & 1h downtrend, 15m & 1h downmove, 1h & 4h & 1d still high
      & (
        (dataframe["not_downtrend_15m"])
        | (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3_15m"] > 20.0)
        | (dataframe["rsi_3_1h"] > 20.0)
        | (dataframe["rsi_14_1h"] < 30.0)
        | (dataframe["rsi_14_4h"] < 40.0)
        | (dataframe["cti_20_1d"] < 0.5)
        | (dataframe["rsi_14_1d"] < 50.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
      )
      # 1h & 4h downtrend, 5m & 1h downmove, 15m & 1h still high, 1h & 4h low, 1h & 4h & 1d downtrend
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["not_downtrend_4h"])
        | (dataframe["rsi_3"] > 30.0)
        | (dataframe["rsi_3_1h"] > 36.0)
        | (dataframe["rsi_14_15m"] < 36.0)
        | (dataframe["rsi_14_1h"] < 36.0)
        | (dataframe["r_480_1h"] > -75.0)
        | (dataframe["r_480_4h"] > -80.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_48_1h"] == False)
        | (dataframe["ema_200_dec_24_4h"] == False)
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
      # 1h downtrend, 5m & 15m downmove, 15m & 1h & 4h still high, 1h low
      & (
        (dataframe["not_downtrend_1h"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_1h"] > 30.0)
        | (dataframe["rsi_14_15m"] < 30.0)
        | (dataframe["cti_20_1h"] < -0.0)
        | (dataframe["rsi_14_1h"] < 40.0)
        | (dataframe["cti_20_4h"] < -0.5)
        | (dataframe["rsi_14_4h"] < 46.0)
        | (dataframe["r_480_1h"] > -75.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
      )
      # 4h & 1d downtrend, 5m & 15m & 4h downmove, 1d downtrend
      & (
        (dataframe["not_downtrend_4h"])
        | (dataframe["not_downtrend_1d"])
        | (dataframe["rsi_3"] > 20.0)
        | (dataframe["rsi_3_15m"] > 10.0)
        | (dataframe["rsi_3_4h"] > 20.0)
        | (dataframe["close"] > dataframe["sup_level_1h"])
        | (dataframe["close"] > dataframe["sup_level_4h"])
        | (dataframe["ema_200_dec_4_1d"] == False)
      )
    )

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] Populate indicators took a total of: {tok - tik:0.4f} seconds.")

    return dataframe

  def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    conditions = []
    dataframe.loc[:, "enter_tag"] = ""

    # the number of free slots
    current_free_slots = self.config["max_open_trades"] - len(LocalTrade.get_trades_proxy(is_open=True))
    # if BTC/ETH stake
    is_btc_stake = self.config["stake_currency"] in self.btc_stakes
    allowed_empty_candles = 144 if is_btc_stake else 60

    for buy_enable in self.entry_long_params:
      index = int(buy_enable.split("_")[2])
      item_buy_protection_list = [True]
      if self.entry_long_params[f"{buy_enable}"]:
        # Buy conditions
        # -----------------------------------------------------------------------------------------
        item_buy_logic = []
        item_buy_logic.append(reduce(lambda x, y: x & y, item_buy_protection_list))

        # Condition #1 - Long mode bull. Uptrend.
        if index == 1:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["cti_20_1h"] < 0.9)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 85.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.9)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 85.0)
          item_buy_logic.append(dataframe["cti_20_1d"] < 0.9)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 85.0)
          item_buy_logic.append(dataframe["r_14_1h"] < -25.0)
          item_buy_logic.append(dataframe["r_14_4h"] < -25.0)

          # Logic
          item_buy_logic.append(dataframe["ema_26"] > dataframe["ema_12"])
          item_buy_logic.append((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.02))
          item_buy_logic.append(
            (dataframe["ema_26"].shift() - dataframe["ema_12"].shift()) > (dataframe["open"] / 100)
          )
          item_buy_logic.append(dataframe["close"] < (dataframe["bb20_2_low"] * 0.999))

        # Condition #2 - Normal mode bull.
        if index == 2:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.16))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["cti_20_1h"] < 0.9)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 85.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.9)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 85.0)
          item_buy_logic.append(dataframe["cti_20_1d"] < 0.9)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 85.0)
          item_buy_logic.append(dataframe["r_14_1h"] < -25.0)
          item_buy_logic.append(dataframe["r_14_4h"] < -25.0)

          item_buy_logic.append(
            ((dataframe["not_downtrend_1h"]) & (dataframe["not_downtrend_4h"]))
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          )

          # Logic
          item_buy_logic.append(dataframe["bb40_2_delta"].gt(dataframe["close"] * 0.06))
          item_buy_logic.append(dataframe["close_delta"].gt(dataframe["close"] * 0.02))
          item_buy_logic.append(dataframe["bb40_2_tail"].lt(dataframe["bb40_2_delta"] * 0.2))
          item_buy_logic.append(dataframe["close"].lt(dataframe["bb40_2_low"].shift()))
          item_buy_logic.append(dataframe["close"].le(dataframe["close"].shift()))

        # Condition #3 - Normal mode bull.
        if index == 3:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.26))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["ema_12_1h"] > dataframe["ema_200_1h"])

          item_buy_logic.append(dataframe["ema_12_4h"] > dataframe["ema_200_4h"])

          item_buy_logic.append(dataframe["rsi_14_4h"] < 70.0)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 85.0)

          item_buy_logic.append((dataframe["change_pct_4h"] > -0.04) | (dataframe["change_pct_4h"].shift(48) < 0.04))

          # Logic
          item_buy_logic.append(dataframe["rsi_14"] < 36.0)
          item_buy_logic.append(dataframe["ha_close"] > dataframe["ha_open"])
          item_buy_logic.append((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.020))

        # Condition #4 - Normal mode bull.
        if index == 4:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["cti_20_1h"] < 0.9)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 85.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.9)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 85.0)
          item_buy_logic.append(dataframe["cti_20_1d"] < 0.9)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 85.0)

          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.5))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 16.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          # BNX
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 15.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1h"] == False)
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.5))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.5))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["r_480_4h"] < -30.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.3))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 16.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < 0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            ((dataframe["not_downtrend_1h"]) & (dataframe["not_downtrend_4h"]))
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 8.0))
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"].shift(48) < 0.02)
            | (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"].shift(48) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.7)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 8.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.06)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["high_max_6_1h"] < (dataframe["close"] * 1.25))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_4h"] == False)
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1d"] < 0.7)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.04)
            | (dataframe["top_wick_pct_4h"] < 0.04)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["rsi_14_1d"] < 50.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["rsi_3_4h"] > 30.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["hl_pct_change_24_1h"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.06)
            | (dataframe["top_wick_pct_1d"] < 0.06)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 50.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["hl_pct_change_6_1d"] < 0.7)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["rsi_3_4h"] > 10.0)
            | (dataframe["cti_20_1d"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.06)
            | (dataframe["top_wick_pct_1d"] < 0.06)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3"] > 10.0)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )

          # Logic
          item_buy_logic.append(dataframe["ema_26"] > dataframe["ema_12"])
          item_buy_logic.append((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.018))
          item_buy_logic.append(
            (dataframe["ema_26"].shift() - dataframe["ema_12"].shift()) > (dataframe["open"] / 100)
          )
          item_buy_logic.append(dataframe["close"] < (dataframe["bb20_2_low"] * 0.996))

        # Condition #5 - Normal mode bull.
        if index == 5:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.32)
            | (dataframe["top_wick_pct_4h"] < 0.16)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.3))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < -0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["cti_20_1h"] < 0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.9)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < -0.75)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.25))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.9)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.25))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.25))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.25))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.08))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.9)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.25))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.08))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.07))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.25))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.08))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.09))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.25))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.1))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 16.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.09))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.9)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < 0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1h"] == False)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.07))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1d"] < -0.75)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            ((dataframe["not_downtrend_1h"]) & (dataframe["not_downtrend_4h"]))
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.2))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.09))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.9)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close_max_48"] < (dataframe["close"] * 1.2))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 5.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["r_14_4h"] < -25.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["hl_pct_change_24_1h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 8.0))
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"].shift(48) < 0.06)
            | (dataframe["change_pct_4h"] > -0.06)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"].shift(48) < 80.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.18))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.08))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.1)
            | (dataframe["top_wick_pct_4h"] < 0.03)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close_max_12"] < (dataframe["close"] * 1.12))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.16)
            | (dataframe["top_wick_pct_4h"] < 0.08)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.12))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 8.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.1)
            | (dataframe["top_wick_pct_1d"] < 0.1)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 80.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 10.0)
            | (dataframe["rsi_3_15m"] > 16.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.08)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["close_max_48"] < (dataframe["close"] * 1.24))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.08)
            | (dataframe["top_wick_pct_1d"] < 0.08)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["top_wick_pct_4h"] < 0.02)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_14_1h"] < 30.0)
            | (dataframe["cti_20_4h"] < 0.7)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.03)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_1d"] < 0.7)
            | (dataframe["rsi_14_1d"] < 60.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.06)
            | (dataframe["top_wick_pct_1d"] < 0.06)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 50.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["hl_pct_change_6_1d"] < 0.7)
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )

          # Logic
          item_buy_logic.append(dataframe["ema_26"] > dataframe["ema_12"])
          item_buy_logic.append((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          item_buy_logic.append(
            (dataframe["ema_26"].shift() - dataframe["ema_12"].shift()) > (dataframe["open"] / 100)
          )
          item_buy_logic.append(dataframe["rsi_14"] < 36.0)

        # Condition #6 - Normal mode bull.
        if index == 6:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["cti_20_1h"] < 0.5)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.75)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 85.0)

          item_buy_logic.append(
            ((dataframe["not_downtrend_1h"]) & (dataframe["not_downtrend_4h"]))
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.02)
            | (dataframe["top_wick_pct_1d"] < 0.06)
            | (dataframe["change_pct_1d"].shift(288) < 0.02)
            | (dataframe["cti_20_1d"] < 0.8)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.3))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.9))
            | (dataframe["rsi_3"] > 20.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.9))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.9))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.9))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.9))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close_max_12"] < (dataframe["close"] * 1.12))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close_max_12"] < (dataframe["close"] * 1.12))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["close_max_12"] < (dataframe["close"] * 1.16))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.9))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["close_max_12"] < (dataframe["close"] * 1.12))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["close_max_12"] < (dataframe["close"] * 1.12))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.8)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 5.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.89))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_14_1h"] < 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close_max_12"] < (dataframe["close"] * 1.12))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close_max_48"] < (dataframe["close"] * 1.26))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.86))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.9))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["r_480_4h"] > -95.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.9))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_1h"] < (dataframe["close"] * 1.3))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close_max_12"] < (dataframe["close"] * 1.12))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 8.0))
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.1)
            | (dataframe["top_wick_pct_1d"] < 0.1)
            | (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 20.0) | (dataframe["rsi_3_15m"] > 20.0) | (dataframe["cti_20_1d"] < 0.8)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 4.0))
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.08)
            | (dataframe["top_wick_pct_1d"] < 0.08)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 3.0)
            | (dataframe["high_max_12_1d"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["hl_pct_change_6_1d"] < 0.7)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["rsi_3_4h"] > 10.0)
            | (dataframe["cti_20_1d"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["rsi_3_4h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 5.0)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3"] > 5.0)
            | (dataframe["rsi_3_15m"] > 16.0)
            | (dataframe["rsi_3_1h"] > 26.0)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.90))
          )

          # Logic
          item_buy_logic.append(dataframe["close"] < (dataframe["ema_26"] * 0.94))
          item_buy_logic.append(dataframe["close"] < (dataframe["bb20_2_low"] * 0.996))

        # Condition #7 Normal mode.
        if index == 7:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["cti_20_1h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_1d"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 80.0)

          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.04)
            | (dataframe["top_wick_pct_4h"] < 0.04)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.04)
            | (dataframe["top_wick_pct_4h"] < 0.04)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1d"] == False)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.08)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.08)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.1)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 50.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.08)
            | (dataframe["change_pct_1d"].shift(288) < 0.08)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"].shift(288) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["rsi_14_1d"] < 40.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.08)
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["rsi_14_4h"] < 40.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["rsi_14_1h"] < 30.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 40.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["rsi_14_4h"] < 50.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 40.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 50.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 2.0))
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 20.0)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["rsi_14"] > dataframe["rsi_14"].shift(1).rolling(6).min())
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_24_15m"] == False)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 6.0)
            | (dataframe["rsi_14_15m"] < 46.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 10.0)
            | (dataframe["rsi_14_15m"] < 46.0)
            | (dataframe["cti_20_1h"] < -0.7)
            | (dataframe["cti_20_4h"] < -0.7)
            | (dataframe["rsi_14_1d"] < 60.0)
          )

          # Logic
          item_buy_logic.append(dataframe["close"] < (dataframe["ema_16"] * 0.974))
          item_buy_logic.append(dataframe["ewo_50_200"] > 2.0)
          item_buy_logic.append(dataframe["rsi_14"] < 30.0)

        # Condition #8 Normal mode.
        if index == 8:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["cti_20_1h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_1d"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 80.0)

          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["r_14_1h"] > -95.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.04)
            | (dataframe["top_wick_pct_1d"] < 0.04)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 4.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["rsi_14_1h"] < 20.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["rsi_14_4h"] < 20.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_1h"] < 20.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["rsi_14_4h"] < 30.0)
            | (dataframe["rsi_14_1d"] < 50.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["rsi_3_4h"] > 20.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["rsi_3_4h"] > 10.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["rsi_3_4h"] > 10.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["rsi_3_4h"] > 10.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_4h"] == False)
            | (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_4h"] > 10.0)
          )

          # Logic
          item_buy_logic.append(dataframe["close"] < (dataframe["ema_16"] * 0.944))
          item_buy_logic.append(dataframe["ewo_50_200"] < -4.0)
          item_buy_logic.append(dataframe["rsi_14"] < 30.0)

        # Condition #9 - Normal mode.
        if index == 9:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.4))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["cti_20_1h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_1d"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 80.0)

          item_buy_logic.append(
            (dataframe["cti_20_4h"] < 0.5) | (dataframe["high_max_6_1h"] < (dataframe["close"] * 1.1))
          )
          item_buy_logic.append(
            (dataframe["rsi_14_4h"] < 40.0) | (dataframe["high_max_6_1h"] < (dataframe["close"] * 1.1))
          )
          item_buy_logic.append((dataframe["change_pct_4h"] > -0.06) | (dataframe["cti_20_4h"] < 0.5))
          item_buy_logic.append((dataframe["change_pct_4h"] > -0.06) | (dataframe["rsi_14_4h"] < 40.0))
          item_buy_logic.append((dataframe["is_downtrend_3_4h"] == False) | (dataframe["cti_20_4h"] < 0.5))
          item_buy_logic.append((dataframe["is_downtrend_3_4h"] == False) | (dataframe["rsi_14_4h"] < 40.0))
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["rsi_3_4h"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["rsi_3_4h"] > 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["rsi_3_4h"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["rsi_3_4h"] > 20.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["rsi_3_4h"] > 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1d"] == False)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 40.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["rsi_3_4h"] > 25.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["rsi_14_1d"] < 40.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["rsi_14_1d"] < 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["rsi_3_4h"] > 10.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 5.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["rsi_3_4h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["rsi_3_4h"] > 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26_15m"] - dataframe["ema_12_15m"]) > (dataframe["open_15m"] * 0.030))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26_15m"] - dataframe["ema_12_15m"]) > (dataframe["open_15m"] * 0.030))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["rsi_3_4h"] > 10.0)
            | (dataframe["cti_20_1d"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.5))
            | ((dataframe["ema_26_15m"] - dataframe["ema_12_15m"]) > (dataframe["open_15m"] * 0.040))
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1d"] == False)
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_1d"] < 0.5)
          )

          # Logic
          item_buy_logic.append(dataframe["ema_26_15m"] > dataframe["ema_12_15m"])
          item_buy_logic.append((dataframe["ema_26_15m"] - dataframe["ema_12_15m"]) > (dataframe["open_15m"] * 0.020))
          item_buy_logic.append(
            (dataframe["ema_26_15m"].shift(3) - dataframe["ema_12_15m"].shift(3)) > (dataframe["open_15m"] / 100.0)
          )
          item_buy_logic.append(dataframe["close_15m"] < (dataframe["bb20_2_low_15m"] * 0.99))

        # Condition #21 - Pump mode bull.
        if index == 21:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.16))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["ema_200_dec_48_1h"] == False)
          item_buy_logic.append(dataframe["ema_200_dec_24_4h"] == False)

          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.8)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.06))
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          # CHZ
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_14_1h"] < 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.75)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < 0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.9)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["r_14_4h"] > -50.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.9)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < -0.8)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.08)
            | (dataframe["top_wick_pct_4h"] < 0.08)
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_14_1h"] > 60.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.8)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["rsi_14_15m"] > 30.0)
            | (dataframe["cti_20_1h"] < -0.9)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < -0.75)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 10.0)
            | (dataframe["rsi_14_1h"] < 10.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.07))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 5.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["r_14_4h"] < -25.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.06)
            | (dataframe["change_pct_1d"].shift(288) > -0.06)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["close"] < (dataframe["ema_200_4h"] * 1.1))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["hl_pct_change_24_1h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 8.0))
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"].shift(288) < 0.02)
            | (dataframe["change_pct_1d"] > -0.06)
            | (dataframe["cti_20_1d"] < 0.85)
            | (dataframe["rsi_14_1d"].shift(288) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 20.0) | (dataframe["rsi_3_15m"] > 20.0) | (dataframe["cti_20_1d"] < 0.8)
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1d"] == False)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.8))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 65.0)
            | (dataframe["high_max_6_1h"] < (dataframe["close"] * 1.3))
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1h"] == False)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 65.0)
            | (dataframe["high_max_6_1h"] < (dataframe["close"] * 1.25))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["cti_20_4h"] < 0.85)
            | (dataframe["cti_20_4h"].shift(48) < 0.85)
            | (dataframe["rsi_14_4h"].shift(48) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["rsi_14_1d"] < 50.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["rsi_14_1h"] < 30.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["rsi_14_4h"] < 20.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["rsi_14_1d"] < 30.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["rsi_14_4h"] < 30.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_1d"] < 0.7)
            | (dataframe["rsi_14_1d"] < 60.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["hl_pct_change_6_1d"] < 0.7)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 6.0))
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_4h"] < -0.5)
          )

          # Logic
          item_buy_logic.append(dataframe["ema_26"] > dataframe["ema_12"])
          item_buy_logic.append((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.016))
          item_buy_logic.append(
            (dataframe["ema_26"].shift() - dataframe["ema_12"].shift()) > (dataframe["open"] / 100)
          )
          item_buy_logic.append(dataframe["rsi_14"] < 36.0)

        # Condition #22 - Pump mode bull.
        if index == 22:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))

          item_buy_logic.append(dataframe["rsi_14_1h"] < 85.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.9)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 85.0)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 85.0)

          item_buy_logic.append(dataframe["ema_200_1h"] > dataframe["ema_200_1h"].shift(96))
          item_buy_logic.append(dataframe["ema_200_dec_48_1h"] == False)
          item_buy_logic.append(dataframe["sma_200_1h"] > dataframe["sma_200_1h"].shift(24))

          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.02)
            | (dataframe["top_wick_pct_1d"] < 0.06)
            | (dataframe["change_pct_1d"].shift(288) < 0.02)
            | (dataframe["cti_20_1d"] < 0.8)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < 0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.75)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.75)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.75)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.9))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < 0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.9)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.75)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.95))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.96))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 8.0))
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.1)
            | (dataframe["top_wick_pct_4h"] < 0.03)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.05) | (dataframe["cti_20_1d"] < 0.8) | (dataframe["rsi_14_1d"] < 65.0)
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 20.0) | (dataframe["rsi_3_15m"] > 20.0) | (dataframe["cti_20_1d"] < 0.8)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_4h"] < 0.5) | (dataframe["rsi_14_4h"] < 70.0) | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.03)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.06)
            | (dataframe["change_pct_4h"].shift(48) < 0.06)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["hl_pct_change_24_1h"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.94))
          )
          item_buy_logic.append(
            (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_16"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["hl_pct_change_6_1d"] < 0.7)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["hl_pct_change_6_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 6.0))
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_4h"] < -0.5)
          )

          # Logic
          item_buy_logic.append(dataframe["close"] < (dataframe["ema_16"] * 0.968))
          item_buy_logic.append(dataframe["cti_20"] < -0.9)
          item_buy_logic.append(dataframe["rsi_14"] < 50.0)

        # Condition #23 - Pump mode.
        if index == 23:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.4))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.6)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.8)
          item_buy_logic.append(dataframe["hl_pct_change_6_1d"] < 1.5)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["cti_20_4h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)

          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 12.0)
            | (dataframe["rsi_3_1h"] > 12.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.0)
            | (dataframe["change_pct_4h"].shift(48) < 0.02)
            | (dataframe["cti_20_4h"] < 0.8)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1h"] > -0.02)
            | (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["change_pct_4h"].shift(48) < 0.02)
            | (dataframe["cti_20_1h"] < 0.8)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.0)
            | (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 6.0))
          )
          item_buy_logic.append(
            (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.8)
            | (dataframe["rsi_14_1d"] < 80.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.08)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_4h"] < 0.7)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1h"] > -0.02)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < 0.7)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.7)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1h"] > -0.0)
            | (dataframe["rsi_3_15m"] > 6.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.0)
            | (dataframe["rsi_3_15m"] > 5.0)
            | (dataframe["cti_20_4h"] < 0.7)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.7)
            | (((dataframe["ema_12_4h"] - dataframe["ema_26_4h"]) / dataframe["ema_26_4h"]) < 0.08)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["rsi_3_15m"] > 26.0)
            | (dataframe["rsi_3_1h"] > 16.0)
            | (dataframe["cti_20_4h"] < 0.8)
          )

          # Logic
          item_buy_logic.append(dataframe["ewo_50_200_15m"] > 4.2)
          item_buy_logic.append(dataframe["rsi_14_15m"].shift(1) < 30.0)
          item_buy_logic.append(dataframe["rsi_14_15m"] < 30.0)
          item_buy_logic.append(dataframe["rsi_14"] < 35.0)
          item_buy_logic.append(dataframe["cti_20"] < -0.8)
          item_buy_logic.append(dataframe["close"] < (dataframe["ema_26_15m"] * 0.958))

        # Condition #41 - Quick mode bull.
        if index == 41:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          # pump and now started dumping, still high
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.05)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["hl_pct_change_48_1h"] < 0.4)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.16)
            | (dataframe["top_wick_pct_1d"] < 0.1)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.06)
            | (dataframe["top_wick_pct_4h"] < 0.06)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.02)
            | (dataframe["top_wick_pct_1d"] < 0.06)
            | (dataframe["change_pct_1d"].shift(288) < 0.12)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.06)
            | (dataframe["change_pct_4h"].shift(48) < 0.06)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["cti_20_4h"] < 0.85)
            | (dataframe["cti_20_4h"].shift(48) < 0.85)
            | (dataframe["rsi_14_4h"].shift(48) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_4h"] < 0.5) | (dataframe["cti_20_1d"] < 0.9) | (dataframe["rsi_14_1d"] < 75.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.75)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.75)
            | (dataframe["cti_20_1d"] < -0.8)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.75)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < 0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < -0.75)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["r_14_4h"] < -30.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < 0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["hl_pct_change_48_1h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.3))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.3))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.75)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.8)
          )
          item_buy_logic.append(
            (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.75)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < 0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["cti_20_1d"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close_max_12"] < (dataframe["close"] * 1.12))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.06)
            | (dataframe["change_pct_1d"].shift(288) > -0.06)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["close"] < (dataframe["ema_200_4h"] * 1.1))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < -0.75)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["r_480_1h"] > -95.0)
            | (dataframe["r_480_4h"] > -95.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 6.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1d"] == False)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.8))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_4h"] == False)
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1d"] < 0.7)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_4h"] < 0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.06)
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 40.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["hl_pct_change_6_1d"] < 0.7)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["rsi_14_1h"] < 30.0)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["rsi_3_4h"] > 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_3"] > 20.0)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.03) | (dataframe["cti_20_1h"] < -0.5) | (dataframe["cti_20_4h"] < 0.7)
          )
          item_buy_logic.append(
            (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.3))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )

          # Logic
          item_buy_logic.append(dataframe["bb40_2_delta"].gt(dataframe["close"] * 0.036))
          item_buy_logic.append(dataframe["close_delta"].gt(dataframe["close"] * 0.02))
          item_buy_logic.append(dataframe["bb40_2_tail"].lt(dataframe["bb40_2_delta"] * 0.4))
          item_buy_logic.append(dataframe["close"].lt(dataframe["bb40_2_low"].shift()))
          item_buy_logic.append(dataframe["close"].le(dataframe["close"].shift()))
          item_buy_logic.append(dataframe["rsi_14"] < 36.0)

        # Condition #42 - Quick mode bull.
        if index == 42:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["cti_20_1h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)

          item_buy_logic.append(
            ((dataframe["not_downtrend_1h"]) & (dataframe["not_downtrend_4h"]))
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 5.0))
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 5.0))
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.1)
            | (dataframe["top_wick_pct_1d"] < 0.05)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 80.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"].shift(48) < 0.1)
            | (dataframe["change_pct_4h"] > -0.04)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 2.0))
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 80.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.05))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.16)
            | (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.75)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 20.0) | (dataframe["rsi_3_15m"] > 20.0) | (dataframe["cti_20_1d"] < 0.8)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 8.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 4.0))
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.04)
            | (dataframe["top_wick_pct_4h"] < 0.04)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 3.0)
            | (dataframe["high_max_12_1d"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.03)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.06)
            | (dataframe["top_wick_pct_1d"] < 0.06)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 50.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.01)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["hl_pct_change_6_1d"] < 0.7)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.06)
            | (dataframe["top_wick_pct_1d"] < 0.06)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )

          # Logic
          item_buy_logic.append(dataframe["ema_26"] > dataframe["ema_12"])
          item_buy_logic.append((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.018))
          item_buy_logic.append(
            (dataframe["ema_26"].shift() - dataframe["ema_12"].shift()) > (dataframe["open"] / 100)
          )
          item_buy_logic.append(dataframe["close"] < (dataframe["bb20_2_low"] * 0.996))
          item_buy_logic.append(dataframe["rsi_14"] < 40.0)

        # Condition #43 - Quick mode bull.
        if index == 43:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)

          item_buy_logic.append(dataframe["cti_20_1h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)

          item_buy_logic.append(
            ((dataframe["not_downtrend_1h"]) & (dataframe["not_downtrend_4h"]))
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 5.0))
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 5.0))
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.1)
            | (dataframe["top_wick_pct_4h"] < 0.05)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.16)
            | (dataframe["top_wick_pct_4h"] < 0.08)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.06)
            | (dataframe["change_pct_1d"].shift(288) < 0.1)
            | (dataframe["top_wick_pct_1d"].shift(288) < 0.1)
            | (dataframe["cti_20_1d"].shift(288) < 0.8)
            | (dataframe["rsi_14_1d"].shift(288) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.1)
            | (dataframe["top_wick_pct_1d"] < 0.05)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 80.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"].shift(48) < 0.1)
            | (dataframe["change_pct_4h"] > -0.04)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 2.0))
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 80.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.12))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.9))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.9)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close_max_12"] < (dataframe["close"] * 1.1))
            | (dataframe["close"] < (dataframe["ema_26"] * 0.89))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.16)
            | (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.75)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.1)
            | (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.9)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.93))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.91))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.92))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close"] < (dataframe["ema_26"] * 0.88))
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 20.0) | (dataframe["rsi_3_15m"] > 20.0) | (dataframe["cti_20_1d"] < 0.8)
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 10.0)
            | (dataframe["rsi_3_15m"] > 16.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1d"] == False)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3"] > 10.0)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 4.0))
            | (dataframe["change_pct_1h"] > -0.02)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )

          # Logic
          item_buy_logic.append(dataframe["close"] < (dataframe["ema_26"] * 0.938))
          item_buy_logic.append(dataframe["cti_20"] < -0.75)
          item_buy_logic.append(dataframe["r_14"] < -94.0)

        # Condition #44 - Quick mode bull.
        if index == 44:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["cti_20_1h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)

          item_buy_logic.append(dataframe["close_max_48"] > (dataframe["close"] * 1.1))

          # pump and now started dumping, still high
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.05)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["hl_pct_change_48_1h"] < 0.4)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.1)
            | (dataframe["top_wick_pct_1d"] < 0.1)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.06)
            | (dataframe["top_wick_pct_4h"] < 0.06)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.02)
            | (dataframe["top_wick_pct_1d"] < 0.06)
            | (dataframe["change_pct_1d"].shift(288) < 0.12)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.06)
            | (dataframe["change_pct_4h"].shift(48) < 0.06)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["cti_20_4h"] < 0.85)
            | (dataframe["cti_20_4h"].shift(48) < 0.85)
            | (dataframe["rsi_14_4h"].shift(48) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 5.0))
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 5.0))
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.1)
            | (dataframe["top_wick_pct_1d"] < 0.05)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 80.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"].shift(48) < 0.1)
            | (dataframe["change_pct_4h"] > -0.04)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 2.0))
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 80.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.16)
            | (dataframe["top_wick_pct_4h"] < 0.08)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.06)
            | (dataframe["change_pct_1d"].shift(288) < 0.1)
            | (dataframe["top_wick_pct_1d"].shift(288) < 0.1)
            | (dataframe["cti_20_1d"].shift(288) < 0.8)
            | (dataframe["rsi_14_1d"].shift(288) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.1)
            | (dataframe["change_pct_1d"].shift(288) < 0.1)
            | (dataframe["cti_20_1d"].shift(288) < 0.5)
            | (dataframe["rsi_14_1d"].shift(288) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.1)
            | (dataframe["top_wick_pct_1d"] < 0.05)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["rsi_14_1d"] < 80.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.2)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.06)
            | (dataframe["top_wick_pct_4h"] < 0.06)
            | (dataframe["change_pct_4h"].shift(48) < 0.01)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"].shift(48) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1h"] < (abs(dataframe["change_pct_1h"]) * 3.0))
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.04)
            | (dataframe["top_wick_pct_4h"] < 0.06)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.06)
            | (dataframe["top_wick_pct_4h"] < 0.06)
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.06)
            | (dataframe["top_wick_pct_4h"] < 0.06)
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1h"] > -0.08)
            | (dataframe["change_pct_1h"].shift(12) < 0.08)
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.06)
            | (dataframe["top_wick_pct_4h"] < 0.06)
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.1)
            | (dataframe["top_wick_pct_4h"] < 0.06)
            | (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.04)
            | (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 4.0))
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.9)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.08)
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.05)
            | (dataframe["top_wick_pct_1d"] < 0.05)
            | (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["is_downtrend_3_4h"] == False)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["close"] < (dataframe["ema_200_4h"] * 1.1))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1h"] == False)
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 2.0))
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.1)
            | (dataframe["top_wick_pct_4h"] < 0.03)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.04)
            | (dataframe["top_wick_pct_1d"] < 0.04)
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 50.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1h"] > -0.03)
            | (dataframe["change_pct_1h"].shift(12) < 0.03)
            | (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 2.0))
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_1h"] < 0.5) | (dataframe["cti_20_4h"] < 0.5) | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.06) | (dataframe["cti_20_1h"] < 0.5) | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"].shift(48) < 0.04)
            | (dataframe["top_wick_pct_4h"].shift(48) < 0.04)
            | (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.06)
            | (dataframe["change_pct_1d"].shift(288) < 0.06)
            | (dataframe["cti_20_1d"].shift(288) < 0.8)
            | (dataframe["rsi_14_1d"].shift(288) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.04)
            | (dataframe["top_wick_pct_4h"] < 0.04)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 50.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.16)
            | (dataframe["top_wick_pct_1d"] < 0.16)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.16)
            | (dataframe["top_wick_pct_1d"] < 0.16)
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.16)
            | (dataframe["top_wick_pct_1d"] < 0.16)
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.1)
            | (dataframe["top_wick_pct_4h"] < 0.1)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < -0.9)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 4.0))
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.08)
            | (dataframe["top_wick_pct_4h"] < 0.04)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1h"] > -0.02)
            | (dataframe["change_pct_1h"].shift(12) < 0.04)
            | (dataframe["top_wick_pct_1h"].shift(12) < 0.04)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["bb20_2_width_1h"] > 0.18)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 5.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.26)
            | (dataframe["top_wick_pct_1d"] < 0.06)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1d"] == False)
            | (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["change_pct_1h"] > -0.06)
            | (dataframe["change_pct_1h"].shift(12) < 0.06)
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 3.0))
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.8)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["bb20_2_width_1h"] > 0.18)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["bb20_2_width_1h"] > 0.2)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.2)
            | (dataframe["top_wick_pct_1d"] < 0.05)
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1d"] < -0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["bb20_2_width_1h"] > 0.17)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.25)
            | (dataframe["top_wick_pct_1d"] < 0.2)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < -0.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["r_14"] < -96.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["bb20_2_width_1h"] > 0.16)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.05)
            | (dataframe["top_wick_pct_4h"] < 0.05)
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["bb20_2_width_1h"] > 0.22)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.1)
            | (dataframe["top_wick_pct_1d"] < 0.06)
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < 0.8)
            | (dataframe["rsi_14_1d"] < 70.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["bb20_2_width_1h"] > 0.17)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["is_downtrend_3_1d"] == False)
            | (dataframe["rsi_3_15m"] > 16.0)
            | (dataframe["rsi_3_1h"] > 16.0)
            | (dataframe["cti_20_1d"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["bb20_2_width_1h"] > 0.18)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["bb20_2_width_1h"] > 0.16)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["bb20_2_width_1h"] > 0.19)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"].shift(48) < 0.06)
            | (dataframe["change_pct_4h"] > -0.06)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["rsi_3_1h"] > 12.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["bb20_2_width_1h"] > 0.23)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_4h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["bb20_2_width_1h"] > 0.22)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["bb20_2_width_1h"] > 0.22)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"].shift(48) < 0.16)
            | (dataframe["top_wick_pct_4h"].shift(48) < 0.04)
            | (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["top_wick_pct_4h"] < 0.04)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1d"] == False)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["high_max_6_1d"] < (dataframe["close"] * 1.8))
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 2.0))
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["cti_20_4h"] < -0.8)
            | (dataframe["cti_20_1d"] < -0.8)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["bb20_2_width_1h"] > 0.25)
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 10.0)
            | (dataframe["rsi_3_15m"] > 16.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_1h"] < (abs(dataframe["change_pct_1h"]) * 4.0))
            | (dataframe["rsi_14_1h"] < 70.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1d"] == False)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_1h"] > 30.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.25))
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_1d"] == False)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.04)
            | (dataframe["top_wick_pct_1d"] < 0.04)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_3_1h"] > 25.0)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["cti_20_4h"] < -0.5)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["rsi_3_15m"] > 20.0)
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_14_15m"] < 20.0)
            | (dataframe["rsi_3_1h"] > 20.0)
            | (dataframe["r_480_1h"] > -90.0)
            | (dataframe["rsi_3_4h"] > 30.0)
            | (dataframe["r_480_4h"] > -90.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["top_wick_pct_4h"] < 0.02)
            | (dataframe["cti_20_4h"].shift(48) < 0.5)
            | (dataframe["rsi_14_4h"].shift(48) < 70.0)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["rsi_14_15m"] < 30.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.06)
            | (dataframe["top_wick_pct_4h"] < 0.06)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["rsi_14_4h"] < 60.0)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 2.0))
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 4.0))
            | (dataframe["rsi_14_1h"] < 40.0)
            | (dataframe["rsi_14_4h"] < 40.0)
            | (dataframe["rsi_14_1d"] < 40.0)
            | (dataframe["cti_20_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.06)
            | (dataframe["top_wick_pct_4h"] < 0.06)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.02)
            | (dataframe["top_wick_pct_4h"] < 0.02)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["rsi_3_15m"] > 25.0)
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
            | (dataframe["hl_pct_change_6_1d"] < 0.5)
          )
          item_buy_logic.append(
            (dataframe["is_downtrend_3_4h"] == False)
            | (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["rsi_3_1h"] > 20.0)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["rsi_3_1h"] > 6.0)
            | (dataframe["rsi_3_4h"] > 16.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
          )
          item_buy_logic.append(
            (dataframe["rsi_3"] > 12.0)
            | (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["rsi_14_15m"] < 36.0)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["rsi_14_1h"] < 60.0)
            | (dataframe["rsi_14_4h"] < 60.0)
          )

          # Logic
          item_buy_logic.append(dataframe["bb20_2_width_1h"] > 0.132)
          item_buy_logic.append(dataframe["cti_20"] < -0.8)
          item_buy_logic.append(dataframe["r_14"] < -90.0)

        # Condition #45 - Quick mode (Long).
        if index == 45:
          # Protections
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close"] > (dataframe["close_max_12"] * self.entry_45_close_max_12.value))
          item_buy_logic.append(dataframe["close"] > (dataframe["close_max_24"] * self.entry_45_close_max_24.value))
          item_buy_logic.append(dataframe["close"] > (dataframe["close_max_48"] * self.entry_45_close_max_48.value))
          item_buy_logic.append(
            dataframe["close"] > (dataframe["high_max_24_1h"] * self.entry_45_high_max_24_1h.value)
          )
          item_buy_logic.append(
            dataframe["close"] > (dataframe["high_max_24_4h"] * self.entry_45_high_max_24_4h.value)
          )
          item_buy_logic.append(dataframe["close"] > (dataframe["high_max_6_1d"] * self.entry_45_high_max_6_1d.value))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < self.entry_45_hl_pct_change_6_1h.value)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < self.entry_45_hl_pct_change_12_1h.value)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < self.entry_45_hl_pct_change_24_1h.value)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < self.entry_45_hl_pct_change_48_1h.value)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["rsi_3"] > self.entry_45_rsi_3_min.value)
          item_buy_logic.append(dataframe["rsi_3"] < self.entry_45_rsi_3_max.value)
          item_buy_logic.append(dataframe["rsi_3_15m"] > self.entry_45_rsi_3_15m_min.value)
          item_buy_logic.append(dataframe["rsi_3_1h"] > self.entry_45_rsi_3_1h_min.value)
          item_buy_logic.append(dataframe["rsi_3_4h"] > self.entry_45_rsi_3_4h_min.value)
          item_buy_logic.append(dataframe["rsi_3_1d"] > self.entry_45_rsi_3_1d_min.value)
          item_buy_logic.append(dataframe["cti_20_1h"] < self.entry_45_cti_20_1h_max.value)
          item_buy_logic.append(dataframe["rsi_14_1h"] < self.entry_45_rsi_14_1h_max.value)
          item_buy_logic.append(dataframe["cti_20_4h"] < self.entry_45_cti_20_4h_max.value)
          item_buy_logic.append(dataframe["rsi_14_4h"] < self.entry_45_rsi_14_4h_max.value)
          item_buy_logic.append(dataframe["cti_20_1d"] < self.entry_45_cti_20_1d_max.value)
          item_buy_logic.append(dataframe["rsi_14_1d"] < self.entry_45_rsi_14_1d_max.value)

          if self.entry_45_sup_level_1h_enabled.value:
            item_buy_logic.append(dataframe["close"] > dataframe["sup_level_1h"])
          if self.entry_45_res_level_1h_enabled.value:
            item_buy_logic.append(dataframe["close"] < dataframe["res_level_1h"])
          if self.entry_45_sup_level_4h_enabled.value:
            item_buy_logic.append(dataframe["close"] > dataframe["sup_level_4h"])
          if self.entry_45_res_level_4h_enabled.value:
            item_buy_logic.append(dataframe["close"] < dataframe["res_level_4h"])
          if self.entry_45_sup_level_1d_enabled.value:
            item_buy_logic.append(dataframe["close"] > dataframe["sup_level_1d"])
          if self.entry_45_res_level_1d_enabled.value:
            item_buy_logic.append(dataframe["close"] < dataframe["res_level_1h"])

          # Logic
          item_buy_logic.append(dataframe["rsi_14"] > self.entry_45_rsi_14_min.value)
          item_buy_logic.append(dataframe["rsi_14"] < self.entry_45_rsi_14_max.value)
          item_buy_logic.append(dataframe["rsi_20"] < dataframe["rsi_20"].shift(1))
          item_buy_logic.append(dataframe["cti_20"] < self.entry_45_cti_20_max.value)
          item_buy_logic.append(dataframe["close"] < (dataframe["sma_16"] * self.entry_45_sma_offset.value))

        # Condition #61 - Rebuy mode (Long).
        if index == 61:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["protections_long_rebuy"] == True)
          item_buy_logic.append(current_free_slots >= self.rebuy_mode_min_free_slots)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.3))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.75))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)

          item_buy_logic.append(dataframe["rsi_3_15m"] > 6.0)
          item_buy_logic.append(dataframe["rsi_3_1h"] > 6.0)
          item_buy_logic.append(dataframe["rsi_3_4h"] > 6.0)
          item_buy_logic.append(dataframe["cti_20_15m"] < 0.9)
          item_buy_logic.append(dataframe["cti_20_1h"] < 0.9)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.9)
          item_buy_logic.append(dataframe["cti_20_1d"] < 0.9)

          # Logic
          item_buy_logic.append(dataframe["rsi_14"] < 40.0)
          item_buy_logic.append(dataframe["bb40_2_delta"].gt(dataframe["close"] * 0.03))
          item_buy_logic.append(dataframe["close_delta"].gt(dataframe["close"] * 0.014))
          item_buy_logic.append(dataframe["bb40_2_tail"].lt(dataframe["bb40_2_delta"] * 0.4))
          item_buy_logic.append(dataframe["close"].lt(dataframe["bb40_2_low"].shift()))
          item_buy_logic.append(dataframe["close"].le(dataframe["close"].shift()))

        # Condition #81 - Long mode bull.
        if index == 81:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.12))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.16))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["high_max_6_1h"] < (dataframe["close"] * 1.24))

          item_buy_logic.append(dataframe["cti_20_1h"] < 0.95)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.95)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 85.0)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 85.0)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 85.0)
          item_buy_logic.append(dataframe["r_14_1h"] < -25.0)
          item_buy_logic.append(dataframe["r_14_4h"] < -25.0)

          item_buy_logic.append(dataframe["pct_change_high_max_6_24_1h"] > -0.3)
          item_buy_logic.append(dataframe["pct_change_high_max_3_12_4h"] > -0.4)

          item_buy_logic.append(dataframe["not_downtrend_15m"])

          # current 4h relative long top wick, overbought 1h, downtrend 1h, downtrend 4h
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 2.0))
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["ema_200_1h"] > dataframe["ema_200_1h"].shift(288))
            | (dataframe["ema_200_4h"] > dataframe["ema_200_4h"].shift(576))
          )
          # current 4h relative long top wick, overbought 1d
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 6.0)) | (dataframe["cti_20_1d"] < 0.5)
          )
          # current 4h relative long top wick, overbought 1h, downtrend 1h
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 2.0))
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["not_downtrend_1h"])
          )
          # big drop in last 48h, downtrend 1h
          item_buy_logic.append(
            (dataframe["high_max_48_1h"] < (dataframe["close"] * 1.5)) | (dataframe["not_downtrend_1h"])
          )
          # downtrend 1h, downtrend 4h, drop in last 2h
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["not_downtrend_4h"])
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          # downtrend 1h, overbought 1h
          item_buy_logic.append((dataframe["not_downtrend_1h"]) | (dataframe["cti_20_1h"] < 0.5))
          # downtrend 1h, overbought 4h
          item_buy_logic.append((dataframe["not_downtrend_1h"]) | (dataframe["cti_20_4h"] < 0.5))
          # downtrend 1h, downtrend 4h, overbought 1d
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"]) | (dataframe["not_downtrend_4h"]) | (dataframe["cti_20_1d"] < 0.5)
          )
          # downtrend 1d, overbought 1d
          item_buy_logic.append((dataframe["is_downtrend_3_1d"] == False) | (dataframe["cti_20_1d"] < 0.5))
          # downtrend 1d, downtrend 1h
          item_buy_logic.append((dataframe["is_downtrend_3_1d"] == False) | (dataframe["not_downtrend_1h"]))
          # current 4h red, previous 4h green, overbought 4h
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.06)
            | (dataframe["change_pct_4h"].shift(48) < 0.06)
            | (dataframe["cti_20_4h"] < 0.5)
          )
          # current 1d long green with long top wick
          item_buy_logic.append((dataframe["change_pct_1d"] < 0.12) | (dataframe["top_wick_pct_1d"] < 0.12))
          # current 1d long 1d with top wick, overbought 1d, downtrend 1h
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.2)
            | (dataframe["top_wick_pct_1d"] < 0.04)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["not_downtrend_1h"])
          )
          # current 1d long red, overbought 1d, downtrend 1h
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.1) | (dataframe["cti_20_1d"] < 0.5) | (dataframe["not_downtrend_1h"])
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.5)
            | (dataframe["cti_20_1h"] < 0.5)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["cti_20_1d"] < 0.75)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.0)
            | (dataframe["cti_20_1h"] < -0.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | (dataframe["ema_200_dec_48_1h"] == False)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )

          # Logic
          item_buy_logic.append(dataframe["bb40_2_delta"].gt(dataframe["close"] * 0.052))
          item_buy_logic.append(dataframe["close_delta"].gt(dataframe["close"] * 0.024))
          item_buy_logic.append(dataframe["bb40_2_tail"].lt(dataframe["bb40_2_delta"] * 0.2))
          item_buy_logic.append(dataframe["close"].lt(dataframe["bb40_2_low"].shift()))
          item_buy_logic.append(dataframe["close"].le(dataframe["close"].shift()))
          item_buy_logic.append(dataframe["rsi_14"] < 30.0)

        # Condition #82 - Long mode bull.
        if index == 82:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["high_max_12_1h"] < (dataframe["close"] * 1.3))

          item_buy_logic.append(dataframe["ema_50_1h"] > dataframe["ema_200_1h"])
          item_buy_logic.append(dataframe["sma_50_1h"] > dataframe["sma_200_1h"])

          item_buy_logic.append(dataframe["ema_50_4h"] > dataframe["ema_200_4h"])
          item_buy_logic.append(dataframe["sma_50_4h"] > dataframe["sma_200_4h"])

          item_buy_logic.append(dataframe["rsi_14_4h"] < 85.0)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 85.0)
          item_buy_logic.append(dataframe["r_480_4h"] < -10.0)

          # current 1d long green with long top wick
          item_buy_logic.append((dataframe["change_pct_1d"] < 0.12) | (dataframe["top_wick_pct_1d"] < 0.12))
          # overbought 1d, overbought 4h, downtrend 1h, drop in last 2h
          item_buy_logic.append(
            (dataframe["rsi_14_1d"] < 70.0)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          # current 4h red, downtrend 1h, overbought 4h, drop in last 2h
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.06)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_4h"] < 0.5)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          # current 4h long red, downtrend 1h, overbought 1d, drop in last 2h
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.12)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1d"] < 0.8)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          # current 1d red, overbought 1d, downtrend 1h, downtrend 4h, drop in last 2h
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.12)
            | (dataframe["cti_20_1d"] < 0.85)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["is_downtrend_3_4h"] == False)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          # current 1d red, overbought 1d, downtrend 1h, current 4h red, previous 4h green with top wick
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.08)
            | (dataframe["cti_20_1d"] < 0.85)
            | (dataframe["not_downtrend_1h"])
            | (dataframe["change_pct_4h"] > -0.0)
            | (dataframe["change_pct_4h"].shift(48) < 0.04)
            | (dataframe["top_wick_pct_4h"].shift(48) < 0.04)
          )
          # current 1d long red with long top wick, overbought 1d, drop in last 2h
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.12)
            | (dataframe["top_wick_pct_1d"] < 0.12)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          # current 1d long red, overbought 1d, drop in last 2h
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.16)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          # current 4h red with top wick, overbought 1d
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.04)
            | (dataframe["top_wick_pct_4h"] < 0.04)
            | (dataframe["cti_20_1d"] < 0.85)
          )
          # current 4h green with top wick, overbought 4h
          item_buy_logic.append(
            (dataframe["change_pct_4h"] < 0.04)
            | (dataframe["top_wick_pct_4h"] < 0.04)
            | (dataframe["rsi_14_4h"] < 70.0)
          )
          # current 4h red, downtrend 1h, overbought 1d
          item_buy_logic.append(
            (dataframe["change_pct_4h"] > -0.04) | (dataframe["not_downtrend_1h"]) | (dataframe["cti_20_1d"] < 0.5)
          )
          # current 1d long relative top wick, overbought 1d, drop in last 2h
          item_buy_logic.append(
            (dataframe["top_wick_pct_1d"] < (abs(dataframe["change_pct_1d"]) * 4.0))
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          # current 4h relative long top wick, overbought 1d, drop in last 2h
          item_buy_logic.append(
            (dataframe["top_wick_pct_4h"] < (abs(dataframe["change_pct_4h"]) * 4.0))
            | (dataframe["cti_20_1d"] < 0.85)
            | (dataframe["rsi_14_1d"] < 50.0)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          # current and previous 1d red, overbought 1d, drop in last 2h
          item_buy_logic.append(
            (dataframe["change_pct_1d"] > -0.04)
            | (dataframe["change_pct_1d"].shift(288) > -0.04)
            | (dataframe["cti_20_1d"] < 0.5)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          # current 4h long green, overbought 4h, drop in last 2h
          item_buy_logic.append(
            (dataframe["change_pct_1d"] < 0.08)
            | (dataframe["rsi_14_4h"] < 70.0)
            | (dataframe["close_max_24"] < (dataframe["close"] * 1.1))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_15m"])
            | (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_1h"] < -0.5)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["cti_20_1d"] < -0.0)
            | (dataframe["ema_200_dec_24_4h"] == False)
            | (dataframe["ema_200_dec_4_1d"] == False)
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.8)
            | (dataframe["rsi_3_15m"] > 10.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["not_downtrend_1h"])
            | (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["rsi_3_15m"] > 30.0)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["rsi_3_1h"] > 10.0)
            | (dataframe["cti_20_4h"] < -0.0)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )
          item_buy_logic.append(
            (dataframe["cti_20_15m"] < -0.9)
            | (dataframe["cti_20_1h"] < -0.8)
            | (dataframe["cti_20_4h"] < 0.75)
            | (dataframe["r_14_4h"] < -25.0)
            | (dataframe["cti_20_1d"] < 0.5)
            | ((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.04))
          )

          # Logic
          item_buy_logic.append(dataframe["ema_26"] > dataframe["ema_12"])
          item_buy_logic.append((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.03))
          item_buy_logic.append(
            (dataframe["ema_26"].shift() - dataframe["ema_12"].shift()) > (dataframe["open"] / 100)
          )
          item_buy_logic.append(dataframe["cti_20"] < -0.8)

        # Condition #101 - Long mode rapid
        if index == 101:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.18))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.22))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["high_max_48_1h"] < (dataframe["close"] * 1.26))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_12_1d"] < (dataframe["close"] * 1.6))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.4)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.8)
          item_buy_logic.append(dataframe["hl_pct_change_6_1d"] < 0.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["rsi_3"] > 4.0)
          item_buy_logic.append(dataframe["rsi_3_15m"] > 6.0)
          item_buy_logic.append(dataframe["cti_20_1h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_1d"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 80.0)

          # Logic
          item_buy_logic.append(dataframe["rsi_14"] < 36.0)
          item_buy_logic.append(dataframe["rsi_14"] < dataframe["rsi_14"].shift(1))
          item_buy_logic.append(dataframe["close"] < (dataframe["sma_16"] * 0.956))
          item_buy_logic.append(dataframe["cti_20_15m"] < -0.5)

        # Condition #102 - Long mode rapid
        if index == 102:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["close_max_12"] < (dataframe["close"] * 1.18))
          item_buy_logic.append(dataframe["close_max_24"] < (dataframe["close"] * 1.2))
          item_buy_logic.append(dataframe["close_max_48"] < (dataframe["close"] * 1.22))
          item_buy_logic.append(dataframe["high_max_24_1h"] < (dataframe["close"] * 1.24))
          item_buy_logic.append(dataframe["high_max_48_1h"] < (dataframe["close"] * 1.26))
          item_buy_logic.append(dataframe["high_max_24_4h"] < (dataframe["close"] * 1.5))
          item_buy_logic.append(dataframe["high_max_12_1d"] < (dataframe["close"] * 1.6))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.8)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["hl_pct_change_6_1d"] < 1.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["rsi_3"] > 6.0)
          item_buy_logic.append(dataframe["rsi_3_15m"] > 16.0)
          item_buy_logic.append(dataframe["cti_20_15m"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_15m"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_1h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_1d"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 80.0)

          # Logic
          item_buy_logic.append(dataframe["rsi_14"] < 32.0)
          item_buy_logic.append(dataframe["close"] < (dataframe["ema_16"] * 0.977))
          item_buy_logic.append(dataframe["close"] < (dataframe["bb20_2_low"] * 0.999))

        # Condition #103 - Long mode rapid
        if index == 103:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["high_max_12_1d"] < (dataframe["close"] * 1.6))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.8)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["hl_pct_change_6_1d"] < 1.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["rsi_3"] > 16.0)
          item_buy_logic.append(dataframe["rsi_3_15m"] > 10.0)
          item_buy_logic.append(dataframe["close"] > dataframe["sup_level_4h"])
          item_buy_logic.append(dataframe["close"] < dataframe["res_hlevel_4h"])
          item_buy_logic.append(dataframe["close"] > dataframe["sup_level_1d"])
          item_buy_logic.append(dataframe["close"] < dataframe["res_hlevel_1d"])

          # Logic
          item_buy_logic.append(dataframe["rsi_3"] < 46.0)
          item_buy_logic.append(dataframe["rsi_14"] > 30.0)
          item_buy_logic.append(dataframe["close"] < (dataframe["sma_16"] * 0.972))

        # Condition #104 - Long mode rapid
        if index == 104:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["high_max_12_1d"] < (dataframe["close"] * 1.6))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.8)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["hl_pct_change_6_1d"] < 1.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["rsi_3"] > 16.0)
          item_buy_logic.append(dataframe["rsi_3_15m"] > 16.0)
          item_buy_logic.append(dataframe["rsi_3_1h"] > 4.0)
          item_buy_logic.append(dataframe["rsi_3_4h"] > 4.0)
          item_buy_logic.append(dataframe["rsi_3_1d"] > 4.0)
          item_buy_logic.append(dataframe["cti_20_15m"] < 0.9)
          item_buy_logic.append(dataframe["cti_20_1h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 70.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)

          # Logic
          item_buy_logic.append(dataframe["rsi_3"] < 50.0)
          item_buy_logic.append(dataframe["rsi_14"] > 30.0)
          item_buy_logic.append(dataframe["rsi_14"] < 40.0)
          item_buy_logic.append(dataframe["ha_close"] > dataframe["ha_open"])
          item_buy_logic.append(dataframe["close"] < (dataframe["sma_16"] * 0.976))

        # Condition #105 - Long mode rapid
        if index == 105:
          # Protections
          item_buy_logic.append(dataframe["protections_long_global"] == True)
          item_buy_logic.append(dataframe["btc_pct_close_max_24_5m"] < 0.03)
          item_buy_logic.append(dataframe["btc_pct_close_max_72_5m"] < 0.03)
          item_buy_logic.append(dataframe["high_max_12_1d"] < (dataframe["close"] * 1.6))
          item_buy_logic.append(dataframe["hl_pct_change_6_1h"] < 0.5)
          item_buy_logic.append(dataframe["hl_pct_change_12_1h"] < 0.75)
          item_buy_logic.append(dataframe["hl_pct_change_24_1h"] < 0.8)
          item_buy_logic.append(dataframe["hl_pct_change_48_1h"] < 0.9)
          item_buy_logic.append(dataframe["hl_pct_change_6_1d"] < 1.9)
          item_buy_logic.append(dataframe["num_empty_288"] < allowed_empty_candles)

          item_buy_logic.append(dataframe["rsi_3"] > 6.0)
          item_buy_logic.append(dataframe["rsi_3_15m"] > 6.0)
          item_buy_logic.append(dataframe["rsi_3_1h"] > 6.0)
          item_buy_logic.append(dataframe["rsi_3_4h"] > 6.0)
          item_buy_logic.append(dataframe["cti_20_1h"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_4h"] < 0.9)
          item_buy_logic.append(dataframe["rsi_14_4h"] < 80.0)
          item_buy_logic.append(dataframe["cti_20_1d"] < 0.8)
          item_buy_logic.append(dataframe["rsi_14_1d"] < 80.0)
          item_buy_logic.append(dataframe["close"] > dataframe["sup_level_4h"])
          item_buy_logic.append(dataframe["close"] > dataframe["sup_level_1d"])

          # Logic
          item_buy_logic.append(dataframe["rsi_3"] < 60.0)
          item_buy_logic.append(dataframe["rsi_14"] < 46.0)
          item_buy_logic.append(dataframe["ema_26"] > dataframe["ema_12"])
          item_buy_logic.append((dataframe["ema_26"] - dataframe["ema_12"]) > (dataframe["open"] * 0.016))
          item_buy_logic.append(
            (dataframe["ema_26"].shift() - dataframe["ema_12"].shift()) > (dataframe["open"] / 100)
          )

        item_buy_logic.append(dataframe["volume"] > 0)
        item_buy = reduce(lambda x, y: x & y, item_buy_logic)
        dataframe.loc[item_buy, "enter_tag"] += f"{index} "
        conditions.append(item_buy)
        dataframe.loc[:, "enter_long"] = item_buy

    if conditions:
      dataframe.loc[:, "enter_long"] = reduce(lambda x, y: x | y, conditions)

    return dataframe

  def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    dataframe.loc[:, "exit_long"] = 0
    dataframe.loc[:, "exit_short"] = 0

    return dataframe

  def confirm_trade_entry(
    self,
    pair: str,
    order_type: str,
    amount: float,
    rate: float,
    time_in_force: str,
    current_time: datetime,
    entry_tag: Optional[str],
    **kwargs,
  ) -> bool:
    # allow force entries
    if entry_tag == "force_entry":
      return True

    dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

    if len(dataframe) < 1:
      return False

    dataframe = dataframe.iloc[-1].squeeze()

    if rate > dataframe["close"]:
      slippage = (rate / dataframe["close"]) - 1.0

      if slippage < self.max_slippage:
        return True
      else:
        log.warning(f"Cancelling buy for {pair} due to slippage {(slippage * 100.0):.2f}%")
        return False

    return True

  def confirm_trade_exit(
    self,
    pair: str,
    trade: Trade,
    order_type: str,
    amount: float,
    rate: float,
    time_in_force: str,
    exit_reason: str,
    current_time: datetime,
    **kwargs,
  ) -> bool:
    # Allow force exits
    if exit_reason != "force_exit":
      if self._should_hold_trade(trade, rate, exit_reason):
        return False
      if exit_reason == "stop_loss":
        return False
      if self.exit_profit_only:
        if self.exit_profit_only:
          profit = 0.0
          if trade.realized_profit != 0.0:
            profit = ((rate - trade.open_rate) / trade.open_rate) * trade.stake_amount * (1 - trade.fee_close)
            profit = profit + trade.realized_profit
            profit = profit / trade.stake_amount
          else:
            profit = trade.calc_profit_ratio(rate)
          if profit < self.exit_profit_offset:
            return False

    self._remove_profit_target(pair)
    return True

  def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
    if self.config["runmode"].value not in ("live", "dry_run"):
      return super().bot_loop_start(datetime, **kwargs)

    if self.hold_support_enabled:
      self.load_hold_trades_config()

    return super().bot_loop_start(current_time, **kwargs)

  def leverage(
    self,
    pair: str,
    current_time: datetime,
    current_rate: float,
    proposed_leverage: float,
    max_leverage: float,
    entry_tag: Optional[str],
    side: str,
    **kwargs,
  ) -> float:
    enter_tags = entry_tag.split()
    if all(c in self.long_rebuy_mode_tags for c in enter_tags):
      return self.futures_mode_leverage_rebuy_mode
    return self.futures_mode_leverage

  def _set_profit_target(
    self, pair: str, sell_reason: str, rate: float, current_profit: float, current_time: datetime
  ):
    self.target_profit_cache.data[pair] = {
      "rate": rate,
      "profit": current_profit,
      "sell_reason": sell_reason,
      "time_profit_reached": current_time.isoformat(),
    }
    self.target_profit_cache.save()

  def _remove_profit_target(self, pair: str):
    if self.target_profit_cache is not None:
      self.target_profit_cache.data.pop(pair, None)
      self.target_profit_cache.save()

  def get_hold_trades_config_file(self):
    proper_holds_file_path = self.config["user_data_dir"].resolve() / "nfi-hold-trades.json"
    if proper_holds_file_path.is_file():
      return proper_holds_file_path

    strat_file_path = pathlib.Path(__file__)
    hold_trades_config_file_resolve = strat_file_path.resolve().parent / "hold-trades.json"
    if hold_trades_config_file_resolve.is_file():
      log.warning(
        "Please move %s to %s which is now the expected path for the holds file",
        hold_trades_config_file_resolve,
        proper_holds_file_path,
      )
      return hold_trades_config_file_resolve

    # The resolved path does not exist, is it a symlink?
    hold_trades_config_file_absolute = strat_file_path.absolute().parent / "hold-trades.json"
    if hold_trades_config_file_absolute.is_file():
      log.warning(
        "Please move %s to %s which is now the expected path for the holds file",
        hold_trades_config_file_absolute,
        proper_holds_file_path,
      )
      return hold_trades_config_file_absolute

  def load_hold_trades_config(self):
    if self.hold_trades_cache is None:
      hold_trades_config_file = self.get_hold_trades_config_file()
      if hold_trades_config_file:
        log.warning("Loading hold support data from %s", hold_trades_config_file)
        self.hold_trades_cache = HoldsCache(hold_trades_config_file)

    if self.hold_trades_cache:
      self.hold_trades_cache.load()

  def _should_hold_trade(self, trade: "Trade", rate: float, sell_reason: str) -> bool:
    if self.config["runmode"].value not in ("live", "dry_run"):
      return False

    if not self.hold_support_enabled:
      return False

    # Just to be sure our hold data is loaded, should be a no-op call after the first bot loop
    self.load_hold_trades_config()

    if not self.hold_trades_cache:
      # Cache hasn't been setup, likely because the corresponding file does not exist, sell
      return False

    if not self.hold_trades_cache.data:
      # We have no pairs we want to hold until profit, sell
      return False

    # By default, no hold should be done
    hold_trade = False

    trade_ids: dict = self.hold_trades_cache.data.get("trade_ids")
    if trade_ids and trade.id in trade_ids:
      trade_profit_ratio = trade_ids[trade.id]
      profit = 0.0
      if trade.realized_profit != 0.0:
        profit = ((rate - trade.open_rate) / trade.open_rate) * trade.stake_amount * (1 - trade.fee_close)
        profit = profit + trade.realized_profit
        profit = profit / trade.stake_amount
      else:
        profit = trade.calc_profit_ratio(rate)
      current_profit_ratio = profit
      if sell_reason == "force_sell":
        formatted_profit_ratio = f"{trade_profit_ratio * 100}%"
        formatted_current_profit_ratio = f"{current_profit_ratio * 100}%"
        log.warning(
          "Force selling %s even though the current profit of %s < %s",
          trade,
          formatted_current_profit_ratio,
          formatted_profit_ratio,
        )
        return False
      elif current_profit_ratio >= trade_profit_ratio:
        # This pair is on the list to hold, and we reached minimum profit, sell
        formatted_profit_ratio = f"{trade_profit_ratio * 100}%"
        formatted_current_profit_ratio = f"{current_profit_ratio * 100}%"
        log.warning(
          "Selling %s because the current profit of %s >= %s",
          trade,
          formatted_current_profit_ratio,
          formatted_profit_ratio,
        )
        return False

      # This pair is on the list to hold, and we haven't reached minimum profit, hold
      hold_trade = True

    trade_pairs: dict = self.hold_trades_cache.data.get("trade_pairs")
    if trade_pairs and trade.pair in trade_pairs:
      trade_profit_ratio = trade_pairs[trade.pair]
      profit = 0.0
      if trade.realized_profit != 0.0:
        profit = ((rate - trade.open_rate) / trade.open_rate) * trade.stake_amount * (1 - trade.fee_close)
        profit = profit + trade.realized_profit
        profit = profit / trade.stake_amount
      else:
        profit = trade.calc_profit_ratio(rate)
      current_profit_ratio = profit
      if sell_reason == "force_sell":
        formatted_profit_ratio = f"{trade_profit_ratio * 100}%"
        formatted_current_profit_ratio = f"{current_profit_ratio * 100}%"
        log.warning(
          "Force selling %s even though the current profit of %s < %s",
          trade,
          formatted_current_profit_ratio,
          formatted_profit_ratio,
        )
        return False
      elif current_profit_ratio >= trade_profit_ratio:
        # This pair is on the list to hold, and we reached minimum profit, sell
        formatted_profit_ratio = f"{trade_profit_ratio * 100}%"
        formatted_current_profit_ratio = f"{current_profit_ratio * 100}%"
        log.warning(
          "Selling %s because the current profit of %s >= %s",
          trade,
          formatted_current_profit_ratio,
          formatted_profit_ratio,
        )
        return False

      # This pair is on the list to hold, and we haven't reached minimum profit, hold
      hold_trade = True

    return hold_trade


# +---------------------------------------------------------------------------+
# |                              Custom Indicators                            |
# +---------------------------------------------------------------------------+


# Range midpoint acts as Support
def is_support(row_data) -> bool:
  conditions = []
  for row in range(len(row_data) - 1):
    if row < len(row_data) // 2:
      conditions.append(row_data[row] > row_data[row + 1])
    else:
      conditions.append(row_data[row] < row_data[row + 1])
  result = reduce(lambda x, y: x & y, conditions)
  return result


# Range midpoint acts as Resistance
def is_resistance(row_data) -> bool:
  conditions = []
  for row in range(len(row_data) - 1):
    if row < len(row_data) // 2:
      conditions.append(row_data[row] < row_data[row + 1])
    else:
      conditions.append(row_data[row] > row_data[row + 1])
  result = reduce(lambda x, y: x & y, conditions)
  return result


# Elliot Wave Oscillator
def ewo(dataframe, ema1_length=5, ema2_length=35):
  ema1 = ta.EMA(dataframe, timeperiod=ema1_length)
  ema2 = ta.EMA(dataframe, timeperiod=ema2_length)
  emadiff = (ema1 - ema2) / dataframe["close"] * 100.0
  return emadiff


# Chaikin Money Flow
def chaikin_money_flow(dataframe, n=20, fillna=False) -> Series:
  """Chaikin Money Flow (CMF)
  It measures the amount of Money Flow Volume over a specific period.
  http://stockcharts.com/school/doku.php?id=chart_school:technical_indicators:chaikin_money_flow_cmf
  Args:
      dataframe(pandas.Dataframe): dataframe containing ohlcv
      n(int): n period.
      fillna(bool): if True, fill nan values.
  Returns:
      pandas.Series: New feature generated.
  """
  mfv = ((dataframe["close"] - dataframe["low"]) - (dataframe["high"] - dataframe["close"])) / (
    dataframe["high"] - dataframe["low"]
  )
  mfv = mfv.fillna(0.0)  # float division by zero
  mfv *= dataframe["volume"]
  cmf = mfv.rolling(n, min_periods=0).sum() / dataframe["volume"].rolling(n, min_periods=0).sum()
  if fillna:
    cmf = cmf.replace([np.inf, -np.inf], np.nan).fillna(0)
  return Series(cmf, name="cmf")


# Williams %R
def williams_r(dataframe: DataFrame, period: int = 14) -> Series:
  """Williams %R, or just %R, is a technical analysis oscillator showing the current closing price in relation to the high and low
  of the past N days (for a given N). It was developed by a publisher and promoter of trading materials, Larry Williams.
  Its purpose is to tell whether a stock or commodity market is trading near the high or the low, or somewhere in between,
  of its recent trading range.
  The oscillator is on a negative scale, from −100 (lowest) up to 0 (highest).
  """

  highest_high = dataframe["high"].rolling(center=False, window=period).max()
  lowest_low = dataframe["low"].rolling(center=False, window=period).min()

  WR = Series(
    (highest_high - dataframe["close"]) / (highest_high - lowest_low),
    name=f"{period} Williams %R",
  )

  return WR * -100


def williams_fractals(dataframe: pd.DataFrame, period: int = 2) -> tuple:
  """Williams Fractals implementation

  :param dataframe: OHLC data
  :param period: number of lower (or higher) points on each side of a high (or low)
  :return: tuple of boolean Series (bearish, bullish) where True marks a fractal pattern
  """

  window = 2 * period + 1

  bears = dataframe["high"].rolling(window, center=True).apply(lambda x: x[period] == max(x), raw=True)
  bulls = dataframe["low"].rolling(window, center=True).apply(lambda x: x[period] == min(x), raw=True)

  return bears, bulls


# Volume Weighted Moving Average
def vwma(dataframe: DataFrame, length: int = 10):
  """Indicator: Volume Weighted Moving Average (VWMA)"""
  # Calculate Result
  pv = dataframe["close"] * dataframe["volume"]
  vwma = Series(ta.SMA(pv, timeperiod=length) / ta.SMA(dataframe["volume"], timeperiod=length))
  vwma = vwma.fillna(0, inplace=True)
  return vwma


# Exponential moving average of a volume weighted simple moving average
def ema_vwma_osc(dataframe, len_slow_ma):
  slow_ema = Series(ta.EMA(vwma(dataframe, len_slow_ma), len_slow_ma))
  return ((slow_ema - slow_ema.shift(1)) / slow_ema.shift(1)) * 100


def t3_average(dataframe, length=5):
  """
  T3 Average by HPotter on Tradingview
  https://www.tradingview.com/script/qzoC9H1I-T3-Average/
  """
  df = dataframe.copy()

  df["xe1"] = ta.EMA(df["close"], timeperiod=length)
  df["xe1"].fillna(0, inplace=True)
  df["xe2"] = ta.EMA(df["xe1"], timeperiod=length)
  df["xe2"].fillna(0, inplace=True)
  df["xe3"] = ta.EMA(df["xe2"], timeperiod=length)
  df["xe3"].fillna(0, inplace=True)
  df["xe4"] = ta.EMA(df["xe3"], timeperiod=length)
  df["xe4"].fillna(0, inplace=True)
  df["xe5"] = ta.EMA(df["xe4"], timeperiod=length)
  df["xe5"].fillna(0, inplace=True)
  df["xe6"] = ta.EMA(df["xe5"], timeperiod=length)
  df["xe6"].fillna(0, inplace=True)
  b = 0.7
  c1 = -b * b * b
  c2 = 3 * b * b + 3 * b * b * b
  c3 = -6 * b * b - 3 * b - 3 * b * b * b
  c4 = 1 + 3 * b + b * b * b + 3 * b * b
  df["T3Average"] = c1 * df["xe6"] + c2 * df["xe5"] + c3 * df["xe4"] + c4 * df["xe3"]

  return df["T3Average"]


# Pivot Points - 3 variants - daily recommended
def pivot_points(dataframe: DataFrame, mode="fibonacci") -> Series:
  if mode == "simple":
    hlc3_pivot = (dataframe["high"] + dataframe["low"] + dataframe["close"]).shift(1) / 3
    res1 = hlc3_pivot * 2 - dataframe["low"].shift(1)
    sup1 = hlc3_pivot * 2 - dataframe["high"].shift(1)
    res2 = hlc3_pivot + (dataframe["high"] - dataframe["low"]).shift()
    sup2 = hlc3_pivot - (dataframe["high"] - dataframe["low"]).shift()
    res3 = hlc3_pivot * 2 + (dataframe["high"] - 2 * dataframe["low"]).shift()
    sup3 = hlc3_pivot * 2 - (2 * dataframe["high"] - dataframe["low"]).shift()
    return hlc3_pivot, res1, res2, res3, sup1, sup2, sup3
  elif mode == "fibonacci":
    hlc3_pivot = (dataframe["high"] + dataframe["low"] + dataframe["close"]).shift(1) / 3
    hl_range = (dataframe["high"] - dataframe["low"]).shift(1)
    res1 = hlc3_pivot + 0.382 * hl_range
    sup1 = hlc3_pivot - 0.382 * hl_range
    res2 = hlc3_pivot + 0.618 * hl_range
    sup2 = hlc3_pivot - 0.618 * hl_range
    res3 = hlc3_pivot + 1 * hl_range
    sup3 = hlc3_pivot - 1 * hl_range
    return hlc3_pivot, res1, res2, res3, sup1, sup2, sup3
  elif mode == "DeMark":
    demark_pivot_lt = dataframe["low"] * 2 + dataframe["high"] + dataframe["close"]
    demark_pivot_eq = dataframe["close"] * 2 + dataframe["low"] + dataframe["high"]
    demark_pivot_gt = dataframe["high"] * 2 + dataframe["low"] + dataframe["close"]
    demark_pivot = np.where(
      (dataframe["close"] < dataframe["open"]),
      demark_pivot_lt,
      np.where((dataframe["close"] > dataframe["open"]), demark_pivot_gt, demark_pivot_eq),
    )
    dm_pivot = demark_pivot / 4
    dm_res = demark_pivot / 2 - dataframe["low"]
    dm_sup = demark_pivot / 2 - dataframe["high"]
    return dm_pivot, dm_res, dm_sup


# Heikin Ashi candles
def heikin_ashi(dataframe, smooth_inputs=False, smooth_outputs=False, length=10):
  df = dataframe[["open", "close", "high", "low"]].copy().fillna(0)
  if smooth_inputs:
    df["open_s"] = ta.EMA(df["open"], timeframe=length)
    df["high_s"] = ta.EMA(df["high"], timeframe=length)
    df["low_s"] = ta.EMA(df["low"], timeframe=length)
    df["close_s"] = ta.EMA(df["close"], timeframe=length)

    open_ha = (df["open_s"].shift(1) + df["close_s"].shift(1)) / 2
    high_ha = df.loc[:, ["high_s", "open_s", "close_s"]].max(axis=1)
    low_ha = df.loc[:, ["low_s", "open_s", "close_s"]].min(axis=1)
    close_ha = (df["open_s"] + df["high_s"] + df["low_s"] + df["close_s"]) / 4
  else:
    open_ha = (df["open"].shift(1) + df["close"].shift(1)) / 2
    high_ha = df.loc[:, ["high", "open", "close"]].max(axis=1)
    low_ha = df.loc[:, ["low", "open", "close"]].min(axis=1)
    close_ha = (df["open"] + df["high"] + df["low"] + df["close"]) / 4

  open_ha = open_ha.fillna(0)
  high_ha = high_ha.fillna(0)
  low_ha = low_ha.fillna(0)
  close_ha = close_ha.fillna(0)

  if smooth_outputs:
    open_sha = ta.EMA(open_ha, timeframe=length)
    high_sha = ta.EMA(high_ha, timeframe=length)
    low_sha = ta.EMA(low_ha, timeframe=length)
    close_sha = ta.EMA(close_ha, timeframe=length)

    return open_sha, close_sha, low_sha
  else:
    return open_ha, close_ha, low_ha


# Peak Percentage Change
def range_percent_change(self, dataframe: DataFrame, method, length: int) -> float:
  """
  Rolling Percentage Change Maximum across interval.

  :param dataframe: DataFrame The original OHLC dataframe
  :param method: High to Low / Open to Close
  :param length: int The length to look back
  """
  if method == "HL":
    return (dataframe["high"].rolling(length).max() - dataframe["low"].rolling(length).min()) / dataframe[
      "low"
    ].rolling(length).min()
  elif method == "OC":
    return (dataframe["open"].rolling(length).max() - dataframe["close"].rolling(length).min()) / dataframe[
      "close"
    ].rolling(length).min()
  else:
    raise ValueError(f"Method {method} not defined!")


# Percentage distance to top peak
def top_percent_change(self, dataframe: DataFrame, length: int) -> float:
  """
  Percentage change of the current close from the range maximum Open price

  :param dataframe: DataFrame The original OHLC dataframe
  :param length: int The length to look back
  """
  if length == 0:
    return (dataframe["open"] - dataframe["close"]) / dataframe["close"]
  else:
    return (dataframe["open"].rolling(length).max() - dataframe["close"]) / dataframe["close"]


# +---------------------------------------------------------------------------+
# |                              Classes                                      |
# +---------------------------------------------------------------------------+


class Cache:
  def __init__(self, path):
    self.path = path
    self.data = {}
    self._mtime = None
    self._previous_data = {}
    try:
      self.load()
    except FileNotFoundError:
      pass

  @staticmethod
  def rapidjson_load_kwargs():
    return {"number_mode": rapidjson.NM_NATIVE}

  @staticmethod
  def rapidjson_dump_kwargs():
    return {"number_mode": rapidjson.NM_NATIVE}

  def load(self):
    if not self._mtime or self.path.stat().st_mtime_ns != self._mtime:
      self._load()

  def save(self):
    if self.data != self._previous_data:
      self._save()

  def process_loaded_data(self, data):
    return data

  def _load(self):
    # This method only exists to simplify unit testing
    with self.path.open("r") as rfh:
      try:
        data = rapidjson.load(rfh, **self.rapidjson_load_kwargs())
      except rapidjson.JSONDecodeError as exc:
        log.error("Failed to load JSON from %s: %s", self.path, exc)
      else:
        self.data = self.process_loaded_data(data)
        self._previous_data = copy.deepcopy(self.data)
        self._mtime = self.path.stat().st_mtime_ns

  def _save(self):
    # This method only exists to simplify unit testing
    rapidjson.dump(self.data, self.path.open("w"), **self.rapidjson_dump_kwargs())
    self._mtime = self.path.stat().st_mtime
    self._previous_data = copy.deepcopy(self.data)


class HoldsCache(Cache):
  @staticmethod
  def rapidjson_load_kwargs():
    return {
      "number_mode": rapidjson.NM_NATIVE,
      "object_hook": HoldsCache._object_hook,
    }

  @staticmethod
  def rapidjson_dump_kwargs():
    return {
      "number_mode": rapidjson.NM_NATIVE,
      "mapping_mode": rapidjson.MM_COERCE_KEYS_TO_STRINGS,
    }

  def save(self):
    raise RuntimeError("The holds cache does not allow programatical save")

  def process_loaded_data(self, data):
    trade_ids = data.get("trade_ids")
    trade_pairs = data.get("trade_pairs")

    if not trade_ids and not trade_pairs:
      return data

    open_trades = {}
    for trade in Trade.get_trades_proxy(is_open=True):
      open_trades[trade.id] = open_trades[trade.pair] = trade

    r_trade_ids = {}
    if trade_ids:
      if isinstance(trade_ids, dict):
        # New syntax
        for trade_id, profit_ratio in trade_ids.items():
          if not isinstance(trade_id, int):
            log.error("The trade_id(%s) defined under 'trade_ids' in %s is not an integer", trade_id, self.path)
            continue
          if not isinstance(profit_ratio, float):
            log.error(
              "The 'profit_ratio' config value(%s) for trade_id %s in %s is not a float",
              profit_ratio,
              trade_id,
              self.path,
            )
          if trade_id in open_trades:
            formatted_profit_ratio = f"{profit_ratio * 100}%"
            log.warning(
              "The trade %s is configured to HOLD until the profit ratio of %s is met",
              open_trades[trade_id],
              formatted_profit_ratio,
            )
            r_trade_ids[trade_id] = profit_ratio
          else:
            log.warning(
              "The trade_id(%s) is no longer open. Please remove it from 'trade_ids' in %s",
              trade_id,
              self.path,
            )
      else:
        # Initial Syntax
        profit_ratio = data.get("profit_ratio")
        if profit_ratio:
          if not isinstance(profit_ratio, float):
            log.error("The 'profit_ratio' config value(%s) in %s is not a float", profit_ratio, self.path)
        else:
          profit_ratio = 0.005
        formatted_profit_ratio = f"{profit_ratio * 100}%"
        for trade_id in trade_ids:
          if not isinstance(trade_id, int):
            log.error("The trade_id(%s) defined under 'trade_ids' in %s is not an integer", trade_id, self.path)
            continue
          if trade_id in open_trades:
            log.warning(
              "The trade %s is configured to HOLD until the profit ratio of %s is met",
              open_trades[trade_id],
              formatted_profit_ratio,
            )
            r_trade_ids[trade_id] = profit_ratio
          else:
            log.warning(
              "The trade_id(%s) is no longer open. Please remove it from 'trade_ids' in %s",
              trade_id,
              self.path,
            )

    r_trade_pairs = {}
    if trade_pairs:
      for trade_pair, profit_ratio in trade_pairs.items():
        if not isinstance(trade_pair, str):
          log.error("The trade_pair(%s) defined under 'trade_pairs' in %s is not a string", trade_pair, self.path)
          continue
        if "/" not in trade_pair:
          log.error(
            "The trade_pair(%s) defined under 'trade_pairs' in %s does not look like "
            "a valid '<TOKEN_NAME>/<STAKE_CURRENCY>' formatted pair.",
            trade_pair,
            self.path,
          )
          continue
        if not isinstance(profit_ratio, float):
          log.error(
            "The 'profit_ratio' config value(%s) for trade_pair %s in %s is not a float",
            profit_ratio,
            trade_pair,
            self.path,
          )
        formatted_profit_ratio = f"{profit_ratio * 100}%"
        if trade_pair in open_trades:
          log.warning(
            "The trade %s is configured to HOLD until the profit ratio of %s is met",
            open_trades[trade_pair],
            formatted_profit_ratio,
          )
        else:
          log.warning(
            "The trade pair %s is configured to HOLD until the profit ratio of %s is met",
            trade_pair,
            formatted_profit_ratio,
          )
        r_trade_pairs[trade_pair] = profit_ratio

    r_data = {}
    if r_trade_ids:
      r_data["trade_ids"] = r_trade_ids
    if r_trade_pairs:
      r_data["trade_pairs"] = r_trade_pairs
    return r_data

  @staticmethod
  def _object_hook(data):
    _data = {}
    for key, value in data.items():
      try:
        key = int(key)
      except ValueError:
        pass
      _data[key] = value
    return _data
