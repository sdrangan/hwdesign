---
title: Building a Python Model
parent: Conditional Subtraction Division
nav_order: 2
has_children: false
---

# Stage 1: Building a Python Golden Model

Before implementing the function in SystemVerilog, it is better to develop a
model in a language like Python where the debugging is simple. This model serves
as a **golden model**: a verified reference the hardware is checked against.

It is worth being clear about what that means here. The SystemVerilog stage does
**not** compare your hardware against our answer — it compares it against
*yours*. So this stage is where correctness is actually established, and
everything downstream inherits it.

## What to write

Complete `subc_divide()` in `subc_divide.py`. The `TODO` comment marks the spot,
and the [theory page](./theory.md) has the four steps of one iteration.

The guard clauses at the top of the function, which reject `b == 0` and `a >= b`,
are given. The lab never calls the function outside those preconditions.

Keep the arithmetic in `np.uint32`. The SystemVerilog you write next has
fixed-width registers, and a model that quietly relies on Python's unbounded
integers would hide an overflow the hardware cannot.

You can run the file directly while you are working, which prints the `a=3, b=10`
example from the theory page without going through the build:

```bash
python subc_divide.py
```

## Running the stage

```bash
python subc_build.py --through pysim
```

The build generates its own test cases — 200 of them, with `0 <= a < b` and a
per-case `nbits` between 4 and 16 — runs your function over every one, and writes
the results to `vectors/tv_python.csv`.

Those cases come from a fixed seed, so they are the same every run, on every
machine. If the build tells you case 37 is wrong, case 37 is the same case
tomorrow, and the same case for whoever you ask for help.

{: .note }
> The test cases live in `subc_build.py`, not in your file. That is deliberate:
> it means a submission cannot change what it is graded against, and a file with
> a syntax error still gets scored against the right numbers instead of taking
> the build down with it.

## What is checked

```
Python golden model: 10/10
  ✓ (3/3) Produced a quotient for all 200 test cases
  ✓ (4/4) Your quotient meets the error bound
  ✓ (3/3) Your z actually depends on a and b
```

The middle check is the [one-sided bound](./theory.md#the-error-bound):
`0 <= a/b - qhat < 2**-nbits`, on every case. It is scored proportionally, so a
divider that is right on most inputs earns most of the marks, and the feedback
names the first case that failed along with its `a`, `b` and `nbits`.

The third check exists because the unedited template returns `0` for everything —
and a constant zero *satisfies the error bound* on any case whose true quotient
happens to be smaller than one unit in the last place. Rather than let that
collect points, the build tests for a constant result directly, and when it finds
one it zeroes the bound check too:

```
✗ (0/4) Your quotient meets the error bound — every case returned z = 0, so your
        result does not depend on a or b — open subc_divide.py and look for the TODO
```

A constant answer has not met the bound; it has dodged the question.

## If something goes wrong

A traceback from your code is caught and scored, not propagated — the build keeps
going and tells you which case raised and what the exception was. The same is true
of a file that will not even import.

----

Go to [measuring the error](./evaluate.md).
