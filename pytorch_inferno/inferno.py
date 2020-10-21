# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/07_inferno.ipynb (unless otherwise specified).

__all__ = ['VariableSoftmax', 'AbsInferno', 'PaperInferno', 'InfernoPred']

# Cell
class VariableSoftmax(nn.Softmax):
    def __init__(self, temp:float=1, dim:int=-1):
        super().__init__(dim=dim)
        self.temp = temp

    def forward(self, x:Tensor) -> Tensor: return super().forward(x/self.temp)

# Cell
class AbsInferno(AbsCallback):
    def __init__(self, n:int, mu_scan:Tensor, true_mu:float, n_steps:int=100, lr:float=0.1):
        super().__init__()
        store_attr()

    def on_train_begin(self) -> None:
        r'''
        Fake loss function, callback computes loss in `on_forwards_end`
        '''
        self.wrapper.loss_func = lambda x,y: None
        for c in self.wrapper.cbs:
            if hasattr(c, 'loss_is_meaned'): c.loss_is_meaned = False  # Ensure that average losses are correct

    @staticmethod
    def _to_shape(p:Tensor) -> Tensor:
        f = p.sum(0)+1e-7
        return f/f.sum()

    @abstractmethod
    def _get_up_down(self, x:Tensor) -> Tuple[Tensor,Tensor]: pass

    def get_ikk(self, f_s:Tensor, f_b_nom:Tensor, f_b_up:Tensor, f_b_dw:Tensor) -> Tensor:
        alpha = torch.zeros((1,f_b_up.shape[0]), requires_grad=True, device=f_b_nom.device)
        mu = torch.tensor([float(self.true_mu)], requires_grad=True, device=f_b_nom.device)
        get_nll = partialler(calc_nll, s_true=self.true_mu, b_true=self.n-self.true_mu,
                             f_s=f_s, f_b_nom=f_b_nom[None,:], f_b_up=f_b_up, f_b_dw=f_b_dw)
        for i in range(self.n_steps):  # Newton optimise nuisances & mu
            nll = get_nll(s_exp=mu, alpha=alpha)
            for p in [alpha, mu]:
                grad, hesse = calc_grad_hesse(nll, p)
                step = torch.clamp(self.lr*grad.detach()/(hesse+1e-7), -100, 100)
                p = p-step
        return hesse

    def on_forwards_end(self) -> None:
        b = self.wrapper.y.squeeze()==0
        f_s = self._to_shape(self.wrapper.y_pred[~b])
        f_b = self._to_shape(self.wrapper.y_pred[b])
        f_b_up,f_b_dw = self._get_up_down(self.wrapper.x[b])
        self.wrapper.loss_val = 1/self.get_ikk(f_s=f_s, f_b_nom=f_b, f_b_up=f_b_up, f_b_dw=f_b_dw)

# Cell
class PaperInferno(AbsInferno):
    def __init__(self, r_mods:Optional[Tuple[float,float]]=(-0.2,0.2), l_mods:Optional[Tuple[float,float]]=(2.5,3.5), l_init:float=3,
                 n:int=1050, mu_scan:Tensor=torch.linspace(20,80,61), true_mu:int=50, n_steps:int=100, lr:float=0.1):
        super().__init__(n=n, mu_scan=mu_scan, true_mu=true_mu, n_steps=n_steps, lr=lr)
        if l_mods is not None: l_mods = (l_mods[0]/l_init, l_mods[1]/l_init)
        self.r_mods,self.l_mods = r_mods,l_mods

    def _get_up_down(self, x:Tensor) -> Tuple[Tensor,Tensor]:
        with torch.no_grad():
            u,d = [],[]
            if r_mods is not None
                x[:,0] += self.r_mods[0]
                d.append(self._to_shape(self.wrapper.model(x)))
                x[:,0] += self.r_mods[1]-self.r_mods[0]
                u.append(self._to_shape(self.wrapper.model(x)))
                x[:,0] -= self.r_mods[1]
            if l_mods is not None
                x[:,2] *= self.l_mods[0]
                d.append(self._to_shape(self.wrapper.model(x)))
                x[:,2] *= self.l_mods[1]/self.l_mods[0]
                u.append(self._to_shape(self.wrapper.model(x)))
                x[:,2] /= self.l_mods[1]
            return torch.stack(u),torch.stack(d)

# Cell
class InfernoPred(PredHandler):
    def get_preds(self) -> np.ndarray: return np.argmax(self.preds, 1)/len(self.wrapper.model[-2].weight)