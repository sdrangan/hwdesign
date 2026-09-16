---
title: Conditional Subtraction Division
parent: Labs
nav_order: 2
has_children: true
---

# Unit 2 Lab: Division by Conditional Subtraction

## Overview

In this lab, you’ll build a small hardware block that performs division using only shifting and subtraction—exactly the kind of logic real processors fall back on when a native floating‑point divider isn’t available. Many microcontrollers, DSP engines, and custom accelerators avoid full floating‑point hardware because it’s large, slow, and power‑hungry, so they rely instead on compact integer circuits that construct the quotient bit‑by‑bit. By implementing this approach yourself, you’ll see how a division operation can be realized with simple, synthesizable building blocks and gain a clearer sense of what actually happens underneath the “/” operator that software makes look effortless.

## Learning Objectives

In going through the lab, you will learn how to:

* Build a python **golden model** for a simple mathematical hardware IP
* **Measure** the accuracy of that model, and check it against what the theory promised, before any hardware exists
* Implement a hardware module in SystemVerilog that performs an algorithm over multiple **iterations**, sequenced by a **finite state machine**
* Implement a **handshaking** protocol between a testbench and the device under test
* **Verify** the hardware against test vectors from the golden model, on both its answers and its **latency**

Unlike the [Unit 1 lab](../prng/), where the iteration happened in the
testbench, here the iteration happens in the hardware. That is what the state
machine is for, and it is why the module takes a variable number of clock cycles
to produce each answer — which in turn is why it needs a handshake rather than
simply presenting a result every cycle.

## Files

The files for the lab can be found in the hwdesign github repo

```
hwdesign/
└── labs/
    └── subc/
        ├── subc_build.py           # Runs the build steps and scores them
        ├── partial/
        │   ├── subc_divide.py      # Python golden model
        │   ├── subc_eval.py        # Your measurements of its error
        │   ├── subc_divide.sv      # SystemVerilog module: the state machine
        │   └── tb_subc_divide.sv   # Testbench that drives the module
        ├── vectors/                # These directories are created by the build
        ├── results/                #   generated data, figures, scores and
        ├── eval/                   #   simulator output -- none of it is edited
        ├── sim/                    #   by hand, and none of it is submitted
        └── submission/             #   except the zip
```

The four files in the `partial` directory are not complete. You will finish them
as part of the lab, and each has `TODO` comments marking what to write:

| File | What you write |
| --- | --- |
| `subc_divide.py` | `subc_divide()` — one quotient bit per iteration, in Python |
| `subc_eval.py` | `quant_error()`, `max_error_by_nbits()` and `plot_error()` — the measurements you use to judge your own design |
| `subc_divide.sv` | The `always_comb` next-state logic and the `always_ff` that commits it |
| `tb_subc_divide.sv` | The handshake that hands a case to the module and collects the answer |

**You do not need to copy anything by hand.** The first time you run the build it
copies each file out of `partial/` into the lab directory and tells you it has
done so:

```
subc_divide_src:
    STARTED subc_divide.py from partial\subc_divide.py — edit subc_divide.py,
    not the copy in partial/.
pysim:
    Python golden model: 0/10
      · (0/10) not started — subc_divide.py is still unchanged from the template.
          Open it, look for the TODO comments, and run this again.
```

A stage whose files you have not touched yet says **not started** rather than
listing failed checks. That is not the same as getting it wrong, and the build
does not pretend otherwise — you will see real check-by-check feedback as soon as
there is real work to check.

Edit the copies at the top level, *not* the ones in `partial/`. The build never
overwrites your work once the top-level files exist — not even with `--force` —
which is what keeps a `git pull`, or a stray rebuild, from destroying an
afternoon.

`subc_build.py` is given and should not be modified. It is worth reading: it is
the script that decides your score, so nothing about the marking is hidden from
you.

## Build steps

So that the lab can be run incrementally, it uses the Waveflow package's
[Build DAG](https://sdrangan.github.io/waveflow/docs/guide/build/). The lab runs
as three *build steps*. In each one you complete one part of the design and then
run that step, which scores it and tells you why. You can edit and re-run as many
times as you like until you get a perfect score. A final step builds the
submission for Gradescope.

| Stage | Command | What it asks |
| --- | --- | --- |
| `pysim` | `python subc_build.py --through pysim` | Does your Python divider meet the error bound? |
| `pyeval` | `python subc_build.py --through pyeval` | How big is the error really — and does it shrink the way the theory says? |
| `svsim` | `python subc_build.py --through svsim` | Does your SystemVerilog agree with your Python, and finish on time? |
| `submit` | `python subc_build.py --through submit` | Collects the three scores and builds the Gradescope zip |

Importantly, observe that you measure the design in Python **before** you build
it in hardware. That is not busywork and it is not the order most people reach
for; see [Measuring the error](./evaluate.md).

The full set of commands:

```bash
python subc_build.py --list-steps-verbose   # what the stages are
python subc_build.py --through pysim        # the golden model, scored
python subc_build.py --through pyeval       # measure its error, scored
python subc_build.py --through svsim        # the SystemVerilog, scored
python subc_build.py                        # everything, then the submission zip
python subc_build.py --grades               # your scores, without rebuilding
```

Each stage prints its score and the reason for it as soon as it runs. A low score
does not stop the build — you can keep going to the next stage and come back, and
you can re-run a stage as many times as you like.

The build only redoes what changed. Edit `subc_divide.py` and every stage re-runs,
because they all work from its output; edit only `subc_divide.sv` and just the
simulation does. Change nothing and each stage reports `UP-TO-DATE` and does no
work at all.

## Pages

* [Theory: how conditional subtraction works](./theory.md)
* [The Python model](./python.md)
* [Measuring the error](./evaluate.md)
* [The SystemVerilog](./sv.md)
* [Grading and submission](./submit.md)

----

Go to [algorithm theory](theory.md)
