# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/07_inferno_exact.ipynb (unless otherwise specified).

__all__ = ['VariableSoftmax', 'calc_nll', 'calc_profile', 'AbsInferno', 'PaperInferno', 'InfernoPred']

# Cell
from .callback import AbsCallback, PredHandler
from .inference import calc_grad_hesse

import numpy as np
from abc import abstractmethod
from fastcore.all import store_attr
from typing import Optional, List

from torch import Tensor, nn
import torch
from torch.distributions import Distribution

# Cell
class VariableSoftmax(nn.Softmax):
    r'''Softmax with temperature'''
    def __init__(self, temp:float=1, dim:int=-1):
        super().__init__(dim=dim)
        self.temp = temp

    def forward(self, x:Tensor) -> Tensor: return super().forward(x/self.temp)

# Cell
from .model_wrapper import ModelWrapper
from .callback import PaperSystMod, PredHandler

import pandas as pd
import numpy as np
from typing import *
from collections import OrderedDict
from scipy.interpolate import InterpolatedUnivariateSpline
import itertools
from fastcore.all import partialler
from fastprogress import progress_bar
import math

from torch import Tensor, autograd
import torch
from torch.distributions import Distribution

from .inference import interp_shape, calc_grad_hesse

# export
def calc_nll(s_true:float, b_true:float, mu:Tensor, f_s_nom:Tensor, f_b_nom:Tensor,
             shape_alpha:Optional[Tensor]=None, s_norm_alpha:Optional[Tensor]=None, b_norm_alpha:Optional[Tensor]=None,
             f_s_up:Optional[Tensor]=None, f_s_dw:Optional[Tensor]=None,
             f_b_up:Optional[Tensor]=None, f_b_dw:Optional[Tensor]=None,
             s_norm_aux:Optional[Distribution]=None, b_norm_aux:Optional[Distribution]=None, shape_aux:Optional[List[Distribution]]=None) -> Tensor:
    r'''Compute negative log-likelihood for specified parameters.'''
    #  Adjust expectation by nuisances
    f_s = interp_shape(shape_alpha, f_s_nom, f_s_up, f_s_dw) if shape_alpha is not None and f_s_up is not None else f_s_nom
    f_b = interp_shape(shape_alpha, f_b_nom, f_b_up, f_b_dw) if shape_alpha is not None and f_b_up is not None  else f_b_nom
    s_exp = mu    +s_norm_alpha.sum() if s_norm_alpha is not None else mu
    b_exp = b_true+b_norm_alpha.sum() if b_norm_alpha is not None else b_true
    #  Compute NLL
    t_exp = (s_exp*f_s)+(b_exp*f_b)
    asimov = (s_true*f_s_nom)+(b_true*f_b_nom)
    nll = -torch.distributions.Poisson(t_exp).log_prob(asimov).sum()
    # Constrain nuisances
    if shape_aux is not None:
        if len(shape_aux) != len(shape_alpha): raise ValueError("Number of auxillary measurements must match the number of nuisance parameters.\
                                                           Pass `None`s for unconstrained nuisances.")
        for a,x in zip(shape_alpha, shape_aux):
            if x is not None: nll = nll-x.log_prob(a)
    if b_norm_alpha is not None:
        for a,x in zip(b_norm_alpha, b_norm_aux): nll = nll-x.log_prob(a)
    if s_norm_alpha is not None:
        for a,x in zip(s_norm_alpha, s_norm_aux): nll = nll-x.log_prob(a)
    return nll

#export
def calc_profile(f_s_nom:Tensor, f_b_nom:Tensor, n_obs:int, mu_scan:Tensor, mu_true:int,
                 f_s_up:Optional[Tensor]=None, f_s_dw:Optional[Tensor]=None,
                 f_b_up:Optional[Tensor]=None, f_b_dw:Optional[Tensor]=None,
                 shape_aux:Optional[List[Distribution]]=None,
                 s_norm_aux:Optional[List[Distribution]]=None, b_norm_aux:Optional[List[Distribution]]=None, nonaux_b_norm:bool=False,
                 n_steps:int=100, lr:float=0.1,  verbose:bool=True) -> Tensor:
    r'''Compute profile likelihoods for range of mu values, optimising on full hessian.
    Ideally mu-values should be computed in parallel, but batch-wise hessian in PyTorch is difficult.'''
    for f in [f_s_nom, f_s_up, f_s_dw, f_b_nom, f_b_up, f_b_dw]:  # Ensure correct dimensions
        if f is not None and len(f.shape) < 2: f.unsqueeze_(0)
    # Cases where nuisance only causes up xor down variation
    if (f_s_up is None and f_s_dw is not None): f_s_up = torch.repeat_interleave(f_s_nom, repeats=len(f_s_dw), dim=0)
    if (f_s_dw is None and f_s_up is not None): f_s_dw = torch.repeat_interleave(f_s_nom, repeats=len(f_s_up), dim=0)
    if (f_b_up is None and f_b_dw is not None): f_b_up = torch.repeat_interleave(f_s_nom, repeats=len(f_b_dw), dim=0)
    if (f_b_dw is None and f_b_up is not None): f_b_dw = torch.repeat_interleave(f_s_nom, repeats=len(f_b_up), dim=0)
    if f_s_up is not None and f_b_up is not None and len(f_s_up) != len(f_b_up):
        raise ValueError("Shape variations for signal & background must have the same number of variations. \
                          Please enter the nominal templates for nuisances that only affect either signal of background.")
    # Norm uncertainties
    if s_norm_aux is None: s_norm_aux = []
    if b_norm_aux is None: b_norm_aux = []
    # Compute nuisance indeces
    n_alpha = len(f_b_up) if f_b_up is not None else 0
    shape_idxs = list(range(n_alpha))
    s_norm_idxs = list(range(n_alpha, n_alpha+len(s_norm_aux)))
    n_alpha += len(s_norm_aux)
    b_norm_idxs = list(range(n_alpha, n_alpha+len(b_norm_aux)+nonaux_b_norm))
    n_alpha += len(b_norm_aux)+nonaux_b_norm

    b_true = n_obs-mu_true
    if n_alpha > 0:
        nlls = []
        get_nll = partialler(calc_nll, s_true=mu_true, b_true=b_true,
                         f_s_nom=f_s_nom, f_s_up=f_s_up, f_s_dw=f_s_dw,
                         f_b_nom=f_b_nom, f_b_up=f_b_up, f_b_dw=f_b_dw,
                         s_norm_aux=s_norm_aux, b_norm_aux=b_norm_aux, shape_aux=shape_aux)
        for mu in progress_bar(mu_scan, display=verbose):  # TODO: Fix this to run mu-scan in parallel
                alpha = torch.zeros((n_alpha), requires_grad=True, device=f_b_nom.device)
                for i in range(n_steps):  # Newton optimise nuisances
                    nll = get_nll(shape_alpha=alpha[shape_idxs], mu=mu, s_norm_alpha=alpha[s_norm_idxs], b_norm_alpha=alpha[b_norm_idxs])
                    grad, hesse = calc_grad_hesse(nll, alpha, create_graph=False)
                    step = lr*grad.detach()@torch.inverse(hesse)
                    step = torch.clamp(step, -100, 100)
                    alpha = alpha-step
                nlls.append(get_nll(shape_alpha=alpha[shape_idxs], mu=mu, s_norm_alpha=alpha[s_norm_idxs], b_norm_alpha=alpha[b_norm_idxs]).detach())
                if alpha[shape_idxs].abs().max() > 1: print(f'Linear regime: Mu {mu.data.item()}, shape nuisances {alpha[shape_idxs].data}')
        nlls = torch.stack(nlls)
    else:
        nlls = -torch.distributions.Poisson((mu_scan.reshape((-1,1))*f_s_nom)+(b_true*f_b)).log_prob((mu_true*f_s_nom)+(b_true*f_b)).sum(1)
    return nlls

# Cell
class AbsInferno(AbsCallback):
    r'''Attempted reproduction of TF1 & TF2 INFERNO with exact effect of nuisances being passed through model'''
    def __init__(self, b_true:float, mu_true:float, n_shape_alphas:int=0, s_shape_alpha:bool=False, b_shape_alpha:bool=False, nonaux_b_norm:bool=False,
                 shape_aux:Optional[List[Distribution]]=None, b_norm_aux:Optional[List[Distribution]]=None, s_norm_aux:Optional[List[Distribution]]=None):
        super().__init__()
        store_attr()
        if len(self.shape_aux) != self.n_shape_alphas: raise ValueError("Number of auxillary measurements on shape nuisances must match the number of shape nuisance parameters")
        self.n=self.mu_true+self.b_true
        # Norm uncertainties
        if self.s_norm_aux is None: self.s_norm_aux = []
        if self.b_norm_aux is None: self.b_norm_aux = []
        # Compute nuisance indeces
        self.poi_idx = [0]
        self.shape_idxs = list(range(1,self.n_shape_alphas+1))
        self.n_alpha = 1+self.n_shape_alphas
        self.s_norm_idxs = list(range(self.n_alpha, self.n_alpha+len(self.s_norm_aux)))
        self.n_alpha += len(self.s_norm_aux)
        self.b_norm_idxs = list(range(self.n_alpha, self.n_alpha+len(self.b_norm_aux)+self.nonaux_b_norm))
        self.n_alpha += len(self.b_norm_aux)+self.nonaux_b_norm

    def on_train_begin(self) -> None:
        self.wrapper.loss_func = None  # Ensure loss function is skipped, callback computes loss value in `on_forwards_end`
        for c in self.wrapper.cbs:
            if hasattr(c, 'loss_is_meaned'): c.loss_is_meaned = False  # Ensure that average losses are correct
        self.alpha = torch.zeros((self.n_alpha), requires_grad=True, device=self.wrapper.device)  # Nuisances set to zero (true values)
        with torch.no_grad(): self.alpha[self.poi_idx] = self.mu_true  # POI set to true value

    def on_batch_begin(self) -> None:
        self.b_mask = self.wrapper.y.squeeze() == 0
        self.aug_data(self.wrapper.x)

    def on_batch_end(self) -> None:
        self.alpha.grad.data.zero_()

    @abstractmethod
    def aug_data(self, x:Tensor) -> Tensor:
        r'''Include nuisances in input data. Overide this for specific problem.'''
        pass

    def get_inv_ikk(self, f_s:Tensor, f_b:Tensor, f_s_asimov:Tensor, f_b_asimov:Tensor) -> Tensor:
        r'''Compute full hessian at true param values'''
        # Compute nll
        s_exp = self.alpha[self.poi_idx]+self.alpha[self.s_norm_idxs].sum() if len(self.s_norm_idxs) > 0 else self.alpha[self.poi_idx]
        b_exp = self.b_true             +self.alpha[self.b_norm_idxs].sum() if len(self.b_norm_idxs) > 0 else self.b_true
        t_exp  = (s_exp*f_s)+(b_exp*f_b)
        asimov = (self.mu_true*f_s)+(self.b_true*f_b_asimov)
        nll = -torch.distributions.Poisson(t_exp).log_prob(asimov).sum()
        # Constrain nll
        if self.shape_aux is not None:
            for a,x in zip(self.alpha[self.shape_idxs], self.shape_aux):
                if x is not None: nll = nll-x.log_prob(a)
        if len(self.b_norm_idxs):
            for i,x in zip(self.b_norm_idxs, self.b_norm_aux): nll = nll-x.log_prob(self.alpha[i])
        if len(self.s_norm_idxs):
            for i,x in zip(self.s_norm_idxs, self.s_norm_aux): nll = nll-x.log_prob(self.alpha[i])
        _,h = calc_grad_hesse(nll, self.alpha, create_graph=True)
        return torch.inverse(h)[self.poi_idx,self.poi_idx]

    def on_forwards_end(self) -> None:
        r'''Compute loss and replace wrapper loss value'''
        def to_shape(p:Tensor) -> Tensor:
            f = p.sum(0)+1e-7
            return f/f.sum()

        f_s = to_shape(self.wrapper.y_pred[~self.b_mask])
        f_b = to_shape(self.wrapper.y_pred[self.b_mask])
        f_s_asimov = to_shape(self.wrapper.model(self.wrapper.x[~self.b_mask].detach())) if self.s_shape_alpha else f_s
        f_b_asimov = to_shape(self.wrapper.model(self.wrapper.x[self.b_mask].detach()))  if self.b_shape_alpha else f_b
        self.wrapper.loss_val = self.get_inv_ikk(f_s=f_s, f_b=f_b, f_s_asimov=f_s_asimov, f_b_asimov=f_b_asimov)

# Cell
class PaperInferno(AbsInferno):
    r'''Inheriting class for dealing with INFERNO paper synthetic problem'''
    def __init__(self, float_r:bool, float_l:bool, l_init:float=3, b_true:float=1000, mu_true:float=50, nonaux_b_norm:bool=False,
                 shape_aux:Optional[List[Distribution]]=None, b_norm_aux:Optional[List[Distribution]]=None, s_norm_aux:Optional[List[Distribution]]=None):
        super().__init__(b_true=b_true, mu_true=mu_true, n_shape_alphas=float_r+float_l, b_shape_alpha=True, nonaux_b_norm=nonaux_b_norm, shape_aux=shape_aux, b_norm_aux=b_norm_aux, s_norm_aux=s_norm_aux)
        self.float_r,self.float_l,self.l_init = float_r,float_l,l_init

    def aug_data(self, x:Tensor) -> None:
        if self.float_r: x[self.b_mask,0] += self.alpha[self.shape_idxs[0]]
        if self.float_l: x[self.b_mask,2] *= (self.alpha[self.shape_idxs[-1]]+self.l_init)/self.l_init

# Cell
class InfernoPred(PredHandler):
    r'''Prediction handler for hard assignments'''
    def get_preds(self) -> np.ndarray: return np.argmax(self.preds, 1)