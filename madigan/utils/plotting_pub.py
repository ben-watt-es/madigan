"""
Utils for making figures for publication or presentation
"""
import os
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

rc_params = {
    'text.usetex': False,
    'lines.linewidth': 2,
    'axes.labelsize': 'large'
}

sns.set_theme(context="paper", font_scale=3, rc=rc_params)


def save_fig(fig, savepath):
    """ Save all figures in pdf format - best for latex """
    savepath = Path(savepath)
    if not savepath.parent.is_dir():
        savepath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(savepath, format='pdf', bbox_inches='tight')


def get_episode_id(
    experiment_id,
    basepath,
    env_steps=None,
    episode_steps=None,
):
    assert env_steps is not None or episode_steps is not None
    path = Path(basepath) / experiment_id
    runs = filter(lambda x: "episode" in str(x.name), path.iterdir())
    runs = list(map(lambda x: x.name.split('_'), runs))
    if env_steps is not None:
        runs = filter(runs, lambda x: env_steps == x[3])
    if episode_steps is not None:
        runs = filter(runs, lambda x: episode_steps == x[5])
    if len(runs) > 0:
        raise ValueError("multiple matches found for env and episode steps "
                         f"combination: {env_steps}, {episode_steps}")
    return ''.join(runs[0])


def load_train_data(experiment_id, basepath):
    path = Path(basepath) / experiment_id / 'logs/train.hdf5'
    df = pd.read_hdf(path, key='train')
    return df


def load_test_history_data(experiment_id, basepath):
    path = Path(basepath) / experiment_id / 'logs/test.hdf5'
    df = pd.read_hdf(path, key='run_history')
    return df


def load_test_run_data(episode_id, experiment_id, basepath):
    path = Path(basepath) / experiment_id / f'logs/{episode_id}.hdf5'
    df = pd.read_hdf(path, key='run_history')
    return df


def make_train_figs(experiment_id, basepath):
    df = load_train_data(experiment_id, basepath).reset_index(drop=True)
    figs = {}
    for label in df.columns:
        fig, ax = plt.subplots(1, 1)
        ax.plot(df[label], label=label)
        ax.legend()
        ax.set_xlabel('training_step')
        # figs.append(fig)
        # figs.append({'fig': fig, 'fname': label})
        figs[label] = fig
    figs['running_reward'].axes[0].set_ylabel('cumulative rewards')
    return figs


def make_multi_asset_plot(ax, x, ys, assets=None):
    n_assets = ys.shape[1]
    assets = assets if assets is not None else [
        f"asset_{i}" for i in range(n_assets)
    ]
    if n_assets != len(assets):
        raise ValueError("data shape does not match number of assets provided")
    for i, asset in enumerate(assets):
        ax.plot(x, ys[:, i], label=asset)
    if n_assets > 1:
        ax.legend(loc='upper left')
    return ax


def make_figs(data: Union[dict, pd.DataFrame], assets=None, x_key=None):
    if x_key is None:
        x = None
    else:
        x = data[x_key]
    figs = {}
    for label in data.keys():
        if x is None or len(x) != len(data[label]):
            x = range(len(data[label]))
        try:
            # dat = data[label].squeeze()
            dat = data[label]
            fig, ax = plt.subplots(1, 1, figsize=(15, 10))
            if len(dat.shape) == 1:
                ax.plot(x, dat, label=label)
                # legend only for multi asset plots
                # ax.legend(loc='upper left')
                if ((np.nanmax(dat) - np.nanmin(dat)) / np.nanmin(dat)) > 1e7:
                    ax.set_yscale('log')
            elif len(dat.shape) == 2:
                ax = make_multi_asset_plot(ax, x, dat, assets=assets, )
            else:
                ax.imshow(dat.squeeze())  # vmin=0., vmax=1.) #, cmap='gray'
            ax.set_ylabel(label)
            ax.set_xlabel('step')
            figs[label] = fig
        except Exception as E:
            print(E)
            print('skipping: ', label)
    return figs


def save_figs(figs, savepath):
    for label, fig in figs.items():
        save_fig(fig, savepath / f"{label}.pdf")
        # save_fig(fig['fig'], savepath/f"{fig['fname']}.pdf")
        # save_fig(fig, savepath/f'{fig.label}.pdf')