# The `fsum` reduction demo

The sum of 1024 floats, unrolled four ways, to see why unrolling a
reduction is not the same as unrolling the cubic in `demos/pipeline/poly`.
A float add takes four cycles at 100 MHz, and each iteration's add needs the
last one's sum, so the plain loop runs at II = 4 (unit 7).

| Variant | Loop body | II | Iterations | Cycles |
| --- | --- | --- | --- | --- |
| `rolled` | `sum += x[i]` | 4 | 1024 | about 4100 |
| `pragma` | the same, `UNROLL factor=4` | 16 | 256 | about 4100 |
| `tree` | `sum += (x0 + x1) + (x2 + x3)` | 4 | 256 | about 1040 |
| `lanes` | four partial sums | 4 | 256 | about 1040 |

The pragma does nothing for speed: Vitis keeps the order of float
additions, so the four adds are a chain through `sum`, 16 cycles long.  The
two hand-written versions keep only one add on the recurrence.  The
walkthrough is the docs page *Demos › Loop Optimization › Unrolling a Sum*
(`docs/demos/loopopt/reduction.md`).

| File | What it is |
| --- | --- |
| `fsum.cpp`, `fsum.h` | the kernel; `FSUM_VARIANT` picks the loop |
| `tb_fsum.cpp` | the testbench |
| `run.tcl` | the Vitis HLS script: `csim` or `synth` per invocation |
| `golden.py` | the test vector (exact in any order) and the Python model |
| `fsum_build.py` | the sequence |

In `hwdesign-venv`, with Vitis HLS installed: `python fsum_build.py`, about
3 minutes.  The table lands in `results/fsum.md`, and each variant's
schedule, state by state, in `results/schedule.md`.  The walkthrough is four
pages, starting at *Unrolling a Sum*; the files behind each number are
listed there.
