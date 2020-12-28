import os
from typing import Union
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from .dqn import DQN
from ...environments import make_env
from ...environments.reward_shaping import RewardShaper, make_reward_shaper
from ..net.conv_net_iqn import ConvNetIQN
from ...utils import default_device, DiscreteActionSpace, DiscreteRangeSpace
from ...utils.preprocessor import make_preprocessor
from ...utils.config import Config
from ...utils.data import State, SARSD


class IQN(DQN):
    """
    Implements a base DQN agent from which extensions can inherit
    The Agent instance can be called directly to get an action based on a state:
        action = dqn(state)
    or:
        action = dqn.get_action(state)
    use dqn.step(n) to step through n environment interactions
    The method for training a single batch is self.train_step(sarsd) where sarsd is a class with ndarray members (I.e of shape (bs, time, feats))
    """
    def __init__(
            self,
            env,
            preprocessor,
            input_shape: tuple,
            action_space: tuple,
            discount: float,
            nstep_return: int,
            reward_shaper: RewardShaper,
            replay_size: int,
            replay_min_size: int,
            prioritized_replay: bool,
            per_alpha: float,
            per_beta: float,
            per_beta_steps: int,
            noisy_net: bool,
            noisy_net_sigma: float,
            eps: float,
            eps_decay: float,
            eps_min: float,
            batch_size: int,
            test_steps: int,
            unit_size: float,
            savepath: Union[Path, str],
            double_dqn: bool,
            tau_soft_update: float,
            model_class: str,
            model_config: Union[dict, Config],
            lr: float,
            ##############
            # Extra 3 Args
            ##############
            nTau1: int,
            nTau2: int,
            k_huber: float):
        super().__init__(env, preprocessor, input_shape, action_space,
                         discount, nstep_return, reward_shaper, replay_size,
                         replay_min_size, prioritized_replay, per_alpha,
                         per_beta, per_beta_steps, noisy_net, noisy_net_sigma,
                         eps, eps_decay, eps_min, batch_size, test_steps,
                         unit_size, savepath, double_dqn, tau_soft_update,
                         model_class, model_config, lr)

        self.nTau1 = nTau1
        self.nTau2 = nTau2
        self.k_huber = k_huber
        self.risk_distortion = lambda x: x

    @classmethod
    def from_config(cls, config):
        env = make_env(config)
        preprocessor = make_preprocessor(config, env.nAssets)
        input_shape = preprocessor.feature_output_shape
        atoms = config.discrete_action_atoms + 1
        action_space = DiscreteRangeSpace((0, atoms), env.nAssets)
        reward_shaper = make_reward_shaper(config)
        aconf = config.agent_config
        unit_size = aconf.unit_size_proportion_avM
        savepath = Path(config.basepath) / config.experiment_id / 'models'
        return cls(
            env, preprocessor, input_shape, action_space, aconf.discount,
            aconf.nstep_return, reward_shaper, aconf.replay_size,
            aconf.replay_min_size, aconf.prioritized_replay, aconf.per_alpha,
            aconf.per_beta, aconf.per_beta_steps, aconf.noisy_net,
            aconf.noisy_net_sigma, aconf.eps, aconf.eps_decay, aconf.eps_min,
            aconf.batch_size, config.test_steps, unit_size, savepath,
            aconf.double_dqn, aconf.tau_soft_update,
            config.model_config.model_class, config.model_config,
            config.optim_config.lr, config.agent_config.nTau1,
            config.agent_config.nTau2, config.agent_config.k_huber)

    @torch.no_grad()
    def get_quantiles(self, state, target=False, device=None):
        device = device or self.device
        state = self.prep_state_tensors(state, device=device)
        if target:
            return self.model_t(state)
        return self.model_b(state)

    @torch.no_grad()
    def get_qvals(self, state, target=False, device=None):
        """
        External interface - for inference and env interaction
        Takes in numpy arrays
        and return qvals for actions
        """
        quantiles = self.get_quantiles(
            state, target=target,
            device=device)  #(bs, nTau1, n_assets, n_actions)
        return quantiles.mean(1)  #(bs, n_assets, n_actions)

    def __call__(self,
                 state: State,
                 target: bool = True,
                 device: torch.device = None):
        return self.get_action(state, target=target, device=device)

    @torch.no_grad()
    def calculate_Gt_target(self, next_state, reward, done):
        """
        Given a next_state State object, calculates the target value
        to be used in td error and loss calculation
        """
        bs = reward.shape[0]
        tau_greedy = torch.rand(bs,
                                self.nTau1,
                                dtype=torch.float32,
                                device=reward.device,
                                requires_grad=False)
        tau_greedy = self.risk_distortion(tau_greedy)
        tau2 = torch.rand(bs,
                          self.nTau2,
                          dtype=torch.float32,
                          device=reward.device,
                          requires_grad=False)

        if self.double_dqn:
            greedy_quantiles = self.model_b(
                next_state, tau=tau_greedy)  # (bs, nTau1, nassets, nactions)
        else:
            greedy_quantiles = self.model_t(
                next_state, tau=tau_greedy)  # (bs, nTau1, nassets, nactions)
        greedy_actions = torch.argmax(greedy_quantiles.mean(1),
                                      dim=-1,
                                      keepdim=True)  # (bs, nassets,  nactions)
        assert greedy_actions.shape[1:] == (self.n_assets, 1)
        one_hot = F.one_hot(greedy_actions,
                            self.action_atoms).to(reward.device)
        quantiles_next = self.model_t(next_state, tau=tau2)
        assert quantiles_next.shape[1:] == (self.nTau2, self.n_assets,
                                            self.action_atoms)
        quantiles_next = (
            quantiles_next * one_hot[:, None, :, 0, :]).sum(-1).mean(
                -1)  # get max qval within asset and average across assets
        assert quantiles_next.shape[1:] == (self.nTau2, )
        Gt = reward[:, None] + (~done[:, None] *
                                (self.discount**self.nstep_return) *
                                quantiles_next)
        assert Gt.shape[1:] == (self.nTau2, )
        return Gt

    def train_step(self, sarsd: SARSD = None, weights: np.ndarray = None):
        self.model_b.sample_noise()
        self.model_t.sample_noise()
        sarsd, weights = self.buffer.sample(
            self.batch_size) if sarsd is None else (sarsd, weights)
        state, action, reward, next_state, done = self.prep_sarsd_tensors(
            sarsd)
        bs = reward.shape[0]
        tau1 = torch.rand(bs,
                          self.nTau1,
                          dtype=torch.float32,
                          device=reward.device)
        quantiles = self.model_b(state, tau=tau1)
        action_mask = F.one_hot(action[:, None],
                                self.action_atoms).to(self.device)

        Gt = self.calculate_Gt_target(next_state, reward, done)  # (bs, nTau2)
        Qt = (quantiles * action_mask).sum(-1).mean(-1)  # (bs, nTau1)
        loss, td_error = self.loss_fn(
            Qt, Gt, tau1,
            torch.from_numpy(weights).to(self.device))
        if self.prioritized_replay:
            self.buffer.update_priority(td_error)
        self.opt.zero_grad()
        loss.backward()
        self.opt.step()

        self.update_target()
        return {
            'loss': loss.detach().item(),
            'td_error': td_error.mean().item(),
            'Qt': Qt.detach().mean().item(),
            'Gt': Gt.detach().mean().item()
        }

    def loss_fn(self, Qt, Gt, tau, weights: torch.Tensor = None):
        """
        Quantile Huber Loss
        returns:  (loss, td_error)
            loss: scalar
            td_error: scalar
        """
        assert Qt.shape[1:] == (self.nTau1, )
        assert Gt.shape[1:] == (self.nTau2, )
        td_error = Gt.unsqueeze(1) - Qt.unsqueeze(2)
        assert td_error.shape[1:] == (
            self.nTau1,
            self.nTau2,
        )
        huber_loss = torch.where(
            td_error.abs() <= self.k_huber, 0.5 * td_error.pow(2),
            self.k_huber * (td_error.abs() - self.k_huber / 2))
        assert huber_loss.shape == td_error.shape
        quantile_loss = torch.abs(tau[:, :, None] -
                                  (td_error.detach() < 0.).float()) *\
            huber_loss / self.k_huber
        assert quantile_loss.shape == huber_loss.shape
        if weights is None:
            loss = quantile_loss.mean(-1).sum(-1)
        else:
            loss = quantile_loss.mean(-1).sum(-1) * weights
        assert loss.shape == (Qt.shape[0], )
        return loss.mean(), td_error.abs().mean(-1).mean(-1).detach()


class IQNCURL(IQN):
    """
    CURL: Contrastive Unsupervised Representation Learning
    This agent mainly just wraps the appropriate CURL-enabled nn.Module which
    contains the actual functionality for performing CURL.
    Keeping the main logic in the contained nn model maintains code resuability
    at the higher abstraction of the agent and lets the model take care of
    internal housekeeping (I.e defining and updating key encoder).
    """
    def train_step(self, sarsd: SARSD = None):
        """
        wraps train_step() of DQN to include the curl objective
        """
        sarsd = sarsd or self.buffer.sample(self.batch_size)
        state = self.prep_state_tensors(sarsd.state, batch=True)
        # contrastive unsupervised objective
        loss_curl = self.model_b.train_contrastive_objective(state)
        # do normal rl training objective and add 'loss_curl' to output dict
        return {'loss_curl': loss_curl, **super().train_step(sarsd)}


# for temporary backward comp
IQNReverser = IQN
