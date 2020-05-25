import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from freqtrade.configuration import TimeRange
from freqtrade.data.btanalysis import (calculate_max_drawdown, combine_dataframes_with_mean,
                                       create_cum_profit, extract_trades_of_period, load_trades)
from freqtrade.data.converter import trim_dataframe
from freqtrade.data.dataprovider import DataProvider
from freqtrade.data.history import get_timerange, load_data
from freqtrade.exceptions import OperationalException
from freqtrade.exchange import timeframe_to_prev_date, timeframe_to_seconds
from freqtrade.misc import pair_to_filename
from freqtrade.resolvers import ExchangeResolver, StrategyResolver
from freqtrade.strategy import IStrategy


logger = logging.getLogger(__name__)


try:
    import plotly.graph_objects as go
    from plotly.offline import plot
    from plotly.subplots import make_subplots
except ImportError:
    logger.exception("Module plotly not found \n Please install using `pip3 install plotly`")
    exit(1)


def init_plotscript(config, startup_candles: int = 0):
    """
    Initialize objects needed for plotting
    :return: Dict with candle (OHLCV) data, trades and pairs
    """

    if "pairs" in config:
        pairs = config['pairs']
    else:
        pairs = config['exchange']['pair_whitelist']

    # Set timerange to use
    timerange = TimeRange.parse_timerange(config.get('timerange'))

    data = load_data(
        datadir=config.get('datadir'),
        pairs=pairs,
        timeframe=config.get('timeframe', '5m'),
        timerange=timerange,
        startup_candles=startup_candles,
        data_format=config.get('dataformat_ohlcv', 'json'),
    )

    if startup_candles:
        min_date, max_date = get_timerange(data)
        logger.info(f"Loading data from {min_date} to {max_date}")
        timerange.adjust_start_if_necessary(timeframe_to_seconds(config.get('timeframe', '5m')),
                                            startup_candles, min_date)

    no_trades = False
    filename = config.get('exportfilename')
    if config.get('no_trades', False):
        no_trades = True
    elif config['trade_source'] == 'file':
        if not filename.is_dir() and not filename.is_file():
            logger.warning("Backtest file is missing skipping trades.")
            no_trades = True

    trades = load_trades(
        config['trade_source'],
        db_url=config.get('db_url'),
        exportfilename=filename,
        no_trades=no_trades,
        strategy=config.get('strategy'),
    )
    trades = trim_dataframe(trades, timerange, 'open_date')

    return {"ohlcv": data,
            "trades": trades,
            "pairs": pairs,
            "timerange": timerange,
            }


def add_indicators(fig, row, indicators: Dict[str, Dict], data: pd.DataFrame) -> make_subplots:
    """
    Generate all the indicators selected by the user for a specific row, based on the configuration
    :param fig: Plot figure to append to
    :param row: row number for this plot
    :param indicators: Dict of Indicators with configuration options.
                       Dict key must correspond to dataframe column.
    :param data: candlestick DataFrame
    """
    for indicator, conf in indicators.items():
        logger.debug(f"indicator {indicator} with config {conf}")
        if indicator in data:
            kwargs = {'x': data['date'],
                      'y': data[indicator].values,
                      'mode': 'lines',
                      'name': indicator
                      }
            if 'color' in conf:
                kwargs.update({'line': {'color': conf['color']}})
            scatter = go.Scatter(
                **kwargs
            )
            fig.add_trace(scatter, row, 1)
        else:
            logger.info(
                'Indicator "%s" ignored. Reason: This indicator is not found '
                'in your strategy.',
                indicator
            )

    return fig


def add_profit(fig, row, data: pd.DataFrame, column: str, name: str) -> make_subplots:
    """
    Add profit-plot
    :param fig: Plot figure to append to
    :param row: row number for this plot
    :param data: candlestick DataFrame
    :param column: Column to use for plot
    :param name: Name to use
    :return: fig with added profit plot
    """
    profit = go.Scatter(
        x=data.index,
        y=data[column],
        name=name,
    )
    fig.add_trace(profit, row, 1)

    return fig


def add_max_drawdown(fig, row, trades: pd.DataFrame, df_comb: pd.DataFrame,
                     timeframe: str) -> make_subplots:
    """
    Add scatter points indicating max drawdown
    """
    try:
        max_drawdown, highdate, lowdate = calculate_max_drawdown(trades)

        drawdown = go.Scatter(
            x=[highdate, lowdate],
            y=[
                df_comb.loc[timeframe_to_prev_date(timeframe, highdate), 'cum_profit'],
                df_comb.loc[timeframe_to_prev_date(timeframe, lowdate), 'cum_profit'],
            ],
            mode='markers',
            name=f"Max drawdown {max_drawdown * 100:.2f}%",
            text=f"Max drawdown {max_drawdown * 100:.2f}%",
            marker=dict(
                symbol='square-open',
                size=9,
                line=dict(width=2),
                color='green'

            )
        )
        fig.add_trace(drawdown, row, 1)
    except ValueError:
        logger.warning("No trades found - not plotting max drawdown.")
    return fig


def plot_trades(fig, trades: pd.DataFrame) -> make_subplots:
    """
    Add trades to "fig"
    """
    # Trades can be empty
    if trades is not None and len(trades) > 0:
        # Create description for sell summarizing the trade
        trades['desc'] = trades.apply(lambda row: f"{round(row['profit_percent'] * 100, 1)}%, "
                                                  f"{row['sell_reason']}, "
                                                  f"{row['trade_duration']} min",
                                                  axis=1)
        trade_buys = go.Scatter(
            x=trades["open_date"],
            y=trades["open_rate"],
            mode='markers',
            name='Trade buy',
            text=trades["desc"],
            marker=dict(
                symbol='circle-open',
                size=11,
                line=dict(width=2),
                color='cyan'

            )
        )

        trade_sells = go.Scatter(
            x=trades.loc[trades['profit_percent'] > 0, "close_date"],
            y=trades.loc[trades['profit_percent'] > 0, "close_rate"],
            text=trades.loc[trades['profit_percent'] > 0, "desc"],
            mode='markers',
            name='Sell - Profit',
            marker=dict(
                symbol='square-open',
                size=11,
                line=dict(width=2),
                color='green'
            )
        )
        trade_sells_loss = go.Scatter(
            x=trades.loc[trades['profit_percent'] <= 0, "close_date"],
            y=trades.loc[trades['profit_percent'] <= 0, "close_rate"],
            text=trades.loc[trades['profit_percent'] <= 0, "desc"],
            mode='markers',
            name='Sell - Loss',
            marker=dict(
                symbol='square-open',
                size=11,
                line=dict(width=2),
                color='red'
            )
        )
        fig.add_trace(trade_buys, 1, 1)
        fig.add_trace(trade_sells, 1, 1)
        fig.add_trace(trade_sells_loss, 1, 1)
    else:
        logger.warning("No trades found.")
    return fig


def create_plotconfig(indicators1: List[str], indicators2: List[str],
                      plot_config: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Combines indicators 1 and indicators 2 into plot_config if necessary
    :param indicators1: List containing Main plot indicators
    :param indicators2: List containing Sub plot indicators
    :param plot_config: Dict of Dicts containing advanced plot configuration
    :return: plot_config - eventually with indicators 1 and 2
    """
    if plot_config:
        # maybe main or sub is given, not both.
        if 'main_plot' not in plot_config.keys():
            plot_config['main_plot'] = {}

        if 'subplots' not in plot_config.keys():
            plot_config['subplots'] = {}
        if indicators1:
            for ind in indicators1:
                # add indicators with NO advanced plot_config, only! to be sure
                # indicator colors given in advanced plot_config will not be
                # overwritten.
                if ind not in plot_config['main_plot'].keys():
                    plot_config['main_plot'][ind] = {}
        if indicators2:
            # add other indicators given on cmd line to advanced plot_config.
            plot_config['subplots'].update(
                {'Other': {ind: {} for ind in indicators2}}
            )

    if not plot_config:
        # If no indicators and no plot-config given, use defaults.
        if not indicators1:
            indicators1 = ['sma', 'ema3', 'ema5']
        if not indicators2:
            indicators2 = ['macd', 'macdsignal']

        # Create subplot configuration if plot_config is not available.
        plot_config = {
            'main_plot': {ind: {} for ind in indicators1},
            'subplots': {'Other': {ind: {} for ind in indicators2}},
        }

    return plot_config


def generate_candlestick_graph(pair: str, data: pd.DataFrame, trades: pd.DataFrame = None, *,
                               indicators1: List[str] = [],
                               indicators2: List[str] = [],
                               plot_config: Dict[str, Dict] = {},
                               ) -> go.Figure:
    """
    Generate the graph from the data generated by Backtesting or from DB
    Volume will always be ploted in row2, so Row 1 and 3 are to our disposal for custom indicators
    :param pair: Pair to Display on the graph
    :param data: OHLCV DataFrame containing indicators and buy/sell signals
    :param trades: All trades created
    :param indicators1: List containing Main plot indicators
    :param indicators2: List containing Sub plot indicators
    :param plot_config: Dict of Dicts containing advanced plot configuration
    :return: Plotly figure
    """
    plot_config = create_plotconfig(indicators1, indicators2, plot_config)
    rows = 2 + len(plot_config['subplots'])
    row_widths = [1 for _ in plot_config['subplots']]
    # Define the graph
    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        row_width=row_widths + [1, 4],
        vertical_spacing=0.0001,
    )
    fig['layout'].update(title=pair)
    fig['layout']['yaxis1'].update(title='Price')
    fig['layout']['yaxis2'].update(title='Volume')
    for i, name in enumerate(plot_config['subplots']):
        fig['layout'][f'yaxis{3 + i}'].update(title=name)
    fig['layout']['xaxis']['rangeslider'].update(visible=False)

    # Common information
    candles = go.Candlestick(
        x=data.date,
        open=data.open,
        high=data.high,
        low=data.low,
        close=data.close,
        name='Price'
    )
    fig.add_trace(candles, 1, 1)

    if 'buy' in data.columns:
        df_buy = data[data['buy'] == 1]
        if len(df_buy) > 0:
            buys = go.Scatter(
                x=df_buy.date,
                y=df_buy.close,
                mode='markers',
                name='buy',
                marker=dict(
                    symbol='triangle-up-dot',
                    size=9,
                    line=dict(width=1),
                    color='green',
                )
            )
            fig.add_trace(buys, 1, 1)
        else:
            logger.warning("No buy-signals found.")

    if 'sell' in data.columns:
        df_sell = data[data['sell'] == 1]
        if len(df_sell) > 0:
            sells = go.Scatter(
                x=df_sell.date,
                y=df_sell.close,
                mode='markers',
                name='sell',
                marker=dict(
                    symbol='triangle-down-dot',
                    size=9,
                    line=dict(width=1),
                    color='red',
                )
            )
            fig.add_trace(sells, 1, 1)
        else:
            logger.warning("No sell-signals found.")

    # TODO: Figure out why scattergl causes problems plotly/plotly.js#2284
    if 'bb_lowerband' in data and 'bb_upperband' in data:
        bb_lower = go.Scatter(
            x=data.date,
            y=data.bb_lowerband,
            showlegend=False,
            line={'color': 'rgba(255,255,255,0)'},
        )
        bb_upper = go.Scatter(
            x=data.date,
            y=data.bb_upperband,
            name='Bollinger Band',
            fill="tonexty",
            fillcolor="rgba(0,176,246,0.2)",
            line={'color': 'rgba(255,255,255,0)'},
        )
        fig.add_trace(bb_lower, 1, 1)
        fig.add_trace(bb_upper, 1, 1)
        if ('bb_upperband' in plot_config['main_plot']
           and 'bb_lowerband' in plot_config['main_plot']):
            del plot_config['main_plot']['bb_upperband']
            del plot_config['main_plot']['bb_lowerband']

    # fill area betwenn traces i.e. for ichimoku
    if 'fill_area' in plot_config.keys():
        for label, area in plot_config['fill_area'].items():
            traces = area['traces']
            if len(traces) != 2:
                raise Exception(
                    f"plot_config.fill_area.traces = {traces}: " +
                    f"needs exactly 2 indicators. " +
                    f"{len(traces)} is given."
                )
            color = area['color']
        if traces[0] in data and traces[1] in data:
            trace_b = go.Scatter(
                x=data.date,
                y=data.get(traces[0]),
                showlegend=False,
                line={'color': 'rgba(255,255,255,0)'},
            )
            trace_a = go.Scatter(
                x=data.date,
                y=data.get(traces[1]),
                name=label,
                fill="tonexty",
                fillcolor=color,
                line={'color': 'rgba(255,255,255,0)'},
            )
            fig.add_trace(trace_b)
            fig.add_trace(trace_a)

    # Add indicators to main plot
    fig = add_indicators(fig=fig, row=1, indicators=plot_config['main_plot'], data=data)

    fig = plot_trades(fig, trades)

    # Volume goes to row 2
    volume = go.Bar(
        x=data['date'],
        y=data['volume'],
        name='Volume',
        marker_color='DarkSlateGrey',
        marker_line_color='DarkSlateGrey'
    )
    fig.add_trace(volume, 2, 1)

    # Add indicators to separate row
    for i, name in enumerate(plot_config['subplots']):
        fig = add_indicators(fig=fig, row=3 + i,
                             indicators=plot_config['subplots'][name],
                             data=data)

    return fig


def generate_profit_graph(pairs: str, data: Dict[str, pd.DataFrame],
                          trades: pd.DataFrame, timeframe: str) -> go.Figure:
    # Combine close-values for all pairs, rename columns to "pair"
    df_comb = combine_dataframes_with_mean(data, "close")

    # Trim trades to available OHLCV data
    trades = extract_trades_of_period(df_comb, trades, date_index=True)

    # Add combined cumulative profit
    df_comb = create_cum_profit(df_comb, trades, 'cum_profit', timeframe)

    # Plot the pairs average close prices, and total profit growth
    avgclose = go.Scatter(
        x=df_comb.index,
        y=df_comb['mean'],
        name='Avg close price',
    )

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_width=[1, 1, 1],
                        vertical_spacing=0.05,
                        subplot_titles=["AVG Close Price", "Combined Profit", "Profit per pair"])
    fig['layout'].update(title="Freqtrade Profit plot")
    fig['layout']['yaxis1'].update(title='Price')
    fig['layout']['yaxis2'].update(title='Profit')
    fig['layout']['yaxis3'].update(title='Profit')
    fig['layout']['xaxis']['rangeslider'].update(visible=False)

    fig.add_trace(avgclose, 1, 1)
    fig = add_profit(fig, 2, df_comb, 'cum_profit', 'Profit')
    fig = add_max_drawdown(fig, 2, trades, df_comb, timeframe)

    for pair in pairs:
        profit_col = f'cum_profit_{pair}'
        try:
            df_comb = create_cum_profit(df_comb, trades[trades['pair'] == pair], profit_col,
                                        timeframe)
            fig = add_profit(fig, 3, df_comb, profit_col, f"Profit {pair}")
        except ValueError:
            pass

    return fig


def generate_plot_filename(pair: str, timeframe: str) -> str:
    """
    Generate filenames per pair/timeframe to be used for storing plots
    """
    pair_s = pair_to_filename(pair)
    file_name = 'freqtrade-plot-' + pair_s + '-' + timeframe + '.html'

    logger.info('Generate plot file for %s', pair)

    return file_name


def store_plot_file(fig, filename: str, directory: Path, auto_open: bool = False) -> None:
    """
    Generate a plot html file from pre populated fig plotly object
    :param fig: Plotly Figure to plot
    :param filename: Name to store the file as
    :param directory: Directory to store the file in
    :param auto_open: Automatically open files saved
    :return: None
    """
    directory.mkdir(parents=True, exist_ok=True)

    _filename = directory.joinpath(filename)
    plot(fig, filename=str(_filename),
         auto_open=auto_open)
    logger.info(f"Stored plot as {_filename}")


def load_and_plot_trades(config: Dict[str, Any]):
    """
    From configuration provided
    - Initializes plot-script
    - Get candle (OHLCV) data
    - Generate Dafaframes populated with indicators and signals based on configured strategy
    - Load trades excecuted during the selected period
    - Generate Plotly plot objects
    - Generate plot files
    :return: None
    """
    strategy = StrategyResolver.load_strategy(config)

    exchange = ExchangeResolver.load_exchange(config['exchange']['name'], config)
    IStrategy.dp = DataProvider(config, exchange)
    plot_elements = init_plotscript(config, strategy.startup_candle_count)
    timerange = plot_elements['timerange']
    trades = plot_elements['trades']
    pair_counter = 0
    for pair, data in plot_elements["ohlcv"].items():
        pair_counter += 1
        logger.info("analyse pair %s", pair)

        df_analyzed = strategy.analyze_ticker(data, {'pair': pair})
        df_analyzed = trim_dataframe(df_analyzed, timerange)
        trades_pair = trades.loc[trades['pair'] == pair]
        trades_pair = extract_trades_of_period(df_analyzed, trades_pair)

        fig = generate_candlestick_graph(
            pair=pair,
            data=df_analyzed,
            trades=trades_pair,
            indicators1=config.get('indicators1', []),
            indicators2=config.get('indicators2', []),
            plot_config=strategy.plot_config if hasattr(strategy, 'plot_config') else {}
        )

        store_plot_file(fig, filename=generate_plot_filename(pair, config['timeframe']),
                        directory=config['user_data_dir'] / 'plot')

    logger.info('End of plotting process. %s plots generated', pair_counter)


def plot_profit(config: Dict[str, Any]) -> None:
    """
    Plots the total profit for all pairs.
    Note, the profit calculation isn't realistic.
    But should be somewhat proportional, and therefor useful
    in helping out to find a good algorithm.
    """
    plot_elements = init_plotscript(config)
    trades = plot_elements['trades']
    # Filter trades to relevant pairs
    # Remove open pairs - we don't know the profit yet so can't calculate profit for these.
    # Also, If only one open pair is left, then the profit-generation would fail.
    trades = trades[(trades['pair'].isin(plot_elements['pairs']))
                    & (~trades['close_date'].isnull())
                    ]
    if len(trades) == 0:
        raise OperationalException("No trades found, cannot generate Profit-plot without "
                                   "trades from either Backtest result or database.")

    # Create an average close price of all the pairs that were involved.
    # this could be useful to gauge the overall market trend
    fig = generate_profit_graph(plot_elements['pairs'], plot_elements['ohlcv'],
                                trades, config.get('timeframe', '5m'))
    store_plot_file(fig, filename='freqtrade-profit-plot.html',
                    directory=config['user_data_dir'] / 'plot', auto_open=True)
