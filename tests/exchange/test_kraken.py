from random import randint
from unittest.mock import MagicMock

import ccxt
import pytest

from freqtrade.exceptions import DependencyException, InvalidOrderException
from tests.conftest import get_patched_exchange
from tests.exchange.test_exchange import ccxt_exceptionhandlers


STOPLOSS_ORDERTYPE = 'stop-loss'
STOPLOSS_LIMIT_ORDERTYPE = 'stop-loss-limit'


def test_buy_kraken_trading_agreement(default_conf, mocker):
    api_mock = MagicMock()
    order_id = 'test_prod_buy_{}'.format(randint(0, 10 ** 6))
    order_type = 'limit'
    time_in_force = 'ioc'
    api_mock.options = {}
    api_mock.create_order = MagicMock(return_value={
        'id': order_id,
        'info': {
            'foo': 'bar'
        }
    })
    default_conf['dry_run'] = False

    mocker.patch('freqtrade.exchange.Exchange.amount_to_precision', lambda s, x, y: y)
    mocker.patch('freqtrade.exchange.Exchange.price_to_precision', lambda s, x, y: y)
    exchange = get_patched_exchange(mocker, default_conf, api_mock, id="kraken")

    order = exchange.create_order(pair='ETH/BTC', ordertype=order_type, side="buy",
                                  amount=1, rate=200, time_in_force=time_in_force)

    assert 'id' in order
    assert 'info' in order
    assert order['id'] == order_id
    assert api_mock.create_order.call_args[0][0] == 'ETH/BTC'
    assert api_mock.create_order.call_args[0][1] == order_type
    assert api_mock.create_order.call_args[0][2] == 'buy'
    assert api_mock.create_order.call_args[0][3] == 1
    assert api_mock.create_order.call_args[0][4] == 200
    assert api_mock.create_order.call_args[0][5] == {'timeInForce': 'ioc',
                                                     'trading_agreement': 'agree'}


def test_sell_kraken_trading_agreement(default_conf, mocker):
    api_mock = MagicMock()
    order_id = 'test_prod_sell_{}'.format(randint(0, 10 ** 6))
    order_type = 'market'
    api_mock.options = {}
    api_mock.create_order = MagicMock(return_value={
        'id': order_id,
        'info': {
            'foo': 'bar'
        }
    })
    default_conf['dry_run'] = False

    mocker.patch('freqtrade.exchange.Exchange.amount_to_precision', lambda s, x, y: y)
    mocker.patch('freqtrade.exchange.Exchange.price_to_precision', lambda s, x, y: y)
    exchange = get_patched_exchange(mocker, default_conf, api_mock, id="kraken")

    order = exchange.create_order(pair='ETH/BTC', ordertype=order_type,
                                  side="sell", amount=1, rate=200)

    assert 'id' in order
    assert 'info' in order
    assert order['id'] == order_id
    assert api_mock.create_order.call_args[0][0] == 'ETH/BTC'
    assert api_mock.create_order.call_args[0][1] == order_type
    assert api_mock.create_order.call_args[0][2] == 'sell'
    assert api_mock.create_order.call_args[0][3] == 1
    assert api_mock.create_order.call_args[0][4] is None
    assert api_mock.create_order.call_args[0][5] == {'trading_agreement': 'agree'}


def test_get_balances_prod(default_conf, mocker):
    balance_item = {
        'free': None,
        'total': 10.0,
        'used': 0.0
    }

    api_mock = MagicMock()
    api_mock.fetch_balance = MagicMock(return_value={
        '1ST': balance_item.copy(),
        '2ST': balance_item.copy(),
        '3ST': balance_item.copy(),
        '4ST': balance_item.copy(),
        'EUR': balance_item.copy(),
        'timestamp': 123123
    })
    kraken_open_orders = [{'symbol': '1ST/EUR',
                           'type': 'limit',
                           'side': 'sell',
                           'price': 20,
                           'cost': 0.0,
                           'amount': 1.0,
                           'filled': 0.0,
                           'average': 0.0,
                           'remaining': 1.0,
                           },
                          {'status': 'open',
                           'symbol': '2ST/EUR',
                           'type': 'limit',
                           'side': 'sell',
                           'price': 20.0,
                           'cost': 0.0,
                           'amount': 2.0,
                           'filled': 0.0,
                           'average': 0.0,
                           'remaining': 2.0,
                           },
                          {'status': 'open',
                           'symbol': '2ST/USD',
                           'type': 'limit',
                           'side': 'sell',
                           'price': 20.0,
                           'cost': 0.0,
                           'amount': 2.0,
                           'filled': 0.0,
                           'average': 0.0,
                           'remaining': 2.0,
                           },
                          {'status': 'open',
                           'symbol': '3ST/EUR',
                           'type': 'limit',
                           'side': 'buy',
                           'price': 0.02,
                           'cost': 0.0,
                           'amount': 100.0,
                           'filled': 0.0,
                           'average': 0.0,
                           'remaining': 100.0,
                           }]
    api_mock.fetch_open_orders = MagicMock(return_value=kraken_open_orders)
    default_conf['dry_run'] = False
    exchange = get_patched_exchange(mocker, default_conf, api_mock, id="kraken")
    balances = exchange.get_balances()
    assert len(balances) == 6

    assert balances['1ST']['free'] == 9.0
    assert balances['1ST']['total'] == 10.0
    assert balances['1ST']['used'] == 1.0

    assert balances['2ST']['free'] == 6.0
    assert balances['2ST']['total'] == 10.0
    assert balances['2ST']['used'] == 4.0

    assert balances['3ST']['free'] == 10.0
    assert balances['3ST']['total'] == 10.0
    assert balances['3ST']['used'] == 0.0

    assert balances['4ST']['free'] == 10.0
    assert balances['4ST']['total'] == 10.0
    assert balances['4ST']['used'] == 0.0

    assert balances['EUR']['free'] == 8.0
    assert balances['EUR']['total'] == 10.0
    assert balances['EUR']['used'] == 2.0
    ccxt_exceptionhandlers(mocker, default_conf, api_mock, "kraken",
                           "get_balances", "fetch_balance")

# TODO-lev: All these stoploss tests with shorts


@pytest.mark.parametrize('ordertype', ['market', 'limit'])
def test_stoploss_order_kraken(default_conf, mocker, ordertype):
    api_mock = MagicMock()
    order_id = 'test_prod_buy_{}'.format(randint(0, 10 ** 6))

    api_mock.create_order = MagicMock(return_value={
        'id': order_id,
        'info': {
            'foo': 'bar'
        }
    })

    default_conf['dry_run'] = False
    mocker.patch('freqtrade.exchange.Exchange.amount_to_precision', lambda s, x, y: y)
    mocker.patch('freqtrade.exchange.Exchange.price_to_precision', lambda s, x, y: y)

    exchange = get_patched_exchange(mocker, default_conf, api_mock, 'kraken')

    order = exchange.stoploss(pair='ETH/BTC', amount=1, stop_price=220, side="sell",
                              order_types={'stoploss': ordertype,
                                           'stoploss_on_exchange_limit_ratio': 0.99
                                           })

    assert 'id' in order
    assert 'info' in order
    assert order['id'] == order_id
    assert api_mock.create_order.call_args_list[0][1]['symbol'] == 'ETH/BTC'
    if ordertype == 'limit':
        assert api_mock.create_order.call_args_list[0][1]['type'] == STOPLOSS_LIMIT_ORDERTYPE
        assert api_mock.create_order.call_args_list[0][1]['params'] == {
            'trading_agreement': 'agree', 'price2': 217.8}
    else:
        assert api_mock.create_order.call_args_list[0][1]['type'] == STOPLOSS_ORDERTYPE
        assert api_mock.create_order.call_args_list[0][1]['params'] == {
            'trading_agreement': 'agree'}
    assert api_mock.create_order.call_args_list[0][1]['side'] == 'sell'
    assert api_mock.create_order.call_args_list[0][1]['amount'] == 1
    assert api_mock.create_order.call_args_list[0][1]['price'] == 220

    # test exception handling
    with pytest.raises(DependencyException):
        api_mock.create_order = MagicMock(side_effect=ccxt.InsufficientFunds("0 balance"))
        exchange = get_patched_exchange(mocker, default_conf, api_mock, 'kraken')
        exchange.stoploss(pair='ETH/BTC', amount=1, stop_price=220, order_types={}, side="sell")

    with pytest.raises(InvalidOrderException):
        api_mock.create_order = MagicMock(
            side_effect=ccxt.InvalidOrder("kraken Order would trigger immediately."))
        exchange = get_patched_exchange(mocker, default_conf, api_mock, 'kraken')
        exchange.stoploss(pair='ETH/BTC', amount=1, stop_price=220, order_types={}, side="sell")

    ccxt_exceptionhandlers(mocker, default_conf, api_mock, "kraken",
                           "stoploss", "create_order", retries=1,
                           pair='ETH/BTC', amount=1, stop_price=220, order_types={}, side="sell")


def test_stoploss_order_dry_run_kraken(default_conf, mocker):
    api_mock = MagicMock()
    default_conf['dry_run'] = True
    mocker.patch('freqtrade.exchange.Exchange.amount_to_precision', lambda s, x, y: y)
    mocker.patch('freqtrade.exchange.Exchange.price_to_precision', lambda s, x, y: y)

    exchange = get_patched_exchange(mocker, default_conf, api_mock, 'kraken')

    api_mock.create_order.reset_mock()

    order = exchange.stoploss(pair='ETH/BTC', amount=1, stop_price=220, order_types={}, side="sell")

    assert 'id' in order
    assert 'info' in order
    assert 'type' in order

    assert order['type'] == STOPLOSS_ORDERTYPE
    assert order['price'] == 220
    assert order['amount'] == 1


def test_stoploss_adjust_kraken(mocker, default_conf):
    exchange = get_patched_exchange(mocker, default_conf, id='kraken')
    order = {
        'type': STOPLOSS_ORDERTYPE,
        'price': 1500,
    }
    assert exchange.stoploss_adjust(1501, order, side="sell")
    assert not exchange.stoploss_adjust(1499, order, side="sell")
    # Test with invalid order case ...
    order['type'] = 'stop_loss_limit'
    assert not exchange.stoploss_adjust(1501, order, side="sell")


@pytest.mark.parametrize('pair,nominal_value,max_lev', [
    ("ADA/BTC", 0.0, 3.0),
    ("BTC/EUR", 100.0, 5.0),
    ("ZEC/USD", 173.31, 2.0),
])
def test_get_max_leverage_kraken(default_conf, mocker, pair, nominal_value, max_lev):
    exchange = get_patched_exchange(mocker, default_conf, id="kraken")
    exchange._leverage_brackets = {
        'ADA/BTC': ['2', '3'],
        'BTC/EUR': ['2', '3', '4', '5'],
        'ZEC/USD': ['2']
    }
    assert exchange.get_max_leverage(pair, nominal_value) == max_lev


def test_fill_leverage_brackets_kraken(default_conf, mocker):
    api_mock = MagicMock()
    exchange = get_patched_exchange(mocker, default_conf, api_mock, id="kraken")
    exchange.fill_leverage_brackets()

    assert exchange._leverage_brackets == {
        'BLK/BTC': ['2', '3'],
        'TKN/BTC': ['2', '3', '4', '5'],
        'ETH/BTC': ['2']
    }
