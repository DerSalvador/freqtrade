from datetime import datetime

from pandas import DataFrame

from freqtrade.persistence.models import Trade

from .strats.strategy_test_v3 import StrategyTestV3


def test_strategy_test_v2_structure():
    assert hasattr(StrategyTestV3, 'minimal_roi')
    assert hasattr(StrategyTestV3, 'stoploss')
    assert hasattr(StrategyTestV3, 'timeframe')
    assert hasattr(StrategyTestV3, 'populate_indicators')
    assert hasattr(StrategyTestV3, 'populate_buy_trend')
    assert hasattr(StrategyTestV3, 'populate_sell_trend')


def test_strategy_test_v2(result, fee):
    strategy = StrategyTestV3({})

    metadata = {'pair': 'ETH/BTC'}
    assert type(strategy.minimal_roi) is dict
    assert type(strategy.stoploss) is float
    assert type(strategy.timeframe) is str
    indicators = strategy.populate_indicators(result, metadata)
    assert type(indicators) is DataFrame
    assert type(strategy.populate_buy_trend(indicators, metadata)) is DataFrame
    assert type(strategy.populate_sell_trend(indicators, metadata)) is DataFrame

    trade = Trade(
        open_rate=19_000,
        amount=0.1,
        pair='ETH/BTC',
        fee_open=fee.return_value
    )

    assert strategy.confirm_trade_entry(pair='ETH/BTC', order_type='limit', amount=0.1,
                                        rate=20000, time_in_force='gtc',
                                        current_time=datetime.now(timezone.utc)(), side='long') is True
    assert strategy.confirm_trade_exit(pair='ETH/BTC', trade=trade, order_type='limit', amount=0.1,
                                       rate=20000, time_in_force='gtc', sell_reason='roi',
                                       current_time=datetime.now(timezone.utc)()) is True

    # TODO-lev: Test for shorts?
    assert strategy.custom_stoploss(pair='ETH/BTC', trade=trade, current_time=datetime.now(),
                                    current_rate=20_000, current_profit=0.05) == strategy.stoploss
