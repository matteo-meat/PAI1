from pinns_v2.model import PINN
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from pinns_v2.train import train
from pinns_v2.gradient import _jacobian, _hessian
from pinns_v2.dataset import DomainDataset, ICDataset

import skopt
from skopt import gp_minimize
from skopt.plots import plot_convergence, plot_objective
from skopt.space import Real, Categorical, Integer
from skopt.utils import use_named_args


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

epochs = 2000
num_inputs = 2 #x, t

u_min = -0.21
u_max = 0.0
x_min = 0.0
x_max = 1.0
t_f = 10
f_min = -3.0
f_max = 0.0
delta_u = u_max - u_min
delta_x = x_max - x_min
delta_f = f_max - f_min

params = {
    "u_min": u_min,
    "u_max": u_max,
    "x_min": x_min,
    "x_max": x_max,
    "t_f": t_f,
    "f_min": f_min,
    "f_max": f_max
}

def hard_constraint(x, y):
    X = x[0]
    tau = x[-1]
    U = ((X-1)*X*(delta_x**2)*t_f*tau)*(y+(u_min/delta_u)) - (u_min/delta_u)
    return U

def f(sample):
    x = sample[0]*(delta_x) + x_min
    #x_f = sample[1]*(delta_x) + x_min
    x_f = 0.2*(delta_x) + x_min
    #h = sample[2]*(delta_f) + f_min
    h = f_min
    
    z = h * torch.exp(-400*((x-x_f)**2))
    return z


def pde_fn(model, sample):
    T = 1
    mu = 1
    k = 1
    alpha_2 = (T/mu)*(t_f**2)/(delta_x**2)
    beta = (t_f**2)/delta_u
    K = k * t_f
    J, d = _jacobian(model, sample)
    dX = J[0][0]
    dtau = J[0][-1]
    H = _jacobian(d, sample)[0]
    ddX = H[0][0, 0]
    ddtau = H[0][-1, -1]
    return ddtau - alpha_2*ddX - beta*f(sample) + K*dtau


def ic_fn_vel(model, sample):
    J, d = _jacobian(model, sample)
    dtau = J[0][-1]
    dt = dtau*delta_u/t_f
    ics = torch.zeros_like(dt)
    return dt, ics



n_calls = 50
dim_learning_rate = Real(low=1e-4, high=5e-2, name="learning_rate", prior="log-uniform")
dim_num_dense_layers = Integer(low=1, high=10, name="num_dense_layers")
dim_num_dense_nodes = Integer(low=5, high=500, name="num_dense_nodes")
dim_activation = Categorical(categories=[torch.sin, nn.Sigmoid, nn.Tanh, nn.SiLU], name="activation")
dim_eps_time = Real(low = 0.1, high = 1000, name="eps_time", prior = "log-uniform")

dimensions = [
    dim_learning_rate,
    dim_num_dense_layers,
    dim_num_dense_nodes,
    dim_activation,
    dim_eps_time
]

default_parameters = [1e-3, 3, 100, nn.Tanh, 100]
ITERATION = 0

@use_named_args(dimensions = dimensions)
def fitness(learning_rate, num_dense_layers, num_dense_nodes, activation, eps_time):
    global ITERATION
    print(ITERATION, "it number")
    # Print the hyper-parameters.
    print("learning rate: {0:.1e}".format(learning_rate))
    print("num_dense_layers:", num_dense_layers)
    print("num_dense_nodes:", num_dense_nodes)
    print("activation:", activation)
    print("epsilon time causality:", eps_time)
    print()

    batchsize = 512
    domainDataset = DomainDataset([0.0]*num_inputs,[1.0]*num_inputs, 10000, period = 3)
    icDataset = ICDataset([0.0]*(num_inputs-1),[1.0]*(num_inputs-1), 10000, period = 3)
    validationDataset = DomainDataset([0.0]*num_inputs,[1.0]*num_inputs, batchsize, shuffle = False)
    validationicDataset = ICDataset([0.0]*(num_inputs-1),[1.0]*(num_inputs-1), batchsize, shuffle = False)

    model = PINN([num_inputs] + [100]*3 + [1], nn.Tanh, hard_constraint)

    def init_normal(m):
        if type(m) == torch.nn.Linear:
            torch.nn.init.xavier_uniform_(m.weight)

    model = model.apply(init_normal)
    model = model.to(device)
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=750, gamma=0.1)

    data = {
        "name": "string_4inputs_nostiffness_force_damping_ic0hard_icv0_causality_t10.0_rff_0.5",
        #"name": "prova",
        "model": model,
        "epochs": epochs,
        "batchsize": batchsize,
        "optimizer": optimizer,
        "scheduler": scheduler,
        "pde_fn": pde_fn,
        "ic_fns": [ic_fn_vel],
        "eps_time": eps_time,
        "domain_dataset": domainDataset,
        "ic_dataset": icDataset,
        "validation_domain_dataset": validationDataset,
        "validation_ic_dataset": validationicDataset,
        "additional_data": params
    }

    
    min_test_loss = train(data, output_to_file=False)

    if np.isnan(min_test_loss):
        min_test_loss = 10**5

    ITERATION += 1
    return min_test_loss


search_result = gp_minimize(
    func=fitness,
    dimensions=dimensions,
    acq_func="EI",  # Expected Improvement.
    n_calls=n_calls,
    x0=default_parameters,
    random_state=1234,
)

print(search_result.x)

plot_convergence(search_result)
plot_objective(search_result, show_points=True, size=3.8)


