---
title: Root Solver
parent: Labs
nav_order: 4
has_children: true
---

# Unit 4 Lab: A Root Solver in Vitis HLS

## Overview

In this lab you'll build a hardware accelerator that finds a **root** of a
monic cubic

```python
    f(x) = a0 + a1*x + a2*x**2 + x**3
```

meaning an `x` with `f(x) ≈ 0`. The method is the simplest iteration there is:

```python
    x[k+1] = x[k] - step * f(x[k])
```

repeated until `|f(x)| < tol`, or until `max_iter` updates have been made. When
`f` is increasing, `f(x) > 0` means `x` is to the right of the root and the
update moves it left; `f(x) < 0` moves it right. Either way `x` closes in on the
root, provided `step` is small enough not to jump over it.

You will write this twice: first as a Python **golden model**, then as a
**Vitis HLS kernel** — a C++ function that Vitis turns into hardware with an
AXI4-Lite register map. The processor writes the coefficients, the starting
point and the iteration settings into registers, starts the kernel, and reads
back `x`, `f(x)` and the number of updates it took.

![Two plots of one run of the solver. On the left, x rises from 0 and levels off at the root, 0.5, after about 20 iterations. On the right, |f(x)| on a log scale falls in a straight line from 1 to just under the tolerance of 1e-5, reached at iteration 39.](./images/fsolve_hist.png)

Unlike the [cubic lab](../cubic/), everything here is **floating point** —
single precision, `float` in C++ and `np.float32` in Python. That changes what
"the hardware matches the model" means, and working that out is part of the lab.

## Learning Objectives

In going through the lab, you will learn how to:

* Build a floating-point **golden model** of an iterative algorithm, and check
  that it converges
* Generate **test vectors** from the model, for the hardware to be checked against
* Write a **Vitis HLS kernel** with an **AXI4-Lite interface** and a
  data-dependent **loop**
* Write a **testbench** that drives the kernel from a vector file, and run it in
  **C simulation** and **RTL co-simulation**
* **Compare** the kernel's answers with the model's, with tolerances you can
  justify

The last point is the one to think about. Two floating-point computations of
the same thing are not guaranteed to agree to the last bit, so "equal" is the
wrong test. "Close" is not good enough either — a kernel that stops ten updates
early can be close. You will write the comparison yourself, and the lab checks
both that your comparison is right and that your kernel passes it.

## Files

The files for the lab can be found in the hwdesign github repo

```
hwdesign/
└── labs/
    └── rootsolve/
        ├── rootsolve_build.py      # Runs the build steps and scores them
        ├── run.tcl                 # The Vitis HLS script, one stage per run
        ├── fsolve.h                # The kernel's interface
        ├── partial/
        │   ├── fsolve.py           # Python golden model and test vectors
        │   ├── fsolve.cpp          # The Vitis HLS kernel
        │   ├── tb_fsolve.cpp       # The testbench
        │   └── fsolve_eval.py      # Your comparison of kernel and model
        ├── vectors/                # These directories are created by the build:
        ├── results/                #   generated data, figures, logs and scores.
        ├── eval/                   #   None of it is edited by hand, and none of
        ├── fsolve_proj/            #   it is submitted except the zip
        └── submission/
```

The four files in the `partial` directory are not complete. You will finish them
as part of the lab, and each has `TODO` comments marking what to write:

| File | What you write |
| --- | --- |
| `fsolve.py` | The loop in `fsolve()`, `plot_convergence()`, and `make_vectors()` — the golden model and the test vectors it produces |
| `fsolve.cpp` | The AXI4-Lite interface pragmas and the same loop, in C++ |
| `tb_fsolve.cpp` | The call to the kernel for each vector, and the line that records what came back |
| `fsolve_eval.py` | `vector_errors()` and `vector_matches()` — how you decide the kernel is right |

`fsolve.h`, `run.tcl` and `rootsolve_build.py` are given whole.

**You do not need to copy anything by hand.** The first time you run the build it
copies each file out of `partial/` into the lab directory and tells you it has
done so:

```
fsolve_py_src:
    STARTED fsolve.py from partial\fsolve.py — edit fsolve.py, not the copy in partial/.
```

Edit the copies at the top level, *not* the ones in `partial/`. The build never
overwrites your work once the top-level files exist — not even with `--force`.

## Build steps

The lab uses the Waveflow package's
[Build DAG](https://sdrangan.github.io/waveflow/docs/guide/build/), as the
[cubic lab](../cubic/) and the [scalar_fun demo](../../demos/procif/) do. You
complete one part of the design, run the step that checks it, and move on.

| Stage | Command | What it does |
| --- | --- | --- |
| 1. `pysim` | `python rootsolve_build.py --through pysim` | Runs your `fsolve()` on the lab's own problems. **Scored:** does it converge, by the update rule, stopping where it should? |
| 2. `vectors` | `python rootsolve_build.py --through vectors` | Runs your `make_vectors()` and writes `vectors/tv_python.csv` |
| 3. `csim` | `python rootsolve_build.py --through csim` | Runs your testbench against your kernel in C simulation |
| &nbsp;&nbsp;&nbsp;`csynth` | `python rootsolve_build.py --through csynth` | Synthesizes the kernel to RTL |
| &nbsp;&nbsp;&nbsp;`cosim` | `python rootsolve_build.py --through cosim` | Runs the same testbench against the RTL |
| 4. `eval` | `python rootsolve_build.py --through eval` | Runs your comparison. **Scored:** is your comparison right, and does the kernel pass it? |
| `submit` | `python rootsolve_build.py` | Collects the scores and builds the Gradescope zip |

Only `pysim` and `eval` carry points. The steps between them are scored through
`eval`: a kernel that does not compile, or vectors that are not real problems,
show up there as a zero with the reason attached.

None of the steps stops the build when it fails. A failed step records what went
wrong, the steps after it report it, and the next build tries it again — so you
always get a submission zip, even for an unfinished lab.

The full set of commands:

```bash
python rootsolve_build.py --list-steps-verbose   # what the steps are
python rootsolve_build.py --through pysim        # 1. the golden model, scored
python rootsolve_build.py --through vectors      # 2. the test vectors
python rootsolve_build.py --through csim         # 3. the kernel, in C simulation
python rootsolve_build.py --through cosim        #    ... and as RTL
python rootsolve_build.py --through eval         # 4. the comparison, scored
python rootsolve_build.py                        # everything, then the submission zip
python rootsolve_build.py --grades               # your scores, without rebuilding
```

The build only redoes what changed. Edit `tb_fsolve.cpp` and the three Vitis
steps and `eval` re-run; edit only `fsolve_eval.py` and just `eval` does. Change
nothing and every step reports `UP-TO-DATE`.

## Pages

* [Stage 1: the golden model](./python.md)
* [Stage 2: the test vectors](./vectors.md)
* [Stage 3: the Vitis kernel](./vitis.md)
* [Stage 4: comparing kernel and model](./evaluate.md)
* [Grading and submission](./submit.md)

The Vitis flow here — a hand-written kernel, testbench and `run.tcl`, run one
stage at a time by a build script — is the one the
[scalar_fun demo](../../demos/procif/) walks through in detail. If AXI4-Lite or
the difference between C simulation and co-simulation is unfamiliar, read that
first.

----

Go to [the golden model](./python.md).
