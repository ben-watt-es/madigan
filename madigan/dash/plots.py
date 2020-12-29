from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
import h5py

from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5.QtGui import QTableWidget, QTableWidgetItem, QGridLayout
from PyQt5.QtGui import QListWidget, QLabel
import pyqtgraph as pg


###############################################################################
############# Factory Methods #################################################
###############################################################################
def make_train_plots(agent_type, title=None, **kw):
    if agent_type in ("DQN", "DQNCURL", "DQNReverser", "DQNController",
                      "DQNRecurrent",
                      "IQN", "IQNCURL", "IQNReverser", "IQNController",
                      "DQNAE"):
        return TrainPlotsDQN(title=title, **kw)
    if agent_type in ("DDPG", "DDPGDiscretized"):
        return TrainDDPG(title=title, **kw)
    if agent_type in ("SACDiscrete", "SACD"):
        return TrainPlotsSACD(title=title, **kw)
    raise NotImplementedError(
        f"Train plot widget for agent_type: {agent_type}"+\
        " has not been implemented")


def make_test_episode_plots(agent_type, title=None, **kw):
    if agent_type in ("DQN", "DQNCURL", "DQNReverser", "DQNController",
                      "DQNRecurrent",
                      "IQN", "IQNCURL", "IQNReverser", "IQNController",
                      "DQNAE"):
        return TestEpisodePlotsDQN(title=title, **kw)
    if agent_type in ("DDPG", "DDPGDiscretized"):
        return TestEpisodeDDPG(title=title, **kw)
    if agent_type in ("SACDiscrete", "SACD"):
        return TestEpisodePlotsSACD(title=title, **kw)
    raise NotImplementedError(
        f"Test episode plot widget for agent_type: {agent_type}"+\
        " has not been implemented")


def make_test_history_plots(agent_type, title=None, **kw):
    if agent_type in ("DQN", "DQNCURL", "DQNReverser", "DQNController",
                      "DQNRecurrent",
                      "IQN", "IQNCURL", "IQNReverser", "IQNController",
                      "DQNAE"):
        return TestHistoryPlotsDQN(title=title, **kw)
    if agent_type in ("DDPG", "DDPGDiscretized"):
        return TestHistoryDDPG(title=title, **kw)
    if agent_type in ("SACDiscrete", "SACD"):
        return TestHistoryPlotsSACD(title=title, **kw)
    raise NotImplementedError(
        f"Test History plot widget for agent_type: {agent_type}"+\
        " has not been implemented")


############# Training Plots  ######################################################
####################################################################################


class TrainPlots(QGridLayout):
    """ Base class for train plots """
    def __init__(self, title=None):
        super().__init__()
        self.datapath = None
        self.data = None
        self.graphs = pg.GraphicsLayoutWidget(show=True, title=title)
        self.addWidget(self.graphs)
        self.colours = {
            'reward': (255, 228, 181),
            'reward_mean': (255, 0, 0),
            'loss': (242, 242, 242)
        }
        self.plots = {}
        self.lines = {}
        self.plots['loss'] = self.graphs.addPlot(title='Loss',
                                                 bottom='step',
                                                 left='Loss')
        self.plots['loss'].showGrid(1, 1)
        self.plots['loss'].addLegend()
        self.plots['running_reward'] = self.graphs.addPlot(
            title='Episode Rewards', bottom='step', left='reward')
        self.plots['running_reward'].showGrid(1, 1)
        self.plots['running_reward'].addLegend()

        self.lines['loss'] = self.plots['loss'].plot(y=[])
        self.lines['running_reward'] = self.plots['running_reward'].plot(
            y=[], name='rewards')
        self.reward_mean_window = 50000
        self.lines['running_reward_mean'] = self.plots['running_reward'].plot(
            y=[], name=f'rewards_{self.reward_mean_window}_window_average')
        self.plots['running_reward'].setLabels()
        self.link_x_axes()

    def link_x_axes(self):
        for name, plot in self.plots.items():
            if name != "loss":
                plot.setXLink(self.plots['loss'])

    def clear_data(self):
        for line in self.lines.values():
            line.setData(y=[])

    def set_data(self, data):
        self.data = data
        if len(data) == 0:
            print("train data is empty")
            data = {k: [] for k in self.lines.keys()}
        self.lines['loss'].setData(y=data['loss'], pen=self.colours['loss'])
        rewards = data['running_reward']
        rewards_mean = pd.Series(data['running_reward']).ewm(20000).mean()
        rewards_mean = np.nan_to_num(rewards_mean.values)
        self.lines['running_reward'].setData(y=rewards,
                                             pen=self.colours['reward'])
        self.lines['running_reward_mean'].setData(
            y=rewards_mean,
            pen=pg.mkPen({
                'color': self.colours['reward_mean'],
                'width': 2
            }))

    def set_datapath(self, path):
        self.datapath = Path(path)
        self.load_from_hdf()

    def load_from_hdf(self, path=None):
        path = path or self.datapath / 'train.hdf5'
        if path is not None:
            data = pd.read_hdf(path, key='train')
            self.set_data(data)


class TrainPlotsDQN(TrainPlots):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.colours.update({'Gt': (0, 255, 255), 'Qt': (255, 86, 0)})
        self.plots['values'] = self.graphs.addPlot(title='Values',
                                                   bottom='step',
                                                   left='Value')
        self.plots['values'].showGrid(1, 1)
        self.plots['values'].addLegend()
        self.lines['Gt'] = self.plots['values'].plot(y=[], name='Gt')
        self.lines['Qt'] = self.plots['values'].plot(y=[], name='Qt')
        self.plots['values'].setLabels()

        self.link_x_axes()

    def set_data(self, data):
        super().set_data(data)
        if data is None or len(data) == 0:
            return
        self.lines['Gt'].setData(y=data['Gt'], pen=self.colours['Gt'])
        self.lines['Qt'].setData(y=data['Qt'], pen=self.colours['Qt'])


class TrainDDPG(TrainPlots):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.colours.update({'Gt': (0, 255, 255), 'Qt': (255, 86, 0)})
        self.colours.update({
            'loss_critic': (255, 0, 0),
            'loss_actor': (0, 255, 0)
        })
        self.plots['values'] = self.graphs.addPlot(title='Values',
                                                   bottom='step',
                                                   left='Value')
        self.plots['values'].showGrid(1, 1)
        self.plots['values'].addLegend()
        self.lines['Gt'] = self.plots['values'].plot(y=[], name='Gt')
        self.lines['Qt'] = self.plots['values'].plot(y=[], name='Qt')
        self.plots['values'].setLabels()

        del self.lines['loss']
        self.lines['loss_critic'] = self.plots['loss'].plot(y=[],
                                                            name='loss_critic')
        self.lines['loss_actor'] = self.plots['loss'].plot(y=[],
                                                           name='loss_actor')
        self.plots['loss'].setLabels()

        self.link_x_axes()

    def set_data(self, data):
        self.data = data
        if len(data) == 0:
            print("train data is empty")
            data = {k: [] for k in self.lines.keys()}

        self.lines['loss_critic'].setData(y=data['loss_critic'],
                                          pen=self.colours['loss_critic'])
        self.lines['loss_actor'].setData(y=data['loss_actor'],
                                         pen=self.colours['loss_actor'])
        rewards = data['running_reward']
        rewards_mean = pd.Series(data['running_reward']).ewm(20000).mean()
        rewards_mean = np.nan_to_num(rewards_mean.values)
        self.lines['running_reward'].setData(y=rewards,
                                             pen=self.colours['reward'])
        self.lines['running_reward_mean'].setData(
            y=rewards_mean,
            pen=pg.mkPen({
                'color': self.colours['reward_mean'],
                'width': 2
            }))
        self.lines['Gt'].setData(y=data['Gt'], pen=self.colours['Gt'])
        self.lines['Qt'].setData(y=data['Qt'], pen=self.colours['Qt'])


class TrainPlotsSACD(TrainPlots):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.colours.update({
            'Gt': (0, 255, 255),
            'Qt1': (255, 86, 0),
            'Qt2': (86, 255, 0),
            'entropy': (255, 0, 0),
            'entropy_temp': (0, 255, 0)
        })
        self.colours.update({
            'loss_critic1': (255, 0, 0),
            'loss_critic2': (0, 0, 255),
            'loss_actor': (0, 255, 0),
            'loss_entropy': (255, 255, 0)
        })
        self.plots['values'] = self.graphs.addPlot(title='Values',
                                                   bottom='step',
                                                   left='Value')
        self.plots['entropy'] = self.graphs.addPlot(title='Entropy',
                                                    bottom='step')
        self.lines['entropy'] = self.plots['entropy'].plot(y=[],
                                                           name='entropy')
        self.lines['entropy_temp'] = self.plots['entropy'].plot(
            y=[], name='entropy_temp')
        self.plots['entropy'].setLabels()

        self.plots['values'].showGrid(1, 1)
        self.plots['values'].addLegend()
        self.lines['Gt'] = self.plots['values'].plot(y=[], name='Gt')
        self.lines['Qt1'] = self.plots['values'].plot(y=[], name='Qt1')
        self.lines['Qt2'] = self.plots['values'].plot(y=[], name='Qt2')
        self.plots['values'].setLabels()

        del self.lines['loss']
        self.lines['loss_critic1'] = self.plots['loss'].plot(
            y=[], name='loss_critic1')
        self.lines['loss_critic2'] = self.plots['loss'].plot(
            y=[], name='loss_critic2')
        self.lines['loss_actor'] = self.plots['loss'].plot(y=[],
                                                           name='loss_actor')
        self.lines['loss_entropy'] = self.plots['loss'].plot(
            y=[], name='loss_entropy')
        self.plots['loss'].setLabels()

        self.link_x_axes()

    def set_data(self, data):
        print("AC ")
        self.data = data
        if len(data) == 0:
            print("train data is empty")
            data = {k: [] for k in self.lines.keys()}

        self.lines['loss_critic1'].setData(y=data['loss_critic1'],
                                           pen=self.colours['loss_critic1'])
        self.lines['loss_critic2'].setData(y=data['loss_critic2'],
                                           pen=self.colours['loss_critic2'])
        self.lines['loss_actor'].setData(y=data['loss_actor'],
                                         pen=self.colours['loss_actor'])
        self.lines['loss_entropy'].setData(y=data['loss_entropy'],
                                           pen=self.colours['loss_entropy'])
        rewards = data['running_reward']
        rewards_mean = pd.Series(data['running_reward']).ewm(20000).mean()
        rewards_mean = np.nan_to_num(rewards_mean.values)
        self.lines['running_reward'].setData(y=rewards,
                                             pen=self.colours['reward'])
        self.lines['running_reward_mean'].setData(
            y=rewards_mean,
            pen=pg.mkPen({
                'color': self.colours['reward_mean'],
                'width': 2
            }))
        self.lines['Gt'].setData(y=data['Gt'], pen=self.colours['Gt'])
        self.lines['Qt1'].setData(y=data['Qt1'], pen=self.colours['Qt1'])
        self.lines['Qt2'].setData(y=data['Qt2'], pen=self.colours['Qt2'])

        self.lines['entropy'].setData(y=data['entropy'],
                                      pen=self.colours['entropy'])
        self.lines['entropy_temp'].setData(y=data['entropy_temp'],
                                           pen=self.colours['entropy_temp'])


####################################################################################
############# Test Episode Plots  ##################################################
####################################################################################


class TestEpisodePlots(QGridLayout):
    def __init__(self, title=None, **kw):
        super().__init__()
        self.graphs = pg.GraphicsLayoutWidget(show=True, title=title)
        self.datapath = None
        self.episodes = []
        self.data = None
        self.assets = None
        self.colours = {
            'equity': (218, 112, 214),
            'reward': (242, 242, 242),
            'cash': (0, 255, 255),
            'margin': (255, 86, 0)
        }
        self.heatmap_colors = [(0, 0, 85), (85, 0, 0)]
        cmap = pg.ColorMap(pos=np.linspace(-1., 1., 2),
                           color=self.heatmap_colors)
        self.plots = {}
        self.lines = {}
        self.plots['prices'] = self.graphs.addPlot(title='Prices',
                                                   bottom='time',
                                                   left='prices',
                                                   colspan=2)
        self.plots['equity'] = self.graphs.addPlot(
            title='Equity',
            bottom='time',
            left='Denomination currency',
            row=0,
            col=2,
            colspan=2)
        self.plots['reward'] = self.graphs.addPlot(title='Rewards',
                                                   bottom='time',
                                                   left='reward',
                                                   row=0,
                                                   col=4,
                                                   colspan=2)
        self.lines['ledgerNormed'] = pg.ImageItem(np.empty(shape=(1, 1, 1)))
        self.lines['ledgerNormed'].setLookupTable(cmap.getLookupTable())
        self.plots['ledgerNormed'] = self.graphs.addPlot(title="Ledger",
                                                         colspan=2)
        self.plots['ledgerNormed'].addItem(self.lines['ledgerNormed'])
        self.plots['ledgerNormed'].showAxis('left', False)
        hist = pg.HistogramLUTItem()
        hist.setImageItem(self.lines['ledgerNormed'])
        self.graphs.addItem(hist, row=0, col=8, colspan=1)
        self.plots['equity'].setLabels()
        self.lines['equity'] = self.plots['equity'].plot(y=[])
        self.lines['reward'] = self.plots['reward'].plot(y=[])
        self.lines['prices'] = {}
        self.current_pos_line = pg.InfiniteLine(movable=True)
        self.plots['equity'].addItem(self.current_pos_line)
        self.plots['cash'] = self.graphs.addPlot(title="cash",
                                                 row=1,
                                                 col=0,
                                                 colspan=2)
        self.plots['availableMargin'] = self.graphs.addPlot(
            title="available margin", row=1, col=2, colspan=2)
        self.plots['transactions'] = self.graphs.addPlot(title="transactions",
                                                         row=1,
                                                         col=4,
                                                         colspan=2)
        self.lines['cash'] = self.plots['cash'].plot(y=[])
        self.lines['availableMargin'] = self.plots['availableMargin'].plot(
            y=[])
        self.lines['transactions'] = {}

        self.plots['prices'].showGrid(1, 1)
        self.plots['equity'].showGrid(1, 1)
        self.plots['reward'].showGrid(1, 1)
        self.plots['prices'].showGrid(1, 1)
        self.plots['cash'].showGrid(1, 1)
        self.plots['availableMargin'].showGrid(1, 1)
        self.plots['transactions'].showGrid(1, 1)
        limits = np.finfo('float64')
        # self.plots['transactions'].setYRange(limits.min, limits.max)
        self.plots['ledgerNormed'].showGrid(1, 1)

        self.episode_table = QListWidget()
        self.episode_table.setWindowTitle('Episode Name')
        self.episode_table.setStyleSheet("background-color:rgb(99, 102, 49) ")
        self.accounting_table = QTableWidget(5, 1)
        self.accounting_table.setVerticalHeaderLabels([
            'Equity', 'Balance', 'Cash', 'Available Margin', 'Used Margin',
            'Net PnL'
        ])
        self.accounting_table.setHorizontalHeaderLabels(['Accounting'])
        # self.accounting_table.horizontalHeaderItem(0).setTextAlignment(
        #     QtCore.Qt.AlignJustify)  # doesn't work
        self.accounting_table.setStyleSheet(
            "background-color:rgb(44, 107, 42) ")
        self.positions_table = QTableWidget(0, 2)
        self.positions_table.setHorizontalHeaderLabels(
            ['Ledger', 'Ledger Normed'])
        self.positions_table.setStyleSheet("background-color:rgb(23, 46, 67) ")

        self.asset_picker = QListWidget()
        self.asset_picker.setWindowTitle('Episode Name')
        self.asset_picker.setStyleSheet("background-color:rgb(99, 102, 49) ")
        self.asset_picker.setSelectionMode(
            QListWidget.MultiSelection)
        self.asset_picker.itemSelectionChanged.connect(
            self._set_data_with_variable_assets)
        self.asset_picker.setStyleSheet("background-color:rgb(23, 46, 67) ")

        # self.episode_table.horizontalHeader().setStretchLastSection(True)
        self.accounting_table.horizontalHeader().setStretchLastSection(True)
        self.positions_table.horizontalHeader().setStretchLastSection(True)

        self.episode_table_label = QLabel("Test Episodes")
        self.asset_picker_label = QLabel("Assets")

        self.addWidget(self.graphs, 0, 0, -1, 8)
        self.addWidget(self.episode_table_label, 0, 10, 1, 1)
        self.addWidget(self.episode_table, 1, 10, 1, 1)
        self.addWidget(self.accounting_table, 2, 10, 1, 1)
        self.addWidget(self.positions_table, 3, 10, 1, 1)
        self.addWidget(self.asset_picker_label, 4, 10, 1, 1)
        self.addWidget(self.asset_picker, 5, 10, 1, 1)
        for i in range(8):
            self.setColumnStretch(i, 4)

        self.current_pos_line.sigPositionChanged.connect(
            self.update_accounting_table)
        self.current_pos_line.sigPositionChanged.connect(
            self.update_positions_table)
        # self.episode_table.cellDoubleClicked.connect(
        #     lambda: self.load_from_hdf(self.datapath/self.episode_table.currentItem().text())
        # )
        self.episode_table.currentRowChanged.connect(
            lambda: self.load_from_hdf(self.datapath / self.episode_table.
                                       currentItem().text()))

        self.link_x_axes()
        # self.unlink_x_axes()


    def log_adjust(self):
        for metric, plot in self.plots.items():
            if metric in self.data.keys():
                max_ele = np.nanmax(self.data[metric])
                min_ele = np.nanmin(self.data[metric])
                if max_ele - min_ele > 1e10:
                    plot.setLogMode(False, True)
                else:
                    plot.setLogMode(False, False)

    def link_x_axes(self):
        for name, plot in self.plots.items():
            if name != "equity":
                plot.setXLink(self.plots['equity'])

    def unlink_x_axes(self):
        for plot in self.plots.values():
            plot.setXLink(plot)

    def set_datapath(self, path):
        self.datapath = Path(path)
        self.load_episode_list()
        self.load_from_hdf()


    def clear_plots(self):
        """ Clear data for all plots """
        for _, line in self.lines.items():
            if isinstance(line, dict):
                for _, sub_line in line.items():
                    sub_line.clear()
            else:
                line.clear()

    def process_data(self, data):
        """ Converts data to ndarrays """
        self.data = dict(data.items())
        if isinstance(data['prices'], (pd.Series, pd.DataFrame)):
            self.data['prices'] = np.array(data['prices'].tolist())
            self.data['transactions'] =\
                np.array(data['transaction'].tolist()) # assuming this is also pd
            self.data['ledgerNormed'] = np.array(data['ledgerNormed'].tolist())
        else:
            self.data['prices'] = np.array(data['prices'])
            self.data['transactions'] = np.array(data['transaction'])
            self.data['ledgerNormed'] = np.array(data['ledgerNormed'])
            assert len(self.data['prices'].shape) == \
                len(self.data['transactions'].shape) ==\
                len(self.data['ledgerNormed'].shape) == 2,\
                "number of assets dims in prices, transactions and ledger" + \
                "must match"
        # self.data = {k: np.nan_to_num(v, 0.) for k, v in self.data.items()}

    def _set_data_with_variable_assets(self):
        """ For plots with multiple lines corresponding to assets """
        for i, asset in enumerate(self.assets):
            if i not in self.lines['prices']:  # initialize plots
                self.lines['prices'][i] = self.plots['prices'].plot(
                    y=[], pen=(i, self.data['prices'].shape[1]))
                self.lines['transactions'][i] =\
                    self.plots['transactions'].plot(
                        y=[], pen=(i, self.data['transactions'].shape[1]))
            idxs = [idx.row() for idx in self.asset_picker.selectedIndexes()]
            if i in idxs:
                self.lines['prices'][i].setData(y=self.data['prices'][:, i])
                self.lines['transactions'][i].setData(
                    y=self.data['transactions'][:, i])
            else:
                self.lines['prices'][i].clear()
                self.lines['transactions'][i].clear()

    def _set_assets(self, assets):
        """
        Call after self.process_data(data) (i.e in self._set_data) so that
        n_assets can be ectracted and compared from self.data['prices']
        """
        n_assets = self.data['prices'].shape[1]
        if assets is None:
            assets = [str(asset) for asset in range(n_assets)]
        else:
            if isinstance(assets, np.ndarray):
                assets = assets.tolist()
            if len(assets) != n_assets:
                raise ValueError(
                    "assets provided by dataset attribute is not"
                    "the same length as assets indicated by  data")
        if self.assets != assets:
            self.assets = assets
            # self.asset_picker.addItems(self.assets)
            for i, asset in enumerate(self.assets):
                self.asset_picker.addItem(asset)
                self.asset_picker.itemAt(i, 0).setSelected(1)

    def _set_data(self, data, assets=None):
        if len(data) == 0:
            print('test episode data is empty')
            data = {k: [] for k in self.lines.keys()}

        self._set_assets(assets)
        self._set_data_with_variable_assets()

        self.lines['equity'].setData(y=data['equity'],
                                     pen=self.colours['equity'])
        self.lines['reward'].setData(y=data['reward'],
                                     pen=self.colours['reward'])
        self.lines['cash'].setData(y=data['cash'], pen=self.colours['cash'])
        self.lines['availableMargin'].setData(y=data['availableMargin'],
                                              pen=self.colours['cash'])
        self.lines['ledgerNormed'].setImage(self.data['ledgerNormed'],
                                            axes={'x': 0, 'y': 1})
        self.current_pos_line.setValue(len(data['equity']) - 1)
        self.current_pos_line.setBounds((0, len(data['equity']) - 1))
        self.update_accounting_table()
        self.positions_table.setRowCount(self.data['ledgerNormed'].shape[1])
        self.update_positions_table()

    def set_data(self, data, assets=None):
        self.process_data(data)
        self.clear_plots()
        self._set_data(data, assets)
        # self.pick_assets()
        self.log_adjust()

    def load_episode_list(self, path=None):
        path = path or self.datapath
        if path is not None:
            episodes = filter(lambda x: "episode" in str(x.name),
                              path.iterdir())
            self.episodes = sorted(
                episodes,
                key=lambda x: int(str(x.name).split('_')[3]),
                reverse=True)
            # self.episode_table.setRowCount(len(self.episodes))
            self.episode_table.clear()
            self.episode_table.addItems([ep.name for ep in self.episodes])
            # for i, episode in enumerate(self.episodes):
            #     val = QTableWidgetItem(str(episode.name))
            #     self.episode_table.setItem(i, 0, val)

    def load_from_hdf(self, path=None):
        if path is None:
            if len(self.episodes) > 0:
                latest_episode = self.episodes[-1]
            else:
                return
        else:
            latest_episode = path
        data = pd.read_hdf(latest_episode, key='full_run')
        assets = None
        with h5py.File(latest_episode, 'r') as f:
            if 'asset_names' in f.attrs.keys():
                assets = f.attrs['asset_names']
        self.set_data(data, assets=assets)

    def update_accounting_table(self):
        current_timepoint = int(self.current_pos_line.value())
        try:
            for i, metric in enumerate([
                    'equity', 'balance', 'cash', 'availableMargin',
                    'usedMargin', 'pnl'
            ]):
                metric = QTableWidgetItem(
                    str(self.data[metric][current_timepoint]))
                self.accounting_table.setItem(i, 0, metric)
        except IndexError:
            print("IndexError")

    def update_positions_table(self):
        current_timepoint = int(self.current_pos_line.value())
        try:
            n_assets = len(self.data['ledger'][0])
            for asset in range(n_assets):
                for i, metric in enumerate(['ledger', 'ledgerNormed']):
                    val = self.data[metric][current_timepoint][asset]
                    val = QTableWidgetItem(f"{val: 0.3f}")
                    self.positions_table.setItem(asset, i, val)
        except IndexError:
            import traceback
            traceback.print_exc()


class TestEpisodePlotsDQN(TestEpisodePlots):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.colours.update({'qvals': (255, 86, 0)})
        self.lines['qvals'] = pg.ImageItem(np.empty(shape=(1, 1, 1)))
        self.plots['qvals'] = self.graphs.addPlot(title="qvals", row=1, col=6)
        self.plots['qvals'].addItem(self.lines['qvals'])
        self.plots['qvals'].showGrid(1, 1)
        hist = pg.HistogramLUTItem()
        hist.setImageItem(self.lines['qvals'])
        self.graphs.addItem(hist, row=1, col=8, colspan=1)
        # self.lines['qvals'].autoLevels()

        self.link_x_axes()

    def process_data(self, data):
        super().process_data(data)
        if isinstance(data['qvals'], (pd.Series, pd.DataFrame)):
            self.data['qvals'] = np.array(data['qvals'].tolist())
        else:
            self.data['qvals'] = np.array(data['qvals'])

    def _set_data(self, data, assets=None):
        super()._set_data(data, assets)
        if len(data) == 0:
            return
        qvals = self.data['qvals']
        assert len(qvals.shape) == 3
        qvals = qvals.reshape(qvals.shape[0], -1)
        self.lines['qvals'].setImage(qvals, axes={'x': 0, 'y': 1})
        cmap = pg.ColorMap(pos=np.linspace(np.nanmin(qvals), np.nanmax(qvals),
                                           2),
                           color=self.heatmap_colors)
        self.lines['qvals'].setLookupTable(cmap.getLookupTable())


class TestEpisodeDDPG(TestEpisodePlots):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.colours.update({'qvals': (255, 86, 0)})
        # self.plots['qvals'].addItem(self.lines['qvals'])
        # self.plots['qvals'] = self.graphs.addViewBox(row=1, col=4)
        self.plots['qvals'] = self.graphs.addPlot(row=1, col=6, colspan=2)
        # self.lines['qvals'] = pg.ImageItem(parent=self.graphs,
        #                                    view=self.plots['qvals'].getViewBox())
        # self.plots['qvals'].addWidget(self.lines['qvals'])
        # self.lines['qvals'] = pg.ImageView(self.graphs)
        self.lines['qvals'] = pg.ImageItem(np.empty(shape=(1, 1)),
                                           axes={
                                               'x': 0,
                                               'y': 1
                                           })
        self.plots['qvals'].addItem(self.lines['qvals'])
        self.plots['qvals'].setTitle('qvals')
        self.plots['qvals'].showAxis('left', False)
        hist = pg.HistogramLUTItem()
        hist.setImageItem(self.lines['qvals'])
        self.graphs.addItem(hist, row=1, col=8, colspan=1)
        # self.lines['qvals'].showGrid(1, 1)
        self.lines['qvals'].setImage(np.empty(shape=(1, 1)),
                                     axes={
                                         'x': 0,
                                         'y': 1
                                     })
        # self.plots['qvals'].ledgerNormedshow()
        # self.plots['qvals'].hoverEvent = self.update_qvals_title
        # self.plots['qvals'].addItem(self.lines['qvals'])
        self.plots['action'] = self.graphs.addPlot(
            title="model output - portfolio weights", row=2, col=0, colspan=2)
        self.lines['action'] = pg.ImageItem(np.empty(shape=(1, 1, 1)))
        self.plots['action'].addItem(self.lines['action'], colspan=2)
        self.plots['action'].showGrid(1, 1)
        hist = pg.HistogramLUTItem()
        hist.setImageItem(self.lines['action'])
        self.graphs.addItem(hist, row=2, col=2, colspan=1)
        self.transaction_table = pg.TableWidget()
        self.transaction_table.setVerticalHeaderLabels(['Model Outputs'])
        # self.graphs.addItem(self.actions_table, row=2, col=3, colspan=1)
        self.addWidget(self.transaction_table, 3, 9, 1, 1)
        self.link_x_axes()
        self.current_pos_line.sigPositionChanged.connect(
            self.update_transaction_table)

    def update_transaction_table(self):
        current_timepoint = int(self.current_pos_line.value())
        try:
            actions = self.data['action'][current_timepoint]
            transactions = self.data['transaction'][current_timepoint]
            transactions = np.concatenate([[0], transactions], axis=0)
            data = np.stack([actions, transactions], axis=1)
            # data = np.array([actions, transactions],
            #                 dtype=[('model_output', float),
            #                        ('transactions', float)])
            # import ipdb; ipdb.set_trace()
            self.transaction_table.setData(data)
            self.transaction_table.setHorizontalHeaderLabels(
                ['Model Outputs', 'Transactions'])
            self.transaction_table.resizeColumnsToContents()
        except IndexError:
            import traceback
            traceback.print_exc()

    # def update_qvals_title(self, event):
    #     if event.isExit():
    #         # self.plots['ledgerNormed'].setTitle("")
    #         return
    #     pos = event.pos()
    #     j, i = pos.y(), pos.x()
    #     i = int(np.clip(i, 0, self.data['qvals'].shape[0]-1))
    #     j = int(np.clip(j, 0, self.data['qvals'].shape[1]-1))
    #     val = self.data['qvals'][i, j]
    #     ppos = self.lines['qvals'].mapToParent(pos)
    #     x, y = ppos.x(), ppos.y()
    #     self.plots['qvals'].setTitle(f"qval ({i}, {j}) ({x}, {y}): {val}")

    def make_matplotlib_image(self, data, metric=''):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 1)
        if isinstance(data[metric], (pd.Series, pd.DataFrame)):
            data_2d = np.stack(data[metric].tolist()).T
        else:
            data_2d = np.stack(data[metric]).T
        assetIdx = 0
        if len(data_2d.shape) == 3:
            print("plotting only first asset - need to implement multi-asset")
            data_2d = data_2d[:, assetIdx, :]
        im = ax.imshow(data_2d)  #vmin=0., vmax=1.) #, cmap='gray'
        ax.set_aspect(data_2d.shape[1] / data_2d.shape[0])
        ax.set_title(metric)
        ax.set_yticks(range(data_2d.shape[0]))
        ax.set_yticklabels(
            labels=[f'action_{i}' for i in range(data_2d.shape[0])])
        fig.colorbar(im, ax=ax)
        return fig, ax

    def process_data(self, data):
        super().process_data(data)
        if isinstance(data['qvals'], (pd.DataFrame, pd.Series)):
            self.data['qvals'] = np.array(data['qvals'].tolist())
        else:
            self.data['qvals'] = np.array(data['qvals'])
        assert len(self.data['qvals'].shape) == 2
        if isinstance(data['action'], (pd.DataFrame, pd.Series)):
            self.data['action'] = np.array(data['action'].tolist())
        else:
            self.data['action'] = np.array(data['action'])
        assert len(self.data['action'].shape) == 2

    def _set_data(self, data, assets=None):
        super()._set_data(data, assets)
        if len(data) == 0:
            return
        self.lines['qvals'].setImage(self.data['qvals'], axes={'x': 0, 'y': 1})
        # cmap = pg.ColorMap(pos=np.linspace(np.nanmin(qvals), np.nanmax(qvals), 2),
        #                    color=self.heatmap_colors)
        # self.lines['qvals'].setLookupTable(cmap.getLookupTable())
        self.lines['action'].setImage(self.data['action'],
                                      axes={
                                          'x': 0,
                                          'y': 1
                                      })
        # cmap = pg.ColorMap(pos=np.linspace(np.nanmin(self.data['action']),
        #                                    np.nanmax(self.data['action']), 2),
        #                    color=self.heatmap_colors)
        # self.lines['action'].setLookupTable(cmap.getLookupTable())


class TestEpisodePlotsSACD(TestEpisodePlots):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.colours.update({'qvals1': (255, 86, 0), 'qvals2': (86, 255, 0)})
        self.plots['qvals'] = self.graphs.addPlot(row=1, col=6, colspan=2)
        self.lines['qvals1'] = pg.ImageItem(np.empty(shape=(1, 1)),
                                            axes={
                                                'x': 0,
                                                'y': 1
                                            })
        self.lines['qvals2'] = pg.ImageItem(np.empty(shape=(1, 1)),
                                            axes={
                                                'x': 0,
                                                'y': 1
                                            })
        self.plots['qvals'].addItem(self.lines['qvals1'])
        self.plots['qvals'].addItem(self.lines['qvals2'])
        self.plots['qvals'].setTitle('qvals')
        self.plots['qvals'].showAxis('left', False)
        hist1 = pg.HistogramLUTItem()
        hist1.setImageItem(self.lines['qvals1'])
        self.graphs.addItem(hist1, row=1, col=8, colspan=1)
        hist2 = pg.HistogramLUTItem()
        hist2.setImageItem(self.lines['qvals2'])
        self.graphs.addItem(hist2, row=1, col=9, colspan=1)
        # self.lines['qvals'].showGrid(1, 1)
        self.lines['qvals1'].setImage(np.empty(shape=(1, 1)),
                                      axes={
                                          'x': 0,
                                          'y': 1
                                      })
        self.lines['qvals2'].setImage(np.empty(shape=(1, 1)),
                                      axes={
                                          'x': 0,
                                          'y': 1
                                      })
        self.plots['action'] = self.graphs.addPlot(
            title="actor greedy actions", row=2, col=0, colspan=2)
        self.lines['action'] = self.plots['action'].plot(y=[])
        self.plots['action'].showGrid(1, 1)
        self.plots['action_probs'] = self.graphs.addPlot(
            title="actor prob distribution", row=2, col=2, colspan=2)
        self.lines['action_probs'] = pg.ImageItem(np.empty(shape=(1, 1, 1)))
        self.plots['action_probs'].addItem(self.lines['action_probs'],
                                           colspan=2)
        self.plots['action_probs'].showGrid(1, 1)
        hist = pg.HistogramLUTItem()
        hist.setImageItem(self.lines['action_probs'])
        self.graphs.addItem(hist, row=2, col=4, colspan=1)
        self.transaction_table = pg.TableWidget()
        self.transaction_table.setVerticalHeaderLabels(['Model Outputs'])
        # self.graphs.addItem(self.actions_table, row=2, col=3, colspan=1)
        self.addWidget(self.transaction_table, 3, 9, 1, 1)
        self.link_x_axes()
        self.current_pos_line.sigPositionChanged.connect(
            self.update_transaction_table)

    def update_transaction_table(self):
        current_timepoint = int(self.current_pos_line.value())
        try:
            actions = self.data['action'][current_timepoint]
            transactions = self.data['transaction'][current_timepoint]
            transactions = np.concatenate([[0], transactions], axis=0)
            data = np.stack([actions, transactions], axis=1)
            # data = np.array([actions, transactions],
            #                 dtype=[('model_output', float),
            #                        ('transactions', float)])
            self.transaction_table.setData(data)
            self.transaction_table.setHorizontalHeaderLabels(
                ['Model Outputs', 'Transactions'])
            self.transaction_table.resizeColumnsToContents()
        except IndexError:
            import traceback
            traceback.print_exc()

    def process_data(self, data):
        super().process_data(data)
        for qval_key in ('qvals1', 'qvals2'):
            if isinstance(data[qval_key], (pd.DataFrame, pd.Series)):
                self.data[qval_key] = np.array(data[qval_key].tolist())
            else:
                self.data[qval_key] = np.array(data[qval_key])
        assert len(self.data['qvals1'].shape) == 2
        if isinstance(data['action_probs'], (pd.DataFrame, pd.Series)):
            self.data['action_probs'] = np.array(data['action_probs'].tolist())
        else:
            self.data['action_probs'] = np.array(data['action_probs'])
        assert len(self.data['action_probs'].shape) == 3
        # self.data['action'] = self.data['action'].cpu().numpy()

    def _set_data(self, data, assets=None):
        super()._set_data(data, assets)
        if len(data) == 0:
            return
        self.lines['qvals1'].setImage(self.data['qvals1'],
                                      axes={
                                          'x': 0,
                                          'y': 1
                                      })
        self.lines['qvals2'].setImage(self.data['qvals2'],
                                      axes={
                                          'x': 0,
                                          'y': 1
                                      })
        # cmap = pg.ColorMap(pos=np.linspace(np.nanmin(qvals), np.nanmax(qvals), 2),
        #                    color=self.heatmap_colors)
        # self.lines['qvals'].setLookupTable(cmap.getLookupTable())
        self.lines['action'].setData(self.data['action'])
        self.lines['action_probs'].setImage(self.data['action_probs'],
                                            axes={
                                                'x': 0,
                                                'y': 1
                                            })
        # cmap = pg.ColorMap(pos=np.linspace(np.nanmin(self.data['action']),
        #                                    np.nanmax(self.data['action']), 2),
        #                    color=self.heatmap_colors)
        # self.lines['action'].setLookupTable(cmap.getLookupTable())


###############################################################################
############# Test History Plots  #############################################
###############################################################################


class TestHistoryPlots(QGridLayout):
    def __init__(self, title=None):
        super().__init__()
        self.graphs = pg.GraphicsLayoutWidget(show=True, title=title)
        self.addWidget(self.graphs)
        self.colours = {
            'mean_equity': (0, 255, 0),
            'final_equity': (255, 0, 0),
            'mean_reward': (242, 242, 242),
            'cash': (0, 255, 255),
            'margin': (255, 86, 0)
        }
        self.data = None
        self.plots = {}
        self.plots['equity'] = self.graphs.addPlot(
            title='Equity Over Episodes',
            bottom='training_steps',
            left='Denomination currency')
        self.plots['reward'] = self.graphs.addPlot(
            title='Mean Returns over Episodes',
            bottom='training_steps',
            left='returns (proportion)')
        self.plots['margin'] = self.graphs.addPlot(
            title='Mean Cash over Episodes',
            bottom='training steps',
            left='returns (proportion)')
        self.plots['equity'].addLegend()
        self.plots['equity'].showGrid(1, 1)
        self.plots['reward'].showGrid(1, 1)
        self.plots['margin'].showGrid(1, 1)
        self.plots['margin'].setLabels()
        self.lines = {}
        self.lines['mean_equity'] = self.plots['equity'].plot(
            y=[], name='mean_equity')
        self.lines['final_equity'] = self.plots['equity'].plot(
            y=[], name='final_equity')
        self.lines['mean_reward'] = self.plots['reward'].plot(y=[])
        self.plots['equity'].setLabels()
        # self.lines['mean_available_margin']= self.plots['margin'].plot(y=[])

    def clear_data(self):
        for _, line in self.lines.items():
            line.setData(y=[])

    def set_data(self, data):
        if data is None or len(data) == 0:
            print("test data is empty")
            data = {k: [] for k in self.lines.keys()}
        self.lines['mean_equity'].setData(y=data['mean_equity'],
                                          pen=self.colours['mean_equity'])
        self.lines['final_equity'].setData(y=data['final_equity'],
                                           pen=self.colours['final_equity'])
        self.lines['mean_reward'].setData(y=data['mean_reward'],
                                          pen=self.colours['mean_reward'])
        # self.lines['mean_transaction_cost'].setData(
        # y=data['mean_transaction_cost'],
        # pen=self.colours['mean_transaction_cost'])
        # self.lines['margin'].setData(y=data['cash'],
        # pen=self.colours['margin'])

    def set_datapath(self, path):
        self.datapath = path
        self.load_from_hdf(path)

    def load_from_hdf(self, path=None):
        path = path or self.datapath
        if path is not None:
            data = pd.read_hdf(path / 'test.hdf5', key='run_history')
            self.set_data(data)


class TestHistoryPlotsDQN(TestHistoryPlots):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.colours.update({'mean_qvals': (255, 86, 0)})
        self.plots['qvals'] = self.graphs.addPlot(
            title='Mean Qvals over Episodes',
            bottom='training_steps',
            left='Value')
        self.lines['mean_qvals'] = self.plots['qvals'].plot(y=[])
        self.plots['qvals'].showGrid(1, 1)
        self.plots['qvals'].setLabels()

    def set_data(self, data):
        super().set_data(data)
        if data is None or len(data) == 0:
            data = {k: [] for k in self.lines.keys()}
        self.lines['mean_qvals'].setData(y=data['mean_qvals'],
                                         pen=self.colours['mean_qvals'])


TestHistoryDDPG = TestHistoryPlotsDQN


class TestHistoryPlotsSACD(TestHistoryPlots):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.colours.update({
            'mean_qvals1': (255, 86, 0),
            'mean_qvals2': (86, 255, 0)
        })
        self.plots['qvals'] = self.graphs.addPlot(
            title='Mean Qvals over Episodes',
            bottom='training_steps',
            left='Value')
        self.lines['mean_qvals1'] = self.plots['qvals'].plot(y=[])
        self.lines['mean_qvals2'] = self.plots['qvals'].plot(y=[])
        self.plots['qvals'].showGrid(1, 1)
        self.plots['qvals'].setLabels()

    def set_data(self, data):
        super().set_data(data)
        if data is None or len(data) == 0:
            data = {k: [] for k in self.lines.keys()}
        self.lines['mean_qvals1'].setData(y=data['mean_qvals1'],
                                          pen=self.colours['mean_qvals1'])
        self.lines['mean_qvals2'].setData(y=data['mean_qvals2'],
                                          pen=self.colours['mean_qvals2'])
