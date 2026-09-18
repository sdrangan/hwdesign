---
title: Grading and submission
parent: Cubic Fixed Point
nav_order: 5
has_children: false
---

# Grading and submission

## Seeing where you stand

Each stage scores itself as it runs and writes the result to disk, so you can ask
for your standing at any time without rebuilding anything:

```bash
python cubic_build.py --grades
```

Every check names itself, says what it is worth, and — when it fails — says why:

```
Python fixed-point model: 10/10
  ✓ (3/3) Produced an output for all 200 cases
  ✓ (3/3) Every output fits in 16 bits
  ✓ (4/4) At F=8 your fixed point tracks the float
Measuring the quantization error: 7/10
  ✓ (3/3) Your rel_mse is correct
  ✗ (0/3) Your mse_by_fbits is correct — at fbits=12 you reported 3.912e-03
          and the true value is 7.847e-02
  ✓ (2/2) F=8 approximates the float and F=12 saturates
  ✓ (2/2) You produced a float-against-fixed figure
```

This output is the authority on the marking scheme, which is why these pages do
not repeat it — a page can go stale, the build cannot.

A stage you have not run yet shows as `not yet run` and scores zero. A stage whose
files you have not edited yet shows as `not started`, which is different: it means
the build has not judged your work, not that your work was judged and failed.

## The build only redoes what changed

The build tracks file timestamps. Edit `cubic_model.py` and every stage re-runs,
because they all work from its output. Edit only `cubic.sv` and just the
simulation re-runs. Change nothing and every stage reports `UP-TO-DATE` and does
no work.

If you ever want to force everything to run again:

```bash
python cubic_build.py --force
```

## Building the submission

`submit` is a build step like any other, and it is the last one in the graph:

```bash
python cubic_build.py --through submit
python cubic_build.py                    # the same thing — submit is the default
```

Because it is a step, it depends on the three graded stages, so running it runs
whatever is out of date first. There is no separate script to remember and no way
to bundle results without regenerating them.

It writes:

```
submission/submitted_results.json    your scores and feedback
submission/submission.zip            what you upload
```

The zip contains that results file, `cubic_model.py`, `cubic_eval.py`,
`cubic.sv`, `vectors/cubic_py.csv`, `vectors/cubic_sv.csv`, and the comparison
figure you drew in [stage 2](./evaluate.md). Upload **`submission.zip`** to
Gradescope.

`tb_cubic_sing.sv` is deliberately *not* in the zip. Nothing grades it, and
requiring it would fail a student who never needed it.

Your figure is in there so it can be looked at. Nothing checks what it shows —
only that you produced one — but it is the part of this lab whose quality a person
can judge at a glance and a script cannot judge at all.

If you are running on the [NYU machine](../../support/nyuremote/), follow the
[uv instructions](../../support/nyuremote/python.md) and run the build through
`uv`:

```bash
uv run python cubic_build.py
```

If you are running Vivado on the NYU server, you will also need to copy
`submission.zip` back to your local machine to upload it.

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
| **Graded** | Whether your fixed-point outputs stay inside their registers, whether they track the float where they should, whether your measurements of the error are right, and whether your two implementations agree exactly — saturating cases included |
| **Not graded** | Your variable names, your coding style, how you arranged the pipeline internally, and anything in `tb_cubic_sing.sv` |

Nothing is compared against a stored reference implementation. Any correct model
passes the Python stage, and the SystemVerilog stage checks your RTL against
*your* Python rather than against ours. The write-up pins one arrangement of the
arithmetic so that nobody has to guess what to build — not because the grader
insists on it.

The one thing this does not let you do is leave both sides unimplemented. Two
untouched placeholders agree with each other perfectly, so a constant output
scores zero on the comparison no matter how well it matches. The same trap one
level down is covered too: if your Python never saturates, the saturation check
has nothing to compare and scores zero rather than passing on an empty set. See
[the SystemVerilog stage](./sv.md#why-the-three-checks-are-weighted-the-way-they-are).
