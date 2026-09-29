---
title: The test vectors
parent: Root Solver
nav_order: 2
has_children: false
---

# Stage 2: The test vectors

A **test vector** is one complete problem for the hardware: the inputs to hand
the kernel, and the answer the golden model says it should give back. In this lab
each vector is one row of `vectors/tv_python.csv`:

| Column | Meaning |
| --- | --- |
| `a0`, `a1`, `a2` | The coefficients |
| `x0` | The starting point |
| `tol`, `max_iter`, `step` | The iteration settings |
| `x`, `fx`, `niter` | What your `fsolve()` returned |

The first seven columns are the kernel's inputs, in the order `fsolve()` takes
them. The testbench reads the file **by position**, so the order is fixed; it is
given as `VECTOR_COLUMNS` at the top of `fsolve.py`.

## What to write

One function in `fsolve.py`:

| Function | Returns |
| --- | --- |
| `make_vectors(nvec, seed)` | A DataFrame with `nvec` rows and exactly the columns in `VECTOR_COLUMNS` |

For each vector, draw a random problem from the ranges at the top of `fsolve.py`,
solve it with your `fsolve()`, and record the inputs beside the answer. The one
draw that needs thought is `a1`:

```python
a2 = rng.uniform(A2_LO, A2_HI)
a1 = a2**2 / 3 + rng.uniform(A1_MARGIN_LO, A1_MARGIN_HI)
```

Draw `a2` first, because the bound on `a1` depends on it. That margin above
`a2²/3` is what keeps `f` increasing, so that every vector is a problem the
iteration can actually solve — see [the golden model](./python.md#why-it-converges).
Draw `a1` independently and some of your vectors will have three roots, or a
flat spot, and the iteration will stall or wander.

`step` is drawn too, rather than fixed, so the vectors cover a range of
convergence rates — your model will take anywhere from about 25 to 160 updates.
`tol` and `max_iter` are the same for every vector.

### Round the inputs to float32 before you solve

The testbench reads each input into a C++ `float`. If the file held a `float64`
value, the kernel would be handed a slightly different number from the one your
model solved, and the two would disagree for a reason that has nothing to do
with either of them. So round each input once, with `float(np.float32(v))`, and
use the rounded value both in the file and in the call to `fsolve()`.

## Running the step

```bash
python rootsolve_build.py --through vectors
```

```
vectors:
    vectors\tv_python.csv
    results\vectors\status.json
    RUNNING...
    wrote 20 vectors to vectors\tv_python.csv; your model took 25 to 157 updates
    PASSED
```

The build decides how many vectors (`nvec = 20`) and the seed, so everyone's
vectors are drawn the same way and a score is reproducible.

This step is **not scored on its own**. The vectors are what the kernel is
checked against in [stage 4](./evaluate.md), and that is where they are
examined. The comparison there scores zero, with the reason, if the vectors are
not real problems:

* fewer than 20 of them;
* a vector with `a1 <= a2²/3`;
* a vector your model did not solve, `|fx| >= tol`;
* vectors that are all the same, or that took no updates.

The last one is not hypothetical. An unfinished `fsolve()` returns `x0` after
zero updates, and an unfinished kernel does the same — so the two agree
perfectly while implementing nothing. Agreement is only evidence when there is
something to agree about.

If `make_vectors()` raises, the step still finishes: it writes an empty vector
file and records the error, which [stage 4](./evaluate.md) then reports.

----

Go to [the Vitis kernel](./vitis.md).
