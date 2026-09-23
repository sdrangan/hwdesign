# The `scalar_fun` demo

A single artificial neuron, `y = max(w*x + b, 0)`, built as a Vitis HLS IP
with an AXI4-Lite register map. It is the smallest design that still has a
real processor interface: the processor writes `x`, `w` and `b` into
registers, raises `ap_start`, waits for `ap_done`, and reads `y` back.

Everything the hardware is made of is written by hand:

| File | What it is |
| --- | --- |
| `src/scalar_fun.cpp`, `src/scalar_fun.h` | the kernel and its interface pragmas |
| `testbench/tb_scalar_fun.cpp` | the testbench, used for both C simulation and co-simulation |
| `run.tcl` | the Vitis HLS script, one stage per invocation |
| `golden.py` | the test vector and an independent Python model |

`scalar_fun_build.py` adds only the *sequence* — which tool runs when, and
what is checked in between. Nothing in this demo is generated from a
higher-level model.

## Running it

Use the environment that has `waveflow` (`hwdesign-venv`), and have Vitis
HLS installed.

```bash
python scalar_fun_build.py --list-steps            # the sequence
python scalar_fun_build.py --through verify_csim   # fast: no synthesis
python scalar_fun_build.py --through report        # the whole flow
python scalar_fun_build.py --through timing_diagram --trange 130 350
```

A step is skipped when its inputs have not changed, so editing the
testbench re-runs C simulation without re-synthesizing. `--force` re-runs
everything; `--status` says what is stale.

## The steps

```
make_inputs -> csim -> verify_csim -> csynth -> cosim -> verify_cosim -> report
                                                      -> extract_cosim_timing -^
                                                      -> extract_vcd -> timing_diagram -^
```

- **make_inputs** writes `data/cases.txt`, which the testbench reads, and
  the expected results in `results/golden/`. Both come from `golden.py`,
  so the stimulus and the expected answers cannot drift apart.
- **csim** compiles the testbench against the C++ kernel and runs it.
- **csynth** synthesizes the kernel to RTL.
- **cosim** runs the *same* testbench against that RTL, with waveform
  tracing on.
- **extract_vcd** re-runs the RTL simulation with VCD logging, because
  co-simulation's own `.wdb` waveform file is a proprietary format only
  Vivado opens. The result lands in `vcd/dump.vcd`.
- **timing_diagram** plots the `s_axi_ctrl` signals from that VCD into
  `results/timing_diagram.png`.  The full run covers all five test cases;
  `--trange 130 350` zooms to one, which is what reads in class.

  There are no `ap_start` or `ap_done` *ports* to plot, because `return` is
  in the `CTRL` bundle: they are bits in the control register at `0x00`.
  So the diagram shows the processor writing `x`, `w` and `b` to `0x10`,
  `0x18` and `0x20`, writing `1` to `0x00` to start, then reading `0x00`
  and getting `0xa` back -- `ap_done` and `ap_ready`.  That is what the
  handshake actually looks like from the processor's side.
- **report** collects the cycle count and both verdicts into
  `results/summary.json`.  It depends on every other step, so
  `--through report` is the whole flow.

## Why verify twice

The testbench computes each expected value itself and prints PASS or FAIL,
and its return code fails the Vitis run. That catches a broken kernel, but
it cannot catch a testbench that is wrong in the same way the kernel is.
So the testbench also writes `results.json`, and `verify_csim` and
`verify_cosim` compare it against the Python model in `golden.py` —
written independently of the hardware.

They run separately, against separate output directories, because they
answer different questions. `verify_csim` asks whether the C++ is right.
`verify_cosim` asks whether the synthesized RTL still does what the C++
did — which is not implied, and is the failure that costs the most time to
find later.
