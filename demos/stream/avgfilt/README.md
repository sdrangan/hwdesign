# The `avgfilt` demo

A moving average of squares over a pure AXI4-Stream, with no TLAST:

```
y[k] = (x[k]^2 + x[k-1]^2 + x[k-2]^2) / 3
```

One sample in, one sample out, forever. There is no start, no done and no
end of frame (`ap_ctrl_none`), which is what makes it *pure* streaming.

Everything the hardware is made of is written by hand:

| File | What it is |
| --- | --- |
| `avgfilt.cpp`, `avgfilt.h` | the kernel and its interface pragmas |
| `tb_avgfilt.cpp` | the testbench, used for both C simulation and co-simulation |
| `run.tcl` | the Vitis HLS script, one stage per invocation |
| `avgfilt_golden.py` | the test signal and an independent Python model |
| `avgfilt_timing.py` | decodes the AXI4-Stream ports from the VCD and plots them |

`avgfilt_build.py` adds only the *sequence*: which tool runs when, and
what is checked in between.

## Running it

Use the environment that has `waveflow` (`hwdesign-venv`). From `csim` on,
you also need Vitis HLS installed.

```bash
python avgfilt_build.py --list-steps             # the sequence
python avgfilt_build.py --through plot_python    # Python only, no Vitis
python avgfilt_build.py --through verify_csim    # fast: no synthesis
python avgfilt_build.py                          # the whole flow
```

A step is skipped when its inputs have not changed: a second run with
nothing edited does nothing, and editing only the plot code re-runs only
`plot_python`. Synthesis waits on a verified C simulation, so anything
that re-runs `csim` re-runs everything after it too. `--force` re-runs
everything, and `--status` says what is stale. `--live-output` streams
Vitis's output to the terminal; otherwise it is saved to
`results/<stage>/vitis.log`.

Staleness is decided by file times, not by options. So an option only
takes effect when its step runs, which you force with `--force-step`:

```bash
python avgfilt_build.py --nsamp 400 --seed 2 --force-step pysim
python avgfilt_build.py --trace-level all --force-step cosim
python avgfilt_build.py --trange 1100 1350 --force-step timing_diagram
```

## The steps

```
pysim -> plot_python ------------------------------------------> report
      -> csim -> verify_csim -> csynth -> cosim -> verify_cosim -^
                                                -> extract_vcd -> timing_diagram -^
```

- **pysim** generates the test signal and runs it through the Python
  model. It writes both to `vectors/tv_python.csv`, as columns `n,x,y`.
  The signal is a sinusoid at 1/6 cycle per sample whose amplitude steps
  from 0.5 to 1.5 halfway through, plus a little noise.
- **plot_python** plots the input and the filtered output to
  `results/avgfilt_python.png`. At that frequency `x[n]^2` repeats every 3
  samples, so the 3-sample average of it is flat at `A^2/2`. The squared
  input swings between 0 and `A^2`, while the output holds at the
  signal's power and steps from 0.125 to 1.125.
- **csim** compiles the testbench against the C++ kernel and runs it. The
  testbench reads `x` from `tv_python.csv` and writes what the kernel
  returned to `vectors/tv_csim.csv`.
- **verify_csim** compares that output against the Python model and
  writes `results/verify_csim.json`.
- **csynth** synthesizes the kernel to RTL. It waits for `verify_csim`,
  because there is no point synthesizing a kernel that computes the wrong
  thing. The report is copied to `results/csynth/`.
- **cosim** runs the *same* testbench against that RTL, driving its
  AXI4-Stream ports, and writes `vectors/tv_cosim.csv`. It records the
  IP's ports as it goes (`--trace-level port`).
- **verify_cosim** compares that output against the Python model.
- **extract_vcd** re-runs the RTL simulation with VCD logging, because
  co-simulation's own `.wdb` waveform file only Vivado opens. The result is
  `vcd/dump.vcd`: the clock, the reset, and TDATA/TVALID/TREADY on each
  stream.
- **timing_diagram** decodes both streams from the VCD. It writes
  `results/timing_diagram.png`, the ports cycle by cycle from the first
  sample in to the first sample out, and `results/stream_data.png`, the
  values that crossed each port over the whole run with the Python model
  on top. It measures the latency (19 cycles) and counts stalls (none)
  into `results/stream_timing.json`, and fails if the data on the wires is
  not the test vector going in and the model's output coming out.
- **report** collects the verdicts and the timing into
  `results/summary.json`.

## Why the model is exact

The Python model computes in float32 and in the same order as the kernel:
square the input, add the two older squares left to right, and multiply by
`1/3`. So a correct kernel matches it bit for bit, and the comparison
reports how many samples were exact as well as the largest error. The
pass criterion is still a small tolerance, because exactness is a property
of this particular kernel, not of float arithmetic in general.

## Why verify twice

The testbench computes each expected value itself and prints PASS or FAIL,
and its return code fails the Vitis run. That catches a broken kernel, but
it cannot catch a testbench that is wrong in the same way the kernel is.
The comparison against `avgfilt_golden.py`, which was written
independently of the hardware, can.

`verify_csim` asks whether the C++ is right. `verify_cosim` asks whether
the synthesized RTL still does what the C++ did. That is not guaranteed,
and it is the failure that costs the most time to find later.
