from datetime import datetime, timezone
from math import isclose
from random import randint
from unittest.mock import MagicMock, PropertyMock

import ccxt
import pytest

from freqtrade.enums import MarginMode, TradingMode
from freqtrade.exceptions import DependencyException, InvalidOrderException, OperationalException
from tests.conftest import get_mock_coro, get_patched_exchange, log_has_re
from tests.exchange.test_exchange import ccxt_exceptionhandlers


@pytest.mark.parametrize('limitratio,expected,side', [
    (None, 220 * 0.99, "sell"),
    (0.99, 220 * 0.99, "sell"),
    (0.98, 220 * 0.98, "sell"),
    (None, 220 * 1.01, "buy"),
    (0.99, 220 * 1.01, "buy"),
    (0.98, 220 * 1.02, "buy"),
])
def test_stoploss_order_binance(
    default_conf,
    mocker,
    limitratio,
    expected,
    side
):
    api_mock = MagicMock()
    order_id = 'test_prod_buy_{}'.format(randint(0, 10 ** 6))
    order_type = 'stop_loss_limit'

    api_mock.create_order = MagicMock(return_value={
        'id': order_id,
        'info': {
            'foo': 'bar'
        }
    })
    default_conf['dry_run'] = False
    mocker.patch('freqtrade.exchange.Exchange.amount_to_precision', lambda s, x, y: y)
    mocker.patch('freqtrade.exchange.Exchange.price_to_precision', lambda s, x, y: y)

    exchange = get_patched_exchange(mocker, default_conf, api_mock, 'binance')

    with pytest.raises(OperationalException):
        order = exchange.stoploss(
            pair='ETH/BTC',
            amount=1,
            stop_price=190,
            side=side,
            order_types={'stoploss_on_exchange_limit_ratio': 1.05},
            leverage=1.0
        )

    api_mock.create_order.reset_mock()
    order_types = {} if limitratio is None else {'stoploss_on_exchange_limit_ratio': limitratio}
    order = exchange.stoploss(
        pair='ETH/BTC',
        amount=1,
        stop_price=220,
        order_types=order_types,
        side=side,
        leverage=1.0
    )

    assert 'id' in order
    assert 'info' in order
    assert order['id'] == order_id
    assert api_mock.create_order.call_args_list[0][1]['symbol'] == 'ETH/BTC'
    assert api_mock.create_order.call_args_list[0][1]['type'] == order_type
    assert api_mock.create_order.call_args_list[0][1]['side'] == side
    assert api_mock.create_order.call_args_list[0][1]['amount'] == 1
    # Price should be 1% below stopprice
    assert api_mock.create_order.call_args_list[0][1]['price'] == expected
    assert api_mock.create_order.call_args_list[0][1]['params'] == {'stopPrice': 220}

    # test exception handling
    with pytest.raises(DependencyException):
        api_mock.create_order = MagicMock(side_effect=ccxt.InsufficientFunds("0 balance"))
        exchange = get_patched_exchange(mocker, default_conf, api_mock, 'binance')
        exchange.stoploss(
            pair='ETH/BTC',
            amount=1,
            stop_price=220,
            order_types={},
            side=side,
            leverage=1.0)

    with pytest.raises(InvalidOrderException):
        api_mock.create_order = MagicMock(
            side_effect=ccxt.InvalidOrder("binance Order would trigger immediately."))
        exchange = get_patched_exchange(mocker, default_conf, api_mock, 'binance')
        exchange.stoploss(
            pair='ETH/BTC',
            amount=1,
            stop_price=220,
            order_types={},
            side=side,
            leverage=1.0
        )

    ccxt_exceptionhandlers(mocker, default_conf, api_mock, "binance",
                           "stoploss", "create_order", retries=1,
                           pair='ETH/BTC', amount=1, stop_price=220, order_types={},
                           side=side, leverage=1.0)


def test_stoploss_order_dry_run_binance(default_conf, mocker):
    api_mock = MagicMock()
    order_type = 'stop_loss_limit'
    default_conf['dry_run'] = True
    mocker.patch('freqtrade.exchange.Exchange.amount_to_precision', lambda s, x, y: y)
    mocker.patch('freqtrade.exchange.Exchange.price_to_precision', lambda s, x, y: y)

    exchange = get_patched_exchange(mocker, default_conf, api_mock, 'binance')

    with pytest.raises(OperationalException):
        order = exchange.stoploss(
            pair='ETH/BTC',
            amount=1,
            stop_price=190,
            side="sell",
            order_types={'stoploss_on_exchange_limit_ratio': 1.05},
            leverage=1.0
        )

    api_mock.create_order.reset_mock()

    order = exchange.stoploss(
        pair='ETH/BTC',
        amount=1,
        stop_price=220,
        order_types={},
        side="sell",
        leverage=1.0
    )

    assert 'id' in order
    assert 'info' in order
    assert 'type' in order

    assert order['type'] == order_type
    assert order['price'] == 220
    assert order['amount'] == 1


@pytest.mark.parametrize('sl1,sl2,sl3,side', [
    (1501, 1499, 1501, "sell"),
    (1499, 1501, 1499, "buy")
])
def test_stoploss_adjust_binance(mocker, default_conf, sl1, sl2, sl3, side):
    exchange = get_patched_exchange(mocker, default_conf, id='binance')
    order = {
        'type': 'stop_loss_limit',
        'price': 1500,
        'info': {'stopPrice': 1500},
    }
    assert exchange.stoploss_adjust(sl1, order, side=side)
    assert not exchange.stoploss_adjust(sl2, order, side=side)
    # Test with invalid order case
    order['type'] = 'stop_loss'
    assert not exchange.stoploss_adjust(sl3, order, side=side)


def test_get_max_leverage_binance(default_conf, mocker):

    # Test Spot
    exchange = get_patched_exchange(mocker, default_conf, id="binance")
    assert exchange.get_max_leverage("BNB/USDT", 100.0) == 1.0

    # Test Futures
    default_conf['trading_mode'] = 'futures'
    default_conf['margin_mode'] = 'isolated'
    exchange = get_patched_exchange(mocker, default_conf, id="binance")

    exchange._leverage_tiers = {
        'BNB/BUSD': [
            {
                "min": 0,       # stake(before leverage) = 0
                "max": 100000,  # max stake(before leverage) = 5000
                "mmr": 0.025,
                "lev": 20,
                "maintAmt": 0.0
            },
            {
                "min": 100000,  # stake = 10000.0
                "max": 500000,  # max_stake = 50000.0
                "mmr": 0.05,
                "lev": 10,
                "maintAmt": 2500.0
            },
            {
                "min": 500000,   # stake = 100000.0
                "max": 1000000,  # max_stake = 200000.0
                "mmr": 0.1,
                "lev": 5,
                "maintAmt": 27500.0
            },
            {
                "min": 1000000,  # stake = 333333.3333333333
                "max": 2000000,  # max_stake = 666666.6666666666
                "mmr": 0.15,
                "lev": 3,
                "maintAmt": 77500.0
            },
            {
                "min": 2000000,  # stake = 1000000.0
                "max": 5000000,  # max_stake = 2500000.0
                "mmr": 0.25,
                "lev": 2,
                "maintAmt": 277500.0
            },
            {
                "min": 5000000,   # stake = 5000000.0
                "max": 30000000,  # max_stake = 30000000.0
                "mmr": 0.5,
                "lev": 1,
                "maintAmt": 1527500.0
            }
        ],
        'BNB/USDT': [
            {
                "min": 0,      # stake = 0.0
                "max": 10000,  # max_stake = 133.33333333333334
                "mmr": 0.0065,
                "lev": 75,
                "maintAmt": 0.0
            },
            {
                "min": 10000,  # stake = 200.0
                "max": 50000,  # max_stake = 1000.0
                "mmr": 0.01,
                "lev": 50,
                "maintAmt": 35.0
            },
            {
                "min": 50000,   # stake = 2000.0
                "max": 250000,  # max_stake = 10000.0
                "mmr": 0.02,
                "lev": 25,
                "maintAmt": 535.0
            },
            {
                "min": 250000,   # stake = 25000.0
                "max": 1000000,  # max_stake = 100000.0
                "mmr": 0.05,
                "lev": 10,
                "maintAmt": 8035.0
            },
            {
                "min": 1000000,  # stake = 200000.0
                "max": 2000000,  # max_stake = 400000.0
                "mmr": 0.1,
                "lev": 5,
                "maintAmt": 58035.0
            },
            {
                "min": 2000000,  # stake = 500000.0
                "max": 5000000,  # max_stake = 1250000.0
                "mmr": 0.125,
                "lev": 4,
                "maintAmt": 108035.0
            },
            {
                "min": 5000000,   # stake = 1666666.6666666667
                "max": 10000000,  # max_stake = 3333333.3333333335
                "mmr": 0.15,
                "lev": 3,
                "maintAmt": 233035.0
            },
            {
                "min": 10000000,  # stake = 5000000.0
                "max": 20000000,  # max_stake = 10000000.0
                "mmr": 0.25,
                "lev": 2,
                "maintAmt": 1233035.0
            },
            {
                "min": 20000000,  # stake = 20000000.0
                "max": 50000000,  # max_stake = 50000000.0
                "mmr": 0.5,
                "lev": 1,
                "maintAmt": 6233035.0
            },
        ],
        'BTC/USDT': [
            {
                "min": 0,      # stake = 0.0
                "max": 50000,  # max_stake = 400.0
                "mmr": 0.004,
                "lev": 125,
                "maintAmt": 0.0
            },
            {
                "min": 50000,   # stake = 500.0
                "max": 250000,  # max_stake = 2500.0
                "mmr": 0.005,
                "lev": 100,
                "maintAmt": 50.0
            },
            {
                "min": 250000,   # stake = 5000.0
                "max": 1000000,  # max_stake = 20000.0
                "mmr": 0.01,
                "lev": 50,
                "maintAmt": 1300.0
            },
            {
                "min": 1000000,  # stake = 50000.0
                "max": 7500000,  # max_stake = 375000.0
                "mmr": 0.025,
                "lev": 20,
                "maintAmt": 16300.0
            },
            {
                "min": 7500000,   # stake = 750000.0
                "max": 40000000,  # max_stake = 4000000.0
                "mmr": 0.05,
                "lev": 10,
                "maintAmt": 203800.0
            },
            {
                "min": 40000000,   # stake = 8000000.0
                "max": 100000000,  # max_stake = 20000000.0
                "mmr": 0.1,
                "lev": 5,
                "maintAmt": 2203800.0
            },
            {
                "min": 100000000,  # stake = 25000000.0
                "max": 200000000,  # max_stake = 50000000.0
                "mmr": 0.125,
                "lev": 4,
                "maintAmt": 4703800.0
            },
            {
                "min": 200000000,  # stake = 66666666.666666664
                "max": 400000000,  # max_stake = 133333333.33333333
                "mmr": 0.15,
                "lev": 3,
                "maintAmt": 9703800.0
            },
            {
                "min": 400000000,  # stake = 200000000.0
                "max": 600000000,  # max_stake = 300000000.0
                "mmr": 0.25,
                "lev": 2,
                "maintAmt": 4.97038E7
            },
            {
                "min": 600000000,   # stake = 600000000.0
                "max": 1000000000,  # max_stake = 1000000000.0
                "mmr": 0.5,
                "lev": 1,
                "maintAmt": 1.997038E8
            },
        ]
    }

    assert exchange.get_max_leverage("BNB/BUSD", 1.0) == 20.0
    assert exchange.get_max_leverage("BNB/USDT", 100.0) == 75.0
    assert exchange.get_max_leverage("BTC/USDT", 170.30) == 125.0
    assert isclose(exchange.get_max_leverage("BNB/BUSD", 99999.9), 5.000005)
    assert isclose(exchange.get_max_leverage("BNB/USDT", 1500), 33.333333333333333)
    assert exchange.get_max_leverage("BTC/USDT", 300000000) == 2.0
    assert exchange.get_max_leverage("BTC/USDT", 600000000) == 1.0  # Last tier

    assert exchange.get_max_leverage("ETC/USDT", 200) == 1.0    # Pair not in leverage_tiers
    assert exchange.get_max_leverage("BTC/USDT", 0.0) == 125.0  # No stake amount
    with pytest.raises(
        InvalidOrderException,
        match=r'Amount 1000000000.01 too high for BTC/USDT'
    ):
        exchange.get_max_leverage("BTC/USDT", 1000000000.01)


def test_fill_leverage_tiers_binance(default_conf, mocker):
    api_mock = MagicMock()
    api_mock.fetch_leverage_tiers = MagicMock(return_value={
        'ADA/BUSD': [
            {
                "tier": 1,
                "notionalFloor": 0,
                "notionalCap": 100000,
                "maintenanceMarginRatio": 0.025,
                "maxLeverage": 20,
                "info": {
                    "bracket": "1",
                    "initialLeverage": "20",
                    "notionalCap": "100000",
                    "notionalFloor": "0",
                    "maintMarginRatio": "0.025",
                    "cum": "0.0"
                }
            },
            {
                "tier": 2,
                "notionalFloor": 100000,
                "notionalCap": 500000,
                "maintenanceMarginRatio": 0.05,
                "maxLeverage": 10,
                "info": {
                    "bracket": "2",
                    "initialLeverage": "10",
                    "notionalCap": "500000",
                    "notionalFloor": "100000",
                    "maintMarginRatio": "0.05",
                    "cum": "2500.0"
                }
            },
            {
                "tier": 3,
                "notionalFloor": 500000,
                "notionalCap": 1000000,
                "maintenanceMarginRatio": 0.1,
                "maxLeverage": 5,
                "info": {
                    "bracket": "3",
                    "initialLeverage": "5",
                    "notionalCap": "1000000",
                    "notionalFloor": "500000",
                    "maintMarginRatio": "0.1",
                    "cum": "27500.0"
                }
            },
            {
                "tier": 4,
                "notionalFloor": 1000000,
                "notionalCap": 2000000,
                "maintenanceMarginRatio": 0.15,
                "maxLeverage": 3,
                "info": {
                    "bracket": "4",
                    "initialLeverage": "3",
                    "notionalCap": "2000000",
                    "notionalFloor": "1000000",
                    "maintMarginRatio": "0.15",
                    "cum": "77500.0"
                }
            },
            {
                "tier": 5,
                "notionalFloor": 2000000,
                "notionalCap": 5000000,
                "maintenanceMarginRatio": 0.25,
                "maxLeverage": 2,
                "info": {
                    "bracket": "5",
                    "initialLeverage": "2",
                    "notionalCap": "5000000",
                    "notionalFloor": "2000000",
                    "maintMarginRatio": "0.25",
                    "cum": "277500.0"
                }
            },
            {
                "tier": 6,
                "notionalFloor": 5000000,
                "notionalCap": 30000000,
                "maintenanceMarginRatio": 0.5,
                "maxLeverage": 1,
                "info": {
                    "bracket": "6",
                    "initialLeverage": "1",
                    "notionalCap": "30000000",
                    "notionalFloor": "5000000",
                    "maintMarginRatio": "0.5",
                    "cum": "1527500.0"
                }
            }
        ],
        "ZEC/USDT": [
            {
                "tier": 1,
                "notionalFloor": 0,
                "notionalCap": 50000,
                "maintenanceMarginRatio": 0.01,
                "maxLeverage": 50,
                "info": {
                    "bracket": "1",
                    "initialLeverage": "50",
                    "notionalCap": "50000",
                    "notionalFloor": "0",
                    "maintMarginRatio": "0.01",
                    "cum": "0.0"
                }
            },
            {
                "tier": 2,
                "notionalFloor": 50000,
                "notionalCap": 150000,
                "maintenanceMarginRatio": 0.025,
                "maxLeverage": 20,
                "info": {
                    "bracket": "2",
                    "initialLeverage": "20",
                    "notionalCap": "150000",
                    "notionalFloor": "50000",
                    "maintMarginRatio": "0.025",
                    "cum": "750.0"
                }
            },
            {
                "tier": 3,
                "notionalFloor": 150000,
                "notionalCap": 250000,
                "maintenanceMarginRatio": 0.05,
                "maxLeverage": 10,
                "info": {
                    "bracket": "3",
                    "initialLeverage": "10",
                    "notionalCap": "250000",
                    "notionalFloor": "150000",
                    "maintMarginRatio": "0.05",
                    "cum": "4500.0"
                }
            },
            {
                "tier": 4,
                "notionalFloor": 250000,
                "notionalCap": 500000,
                "maintenanceMarginRatio": 0.1,
                "maxLeverage": 5,
                "info": {
                    "bracket": "4",
                    "initialLeverage": "5",
                    "notionalCap": "500000",
                    "notionalFloor": "250000",
                    "maintMarginRatio": "0.1",
                    "cum": "17000.0"
                }
            },
            {
                "tier": 5,
                "notionalFloor": 500000,
                "notionalCap": 1000000,
                "maintenanceMarginRatio": 0.125,
                "maxLeverage": 4,
                "info": {
                    "bracket": "5",
                    "initialLeverage": "4",
                    "notionalCap": "1000000",
                    "notionalFloor": "500000",
                    "maintMarginRatio": "0.125",
                    "cum": "29500.0"
                }
            },
            {
                "tier": 6,
                "notionalFloor": 1000000,
                "notionalCap": 2000000,
                "maintenanceMarginRatio": 0.25,
                "maxLeverage": 2,
                "info": {
                    "bracket": "6",
                    "initialLeverage": "2",
                    "notionalCap": "2000000",
                    "notionalFloor": "1000000",
                    "maintMarginRatio": "0.25",
                    "cum": "154500.0"
                }
            },
            {
                "tier": 7,
                "notionalFloor": 2000000,
                "notionalCap": 30000000,
                "maintenanceMarginRatio": 0.5,
                "maxLeverage": 1,
                "info": {
                    "bracket": "7",
                    "initialLeverage": "1",
                    "notionalCap": "30000000",
                    "notionalFloor": "2000000",
                    "maintMarginRatio": "0.5",
                    "cum": "654500.0"
                }
            }
        ],

    })
    default_conf['dry_run'] = False
    default_conf['trading_mode'] = TradingMode.FUTURES
    default_conf['margin_mode'] = MarginMode.ISOLATED
    exchange = get_patched_exchange(mocker, default_conf, api_mock, id="binance")
    exchange.fill_leverage_tiers()

    assert exchange._leverage_tiers == {
        'ADA/BUSD': [
            {
                "min": 0,
                "max": 100000,
                "mmr": 0.025,
                "lev": 20,
                "maintAmt": 0.0
            },
            {
                "min": 100000,
                "max": 500000,
                "mmr": 0.05,
                "lev": 10,
                "maintAmt": 2500.0
            },
            {
                "min": 500000,
                "max": 1000000,
                "mmr": 0.1,
                "lev": 5,
                "maintAmt": 27500.0
            },
            {
                "min": 1000000,
                "max": 2000000,
                "mmr": 0.15,
                "lev": 3,
                "maintAmt": 77500.0
            },
            {
                "min": 2000000,
                "max": 5000000,
                "mmr": 0.25,
                "lev": 2,
                "maintAmt": 277500.0
            },
            {
                "min": 5000000,
                "max": 30000000,
                "mmr": 0.5,
                "lev": 1,
                "maintAmt": 1527500.0
            }
        ],
        "ZEC/USDT": [
            {
                'min': 0,
                'max': 50000,
                'mmr': 0.01,
                'lev': 50,
                'maintAmt': 0.0
            },
            {
                'min': 50000,
                'max': 150000,
                'mmr': 0.025,
                'lev': 20,
                'maintAmt': 750.0
            },
            {
                'min': 150000,
                'max': 250000,
                'mmr': 0.05,
                'lev': 10,
                'maintAmt': 4500.0
            },
            {
                'min': 250000,
                'max': 500000,
                'mmr': 0.1,
                'lev': 5,
                'maintAmt': 17000.0
            },
            {
                'min': 500000,
                'max': 1000000,
                'mmr': 0.125,
                'lev': 4,
                'maintAmt': 29500.0
            },
            {
                'min': 1000000,
                'max': 2000000,
                'mmr': 0.25,
                'lev': 2,
                'maintAmt': 154500.0
            },
            {
                'min': 2000000,
                'max': 30000000,
                'mmr': 0.5,
                'lev': 1,
                'maintAmt': 654500.0
            },
        ]
    }

    api_mock = MagicMock()
    api_mock.load_leverage_tiers = MagicMock()
    type(api_mock).has = PropertyMock(return_value={'fetchLeverageTiers': True})

    ccxt_exceptionhandlers(
        mocker,
        default_conf,
        api_mock,
        "binance",
        "fill_leverage_tiers",
        "fetch_leverage_tiers"
    )


def test_fill_leverage_tiers_binance_dryrun(default_conf, mocker):
    api_mock = MagicMock()
    default_conf['trading_mode'] = TradingMode.FUTURES
    default_conf['margin_mode'] = MarginMode.ISOLATED
    exchange = get_patched_exchange(mocker, default_conf, api_mock, id="binance")
    exchange.fill_leverage_tiers()

    leverage_tiers = {
        "1000SHIB/USDT": [
            {
                'min': 0,
                'max': 50000,
                'mmr': 0.01,
                'lev': 50,
                'maintAmt': 0.0
            },
            {
                'min': 50000,
                'max': 150000,
                'mmr': 0.025,
                'lev': 20,
                'maintAmt': 750.0
            },
            {
                'min': 150000,
                'max': 250000,
                'mmr': 0.05,
                'lev': 10,
                'maintAmt': 4500.0
            },
            {
                'min': 250000,
                'max': 500000,
                'mmr': 0.1,
                'lev': 5,
                'maintAmt': 17000.0
            },
            {
                'min': 500000,
                'max': 1000000,
                'mmr': 0.125,
                'lev': 4,
                'maintAmt': 29500.0
            },
            {
                'min': 1000000,
                'max': 2000000,
                'mmr': 0.25,
                'lev': 2,
                'maintAmt': 154500.0
            },
            {
                'min': 2000000,
                'max': 30000000,
                'mmr': 0.5,
                'lev': 1,
                'maintAmt': 654500.0
            },
        ],
        "1INCH/USDT": [
            {
                'min': 0,
                'max': 5000,
                'mmr': 0.012,
                'lev': 50,
                'maintAmt': 0.0
            },
            {
                'min': 5000,
                'max': 25000,
                'mmr': 0.025,
                'lev': 20,
                'maintAmt': 65.0
            },
            {
                'min': 25000,
                'max': 100000,
                'mmr': 0.05,
                'lev': 10,
                'maintAmt': 690.0
            },
            {
                'min': 100000,
                'max': 250000,
                'mmr': 0.1,
                'lev': 5,
                'maintAmt': 5690.0
            },
            {
                'min': 250000,
                'max': 1000000,
                'mmr': 0.125,
                'lev': 2,
                'maintAmt': 11940.0
            },
            {
                'min': 1000000,
                'max': 100000000,
                'mmr': 0.5,
                'lev': 1,
                'maintAmt': 386940.0
            },
        ],
        "AAVE/USDT": [
            {
                'min': 0,
                'max': 50000,
                'mmr': 0.01,
                'lev': 50,
                'maintAmt': 0.0
            },
            {
                'min': 50000,
                'max': 250000,
                'mmr': 0.02,
                'lev': 25,
                'maintAmt': 500.0
            },
            {
                'min': 250000,
                'max': 1000000,
                'mmr': 0.05,
                'lev': 10,
                'maintAmt': 8000.0
            },
            {
                'min': 1000000,
                'max': 2000000,
                'mmr': 0.1,
                'lev': 5,
                'maintAmt': 58000.0
            },
            {
                'min': 2000000,
                'max': 5000000,
                'mmr': 0.125,
                'lev': 4,
                'maintAmt': 108000.0
            },
            {
                'min': 5000000,
                'max': 10000000,
                'mmr': 0.1665,
                'lev': 3,
                'maintAmt': 315500.0
            },
            {
                'min': 10000000,
                'max': 20000000,
                'mmr': 0.25,
                'lev': 2,
                'maintAmt': 1150500.0
            },
            {
                "min": 20000000,
                "max": 50000000,
                "mmr": 0.5,
                "lev": 1,
                "maintAmt": 6150500.0
            }
        ],
        "ADA/BUSD": [
            {
                "min": 0,
                "max": 100000,
                "mmr": 0.025,
                "lev": 20,
                "maintAmt": 0.0
            },
            {
                "min": 100000,
                "max": 500000,
                "mmr": 0.05,
                "lev": 10,
                "maintAmt": 2500.0
            },
            {
                "min": 500000,
                "max": 1000000,
                "mmr": 0.1,
                "lev": 5,
                "maintAmt": 27500.0
            },
            {
                "min": 1000000,
                "max": 2000000,
                "mmr": 0.15,
                "lev": 3,
                "maintAmt": 77500.0
            },
            {
                "min": 2000000,
                "max": 5000000,
                "mmr": 0.25,
                "lev": 2,
                "maintAmt": 277500.0
            },
            {
                "min": 5000000,
                "max": 30000000,
                "mmr": 0.5,
                "lev": 1,
                "maintAmt": 1527500.0
            },
        ]
    }

    for key, value in leverage_tiers.items():
        assert exchange._leverage_tiers[key] == value


def test__set_leverage_binance(mocker, default_conf):

    api_mock = MagicMock()
    api_mock.set_leverage = MagicMock()
    type(api_mock).has = PropertyMock(return_value={'setLeverage': True})
    default_conf['dry_run'] = False
    exchange = get_patched_exchange(mocker, default_conf, id="binance")
    exchange._set_leverage(3.0, trading_mode=TradingMode.MARGIN)

    ccxt_exceptionhandlers(
        mocker,
        default_conf,
        api_mock,
        "binance",
        "_set_leverage",
        "set_leverage",
        pair="XRP/USDT",
        leverage=5.0,
        trading_mode=TradingMode.FUTURES
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('candle_type', ['mark', ''])
async def test__async_get_historic_ohlcv_binance(default_conf, mocker, caplog, candle_type):
    ohlcv = [
        [
            int((datetime.now(timezone.utc).timestamp() - 1000) * 1000),
            1,  # open
            2,  # high
            3,  # low
            4,  # close
            5,  # volume (in quote currency)
        ]
    ]

    exchange = get_patched_exchange(mocker, default_conf, id='binance')
    # Monkey-patch async function
    exchange._api_async.fetch_ohlcv = get_mock_coro(ohlcv)

    pair = 'ETH/BTC'
    respair, restf, restype, res = await exchange._async_get_historic_ohlcv(
        pair, "5m", 1500000000000, is_new_pair=False, candle_type=candle_type)
    assert respair == pair
    assert restf == '5m'
    assert restype == candle_type
    # Call with very old timestamp - causes tons of requests
    assert exchange._api_async.fetch_ohlcv.call_count > 400
    # assert res == ohlcv
    exchange._api_async.fetch_ohlcv.reset_mock()
    _, _, _, res = await exchange._async_get_historic_ohlcv(
        pair, "5m", 1500000000000, is_new_pair=True, candle_type=candle_type)

    # Called twice - one "init" call - and one to get the actual data.
    assert exchange._api_async.fetch_ohlcv.call_count == 2
    assert res == ohlcv
    assert log_has_re(r"Candle-data for ETH/BTC available starting with .*", caplog)


@pytest.mark.parametrize("trading_mode,margin_mode,config", [
    ("spot", "", {}),
    ("margin", "cross", {"options": {"defaultType": "margin"}}),
    ("futures", "isolated", {"options": {"defaultType": "future"}}),
])
def test__ccxt_config(default_conf, mocker, trading_mode, margin_mode, config):
    default_conf['trading_mode'] = trading_mode
    default_conf['margin_mode'] = margin_mode
    exchange = get_patched_exchange(mocker, default_conf, id="binance")
    assert exchange._ccxt_config == config


@pytest.mark.parametrize('pair,nominal_value,mm_ratio,amt', [
    ("BNB/BUSD", 0.0, 0.025, 0),
    ("BNB/USDT", 100.0, 0.0065, 0),
    ("BTC/USDT", 170.30, 0.004, 0),
    ("BNB/BUSD", 999999.9, 0.1, 27500.0),
    ("BNB/USDT", 5000000.0, 0.15, 233035.0),
    ("BTC/USDT", 600000000, 0.5, 1.997038E8),
])
def test_get_maintenance_ratio_and_amt_binance(
    default_conf,
    mocker,
    pair,
    nominal_value,
    mm_ratio,
    amt,
):
    exchange = get_patched_exchange(mocker, default_conf, id="binance")
    exchange._leverage_tiers = {
        'BNB/BUSD': [
            {
                "min": 0,       # stake(before leverage) = 0
                "max": 100000,  # max stake(before leverage) = 5000
                "mmr": 0.025,
                "lev": 20,
                "maintAmt": 0.0
            },
            {
                "min": 100000,  # stake = 10000.0
                "max": 500000,  # max_stake = 50000.0
                "mmr": 0.05,
                "lev": 10,
                "maintAmt": 2500.0
            },
            {
                "min": 500000,   # stake = 100000.0
                "max": 1000000,  # max_stake = 200000.0
                "mmr": 0.1,
                "lev": 5,
                "maintAmt": 27500.0
            },
            {
                "min": 1000000,  # stake = 333333.3333333333
                "max": 2000000,  # max_stake = 666666.6666666666
                "mmr": 0.15,
                "lev": 3,
                "maintAmt": 77500.0
            },
            {
                "min": 2000000,  # stake = 1000000.0
                "max": 5000000,  # max_stake = 2500000.0
                "mmr": 0.25,
                "lev": 2,
                "maintAmt": 277500.0
            },
            {
                "min": 5000000,   # stake = 5000000.0
                "max": 30000000,  # max_stake = 30000000.0
                "mmr": 0.5,
                "lev": 1,
                "maintAmt": 1527500.0
            }
        ],
        'BNB/USDT': [
            {
                "min": 0,      # stake = 0.0
                "max": 10000,  # max_stake = 133.33333333333334
                "mmr": 0.0065,
                "lev": 75,
                "maintAmt": 0.0
            },
            {
                "min": 10000,  # stake = 200.0
                "max": 50000,  # max_stake = 1000.0
                "mmr": 0.01,
                "lev": 50,
                "maintAmt": 35.0
            },
            {
                "min": 50000,   # stake = 2000.0
                "max": 250000,  # max_stake = 10000.0
                "mmr": 0.02,
                "lev": 25,
                "maintAmt": 535.0
            },
            {
                "min": 250000,   # stake = 25000.0
                "max": 1000000,  # max_stake = 100000.0
                "mmr": 0.05,
                "lev": 10,
                "maintAmt": 8035.0
            },
            {
                "min": 1000000,  # stake = 200000.0
                "max": 2000000,  # max_stake = 400000.0
                "mmr": 0.1,
                "lev": 5,
                "maintAmt": 58035.0
            },
            {
                "min": 2000000,  # stake = 500000.0
                "max": 5000000,  # max_stake = 1250000.0
                "mmr": 0.125,
                "lev": 4,
                "maintAmt": 108035.0
            },
            {
                "min": 5000000,   # stake = 1666666.6666666667
                "max": 10000000,  # max_stake = 3333333.3333333335
                "mmr": 0.15,
                "lev": 3,
                "maintAmt": 233035.0
            },
            {
                "min": 10000000,  # stake = 5000000.0
                "max": 20000000,  # max_stake = 10000000.0
                "mmr": 0.25,
                "lev": 2,
                "maintAmt": 1233035.0
            },
            {
                "min": 20000000,  # stake = 20000000.0
                "max": 50000000,  # max_stake = 50000000.0
                "mmr": 0.5,
                "lev": 1,
                "maintAmt": 6233035.0
            },
        ],
        'BTC/USDT': [
            {
                "min": 0,      # stake = 0.0
                "max": 50000,  # max_stake = 400.0
                "mmr": 0.004,
                "lev": 125,
                "maintAmt": 0.0
            },
            {
                "min": 50000,   # stake = 500.0
                "max": 250000,  # max_stake = 2500.0
                "mmr": 0.005,
                "lev": 100,
                "maintAmt": 50.0
            },
            {
                "min": 250000,   # stake = 5000.0
                "max": 1000000,  # max_stake = 20000.0
                "mmr": 0.01,
                "lev": 50,
                "maintAmt": 1300.0
            },
            {
                "min": 1000000,  # stake = 50000.0
                "max": 7500000,  # max_stake = 375000.0
                "mmr": 0.025,
                "lev": 20,
                "maintAmt": 16300.0
            },
            {
                "min": 7500000,   # stake = 750000.0
                "max": 40000000,  # max_stake = 4000000.0
                "mmr": 0.05,
                "lev": 10,
                "maintAmt": 203800.0
            },
            {
                "min": 40000000,   # stake = 8000000.0
                "max": 100000000,  # max_stake = 20000000.0
                "mmr": 0.1,
                "lev": 5,
                "maintAmt": 2203800.0
            },
            {
                "min": 100000000,  # stake = 25000000.0
                "max": 200000000,  # max_stake = 50000000.0
                "mmr": 0.125,
                "lev": 4,
                "maintAmt": 4703800.0
            },
            {
                "min": 200000000,  # stake = 66666666.666666664
                "max": 400000000,  # max_stake = 133333333.33333333
                "mmr": 0.15,
                "lev": 3,
                "maintAmt": 9703800.0
            },
            {
                "min": 400000000,  # stake = 200000000.0
                "max": 600000000,  # max_stake = 300000000.0
                "mmr": 0.25,
                "lev": 2,
                "maintAmt": 4.97038E7
            },
            {
                "min": 600000000,   # stake = 600000000.0
                "max": 1000000000,  # max_stake = 1000000000.0
                "mmr": 0.5,
                "lev": 1,
                "maintAmt": 1.997038E8
            },
        ]
    }
    (result_ratio, result_amt) = exchange.get_maintenance_ratio_and_amt(pair, nominal_value)
    assert (round(result_ratio, 8), round(result_amt, 8)) == (mm_ratio, amt)
