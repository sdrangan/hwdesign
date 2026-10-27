# The `quad` timing demo

The quadratic from unit 6, `y = w2*x^2 + w1*x + w0`, synthesized by Vitis
HLS at clock periods from 20 ns to 2.5 ns, to see how many cycles it takes
at each. No loops and no AXI: plain input wires, `ap_return`, and the
`ap_start` / `ap_done` handshake.

The walkthrough, with the results, is the docs page *Demos › Timing and
the Clock* (`docs/demos/timing/index.md`).

| File | What it is |
| --- | --- |
| `src/quad.cpp`, `src/quad.h` | the kernel and its interface pragmas |
| `testbench/tb_quad.cpp` | the testbench, for C simulation and co-simulation |
| `run.tcl` | the Vitis HLS script: `csim`, `sweep` or `cosim` per invocation |
| `golden.py` | the test vector and an independent Python model |
| `quad_timing.py` | reads the sweep's reports, and plots them and the VCDs |
| `quad_build.py` | the sequence, and what is checked in between |

## Running it

In `hwdesign-venv`, with Vitis HLS installed:

```bash
python quad_build.py --list-steps
python quad_build.py --through sweep_report    # the sweep: about 4 minutes
python quad_build.py                           # everything: about 8
```

The results land in `results/`: `sweep.md`, `sweep.png`, `timing_slow.png`,
`timing_fast.png` and `summary.json`. A second run with nothing changed
does nothing; `--force-step <step>` re-runs one step and what depends on
it.

```bash
python quad_build.py --periods 10 5 2.5 --slow-ns 10 --fast-ns 2.5 --force-step sweep
```

The slow and fast periods must be among the swept ones: they name the
solutions that are simulated.
