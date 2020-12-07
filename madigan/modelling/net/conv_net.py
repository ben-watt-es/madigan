from functools import reduce, partial
from collections.abc import Iterable
import math

import torch
import torch.nn as nn

from .base import QNetworkBase
from .common import NoisyLinear, NormalHeadDQN, DuelingHeadDQN
from .utils import make_conv1d_layers, calc_conv_out_shape
from .utils import calc_pad_to_conserve
from .utils import xavier_initialization, orthogonal_initialization
from ...utils.data import State


class ConvNet(QNetworkBase):
    """
    For use in DQN
    """
    def __init__(self,
                 input_shape: tuple,
                 output_shape: tuple,
                 d_model=512,
                 channels=[32, 32],
                 kernels=[5, 5],
                 strides=[1, 1],
                 dueling=True,
                 preserve_window_len: bool = False,
                 noisy_net: bool = True,
                 noisy_net_sigma: float = 0.5,
                 **extra):
        """
        input_shape: (window_length, n_features)
        output_shape: (n_assets, action_atoms)
        """
        super().__init__()

        window_len = input_shape[0]
        assert window_len >= reduce(lambda x, y: x+y, kernels), \
            "window_length should be at least as long as sum of kernels"

        self.input_shape = input_shape
        self.n_assets = output_shape[0]
        self.action_atoms = output_shape[1]
        self.d_model = d_model
        self.act = nn.GELU()
        self.conv_layers = make_conv1d_layers(
            input_shape,
            kernels,
            channels,
            strides=strides,
            act=nn.GELU,
            preserve_window_len=preserve_window_len,
            causal_dim=0)
        conv_out_shape = calc_conv_out_shape(window_len, self.conv_layers)
        Linear = partial(NoisyLinear, sigma=noisy_net_sigma) \
            if noisy_net else nn.Linear
        self.price_project = Linear(conv_out_shape[0] * channels[-1],
                                       d_model)
        self.port_project = Linear(self.n_assets + 1, d_model)
        if dueling:
            self.output_head = DuelingHeadDQN(d_model,
                                              output_shape,
                                              noisy_net=noisy_net)
        else:
            self.output_head = NormalHeadDQN(d_model,
                                             output_shape,
                                             noisy_net=noisy_net)
        self.register_noisy_layers()

    def get_state_emb(self, state: State):
        """
        Given a State object containing tensors as .price and .portfolio
        attributes, returns an embedding of shape (bs, d_model)
        """
        price = state.price.transpose(-1,
                                      -2)  # switch features and time dimension
        port = state.portfolio
        price_emb = self.conv_layers(price).view(price.shape[0], -1)
        price_emb = self.price_project(price_emb)
        port_emb = self.port_project(port)
        state_emb = price_emb * port_emb
        out = self.act(state_emb)
        return out

    def forward(self, state: State = None, state_emb: torch.Tensor = None):
        """
        Returns qvals given either state or state_emb
        output_shape = (bs, n_assets, action_atoms)
        """
        assert state is not None or state_emb is not None
        if state_emb is None:
            state_emb = self.get_state_emb(state)  # (bs, d_model)
        qvals = self.output_head(state_emb)  # (bs, n_assets, action_atoms)
        return qvals


class ConvCriticQ(nn.Module):
    """
    For use as critic in Actor Critic methods, takes both state and action as input
    """
    def __init__(self,
                 input_shape: tuple,
                 n_assets: int,
                 n_actions: int = 1,
                 d_model=512,
                 channels=[32, 32],
                 kernels=[5, 5],
                 strides=[1, 1],
                 dueling=True,
                 preserve_window_len: bool = False,
                 noisy_net: bool = True,
                 noisy_net_sigma: float = 0.5,
                 **extra):
        super().__init__()
        window_len = input_shape[0]
        assert window_len >= reduce(lambda x, y: x+y, kernels), \
            "window_length should be at least as long as sum of kernels"

        self.input_shape = input_shape
        self.n_assets = n_assets
        self.n_actions = n_actions
        self.d_model = d_model
        self.act = nn.GELU()
        self.conv_layers = make_conv1d_layers(
            input_shape,
            kernels,
            channels,
            strides=strides,
            act=nn.GELU,
            preserve_window_len=preserve_window_len,
            causal_dim=0)
        conv_out_shape = calc_conv_out_shape(window_len, self.conv_layers)
        # self.price_project = nn.Linear(conv_out_shape[0]*channels[-1], d_model)
        # self.port_project = nn.Linear(self.n_assets, d_model)
        # self.action_project = nn.Linear(self.n_assets, d_model)
        Linear = partial(NoisyLinear, sigma=noisy_net_sigma) \
            if noisy_net else nn.Linear
        project_in = conv_out_shape[0] * channels[-1] + 2 * self.n_assets
        self.projection = nn.Linear(project_in, d_model)
        self.output_head = Linear(d_model, 1)
        self.register_noisy_layers()
        self.apply(orthogonal_initialization)


    def get_state_emb(self, state: State, action: torch.Tensor):
        """
        Given a State object containing tensors as .price and .portfolio
        attributes, returns an embedding of shape (bs, d_model)
        """
        price = state.price.transpose(-1,
                                      -2)  # switch features and time dimension
        port = state.portfolio
        price_emb = self.conv_layers(price).view(price.shape[0], -1)
        # price_emb = self.price_project(price_emb)
        # port_emb = self.port_project(port)
        # action_emb = self.action_project(action)
        state_emb = torch.cat([price_emb, port, action], dim=-1)
        state_emb = self.projection(state_emb)
        out = self.act(state_emb)
        return out

    def forward(self,
                state: State = None,
                action: torch.Tensor = None,
                state_emb: torch.Tensor = None):
        """
        Returns qvals given either state or state_emb
        output_shape = (bs, n_assets, action_atoms)
        """
        assert (None not in (state, action)) or state_emb is not None
        if state_emb is None:
            state_emb = self.get_state_emb(state, action)  # (bs, d_model)
        qvals = self.output_head(state_emb)  # (bs, n_assets, action_atoms)
        return qvals


class ConvPolicyDeterministic(nn.Module):
    """
    For use as actor in Actor Critic methods, takes both state and action as input
    """
    def __init__(self,
                 input_shape: tuple,
                 n_assets: int,
                 n_actions: int = 1,
                 d_model=512,
                 channels=[32, 32],
                 kernels=[5, 5],
                 strides=[1, 1],
                 dueling=True,
                 preserve_window_len: bool = False,
                 **extra):
        super().__init__()
        window_len = input_shape[0]
        assert window_len >= reduce(lambda x, y: x+y, kernels), \
            "window_length should be at least as long as sum of kernels"

        self.input_shape = input_shape
        self.n_assets = n_assets
        self.n_actions = n_actions
        assert self.n_actions == 1
        self.d_model = d_model
        self.act_fn = nn.GELU
        self.act = self.act_fn()
        self.conv_layers = make_conv1d_layers(
            input_shape,
            kernels,
            channels,
            strides=strides,
            act=self.act_fn,
            preserve_window_len=preserve_window_len,
            causal_dim=0)
        conv_out_shape = calc_conv_out_shape(window_len, self.conv_layers)
        project_in = conv_out_shape[0] * channels[-1] + self.n_assets
        self.projection = nn.Linear(project_in, d_model)
        self.output_head = nn.Linear(d_model, self.n_assets * self.n_actions)
        # self.apply(self.initialize_weights)
        # self.apply(xavier_initialization, linear_range=(-3e-4, 3e-4))
        self.apply(orthogonal_initialization)

    # def initialize_weights(self, m):
    #     if isinstance(m, nn.Linear):
    #         nn.init.uniform_(m.weight, -3e-4, 3e-4)
    #     elif isinstance(m, nn.Conv1d):
    #         fan_in, _ = nn.init._calculate_fan_in_and_fan_out(
    #             m.weight)
    #         scale = 1/math.sqrt(fan_in)
    #         nn.init.uniform_(m.weight, -scale, scale)
    #         if m.bias is not None:
    #             nn.init.constant_(m.bias, 0)

    def get_state_emb(self, state: State):
        """
        Given a State object containing tensors as .price and .portfolio
        attributes, returns an embedding of shape (bs, d_model)
        """
        price = state.price.transpose(-1,
                                      -2)  # switch features and time dimension
        port = state.portfolio
        price_emb = self.conv_layers(price).view(price.shape[0], -1)
        # price_emb = self.price_project(price_emb)
        # port_emb = self.port_project(port)
        state_emb = torch.cat([price_emb, port], dim=-1)
        # import ipdb; ipdb.set_trace()
        state_emb = self.projection(state_emb)
        out = self.act(state_emb)
        return out

    def forward(self, state: State = None, state_emb: torch.Tensor = None):
        """
        Returns qvals given either state or state_emb
        output_shape = (bs, n_assets, action_atoms)
        """
        assert (None not in (state, )) or state_emb is not None
        if state_emb is None:
            state_emb = self.get_state_emb(state)  # (bs, d_model)
        actions = self.output_head(state_emb).view(state_emb.shape[0],
                                                   self.n_assets,
                                                   self.n_actions)
        return torch.tanh(actions)
        # return torch.sigmoid(actions)