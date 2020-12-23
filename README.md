[![pypi pytorch_inferno version](https://img.shields.io/pypi/v/pytorch_inferno.svg)](https://pypi.python.org/pypi/pytorch_inferno)
[![pytorch_inferno python compatibility](https://img.shields.io/pypi/pyversions/pytorch_inferno.svg)](https://pypi.python.org/pypi/pytorch_inferno) [![pytorch_inferno license](https://img.shields.io/pypi/l/pytorch_inferno.svg)](https://pypi.python.org/pypi/pytorch_inferno)

# PyTorch INFERNO

Documentation: https://gilesstrong.github.io/pytorch_inferno/

### User install
```
pip install pytorch_inferno
```

### Developer install
```
[install torch>=1.7 according to CUDA version]
pip install nbdev fastcore numpy pandas fastprogress matplotlib>=3.0.0 seaborn scipy
git clone git@github.com:GilesStrong/pytorch_inferno.git
cd pytorch_inferno
pip install -e .
nbdev_install_git_hooks
```

## Overview
Library developed and testing in `nbs` directory.

Experiments run in `experiments` directory.

Use `nbdev_build_lib` to export code to library located in `pytorch_inferno`. This overwrites any changes in `pytorch_inferno`, i.e. only edit the notebooks.

## Results
![title](nbs/imgs/results.png)

https://docs.google.com/spreadsheets/d/1feR_prOMzlNAfuMtB7JyhSVaTM32wvdnt72aqcWzyy4/edit?usp=sharing
