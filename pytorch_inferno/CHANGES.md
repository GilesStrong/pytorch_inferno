# Targeting v0.2.1

## Important changes

## Breaking

## Additions

## Removals

## Fixes

- Undefined `wgt_scale` removed from `plot_preds`
- Bug in INFERNO when None was passed as `shape_aux` argument 

## Changes

## Depreciations

## Comments

# v0.2.0

## Important changes

- APIs and scope of INFERNO and inference methods changed to be more general, allowing:
    - shape systematics for signal
    - multiple constrained rate nuisances for signal and background
    - Auxiliary measurements of rate parameters should now be provided centred at zero, rather than the rate.
- Module layout changed

## Breaking

- APIs and scope of INFERNO and inference methods changed to be more general, allowing:
    - shape systematics for signal
    - multiple constrained rate nuisances for signal and background
    - Auxiliary measurements of rate parameters should now be provided centred at zero, rather than the rate.
- Module layout changed

## Additions

- APIs and scope of INFERNO and inference methods changed to be more general, allowing:
    - shape systematics for signal
    - multiple constrained rate nuisances for signal and background
    - Auxiliary measurements of rate parameters should now be provided centred at zero, rather than the rate.
- Inference can now better handle cases where no systematics are present

## Removals

## Fixes

- Set `validate_args` in `Poisson`s to False to ensure compatibility with `torch v1.8`

## Changes

## Depreciations

## Comments
