# The `fir` nested-loop demo

A 16-tap FIR filter on 16-bit samples, `y[n] = h[0]*x[n] + ... +
h[15]*x[n-15]`: a loop over the samples around a loop over the taps.  The
same arithmetic is written four ways, and Vitis HLS synthesizes each, to see
which loop to pipeline and where the samples should come from.  No AXI: the
arrays are memory ports (`ap_memory`) and the call is the `ap_start` /
`ap_done` handshake, as in the `poly` demo.

| Variant | The loop nest | Cycles per sample | DSP |
| --- | --- | --- | --- |
| `inner` | the tap loop pipelined, the nest kept as two loops | 25 | 1 |
| `flat` | the same code, flattened by Vitis into one loop | 16 | 1 |
| `outer` | the sample loop pipelined: 16 reads of `x` per sample | 16 | 16 |
| `delay` | the sample loop pipelined, with a delay line | 1 | 16 |

The walkthrough is the docs page *Demos › FIR: Nested Loops*
(`docs/demos/fir/index.md`).

| File | What it is |
| --- | --- |
| `fir.cpp`, `fir.h` | the kernel; `FIR_VARIANT` picks the way the nest is written |
| `tb_fir.cpp` | the testbench, for C simulation and co-simulation |
| `run.tcl` | the Vitis HLS script: `csim`, `synth` or `cosim` per invocation |
| `golden.py` | the test vector and an integer Python model |
| `fir_build.py` | the sequence, and what is checked in between |

## Running it

In `hwdesign-venv`, with Vitis HLS installed:

```bash
python fir_build.py --list-steps
python fir_build.py --through report      # check and synthesize all four: about 3 minutes
python fir_build.py                       # co-simulate the delay line and draw it: 3 more
python fir_build.py --sim-variant outer --force-step cosim
```

Each variant is its own Vitis project, `proj_<variant>`.  The results land
in `results/`: `fir.md`, `fir.png`, `fir.json`, and `timing_<variant>.png`
from the co-simulation.
