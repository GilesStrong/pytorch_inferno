# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/06_inference.ipynb (unless otherwise specified).

__all__ = ['bin_preds', 'get_shape', 'get_paper_syst_shapes', 'get_likelihood_width', 'interp_shape', 'calc_nll',
           'calc_grad_hesse', 'calc_profile']

# Cell
from .model_wrapper import ModelWrapper
from .callback import PaperSystMod

import pandas as pd
import numpy as np
from typing import *
from collections import OrderedDict
from scipy.interpolate import InterpolatedUnivariateSpline
import itertools
from fastcore.all import partialler
from fastprogress import progress_bar
import math

from torch import Tensor
import torch
from torch import autograd

# Cell
def bin_preds(df:pd.DataFrame, bins:np.ndarray=np.linspace(0.,1.,11), pred_name='pred') -> None:
    df[f'{pred_name}_bin'] = np.digitize(df[pred_name], bins)-1

# Cell
def get_shape(df:pd.DataFrame, targ:int, pred_name:str='pred_bin') -> Tensor:
    f = df.loc[df.gen_target == targ, pred_name].value_counts()
    f.sort_index(inplace=True)
    f /= f.sum()
    return Tensor(f)

# Cell
def get_paper_syst_shapes(bkg_data:np.ndarray, df:pd.DataFrame, model:ModelWrapper,
                    r_vals:Tuple[float,float,float]=[-0.2,0,0.2], l_vals:Tuple[float]=[2.5,3,3.5]) -> OrderedDict:
    def _get_shape(r,l):
        bp = model.predict(bkg_data, cbs=PaperSystMod(r=r,l=l))
        n = f'pred_{r}_{l}'
        df[n] = df.pred
        df.loc[df.gen_target == 0, n] = bp
        bin_preds(df, pred_name=n)
        return get_shape(df, 0, f'{n}_bin')

    shapes = OrderedDict()
    for i,r in enumerate(r_vals):
        print(f'Running: r={r}')
        shapes[f'{i}_{1}'] = _get_shape(r,l_vals[1])
    for i,l in enumerate(l_vals):
        print(f'Running: l={l}')
        shapes[f'{1}_{i}'] = _get_shape(r_vals[1],l)
    return OrderedDict((('f_b_nom',shapes['1_1']),
                        ('f_b_up', torch.stack((shapes['2_1'],shapes['1_2']))),
                        ('f_b_dw', torch.stack((shapes['0_1'],shapes['1_0'])))))

# Cell
def get_likelihood_width(nll:np.ndarray, mu_scan:np.ndarray, val:float=0.5) -> float:
    r = InterpolatedUnivariateSpline(mu_scan, nll-val-nll.min()).roots()
    if len(r) == 0: raise ValueError(f'No roots found at {val}, set val to a smaller value.')
    return (r[1]-r[0])/2

# Cell
def interp_shape(alpha:Tensor, f_b_nom:Tensor, f_b_up:Tensor, f_b_dw:Tensor):
    alpha_t = torch.repeat_interleave(alpha.unsqueeze(-1), repeats=f_b_nom.shape[-1], dim=-1)
    a = 0.5*(f_b_up+f_b_dw)[None,:]-f_b_nom
    b = 0.5*(f_b_up-f_b_dw)[None,:]

    switch = torch.where(alpha_t < 0., f_b_dw - f_b_nom, f_b_up - f_b_nom)
    abs_var = torch.where(torch.abs(alpha_t) > 1.,
                          (2 * b + torch.sign(alpha_t) * a) *
                          (alpha_t - torch.sign(alpha_t)) + switch,
                          a*torch.pow(alpha_t, 2)+ b * alpha_t)
    return (f_b_nom + abs_var.sum(1, keepdim=True)).squeeze(1)

# Cell
def calc_nll(s_true:float, b_true:float, s_exp:float, f_s:Tensor, alpha:Tensor,
                      f_b_nom:Tensor, f_b_up:Tensor, f_b_dw:Tensor) -> Tensor:
    f_b = interp_shape(alpha, f_b_nom, f_b_up, f_b_dw)
    t_exp = (s_exp[:,None]*f_s[None,])+(b_true*f_b)
    asimov = (s_true*f_s)+(b_true*f_b_nom)
    p = torch.distributions.Poisson(t_exp)
    return -p.log_prob(asimov).sum(1)

# Cell
def calc_grad_hesse(nll:Tensor, alpha:Tensor) -> Tuple[Tensor,Tensor]:
    grad = autograd.grad(nll, alpha, torch.ones_like(nll, device=nll.device), create_graph=True)[0]
    hesse = autograd.grad(grad, alpha, torch.ones_like(alpha, device=nll.device))[0]
    alpha.grad=None
    return grad, hesse

# Cell
def calc_profile(f_s:Tensor, f_b_nom:Tensor, f_b_up:Tensor, f_b_dw:Tensor, n:int,
                          mu_scan:Tensor, true_mu:int, n_steps:int=100, lr:float=0.1,  verbose:bool=True) -> Tensor:
    alpha = torch.zeros((len(mu_scan),f_b_up.shape[0]), requires_grad=True, device=f_b_nom.device)
    f_b_nom = f_b_nom.unsqueeze(0)
    get_nll = partialler(calc_nll, s_true=true_mu, b_true=n-true_mu, s_exp=mu_scan,
                         f_s=f_s, f_b_nom=f_b_nom, f_b_up=f_b_up, f_b_dw=f_b_dw)
    for i in range(n_steps):  # Newton optimise nuisances
        nll = get_nll(alpha=alpha)
        grad, hesse = calc_grad_hesse(nll, alpha)
        step = torch.clamp(lr*grad.detach()/(hesse+1e-7), -100, 100)
        alpha = alpha-step
    return get_nll(alpha=alpha), alpha