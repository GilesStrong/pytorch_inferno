# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03_callback.ipynb (unless otherwise specified).

__all__ = ['AbsCallback', 'LossTracker', 'EarlyStopping', 'SaveBest', 'PredHandler', 'PaperSystMod', 'GradClip']

# Cell
from .utils import to_np

from typing import Optional, Callable, Union
from abc import ABC
from fastcore.all import store_attr, Path
import math
import numpy as np

from torch import Tensor
from torch import nn

# Cell
class AbsCallback(ABC):
    r'''Abstract callback passing though all action points and indicating where callbacks can affect the model.
    See `ModelWrapper` etc. to see where exactly these action points are called.'''
    def __init__(self): pass
    def set_wrapper(self, wrapper) -> None: self.wrapper = wrapper
    def on_train_begin(self) -> None: pass
    def on_train_end(self) -> None: pass

    def on_epoch_begin(self) -> None: pass
    def on_epoch_end(self) -> None:   pass

    def on_batch_begin(self) -> None: pass
    def on_batch_end(self) -> None:   pass

    def on_forwards_end(self) -> None: pass

    def on_backwards_begin(self) -> None: pass
    def on_backwards_end(self) -> None:   pass

    def on_pred_begin(self) -> None: pass
    def on_pred_end(self) -> None:   pass

# Cell
class LossTracker(AbsCallback):
    r'''Tracks training and validation losses during training.
    Losses are assumed to be averaged and will be re-averaged over the epoch unless `loss_is_meaned` is false.'''
    def __init__(self, loss_is_meaned:bool=True):
        store_attr()
        self.reset()

    def reset(self) -> None: self.losses,self.epoch = {'trn':[], 'val':[]},0
    def on_train_begin(self) -> None: self.reset()
    def on_epoch_begin(self) -> None: self.loss,self.cnt = 0,0

    def on_epoch_end(self) -> None:
        if self.wrapper.state == 'train':
            self.losses['trn'].append(self.loss/self.cnt)
        else:
            self.losses['val'].append(self.loss/self.cnt)
            self.epoch += 1
            print(f'{self.epoch}: Train={self.losses["trn"][-1]} Valid={self.losses["val"][-1]}')

    def on_forwards_end(self) -> None:
        sz = len(self.wrapper.x) if self.loss_is_meaned else 1
        self.loss += self.wrapper.loss_val.data.item()*sz
        self.cnt += sz

# Cell
class EarlyStopping(AbsCallback):
    r'''Tracks validation loss during training and terminates training if loss doesn't decrease after `patience` number of epochs.
    Losses are assumed to be averaged and will be re-averaged over the epoch unless `loss_is_meaned` is false.'''
    def __init__(self, patience:int, loss_is_meaned:bool=True):
        store_attr()
        self.reset()

    def reset(self) -> None: self.epochs,self.min_loss = 0,math.inf
    def on_train_begin(self) -> None: self.reset()
    def on_epoch_begin(self) -> None: self.loss,self.cnt = 0,0

    def on_forwards_end(self) -> None:
        if self.wrapper.state == 'valid':
            sz = len(self.wrapper.x) if self.loss_is_meaned else 1
            self.loss += self.wrapper.loss_val.data.item()*sz
            self.cnt += sz

    def on_epoch_end(self) -> None:
        if self.wrapper.state == 'valid':
            loss = self.loss/self.cnt
            if loss < self.min_loss:
                self.min_loss = loss
                self.epochs = 0
            else:
                self.epochs += 1
            if self.epochs >= self.patience:
                print('Early stopping')
                self.wrapper.stop = True

# Cell
class SaveBest(AbsCallback):
    r'''Tracks validation loss during training and automatically saves a copy of the weights to indicated file whenever validation loss decreases.
    Losses are assumed to be averaged and will be re-averaged over the epoch unless `loss_is_meaned` is false.'''
    def __init__(self, savename:Union[str,Path], auto_reload:bool=True, loss_is_meaned:bool=True):
        store_attr()
        self.reset()

    def reset(self) -> None: self.min_loss = math.inf
    def on_train_begin(self) -> None: self.reset()
    def on_epoch_begin(self) -> None: self.loss,self.cnt = 0,0

    def on_forwards_end(self) -> None:
        if self.wrapper.state == 'valid':
            sz = len(self.wrapper.x) if self.loss_is_meaned else 1
            self.loss += self.wrapper.loss_val.data.item()*sz
            self.cnt += sz

    def on_epoch_end(self) -> None:
        if self.wrapper.state == 'valid':
            loss = self.loss/self.cnt
            if loss < self.min_loss:
                self.min_loss = loss
                self.wrapper.save(self.savename)

    def on_train_end(self) -> None:
        print(f'Loading best model with loss {self.min_loss}')
        self.wrapper.load(self.savename)

# Cell
class PredHandler(AbsCallback):
    r'''Default callback for predictions. Collects predictions over batches and returns them as stacked array'''
    def __init__(self): self.reset()
    def reset(self) -> None: self.preds = []
    def on_pred_begin(self) -> None: self.reset()
    def on_pred_end(self) -> None: self.preds = np.vstack(self.preds)
    def get_preds(self) -> np.ndarray: return self.preds
    def on_forwards_end(self) -> None:
        if self.wrapper.state == 'test': self.preds.append(to_np(self.wrapper.y_pred))

# Cell
class PaperSystMod(AbsCallback):
    r'''Prediction callback for modifying input data from INFERNO paper according to specified nuisances.'''
    def __init__(self, r:float=0, l:float=3): store_attr()
    def on_batch_begin(self) -> None:
        self.wrapper.x[:,0] += self.r
        self.wrapper.x[:,2] *= self.l/3

# Cell
class GradClip(AbsCallback):
    r'''Training callback implementing gradient clipping'''
    def __init__(self, clip:float, clip_norm:bool=True):
        self.clip = clip
        self.func = nn.utils.clip_grad_norm_ if clip_norm else nn.utils.clip_grad_value_

    def on_backwards_end(self) -> None:
        if self.clip > 0: self.func(self.wrapper.model.parameters(), self.clip)