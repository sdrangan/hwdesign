"""Fit the crossbar's LUTs to its shape, and check the fit by leave-one-out.

The model, for M masters and S slaves, separately for each mode:

    LUT = a0 + a1*M + a2*S + a3*M*S

a0 is fixed cost, a1 and a2 cost per master and per slave port, a3 cost
per master/slave pair -- the term a crossbar should have and a shared bus
should not.

    python xbar_lut_fit.py              # 64-bit, from xbar_zynq7020_100mhz.csv
    python xbar_lut_fit.py --dw 32

Five shapes, four coefficients: the full fit has one degree of freedom
left, and each leave-one-out fold fits four coefficients to four points,
so it passes through them exactly and the held-out point is all that
tests it.  Only 1x2 and 2x1 have M != S, so they alone separate a1 from
a2; holding one of them out leaves a1 and a2 pinned by the other.  The
script also fits a symmetric model, LUT = b0 + b1*(M+S) + b3*M*S, with
one coefficient fewer, for comparison.
"""
from __future__ import annotations

import argparse

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import LeaveOneOut, cross_val_predict

from xbar_demo import MODE_LABEL, MODES, parse_shape, read_cached

MODELS = {
    "a0 + a1*M + a2*S + a3*M*S": (["a1 (per M)", "a2 (per S)", "a3 (per M*S)"],
                                  lambda m, s: np.column_stack([m, s, m * s])),
    "b0 + b1*(M+S) + b3*M*S": (["b1 (per port)", "b3 (per M*S)"],
                               lambda m, s: np.column_stack([m + s, m * s])),
}


def fit(shapes: list[str], luts: np.ndarray, features) -> dict:
    ms = np.array([parse_shape(s) for s in shapes], dtype=float)
    X = features(ms[:, 0], ms[:, 1])
    model = LinearRegression().fit(X, luts)
    loo = cross_val_predict(LinearRegression(), X, luts, cv=LeaveOneOut())
    # A fold whose four remaining points cannot pin the coefficients would make the held-out
    # prediction arbitrary; say so rather than print it.
    ranks = [np.linalg.matrix_rank(np.column_stack([np.ones(len(X) - 1), np.delete(X, i, 0)]))
             for i in range(len(X))]
    return {"model": model, "fitted": model.predict(X), "loo": loo, "ranks": ranks,
            "n_coef": X.shape[1] + 1}


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dw", type=int, default=64, choices=[32, 64])
    args = ap.parse_args(argv)
    rows = [r for r in read_cached() if r["dw"] == args.dw]
    if not rows:
        print(f"no {args.dw}-bit rows in the CSV")
        return 1

    for mode in MODES:
        mine = [r for r in rows if r["mode"] == mode]
        shapes = [r["shape"] for r in mine]
        luts = np.array([r["lut"] for r in mine], dtype=float)
        print(f"\n=== {MODE_LABEL[mode]}, {args.dw}-bit: LUTs "
              + ", ".join(f"{s} {int(v)}" for s, v in zip(shapes, luts)))
        for name, (labels, features) in MODELS.items():
            res = fit(shapes, luts, features)
            m = res["model"]
            coefs = "  ".join(f"{lbl} = {c:+.1f}" for lbl, c in zip(labels, m.coef_))
            print(f"\n  LUT = {name}")
            print(f"    {name[:2]} = {m.intercept_:+.1f}  {coefs}")
            print(f"    {'shape':5}  {'LUT':>5}  {'fit':>7}  {'resid':>6}  {'LOO pred':>8}  {'LOO err':>7}")
            for s, y, f, p, rk in zip(shapes, luts, res["fitted"], res["loo"], res["ranks"]):
                flag = "" if rk == res["n_coef"] else "  (fold rank-deficient)"
                print(f"    {s:5}  {y:5.0f}  {f:7.1f}  {y - f:+6.1f}  {p:8.1f}  {p - y:+7.1f}{flag}")
            dof = len(luts) - res["n_coef"]
            rmse_fit = np.sqrt(np.sum((luts - res["fitted"]) ** 2) / max(dof, 1))
            rmse_loo = np.sqrt(np.mean((luts - res["loo"]) ** 2))
            print(f"    residual std ({dof} dof) {rmse_fit:.1f} LUT;  LOOCV RMSE {rmse_loo:.1f} LUT "
                  f"({100 * rmse_loo / luts.mean():.0f}% of the mean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
