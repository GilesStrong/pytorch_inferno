# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/05_plotting.ipynb (unless otherwise specified).

__all__ = ['plt_style', 'plt_sz', 'plt_cat_pal', 'plt_tk_sz', 'plt_lbl_sz', 'plt_title_sz', 'plt_leg_sz', 'plot_preds',
           'plot_likelihood']

# Cell
from .inference import get_likelihood_width

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Optional, Union, List, Dict
import numpy as np

from torch import Tensor

from fastcore.all import is_listy

# Cell
plt_style    = {'style':'whitegrid', 'rc':{'patch.edgecolor':'none'}}
plt_sz       = 8
plt_cat_pal  = 'tab10'
plt_tk_sz    = 16
plt_lbl_sz   = 24
plt_title_sz = 26
plt_leg_sz   = 16

# Cell
def plot_preds(df:pd.DataFrame, bin_edges:np.ndarray=np.linspace(0.,1.,11), pred_names:Union[List[str],str]='pred') -> None:
    r'''Plots predictions and background variations.
    TODO: Gnerelaise this to plllot signal variations'''
    if not is_listy(pred_names): pred_names = [pred_names]
    with sns.axes_style(**plt_style), sns.color_palette(plt_cat_pal) as palette:
        plt.figure(figsize=(plt_sz*16/9, plt_sz))
        for t,n in ((1,'Signal'),(0,'Background')):
            cut = (df['gen_target'] == t)
            hist_kws = {} if 'gen_weight' not in df.columns else {'weights':df.loc[cut, 'gen_weight']}
            if t == 0:
                for i,p in enumerate(pred_names):
                    d = df.loc[cut, p]
                    sns.distplot(d, bins=bin_edges, label=f'{n}_{p}' if i > 0 else n, norm_hist=True, kde=False,
                                 hist_kws={'fill':not i > 0, 'edgecolor':palette[i+1] if i > 0 else None,
                                           'linewidth':2 if i > 0 else 1, **hist_kws})
            else:
                sns.distplot(df.loc[cut, pred_names[0]], bins=bin_edges, label=f'{n}', hist_kws=hist_kws, norm_hist=True, kde=False)
        plt.legend(fontsize=plt_leg_sz)
        plt.xlabel("Class prediction", fontsize=plt_lbl_sz)
        plt.ylabel(r"$\frac{1}{N}\ \frac{dN}{dp}$", fontsize=plt_lbl_sz)
        plt.xticks(fontsize=plt_tk_sz)
        plt.yticks(fontsize=plt_tk_sz)
        plt.show()

# Cell
def plot_likelihood(nlls:Union[Dict[str,Tensor],List[Tensor]], mu_scan:Tensor, labels:Optional[List[str]]=None) -> List[float]:
    if isinstance(nlls, dict):
        labels = list(nlls.keys())
        nlls = [nlls[k] for k in nlls]
    if not is_listy(nlls): nlls = [nlls]
    if labels is None: labels = ['' for _ in nlls]
    elif not is_listy(labels): labels = [labels]

    widths = []
    with sns.axes_style(**plt_style), sns.color_palette(plt_cat_pal):
        plt.figure(figsize=(plt_sz*16/9, plt_sz))
        plt.plot(mu_scan,0.5*np.ones_like(mu_scan), linestyle='--', color='black')
        for nll,lbl in zip(nlls,labels):
            m = nll == nll
            dnll = nll-nll[m].min()  # Shift nll to zero
            try:               widths.append(get_likelihood_width(nll, mu_scan=mu_scan))
            except ValueError: widths.append(np.NaN)
            plt.plot(mu_scan[m], dnll[m], label=fr'{lbl} $\mu={mu_scan[np.argmin(nll[m])]}\pm {widths[-1]:.2f}$')
        plt.legend(fontsize=plt_leg_sz)
        plt.xlabel(r"$\mu$", fontsize=plt_lbl_sz)
        plt.ylabel(r"Profiled $\Delta\left(-L\right)$", fontsize=plt_lbl_sz)
        plt.xticks(fontsize=plt_tk_sz)
        plt.yticks(fontsize=plt_tk_sz)
        plt.show()

        return widths