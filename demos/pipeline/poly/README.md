# The `poly` pipelining demo

The cubic from unit 7, `y = c0 + c1*x + c2*x^2 + c3*x^3`, evaluated in FP32
by Horner's method over an array of samples, and synthesized by Vitis HLS
with different loop optimizations, to see what each one buys and what it
costs. No AXI: the arrays are memory ports (`ap_memory`), and the call is
the `ap_start` / `ap_done` handshake, as in the unit 6 `quad` demo.

The walkthrough, with the results, is the docs page *Demos › Loop
Optimization* (`docs/demos/loopopt/index.md`).

| File | What it is |
| --- | --- |
| `poly.cpp`, `poly.h` | the kernel; its pragmas are switched by the `POLY_*` macros |
| `tb_poly.cpp` | the testbench, for C simulation and co-simulation |
| `run.tcl` | the Vitis HLS script: `csim`, `synth` or `cosim` per invocation |
| `golden.py` | the test vector and an independent FP32 Python model |
| `poly_analysis.py` | reads the reports and schedules, and plots them and the VCDs |
| `poly_build.py` | the sequence, and what is checked in between |

## Running it

In `hwdesign-venv`, with Vitis HLS installed:

```bash
python poly_build.py --list-steps
python poly_build.py --through pipeline     # part 1, pipelining
python poly_build.py                        # part 2, unrolling, too
```

Each variant is its own Vitis project, `proj_<variant>`: `proj_nopipe`,
`proj_pipe`, `proj_u2`, `proj_u4`, `proj_u8` and `proj_u4_nopart`. The
results land in `results/`: `pipe.md`, `schedule_pipe.png`,
`timing_nopipe.png` and `timing_pipe.png` for part 1; `unroll.md`,
`unroll.png`, `schedule_nopart.png` and `timing_unroll.png` for part 2;
and `summary.json`. A second run with nothing changed does nothing;
`--force-step <step>` re-runs one step and what depends on it.

```bash
python poly_build.py --unroll 2 4 8 16 --force-step synth_unroll
python poly_build.py --sim-unroll 8 --force-step cosim_unroll
```

`--sim-unroll` names the unrolled variant that is simulated, and must be
among the `--unroll` factors.
