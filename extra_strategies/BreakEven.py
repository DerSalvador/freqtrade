# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from pandas import DataFrame
# --------------------------------

class BreakEven(IStrategy):
    INTERFACE_VERSION = 3
    '\n    author@: lenik\n\n    Sometimes I want to close the bot ASAP, but not have the positions floating around.\n\n    I can "/stopentry" and wait for the positions to get closed by the bot rules, which is\n    waiting for some profit, etc -- this usually takes too long...\n\n    What I would prefer is to close everything that is over 0% profit to avoid the losses.\n\n    Here\'s a simple strategy with empty entry/exit signals and "minimal_roi = { 0 : 0 }" that\n    exits everything already at profit and wait until the positions at loss will come to break\n    even point (or the small profit you provide in ROI table).\n\n    You may restart the bot with the new strategy as a command-line parameter.\n\n    Another way would be to specify the original strategy in the config file, then change to\n    this one and simply "/reload_config" from the Telegram bot.\n\n    '
    INTERFACE_VERSION: int = 3
    # This attribute will be overridden if the config file contains "minimal_roi"
    # at least 1% at first
    # after 10min, everything goes
    minimal_roi = {'0': 0.01, '10': 0}
    # This is more radical version that exits everything above the profit level
    #    minimal_roi = {
    #        "0": 0
    #    }
    # And this is basically "/forceexit all", that exits no matter what profit
    #    minimal_roi = {
    #        "0": -1
    #    }
    # Optimal stoploss designed for the strategy
    stoploss = -0.05
    # Optimal timeframe for the strategy
    timeframe = '5m'
    # don't generate any entry or exit signals, everything is handled by ROI and stop_loss

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(), 'enter_long'] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(), 'exit_long'] = 0
        return dataframe