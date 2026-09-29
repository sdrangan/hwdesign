---
title: Comparing kernel and model
parent: Root Solver
nav_order: 4
has_children: false
---

# Stage 4: Comparing the kernel with the model

You have two files that should say the same thing: `vectors/tv_python.csv`, what
your model says each vector's answer is, and `vectors/tv_csim.csv` (or
`tv_cosim.csv`), what the kernel said. This stage decides whether they agree —
and you write the code that decides it.

## Why not just test for equality

The kernel and the model compute in the same precision, and if they evaluate the
polynomial in the same order they often *do* agree to the last bit. But nothing
guarantees it. A synthesized floating-point core may round differently from the
CPU where the C standard leaves it free to, and a kernel that evaluates `f` by
Horner's rule instead is not wrong, just different in the last bit. Equality
would fail a correct kernel.

"Close" is not good enough either. A kernel that stops ten updates early can
return an `x` close to the model's while not having converged at all.

What *is* guaranteed is weaker, and it has three parts:

* **The kernel converged:** `|fx| < tol` at the `x` it returned. This is checked
  on the kernel's own `fx` — a root estimate near the model's that did not
  converge is a kernel that got lucky.
* **It found the same root**, to within `xtol`. Both answers satisfy
  `|f(x)| < tol`, so each is within about `tol / f'(root)` of the true root. In
  this lab's family of problems `f' ≥ 0.5` at every root, so the two answers are
  within `4e-5` of each other. The lab uses `xtol = 1e-4`.
* **It took about as many updates**, to within `niter_tol`. Near the end of a slow
  run, `|f(x)|` shrinks by only a few percent per update, and a last-bit
  difference in `f` is about the same size — so the update at which `|f|` crosses
  `tol` can move by one or two. The lab uses `niter_tol = 5`. A difference of
  fifty is not rounding; it is a different loop.

## What to write

Two functions in `fsolve_eval.py`:

| Function | Returns |
| --- | --- |
| `vector_errors(golden, dut)` | A DataFrame with columns `x_err`, `fx_err`, `niter_err`: the absolute difference between model and kernel, per vector |
| `vector_matches(golden, dut, xtol, niter_tol)` | A boolean array: which vectors the kernel got right, by the three conditions above |

`golden` is the vector file and `dut` is the testbench's output, read with
`pd.read_csv`. They have the same columns and the same rows in the same order, so
`golden["x"] - dut["x"]` subtracts vector by vector.

Two details:

* Take `tol` from `golden["tol"]`, not from a constant. It is a per-vector input
  like any other.
* Call your own `vector_errors()` inside `vector_matches()` rather than computing
  the differences again. If it is wrong, you want it wrong in one place.

Once the build has run the Vitis steps, you can try your code on the real output
by running the file directly:

```bash
python fsolve_eval.py
```

## Running the stage

```bash
python rootsolve_build.py --through eval
```

This runs everything before it that is out of date, including co-simulation.

```
The kernel agrees with the model: 10/10
  ✓ (2/2) Your vector_errors is correct
  ✓ (2/2) Your vector_matches is correct
  ✓ (3/3) C simulation agrees with your model
  ✓ (3/3) RTL co-simulation agrees with your model
    csim: 20 of 20 vectors match the model exactly
    cosim: 20 of 20 vectors match the model exactly
```

The first two checks and the last two ask different questions.

**Can you compare?** Your two functions are not run on your kernel's output for
these checks. They are run on a made-up pair of tables with twelve vectors, built
so that each way a vector can fail appears at least once: a root off in either
direction, an iteration count off in either direction, a kernel that did not
converge with `fx` above `tol` and one with `fx` below `-tol`, and a few that
differ by a rounding-sized amount and should still match. Your kernel, being
correct, would never exercise most of these, so testing your code on it alone
would say little.

**Does the kernel agree?** These are scored with the build's *own* comparison,
using the same rule, rather than with yours. A mistake in your comparison code
costs you the comparison points; it does not also get your kernel judged by a
broken instrument. The two lines at the end say how many vectors agreed *exactly*
— if you evaluated the polynomial in the model's order, it should be all of them.

When a vector disagrees, the check names the first one and says which condition
failed:

```
~ (2.4/3) C simulation agrees with your model — 4 of 20 vectors differ; the first
          is vector 0: the model says x = 0.553724 after 109 updates, csim says
          x = 0.5537146, fx = -2.73e-05 after 100 — the kernel did not converge
```

That kernel had its loop bound written as `i < 100` instead of `i < max_iter`.
Every vector that needed more than 100 updates stopped short — close to the root,
which is why `x` looks nearly right, but not converged, which is why the check
fails it. A test that compared `x` alone would have passed this kernel.

The C simulation and co-simulation checks are scored separately. If C simulation
passes and co-simulation does not, your C++ is right and something changed in
synthesis — look at `results/cosim/vitis.log`.

----

Go to [grading and submission](./submit.md).
