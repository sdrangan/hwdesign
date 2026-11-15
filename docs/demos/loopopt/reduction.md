---
title: Unrolling a Sum
parent: Loop Optimization
nav_order: 6
has_children: false
---

# Unrolling a Sum

Unrolling the cubic worked because its iterations are **independent**:
sample `i + 1` does not need anything sample `i` computes. A sum is
different. Every iteration adds to the total the last one produced: a
**loop-carried dependency**, as in unit 7. What does unrolling do to that?

The code is in `hwdesign/demos/fsum`. It sums 1024 floats, four ways. This
page runs the demo and shows where each number comes from. The next three
pages read the results:

1. [Reading the II from the stages](reduction_stages.md): the rolled loop,
   and why the `UNROLL` pragma alone makes it no faster.
2. [Rewriting the body](reduction_rewrite.md): a tree, and four lanes, each
   four times faster.
3. [How many adders?](reduction_adders.md): what each version costs in
   hardware, and why.

## The four versions

`fsum.cpp` holds all four; the macro `FSUM_VARIANT` (in `fsum.h`) picks one.
`x` is one memory with one port, as in the other demos: one read per cycle.

| Variant | `FSUM_VARIANT` | The loop |
|---|---|---|
| `rolled` | 0 | `sum += x[i];` |
| `pragma` | 1 | the same, with `#pragma HLS UNROLL factor=4` |
| `tree` | 2 | `sum += (x[i] + x[i+1]) + (x[i+2] + x[i+3]);`, `i += 4` |
| `lanes` | 3 | `part[j] += x[i + j];` for `j` = 0 to 3, `i += 4`, then `sum = (part[0] + part[1]) + (part[2] + part[3]);` |

Every loop carries `#pragma HLS PIPELINE II=1`. [Why `II=1`](#why-ii1),
when no version reaches it, is at the end of this page.

## Running it

In `hwdesign-venv`, with Vitis HLS installed:

```bash
(env) cd demos/fsum
(env) python fsum_build.py --list-steps     # the sequence
(env) python fsum_build.py                  # all of it, about 3 minutes
```

The steps:

| Step | What it does | Writes |
|---|---|---|
| `make_inputs` | the test vector, and the expected sum, from `golden.py` | `data/cases.txt`, `results/golden/` |
| `csim` | C simulation of all four variants | `results/csim/<variant>/` |
| `verify_csim_<variant>` | checks each against the Python model, bit for bit | `results/verify_csim_<variant>.json` |
| `synth` | synthesizes each variant in its own Vitis project | `proj_<variant>/`, `results/synth/vitis.log` |
| `report` | the four synthesis reports side by side | `results/fsum.md`, `fsum.json` |
| `schedule` | the four schedules, state by state | `results/schedule.md` |

The four variants add in different orders, and a float sum in general
depends on the order, so the test values are multiples of 1/8: every
partial sum is then exact, and all four must match the model exactly.

A step is skipped when its inputs have not changed. To redo one,
`python fsum_build.py --force-step schedule`; to stop after one,
`--through report`. To synthesize one variant by hand, from `demos/fsum`
in PowerShell:

```powershell
$env:FSUM_STAGE="synth"; $env:FSUM_VARIANTS="tree:2"; vitis-run --mode hls --tcl run.tcl
```

## The results

`results/fsum.md`, Vitis HLS 2025.1 on the Zynq-7020 at 100 MHz:

| Variant | Loop body | II | Trip count | Iteration latency | Cycles, 1024 samples | DSP | FF | LUT |
|---|---|---|---|---|---|---|---|---|
| rolled | `sum += x[i]` | 4 | 1024 | 7 | 4100 | 2 | 290 | 526 |
| pragma | `sum += x[i], UNROLL factor=4` | 16 | 256 | 18 | 4099 | 2 | 384 | 632 |
| tree | `sum += (x0 + x1) + (x2 + x3)` | 4 | 256 | 21 | 1042 | 2 | 510 | 682 |
| lanes | `part[j] += x[i+j], j = 0..3` | 4 | 256 | 10 | 1042 | 4 | 878 | 1175 |

The pragma makes the loop no faster; the two rewritten bodies make it four
times faster; lanes costs twice the DSPs of the tree for the same speed.
The next pages explain all three.

## Where each number comes from

Paths are from `demos/fsum`. The `report` and `schedule` steps read these
files for you, but each is plain text, worth opening once.

| What | File | Look for |
|---|---|---|
| II, iteration latency, trip count | `proj_<variant>/sol/syn/report/fsum_csynth.rpt` | the `Loop` table |
| cycles for the call | the same file | `Latency (cycles)` |
| DSP, FF, LUT | the same file | the `Total` row of `Utilization Estimates` |
| how many adders | the same file | the `Instance` table: one `fadd_..._U<n>` row per adder |
| the II Vitis aimed for, and what stopped it | `results/synth/vitis.log` | `HLS 200-1470` and `HLS 200-880` |
| which cycle each operation is in | `proj_<variant>/sol/.autopilot/db/fsum.verbose.sched.rpt` | `Pipeline-0` and the `ST_<n>` lines |

**`lanes` is different.** Vitis makes its loop a module of its own, so its
loop table and schedule are in `fsum_Pipeline_sum_loop_csynth.rpt` and
`fsum_Pipeline_sum_loop.verbose.sched.rpt`, beside `fsum`'s. `fsum`'s files
then hold what comes after the loop.

The synthesis report's loop table, for `tree`:

```text
|  Loop Name |   min   |   max   |  Latency |  achieved |   target  | Count| Pipelined|
|- sum_loop  |     1040|     1040|        21|          4|          1|   256|       yes|
```

`Latency` is the iteration latency, `achieved` and `target` the II, and
`Count` the trip count.

The log names the loop-carried dependency. For `rolled`:

```text
WARNING: [HLS 200-880] The II Violation in module 'fsum' (loop 'sum_loop'): Unable to enforce
a carried dependence constraint (II = 1, distance = 1, offset = 0) between 'store' operation
... on local variable 'sum2' and 'load' operation 32 bit ('sum2_load', fsum.cpp:20) on local
variable 'sum2'.
INFO: [HLS 200-1470] Pipelining result : Target II = 1, Final II = 4, Depth = 7, loop 'sum_loop'
```

`sum2` is Vitis's name for the register holding `sum`. The store of one
iteration and the load of the next are too close together at II = 1: the
dependency [the next page](reduction_stages.md) counts.

The schedule report, `.autopilot/db/*.verbose.sched.rpt`, is the one
[the pipelining demo](schedule.md) introduced. `.autopilot` is a hidden
folder, the file exists only after synthesis, and it is an internal Vitis
file whose format can change between versions. The `schedule` step pulls
out the lines that matter into `results/schedule.md`; the next pages quote
it.

## Why `II=1`?

No version reaches II = 1, so why ask for it? Because the target makes the
scheduler work. With `II=1`, the log shows Vitis trying II = 1, 2 and 3,
an `HLS 200-880` violation at each, before it settles at 4. Change every
pragma to a bare `#pragma HLS PIPELINE` and the log says
`Target II = NA`, and the same loops come out slower:

| Variant | `PIPELINE II=1` | `PIPELINE` |
|---|---|---|
| rolled | II = 4, 4100 cycles | II = 6, 6147 cycles |
| pragma | II = 16, 4099 | II = 21, 5379 |
| tree | II = 4, 1042 | II = 6, 1555 |
| lanes | II = 4, 1042 | II = 6, 1553 |

Vitis HLS 2025.1, this demo. Ask for the II you want, and read the log for
the one you got.

Next: [reading the II from the stages](reduction_stages.md).
