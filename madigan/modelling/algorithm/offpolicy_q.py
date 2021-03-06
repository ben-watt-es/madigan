"""
Serves as a base class for OffPolicy Q-Learning agents. So that derivatives
such as DQN or RDQN can inherit common functionality.
Main functionality implemented:
- init() - some initialisation expected to be common to all such agents
- step() - main training loop
- explore() - part of main training loop
- reset_state() - part of main training loop
- initialize_buffer() - part of main training loop
- test_episode()

"""
import pickle
from typing import Tuple, Union
from abc import abstractmethod
from random import random

import numpy as np
import pandas as pd
import torch

from .base import Agent
from ...environments import get_env_info
from ...utils.buffers import make_buffer_from_agent
# from ...utils.replay_buffer import ReplayBufferC as ReplayBuffer
from ...utils.data import SARSD, State, SARSDR, StateRecurrent
from ...utils.metrics import list_2_dict
from ...utils import DiscreteRangeSpace


class OffPolicyQ(Agent):
    """
    Base class for all off policy agents with experience replay buffers
    """
    def __init__(self, env, preprocessor, input_shape, action_space, discount,
                 nstep_return, reduce_rewards, reward_shaper_config,
                 replay_size, replay_min_size, prioritized_replay, per_alpha,
                 per_beta, per_beta_steps, noisy_net, eps, eps_decay, eps_min,
                 batch_size, test_steps, unit_size, savepath):
        super().__init__(env, preprocessor, input_shape, action_space,
                         discount, nstep_return, reduce_rewards, savepath)
        self.noisy_net = noisy_net
        self.eps = eps
        self.eps_decay = max(eps_decay, 1 -
                             eps_decay)  # to make sure we use 0.99999 not 1e-5
        self.eps_min = eps_min
        self.replay_size = replay_size
        self.nstep_return = nstep_return
        self.reward_shaper_config = reward_shaper_config
        self.discount = discount
        self.replay_min_size = replay_min_size
        self.prioritized_replay = prioritized_replay
        self.per_alpha = per_alpha
        self.per_beta = per_beta
        self.per_beta_steps = per_beta_steps
        self.buffer = make_buffer_from_agent(self)
        self.bufferpath = self.savepath.parent / 'replay.pkl'
        self.batch_size = batch_size
        self.test_steps = test_steps
        self.unit_size = unit_size
        self.action_atoms = self.action_space.action_atoms
        self.n_assets = self.action_space.n_assets
        self.centered_actions = np.arange(
            self.action_atoms) - self.action_atoms // 2
        self.log_freq = 2000
        self.debug_savepath = self.savepath.parent / 'logs/debug_trainloop.csv'

    def save_buffer(self):
        with open(self.bufferpath, 'wb') as f:
            pickle.dump(self.buffer, f)

    def load_buffer(self):
        if self.bufferpath.is_file():
            with open(self.bufferpath, 'rb') as f:
                self.buffer = pickle.load(f)

    @abstractmethod
    def get_qvals(self, state, target=False):
        pass

    @abstractmethod
    def get_action(self,
                   state: State = None,
                   qvals: torch.Tensor = None,
                   hidden=None,
                   target=False):
        pass

    @abstractmethod
    def action_to_transaction(self, action: Union[np.ndarray, torch.tensor]):
        pass

    def reset_state(self) -> State:
        self.buffer.clear_nstep()
        state = self._env.reset()
        self._preprocessor.reset_state()
        self._preprocessor.stream_state(state)
        self._preprocessor.initialize_history(self._env)
        return self._preprocessor.current_data()

    def initialize_buffer(self):
        if self.bufferpath.is_file():
            self.load_buffer()
        if len(self.buffer) < self.replay_min_size:
            steps = self.replay_min_size - len(self.buffer)
            self.step(steps)

    def step(self,
             n,
             reset: bool = True,
             log_freq: int = None,
             DEBUG: bool = False):
        """
        Performs n steps of interaction with the environment
        Accumulates experiences inside self.buffer (replay buffer for offpolicy)
        performs train_step when conditions are met (replay_min_size)
        n: int = number of training steps
        reset: bool = whether to reset environment before commencing training
        log_freq: int = frequency with which to yield results to caller.
        """
        self.train_mode()
        trn_metrics = []
        if reset:
            self.reset_state()
        state = self._preprocessor.current_data()
        log_freq = min(log_freq if log_freq is not None else self.log_freq, n)
        running_reward = 0.  # for logging
        running_cost = 0.  # for logging
        # i = 0
        max_steps = self.training_steps + n
        # DEBUG = False
        # if DEBUG:
        #     print("DEBUGGING")
        #     debug_logs = []
        # min_rewards = np.log(.35 * np.ones(self._env.nAssets))
        while True:
            self.model_b.sample_noise()
            action, transaction = self.explore(state)

            prev_eq = self._env.equity
            prev_val = self._env.positionValues

            _next_state, reward, done, info = self._env.step(transaction)

            if info.dataEnd:  # always False for synths
                state = self.reset_state()
                # print('reached data end')
                continue

            # rew = reward

            info = info.brokerResponse
            curr_val = self._env.positionValues
            mar_diff = (info.transactionUnits * info.transactionPrice +
                        info.transactionCost)
            reward = (curr_val - prev_val - mar_diff) / prev_eq
            reward += 1
            if (reward < 0.).any():
                print('large neg reward, prev_eq, curr_eq: ', reward, prev_eq,
                      self._env.equity)
            reward = np.log(np.maximum(reward, .35))
            # reward = np.log(reward, where=reward > 0.35, out=min_rewards)
            if self.reduce_rewards:
                reward = reward.sum(keepdims=True)

            running_cost += np.sum(info.transactionCost)


            # if DEBUG:
            #     debug_metrics = {
            #         'action': action,
            #         'transaction': transaction,
            #         'reward_pre_shape': reward,
            #         'done': done,
            #         # 'info': info,
            #         'transactionCost': info.brokerResponse.transactionCost,
            #         'transactionUnit': info.brokerResponse.transactionUnits,
            #         'running_cost': running_cost,
            #         **get_env_info(self._env)
            #     }

            # if done:  # unnecessary as rewards are truncated anyway
            #     reward = -0.01 * np.ones_like(reward)
            # reward = -0.1

            running_reward += reward.sum()
            # running_reward += reward
            # if DEBUG:
            #     debug_metrics['reward_post_shape'] = reward
            #     debug_metrics['running_reward'] = running_reward
            #     debug_logs.append(debug_metrics)

            self._preprocessor.stream_state(_next_state)
            next_state = self._preprocessor.current_data()

            sarsd = SARSD(state, action, reward, next_state, done)
            self.buffer.add(sarsd)

            if done:
                self.reset_state()
                state = self._preprocessor.current_data()
                running_reward = 0.
            else:
                state = next_state

            if len(self.buffer) > self.replay_min_size:
                _trn_metrics = self.train_step()
                _trn_metrics['eps'] = self.eps
                _trn_metrics['running_reward'] = running_reward
                trn_metrics.append(_trn_metrics)
                self.training_steps += 1

                if self.training_steps % log_freq == 0:
                    yield trn_metrics
                    trn_metrics.clear()
                    # if DEBUG:
                    #     print("Saving debug logs")
                    #     df = pd.DataFrame(list_2_dict(debug_logs))
                    #     if not self.debug_savepath.is_file():
                    #         df.to_csv(self.debug_savepath, mode='w')
                    #     else:
                    #         df.to_csv(self.debug_savepath,
                    #                   mode='a',
                    #                   header=False)
                    #     debug_logs = []

                if self.training_steps > max_steps:
                    yield trn_metrics
                    break

            self.env_steps += 1

    def explore(self, state: State) -> Tuple[np.ndarray, np.ndarray]:
        if self.noisy_net:
            action = self.get_action(state, target=False).cpu().numpy()
        else:
            if random() < self.eps:
                action = self.get_action(state, target=False).cpu().numpy()
            else:
                action = self.action_space.sample()
            self.eps = max(self.eps_min, self.eps * self.eps_decay)
        return action, self.action_to_transaction(action)

    @torch.no_grad()
    def test_episode(self, test_steps=None, reset=True, target=True) -> dict:
        self.test_mode()
        test_steps = test_steps or self.test_steps
        if reset:
            self.reset_state()
        self._preprocessor.initialize_history(
            self.env)  # probably already initialized
        state = self._preprocessor.current_data()
        tst_metrics = []
        i = 0
        while i <= test_steps:
            _tst_metrics = {}
            qvals = self.get_qvals(state, target=target)
            action = self.get_action(qvals=qvals, target=target).cpu().numpy()
            transaction = self.action_to_transaction(action)
            _tst_metrics['timestamp'] = state.timestamp[-1]
            state, reward, done, info = self._env.step(transaction)
            self._preprocessor.stream_state(state)
            state = self._preprocessor.current_data()
            _tst_metrics['qvals'] = qvals.cpu().numpy()
            _tst_metrics['reward'] = reward
            _tst_metrics['transaction'] = info.brokerResponse.transactionUnits
            _tst_metrics[
                'transaction_cost'] = info.brokerResponse.transactionCost
            # _tst_metrics['info'] = info
            tst_metrics.append({**_tst_metrics, **get_env_info(self._env)})
            if done:
                break
            i += 1
        return list_2_dict(tst_metrics)


class OffPolicyQRecurrent(Agent):
    """
    Recurrent OffPolicyQ Base
    """
    def __init__(self, env, preprocessor, input_shape, action_space, discount,
                 nstep_return, reward_shaper, replay_size, replay_min_size,
                 prioritized_replay, per_alpha, per_beta, per_beta_steps,
                 episode_len, burn_in_steps, episode_overlap, store_hidden,
                 noisy_net, eps, eps_decay, eps_min, batch_size, test_steps,
                 unit_size, savepath):
        super().__init__(env, preprocessor, input_shape, action_space,
                         discount, nstep_return, reward_shaper, savepath)
        self.noisy_net = noisy_net
        self.eps = eps
        self.eps_decay = max(eps_decay, 1 -
                             eps_decay)  # to make sure we use 0.99999 not 1e-5
        self.eps_min = eps_min
        self.replay_size = replay_size
        self.replay_min_size = replay_min_size
        self.prioritized_replay = prioritized_replay
        self.per_alpha = per_alpha
        self.per_beta = per_beta
        self.per_beta_steps = per_beta_steps
        self.episode_len = episode_len
        self.burn_in_steps = burn_in_steps
        self.episode_overlap = episode_overlap
        self.store_hidden = store_hidden
        self.nstep_return = nstep_return
        self.discount = discount
        self.buffer = EpisodeReplayBuffer.from_agent(self)
        self.bufferpath = self.savepath.parent / 'replay.pkl'
        self.batch_size = batch_size
        self.test_steps = test_steps
        self.unit_size = unit_size
        self.action_atoms = self.action_space.action_atoms
        self.n_assets = self.action_space.n_assets
        self.centered_actions = np.arange(
            self.action_atoms) - self.action_atoms // 2
        self.log_freq = 2000
        self.debug_savepath = self.savepath.parent / 'logs/debug_trainloop.csv'

    def save_buffer(self):
        with open(self.bufferpath, 'wb') as f:
            pickle.dump(self.buffer, f)

    def load_buffer(self):
        if self.bufferpath.is_file():
            with open(self.bufferpath, 'rb') as f:
                self.buffer = pickle.load(f)

    def initialize_buffer(self):
        if self.bufferpath.is_file():
            self.load_buffer()
        if len(self.buffer) < self.replay_min_size:
            steps = self.replay_min_size - len(self.buffer)
            self.step(steps)

    @abstractmethod
    def get_qvals(self, state: StateRecurrent, target: bool = False) -> Tuple:
        pass

    @abstractmethod
    def get_action(self,
                   state: StateRecurrent = None,
                   qvals: torch.Tensor = None,
                   target: bool = False) -> Tuple:
        pass

    @abstractmethod
    def get_default_hidden(self, batch_size):
        pass

    def explore(self, state: StateRecurrent) -> Tuple[np.ndarray, np.ndarray]:
        if self.noisy_net:
            action, hidden = self.get_action(state, target=False)
            action = action.cpu().numpy()[0]
        else:
            if random() < self.eps:
                action, hidden = self.get_action(state, target=False)
                action = action.cpu().numpy()[0]
            else:
                _, hidden = self.get_qvals(state, target=False)
                action = self.action_space.sample()
            self.eps = max(self.eps_min, self.eps * self.eps_decay)
        return action, self.action_to_transaction(action), hidden

    def make_recurrent_state(self, state, prev_action, prev_reward, hidden):
        """
        For converting the state received from the env to StateRecurrent
        """
        return StateRecurrent(state.price, state.portfolio, state.timestamp,
                              prev_action, prev_reward, hidden)

    def reset_state(self) -> State:
        state = self._env.reset()
        self._preprocessor.reset_state()
        self._preprocessor.stream_state(state)
        self._preprocessor.initialize_history(self._env)
        self.reward_shaper.reset()
        state = self._preprocessor.current_data()
        action = torch.zeros_like(torch.from_numpy(self.action_space.sample()))
        state = self.make_recurrent_state(state, action, 0.,
                                          self.get_default_hidden(1))
        return state

    def step(self, n, reset: bool = True, log_freq: int = None):
        """
        Performs n steps of interaction with the environment
        Accumulates experiences into memory (replay buffer for offpolicy)
        performs train_step when conditions are met (replay_min_size)
        @params:
            n: int = number of training steps
            reset: bool = whether to reset environment before starting training
            log_freq: int = frequency with which to yield results to caller.
        yields:
            train_metrics: dict

        """
        self.train_mode()
        trn_metrics = []
        if reset:
            self.reset_state()
        state = self._preprocessor.current_data()
        log_freq = min(log_freq if log_freq is not None else self.log_freq, n)
        running_reward = 0.  # for logging
        running_cost = 0.  # for logging
        # i = 0
        max_steps = self.training_steps + n
        reward = 0.
        action = torch.zeros_like(torch.from_numpy(self.action_space.sample()))
        hidden = self.get_default_hidden(1)
        state = self.make_recurrent_state(state, action, reward, hidden)
        while True:
            self.model_b.sample_noise()

            action, transaction, hidden = self.explore(state)
            _next_state, reward, done, info = self._env.step(transaction)
            reward = self.reward_shaper.stream(reward)

            self._preprocessor.stream_state(_next_state)
            next_state = self._preprocessor.current_data()
            next_state = self.make_recurrent_state(next_state, action, reward,
                                                   hidden)

            running_cost += np.sum(info.brokerResponse.transactionCost)
            running_reward += reward
            # if done:
            #     reward = -.1
            sarsd = SARSDR(state, action, reward, next_state, done)
            self.buffer.add(sarsd)

            if done:
                self.reset_state()
                state = self._preprocessor.current_data()
                state = self.make_recurrent_state(state, action, reward,
                                                  hidden)
                running_reward = 0.
            else:
                state = next_state

            if len(self.buffer) > self.replay_min_size:
                _trn_metrics = self.train_step()
                _trn_metrics['eps'] = self.eps
                _trn_metrics['running_reward'] = running_reward
                trn_metrics.append(_trn_metrics)
                self.training_steps += 1

                if self.training_steps % log_freq == 0:
                    yield trn_metrics
                    trn_metrics.clear()

                if self.training_steps > max_steps:
                    yield trn_metrics
                    break

            self.env_steps += 1

    @torch.no_grad()
    def test_episode(self, test_steps=None, reset=True, target=True) -> dict:
        self.test_mode()
        test_steps = test_steps or self.test_steps
        if reset:
            self.reset_state()
        self._preprocessor.initialize_history(
            self.env)  # probably already initialized
        action = torch.zeros_like(torch.from_numpy(self.action_space.sample()))
        reward = 0.
        hidden = self.get_default_hidden(1)
        state = self._preprocessor.current_data()
        state = self.make_recurrent_state(state, action, reward, hidden)
        tst_metrics = []
        i = 0
        while i <= test_steps:
            _tst_metrics = {}
            qvals, hidden = self.get_qvals(state, target=target)
            action, _ = self.get_action(qvals=qvals,
                                        hidden=hidden,
                                        target=target)
            action = action.cpu().numpy()[0]
            transaction = self.action_to_transaction(action)
            state, reward, done, info = self._env.step(transaction)
            self._preprocessor.stream_state(state)
            state = self._preprocessor.current_data()
            state = self.make_recurrent_state(state, action, reward, hidden)
            _tst_metrics['qvals'] = qvals.cpu().numpy()
            _tst_metrics['action'] = action
            _tst_metrics['reward'] = reward
            _tst_metrics['transaction'] = info.brokerResponse.transactionUnits
            _tst_metrics[
                'transaction_cost'] = info.brokerResponse.transactionCost
            # _tst_metrics['info'] = info
            tst_metrics.append({**_tst_metrics, **get_env_info(self._env)})
            if done:
                break
            if self._env.dataEnd():
                break
            i += 1
        return list_2_dict(tst_metrics)
