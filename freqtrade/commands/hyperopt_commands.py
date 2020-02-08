import logging
from operator import itemgetter
from typing import Any, Dict, List

from colorama import init as colorama_init

from freqtrade.configuration import setup_utils_configuration
from freqtrade.exceptions import OperationalException
from freqtrade.state import RunMode

logger = logging.getLogger(__name__)


def start_hyperopt_list(args: Dict[str, Any]) -> None:
    """
    List hyperopt epochs previously evaluated
    """
    from freqtrade.optimize.hyperopt import Hyperopt

    config = setup_utils_configuration(args, RunMode.UTIL_NO_EXCHANGE)

    print_colorized = config.get('print_colorized', False)
    print_json = config.get('print_json', False)
    no_details = config.get('hyperopt_list_no_details', False)
    no_header = False

    filteroptions = {
        'only_best': config.get('hyperopt_list_best', False),
        'only_profitable': config.get('hyperopt_list_profitable', False),
        'filter_min_avg_time': config.get('hyperopt_list_min_avg_time', 0),
        'filter_max_avg_time': config.get('hyperopt_list_max_avg_time', 0),
        'filter_min_avg_profit': config.get('hyperopt_list_min_avg_profit', 0.0),
        'filter_min_total_profit': config.get('hyperopt_list_min_total_profit', 0.0)
    }

    trials_file = (config['user_data_dir'] /
                   'hyperopt_results' / 'hyperopt_results.pickle')

    # Previous evaluations
    trials = Hyperopt.load_previous_results(trials_file)
    total_epochs = len(trials)

    trials = _hyperopt_filter_trials(trials, filteroptions)

    # TODO: fetch the interval for epochs to print from the cli option
    epoch_start, epoch_stop = 0, None

    if print_colorized:
        colorama_init(autoreset=True)

    try:
        # Human-friendly indexes used here (starting from 1)
        for val in trials[epoch_start:epoch_stop]:
            Hyperopt.print_results_explanation(val, total_epochs,
                                               not filteroptions['only_best'], print_colorized)

    except KeyboardInterrupt:
        print('User interrupted..')

    if trials and not no_details:
        sorted_trials = sorted(trials, key=itemgetter('loss'))
        results = sorted_trials[0]
        Hyperopt.print_epoch_details(results, total_epochs, print_json, no_header)


def start_hyperopt_show(args: Dict[str, Any]) -> None:
    """
    Show details of a hyperopt epoch previously evaluated
    """
    from freqtrade.optimize.hyperopt import Hyperopt

    config = setup_utils_configuration(args, RunMode.UTIL_NO_EXCHANGE)

    filteroptions = {
        'only_best': config.get('hyperopt_list_best', False),
        'only_profitable': config.get('hyperopt_list_profitable', False),
        'filter_min_avg_time': config.get('hyperopt_list_min_avg_time', 0),
        'filter_max_avg_time': config.get('hyperopt_list_max_avg_time', 0),
        'filter_min_avg_profit': config.get('hyperopt_list_min_avg_profit', 0),
        'filter_min_total_profit': config.get('hyperopt_list_min_total_profit', 0)
    }
    no_header = config.get('hyperopt_show_no_header', False)

    trials_file = (config['user_data_dir'] /
                   'hyperopt_results' / 'hyperopt_results.pickle')

    # Previous evaluations
    trials = Hyperopt.load_previous_results(trials_file)
    total_epochs = len(trials)

    trials = _hyperopt_filter_trials(trials, filteroptions)
    trials_epochs = len(trials)

    n = config.get('hyperopt_show_index', -1)
    if n > trials_epochs:
        raise OperationalException(
                f"The index of the epoch to show should be less than {trials_epochs + 1}.")
    if n < -trials_epochs:
        raise OperationalException(
                f"The index of the epoch to show should be greater than {-trials_epochs - 1}.")

    # Translate epoch index from human-readable format to pythonic
    if n > 0:
        n -= 1

    print_json = config.get('print_json', False)

    if trials:
        val = trials[n]
        Hyperopt.print_epoch_details(val, total_epochs, print_json, no_header,
                                     header_str="Epoch details")


def _hyperopt_filter_trials(trials: List, filteroptions: dict) -> List:
    """
    Filter our items from the list of hyperopt results
    """
    if filteroptions['only_best']:
        trials = [x for x in trials if x['is_best']]
    if filteroptions['only_profitable']:
        trials = [x for x in trials if x['results_metrics']['profit'] > 0]

    if not filteroptions['only_best']:
        if filteroptions['filter_min_avg_time'] > 0:
            trials = [
                        x for x in trials
                        if x['results_metrics']['duration'] > filteroptions['filter_min_avg_time']
                     ]
        if filteroptions['filter_max_avg_time'] > 0:
            trials = [
                        x for x in trials
                        if x['results_metrics']['duration'] < filteroptions['filter_max_avg_time']
                     ]
        if filteroptions['filter_min_avg_profit'] > 0:
            trials = [
                        x for x in trials
                        if x['results_metrics']['avg_profit']
                        > filteroptions['filter_min_avg_profit']
                     ]
        if filteroptions['filter_min_total_profit'] > 0:
            trials = [
                        x for x in trials
                        if x['results_metrics']['profit'] > filteroptions['filter_min_total_profit']
                     ]

    logger.info(f"{len(trials)} " +
                ("best " if filteroptions['only_best'] else "") +
                ("profitable " if filteroptions['only_profitable'] else "") +
                "epochs found.")

    return trials
