---
title: Grading and submission
parent: Root Solver
nav_order: 5
has_children: false
---

# Grading and submission

## Seeing where you stand

Each scored stage writes its result to disk, so you can ask for your standing at
any time without rebuilding anything:

```bash
python rootsolve_build.py --grades
```

Every check names itself, says what it is worth, and — when it fails — says why.
This output is the authority on the marking scheme, which is why these pages do
not repeat it: a page can go stale, the build cannot.

A stage you have not run yet shows as `not yet run` and scores zero. A stage whose
files you have not edited yet shows as `not started`, which is different: it means
the build has not judged your work, not that your work was judged and failed. For
`eval`, "your files" means `fsolve_eval.py`, `fsolve.cpp` and `tb_fsolve.cpp` —
edit any one of them and the stage is graded normally.

## The build only redoes what changed

The build tracks file timestamps. Edit `fsolve.py` and everything re-runs,
because every later step works from its vectors. Edit `fsolve.cpp` and the three
Vitis steps and `eval` re-run. Edit only `fsolve_eval.py` and just `eval` does.

A step that *failed* always re-runs on the next build, even if nothing changed,
so a failure caused by your setup clears as soon as the setup is fixed. To force
everything to run again anyway:

```bash
python rootsolve_build.py --force
```

## Building the submission

`submit` is a build step like any other, and it is the default:

```bash
python rootsolve_build.py
```

Because it is a step, it depends on both scored stages, so running it runs
whatever is out of date first — including C simulation, synthesis and
co-simulation. There is no separate script to remember and no way to bundle
results without regenerating them.

It writes:

```
submission/submitted_results.json    your scores and feedback
submission/submission.zip            what you upload
```

The zip contains that results file, your four source files (`fsolve.py`,
`fsolve_eval.py`, `fsolve.cpp`, `tb_fsolve.cpp`), the three vector files
(`tv_python.csv`, `tv_csim.csv`, `tv_cosim.csv`) and your convergence figure.
Upload **`submission.zip`** to Gradescope.

If you are running on the [NYU machine](../../support/nyuremote/), follow the
[uv instructions](../../support/nyuremote/python.md) and run the build through
`uv`:

```bash
uv run python rootsolve_build.py
```

and copy `submission.zip` back to your local machine to upload it.

{: .warning }
> Gradescope reports the score in the zip you upload. Run the full build after
> your last edit — if you fix something and upload without re-running, you submit
> the old score.

You can submit an unfinished lab. A step that failed or never ran scores zero and
the zip is still built — including when Vitis did not run at all.

## What is graded, and what is not

| | |
| --- | --- |
| **Graded** | Whether your model converges by the update rule and stops where it should; whether your comparison code is right; whether your kernel, in C simulation and as RTL, agrees with your model on your vectors |
| **Not graded** | Your coding style, how your kernel is structured internally, its latency, and what your figure looks like — only that you produced one |

Nothing is compared against a stored reference answer. The kernel is checked
against *your* model on *your* vectors — which is why the vectors themselves have
to be real problems your model really solved before any agreement counts. See
[the test vectors](./vectors.md#running-the-step).
