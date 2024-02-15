import numpy as np
from enum import Enum

import pywt
import talib.abstract as ta
from scipy.ndimage import gaussian_filter1d
from statsmodels.discrete.discrete_model import Probit

import freqtrade.vendor.qtpylib.indicators as qtpylib
import arrow

from freqtrade.exchange import timeframe_to_minutes
from freqtrade.strategy import (IStrategy, merge_informative_pair, stoploss_from_open,
                                IntParameter, DecimalParameter, CategoricalParameter)

from typing import Dict, List, Optional, Tuple, Union
from pandas import DataFrame, Series
from functools import reduce
from datetime import datetime, timedelta
from freqtrade.persistence import Trade

# Get rid of pandas warnings during backtesting
import pandas as pd
import pandas_ta as pta

pd.options.mode.chained_assignment = None  # default='warn'

# Strategy specific imports, files must reside in same folder as strategy
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__)))

import logging
import warnings

log = logging.getLogger(__name__)
# log.setLevel(logging.DEBUG)
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)

from DataframePopulator import DatasetType
from NNTC import NNTC
import TrainingSignals
import NNTClassifier


"""
####################################################################################
NNTC_bbw_LSTM:
    This is a subclass of NNTC, which provides a framework for deriving a dimensionally-reduced model
    This class trains the model based on  Bollinger Band Width trends 

####################################################################################
"""


class NNTC_bbw_LSTM(NNTC):

    plot_config = {
        'main_plot': {
            # 'dwt': {'color': 'darkcyan'},
            # '%future_min': {'color': 'salmon'},
            # '%future_max': {'color': 'cadetblue'},
        },
        'subplots': {
            "Diff": {
                'bb_width': {'color': 'teal'},
                '%train_buy': {'color': 'mediumaquamarine'},
                'predict_buy': {'color': 'cornflowerblue'},
                '%train_sell': {'color': 'lightsalmon'},
                'predict_sell': {'color': 'mediumturquoise'},
            },
        }
    }

    # Do *not* hyperopt for the roi and stoploss spaces

    # Have to re-declare any globals that we need to modify because freqtrade can/will run strats in parallel

    # Have to re-declare any globals that we need to modify because freqtrade can/will run strats in parallel

    custom_trade_info = {}

    dbg_test_classifier = False  # test clasifiers after fitting
    dbg_verbose = False  # controls debug output

    ###################################
    # override the (most often changed) default parameters for this particular strategy

    dataset_type = DatasetType.DEFAULT
    signal_type = TrainingSignals.SignalType.Bollinger_Width
    classifier_type = NNTClassifier.ClassifierType.LSTM

    ignore_exit_signals = False

    compress_data = False

