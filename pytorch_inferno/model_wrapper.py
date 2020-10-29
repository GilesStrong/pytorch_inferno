# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/01_model_wrapper.ipynb (unless otherwise specified).

__all__ = ['ModelWrapper']

# Cell
from .callback import AbsCallback, PredHandler
from .utils import to_device, device
from .data import DataPair, WeightedDataLoader, DataSet

from typing import Optional, Union, List, Generator, Callable
from fastcore.all import store_attr, is_listy, typedispatch, Path
from fastprogress import master_bar, progress_bar
import numpy as np

from torch.tensor import Tensor
import torch
import torch.nn as nn
from torch import optim

# Cell
class ModelWrapper():
    r'''Class to handle training and prediction of NN over data, with optional callbacks. Also supports loading and saving.'''
    def __init__(self, model:nn.Module, device:torch.device=device):
        self.model,self.device = to_device(model, device),device

    def _fit_batch(self, x:Tensor, y:Tensor, w:Tensor) -> None:
        self.x,self.y,self.w = to_device(x,self.device),to_device(y,self.device),to_device(w,self.device)
        for c in self.cbs: c.on_batch_begin()
        self.y_pred = self.model(self.x)
        if self.state != 'test' and self.loss_func is not None:
            self.loss_func.weights = self.w
            self.loss_val = self.loss_func(self.y_pred, self.y)
        for c in self.cbs: c.on_forwards_end()
        if self.state != 'train': return

        self.opt.zero_grad()
        for c in self.cbs: c.on_backwards_begin()
        self.loss_val.backward()
        for c in self.cbs: c.on_backwards_end()
        self.opt.step()
        for c in self.cbs: c.on_batch_end()

    def fit(self, n_epochs:int, data:DataPair, opt:Callable[[Generator],optim.Optimizer],
            loss:Optional[Callable[[Tensor,Tensor],Tensor]], cbs:Optional[Union[AbsCallback,List[AbsCallback]]]=None) -> None:
        def fit_epoch(epoch:int) -> None:
            self.model.train()
            self.state = 'train'
            self.epoch = epoch
            for c in self.cbs: c.on_epoch_begin()
            for b in progress_bar(self.data.trn_dl, parent=self.mb): self._fit_batch(*b)
            for c in self.cbs: c.on_epoch_end()

            self.model.eval()
            self.state = 'valid'
            for c in self.cbs: c.on_epoch_begin()
            for b in progress_bar(self.data.val_dl, parent=self.mb): self._fit_batch(*b)
            for c in self.cbs: c.on_epoch_end()

        if cbs is None: cbs = []
        elif not is_listy(cbs): cbs = [cbs]
        self.cbs,self.stop,self.n_epochs = cbs,False,n_epochs
        self.data,self.loss_func,self.opt = data,loss,opt(self.model.parameters())
        for c in self.cbs: c.set_wrapper(self)
        for c in self.cbs: c.on_train_begin()
        self.mb = master_bar(range(self.n_epochs))
        for e in self.mb:
            fit_epoch(e)
            if self.stop: break
        for c in self.cbs: c.on_train_end()

    def _predict_dl(self, x:WeightedDataLoader, pred_cb:PredHandler=PredHandler(),
                cbs:Optional[Union[AbsCallback,List[AbsCallback]]]=None) -> np.ndarray:
        if cbs is None: cbs = []
        elif not is_listy(cbs): cbs = [cbs]
        cbs.append(pred_cb)
        self.cbs,self.data = cbs,x
        self.state = 'test'
        for c in self.cbs: c.set_wrapper(self)
        self.model.eval()
        for c in self.cbs: c.on_pred_begin()
        for b in progress_bar(self.data): self._fit_batch(*b)
        for c in self.cbs: c.on_pred_end()
        return pred_cb.get_preds()

    def _predict_array(self, x:Union[Tensor,np.ndarray], pred_cb:PredHandler=PredHandler(),
                   cbs:Optional[Union[AbsCallback,List[AbsCallback]]]=None) -> np.ndarray:
        return self._predict_dl(WeightedDataLoader(DataSet(x), batch_size=len(x)), pred_cb, cbs)

    def predict(self, x:Union[Tensor,np.ndarray], pred_cb:PredHandler=PredHandler(),
                cbs:Optional[Union[AbsCallback,List[AbsCallback]]]=None) -> np.ndarray:
        if isinstance(x, WeightedDataLoader): return self._predict_dl(x, pred_cb, cbs)
        else:                                 return self._predict_array(x, pred_cb, cbs)

    def save(self, fname:Union[Path,str]) -> None: torch.save({'model':self.model.state_dict()}, fname)

    def load(self, fname:Union[Path,str]) -> None:
        state = torch.load(fname, map_location='cpu')
        self.model.load_state_dict(state['model'])
        self.model = to_device(self.model, device)