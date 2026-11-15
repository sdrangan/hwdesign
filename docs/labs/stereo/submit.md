---
title: Grading and submission
parent: Stereo Depth
nav_order: 5
has_children: false
---

# Grading and submission

## Seeing where you stand

Each scored stage writes its result to disk, so you can ask for your standing at
any time without rebuilding anything:

```bash
python stereo_build.py --grades
```

Every check names itself, says what it is worth, and, when it fails, says why.
That output is the authority on the marking scheme; these pages do not repeat
it.

A stage whose files you have not edited yet shows as `not started`. That means
the build has not judged your work, not that it was judged and failed.

## The build only redoes what changed

Edit `stereo.py` and everything re-runs, because every later stage is checked
against your model. Edit `stereo_base.cpp` and only `base` re-runs. Edit
`stereo.cpp` and `opt`, `cosim` and `timing` re-run. Edit only
`stereo_timing.py` and just `timing` does, without another four-minute
co-simulation.

A Vitis run that failed is retried on the next build even if nothing changed.
To force everything to run again anyway:

```bash
python stereo_build.py --force
```

## Building the submission

```bash
python stereo_build.py
```

runs whatever is out of date, then writes:

```
submission/submitted_results.json    your scores and feedback
submission/submission.zip            what you upload
```

The zip contains that results file, your four source files, your two figures
(`disparity.png`, `phases.png`) and the two synthesis reports
(`base_csynth.rpt`, `opt_csynth.rpt`). Upload **`submission.zip`** to
Gradescope.

{: .warning }
> Gradescope reports the score in the zip you upload. Run the full build after
> your last edit: if you fix something and upload without re-running, you submit
> the old score.

You can submit an unfinished lab. A stage that failed or never ran scores zero,
and the zip is still built.

## What is graded, and what is not

| | |
| --- | --- |
| **Graded** | Your model, on scenes whose answer is known; that each kernel matches your model bit for bit; that the baseline is unpipelined; the optimized kernel's II, latency and size; your reading of the co-simulation's phases |
| **Not graded** | Coding style, how your loops are written inside, and what your figures look like, only that you made them |

The kernels are checked against **your** model on the lab's scene, and only once
your model is right, which is why stage 1 comes first.
