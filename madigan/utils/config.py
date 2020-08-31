import numpy as np

class Config(dict):
    """
    Wraps a dictionary to have its keys accesible like attributes
    I.e can do both config['steps'] and config.steps to get/set items

    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        recursive=True
        if recursive:
            for k, v in self.items():
                if isinstance(v, dict):
                    self[k] = Config(v)

    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError("No such attribute: " + name)

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        if name in self:
            del self[name]
        else:
            raise AttributeError("No such attribute: " + name)


def make_config(generator_params=None, nsteps=100, agent_type="DQN",
                discrete_actions=True, discrete_action_atoms=11,
                min_tf=1, savepath="/home/hemu/madigan/farm/",
                double_dqn=False, dueling=False, iqn=False,
                discount=0.99, nstep_agent=1,
                model_class="MLPModel", n_assets=4, d_model=256,
                n_feats=1, n_layers=4, lr=1e-3, optim_eps=1e-8,
                momentum=0.9, betas=(0.9, 0.999), optim_wd=0):
    freq=[1., 2., 3., 4.]
    mu=[2., 3, 4., 5.] # (mu == offset) Keeps negative prices from ocurring
    amp=[1., 2., 3., 4.]
    phase=[0., 1., 2., 0.]
    gen_state_space = np.stack([freq, mu, amp, phase], axis=1) # (n_assets, nparameters)

    generator_params = generator_params or {'type': 'multisine',
                            'state_space': gen_state_space.tolist()}
    assert n_assets == len(generator_params['state_space'])
    model_config = {
        'model_class': model_class,
        'd_model': 256,
        'n_layers': n_layers,
        'n_feats': n_feats,
        'action_atoms': discrete_action_atoms,
        'n_assets': n_assets,
        'min_tf': min_tf,
        'dueling': dueling,
        'iqn': iqn,
    }
    optim_config = {
        'type': 'Adam',
        'lr': lr,
        'eps': optim_eps,
        'momentum': momentum,
        'betas': betas,
        'weight_decay': optim_wd,
    }
    agent_config = {
        'type': agent_type,
        'savepath': savepath,
        'model_config': model_config,
        'optim_config': optim_config,
        'double_dqn': double_dqn,
        'discount': discount,
        'nstep': nstep_agent,
        'action_atoms': discrete_action_atoms,
    }
    config = dict(
        name='test',
        generator_params=generator_params,
        discrete_actions=discrete_actions,
        discrete_action_atoms=discrete_action_atoms,
        nsteps=nsteps,
        lot_unit_value=1_000,
        min_tf = min_tf,
        agent_config=agent_config,
        n_assets = n_assets,
    )
    return Config(config)