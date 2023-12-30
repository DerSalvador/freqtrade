from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import logging
from pandas import DataFrame
from freqtrade.resolvers import StrategyResolver
from itertools import combinations
from functools import reduce
import catboost
import pandas as pd
import numpy as np
from catboost import CatBoostClassifier, Pool, sum_models
logger = logging.getLogger(__name__)
STRATEGIES = ['CombinedBinHAndClucV8', 'CombinedBinHClucAndMADV6', 'SMAOffset', 'SMAOffsetV2', 'SMAOffsetProtectOptV0', 'SMAOffsetProtectOptV1', 'NostalgiaForInfinityV4']

class TrainCatBoostStrategy(IStrategy):
    INTERFACE_VERSION = 3
    loaded_strategies = {}

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, self.informative_timeframe) for pair in pairs]
        return informative_pairs

    def get_strategy(self, strategy_name):
        cached_strategy = self.loaded_strategies.get(strategy_name)
        if cached_strategy:
            return cached_strategy
        config = self.config
        config['strategy'] = strategy_name
        strategy = StrategyResolver.load_strategy(config)
        strategy.dp = self.dp
        self.loaded_strategies[strategy_name] = strategy
        return strategy

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        strategies = STRATEGIES
        populated_dataframe = dataframe
        populated_dataframe['pair'] = metadata.get('pair')
        for strategy_name in strategies:
            strategy = self.get_strategy(strategy_name)
            populated_dataframe = strategy.advise_indicators(populated_dataframe, metadata)
        for strategy_name in strategies:
            strategy = self.get_strategy(strategy_name)
            strategy_indicators = strategy.advise_indicators(dataframe, metadata)
            dataframe[f'strat_entry_signal_{strategy_name}'] = strategy.advise_entry(strategy_indicators, metadata)['enter_long']
            y = dataframe[f'strat_entry_signal_{strategy_name}']
            x = populated_dataframe[[col for col in populated_dataframe.columns if 'date' not in col]].fillna(-1)
            # remove duplicated columns
            x = x.loc[:, ~x.columns.duplicated()]
            cat_features = [i for i in x.columns if x.dtypes[i] == 'object']
            dataset = Pool(data=x, label=y, cat_features=cat_features)
            baseline_model = CatBoostClassifier(iterations=10)
            try:
                baseline_model = baseline_model.load_model('/freqtrade/user_data/entry_model')
            except:
                # first run
                pass
            model = CatBoostClassifier(iterations=10)
            try:
                model.fit(dataset, use_best_model=True, eval_set=dataset)
            except:
                #  target contains only one value
                pass
            final_model = sum_models([baseline_model, model], weights=None, ctr_merge_policy='IntersectingCountersAverage')
            final_model.save_model('/freqtrade/user_data/entry_model')
        preds = final_model.predict(dataset, prediction_type='Probability')
        dataframe['entry_proba'] = preds[:, 1]
        dataframe['enter_long'] = dataframe['entry_proba'].apply(lambda x: 1 if x > 0.7 else 0)
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        strategies = STRATEGIES
        populated_dataframe = dataframe
        populated_dataframe['pair'] = metadata.get('pair')
        for strategy_name in strategies:
            strategy = self.get_strategy(strategy_name)
            populated_dataframe = strategy.advise_indicators(populated_dataframe, metadata)
        for strategy_name in strategies:
            strategy = self.get_strategy(strategy_name)
            strategy_indicators = strategy.advise_indicators(dataframe, metadata)
            dataframe[f'strat_exit_signal_{strategy_name}'] = strategy.advise_exit(strategy_indicators, metadata)['exit_long']
            y = dataframe[f'strat_exit_signal_{strategy_name}']
            x = populated_dataframe[[col for col in populated_dataframe.columns if 'date' not in col]].fillna(-1)
            # remove duplicated columns
            x = x.loc[:, ~x.columns.duplicated()]
            cat_features = [i for i in x.columns if x.dtypes[i] == 'object']
            dataset = Pool(data=x, label=y, cat_features=cat_features)
            baseline_model = CatBoostClassifier(iterations=10)
            try:
                baseline_model = baseline_model.load_model('/freqtrade/user_data/exit_model')
            except:
                # first run
                pass
            model = CatBoostClassifier(iterations=10)
            try:
                model.fit(dataset, use_best_model=True, eval_set=dataset)
            except:
                #  target contains only one value
                pass
            final_model = sum_models([baseline_model, model], weights=None, ctr_merge_policy='IntersectingCountersAverage')
            final_model.save_model('/freqtrade/user_data/exit_model')
        preds = final_model.predict(dataset, prediction_type='Probability')
        dataframe['exit_proba'] = preds[:, 1]
        dataframe['exit_long'] = dataframe['exit_proba'].apply(lambda x: 1 if x > 0.7 else 0)
        return dataframe