---
title: Grading and submission
parent: Conditional Subtraction Division
nav_order: 5
has_children: false
---

# Grading and submission

## Seeing where you stand

Each stage scores itself as it runs and writes the result to disk, so you can ask
for your standing at any time without rebuilding anything:

```bash
python subc_build.py --grades
```

Every check names itself, says what it is worth, and — when it fails — says why:

```
Python golden model: 10/10
  ✓ (3/3) Produced a quotient for all 200 test cases
  ✓ (4/4) Your quotient meets the error bound
  ✓ (3/3) Your z actually depends on a and b
Measuring the error: 7/10
  ✓ (3/3) Your quant_error is correct
  ✗ (0/3) Your per-nbits worst case is correct — at nbits=8 you reported
          1.221e-04 and the true worst case is 3.891e-03
  ✓ (2/2) The error is one-sided and below 2**-nbits
  ✓ (2/2) You produced an error-vs-nbits figure
```

This output is the authority on the marking scheme, which is why these pages do
not repeat it — a page can go stale, the build cannot.

A stage you have not run yet shows as `not yet run` and scores zero. A stage whose
files you have not edited yet shows as `not started`, which is different: it means
the build has not judged your work, not that your work was judged and failed.

## The build only redoes what changed

The build tracks file timestamps. Edit `subc_divide.py` and every stage re-runs,
because they all work from its output. Edit only `subc_divide.sv` and just the
simulation re-runs. Change nothing and every stage reports `UP-TO-DATE` and does no
work.

If you ever want to force everything to run again:

```bash
python subc_build.py --force
```

## Building the submission

`submit` is a build step like any other, and it is the last one in the graph:

```bash
python subc_build.py --through submit
python subc_build.py                     # the same thing — submit is the default
```

Because it is a step, it depends on the three graded stages, so running it runs
whatever is out of date first. There is no separate script to remember and no way
to bundle results without regenerating them.

It writes:

```
submission/submitted_results.json    your scores and feedback
submission/submission.zip            what you upload
```

The zip contains that results file, your four source files,
`vectors/tv_python.csv`, `vectors/tv_sv.csv`, and the error plot you drew in
[stage 2](./evaluate.md). Upload **`submission.zip`** to Gradescope.

Your figure is in there so it can be looked at. Nothing checks what it shows —
only that you produced one — but it is the part of this lab whose quality a person
can judge at a glance and a script cannot judge at all.

If you are running on the [NYU machine](../../support/nyuremote/), follow the
[uv instructions](../../support/nyuremote/python.md) and run the build through
`uv`:

```bash
uv run python subc_build.py
```

{: .warning }
> Gradescope reports the score in the zip you upload. Run the full build after
> your last edit — if you fix something and upload without re-running, you submit
> the old score.

You can submit an unfinished lab. A stage you never ran scores zero and the zip is
still built, so partial work is always submittable — including when the simulation
did not run at all.

## What is graded, and what is not

| | |
| --- | --- |
| **Graded** | Whether your quotients meet the error bound, whether your measurements of them are right, whether your two implementations agree, and how many cycles the hardware takes |
| **Not graded** | Your variable names, your coding style, how you structured the state machine internally |

Nothing is compared against a stored reference implementation. Any correct divider
passes the Python stage, and the SystemVerilog stage checks it against *your*
Python rather than against ours. The write-up pins one algorithm so that nobody
has to guess what to build — not because the grader insists on it.

The one thing this does not let you do is leave both sides unimplemented. Two
untouched placeholders agree with each other perfectly, so a constant quotient
scores zero on the comparison no matter how well it matches. See
[the SystemVerilog stage](./sv.md).
