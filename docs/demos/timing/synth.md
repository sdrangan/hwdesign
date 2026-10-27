---
title: Synthesis at One Clock
parent: Timing and the Clock
nav_order: 2
has_children: false
---

# Synthesis at One Clock

This page builds the kernel for a single clock, **100 MHz** (a 10 ns
period), and reads what Vitis made of it: first in the synthesis report,
then in a simulation of the RTL.

## Pre-requirements

You will need the [software set-up](../../support/amd/) for Vitis and
Python. Run everything below from `hwdesign/demos/timing/quad`, in the
environment with `waveflow` (`hwdesign-venv`).

## The build script

`quad_build.py` runs each tool in turn and checks the results in between.
List its steps with:

```bash
(env) python quad_build.py --list-steps
```

```
make_inputs -> csim -> verify_csim -> sweep -> sweep_report ----------------------> report
                                   -> cosim_slow -> verify_cosim_slow -> vcd_slow -> timing_slow
                                   -> cosim_fast -> verify_cosim_fast -> vcd_fast -> timing_fast
```

This page runs the steps up to `timing_slow`, for one clock period:

```bash
(env) python quad_build.py --periods 10 --force-step sweep --through timing_slow
```

It takes about three minutes. A step is skipped when nothing it depends on
has changed, so running the same command again does nothing.
`--force-step sweep` makes the synthesis run even if it has run before,
for other periods.

## Step 1: C simulation (`make_inputs`, `csim`, `verify_csim`)

`make_inputs` writes the test vector from `golden.py`, and the expected
results from its Python model. `csim` compiles the testbench against the
C++ function and runs it:

```text
Test 0: x=10 w2=5 w1=-7 w0=4 got 434, expected 434  PASS
Test 1: x=-4 w2=5 w1=-7 w0=4 got 112, expected 112  PASS
Test 2: x=8 w2=5 w1=-7 w0=4 got 268, expected 268  PASS
Test 3: x=3 w2=2 w1=1 w0=0 got 21, expected 21  PASS
Test 4: x=-6 w2=-1 w1=3 w0=9 got -45, expected -45  PASS
All tests passed.
```

`verify_csim` then compares the testbench's `results.json` with the
Python model's. There is no point synthesizing a function that computes
the wrong thing, so synthesis waits for this check.

## Step 2: C synthesis (`sweep`)

The step is called `sweep` because the [next page](sweep.md) uses it for
many clock periods. With `--periods 10` it synthesizes the kernel twice,
into two *solutions* of the project `quad_proj`:

- `p10`: the function as written, for a 10 ns clock
- `pipe_p10`: the same, pipelined; the next page explains it

The Tcl that does it, from `run.tcl`, comes down to:

```tcl
open_solution -reset -flow_target vivado p10
set_part xc7z020clg484-1          ;# the PYNQ-Z2's FPGA
create_clock -period 10           ;# ns
csynth_design
```

### Reading the synthesis report

Each solution's report is in `quad_proj/<solution>/syn/report/`. Open
`quad_proj/p10/syn/report/quad_csynth.rpt` in a text editor, or in the
Vitis GUI. The first section is the timing:

```text
+ Timing:
    * Summary:
    +--------+----------+----------+------------+
    |  Clock |  Target  | Estimated| Uncertainty|
    +--------+----------+----------+------------+
    |ap_clk  |  10.00 ns|  4.586 ns|     2.70 ns|
    +--------+----------+----------+------------+

+ Latency:
    * Summary:
    +---------+---------+-----------+-----------+-----+-----+---------+
    |  Latency (cycles) |   Latency (absolute)  |  Interval | Pipeline|
    |   min   |   max   |    min    |    max    | min | max |   Type  |
    +---------+---------+-----------+-----------+-----+-----+---------+
    |        2|        2|  20.000 ns|  20.000 ns|    3|    3|       no|
    +---------+---------+-----------+-----------+-----+-----+---------+
```

Reading it:

- **Target**: the clock period asked for, 10 ns.
- **Uncertainty**: a margin Vitis keeps back, 27% of the period by
  default, for what synthesis cannot predict, routing delay above all. So
  Vitis schedules to **10 − 2.7 = 7.3 ns**, not to 10.
- **Estimated**: the slowest path between two registers in what it
  scheduled, 4.586 ns. It fits in 7.3 ns, so the design **meets timing**,
  as far as synthesis can tell.
- **Latency**: 2 cycles, 20 ns, from `ap_start` to `ap_done`.
- **Interval**: 3 cycles before the next call can start: the latency, plus
  a cycle for the handshake.

The utilization section counts the hardware:

```text
+-----------------+---------+-----+--------+-------+-----+
|       Name      | BRAM_18K| DSP |   FF   |  LUT  | URAM|
+-----------------+---------+-----+--------+-------+-----+
|Total            |        0|    3|      73|     66|    0|
+-----------------+---------+-----+--------+-------+-----+
```

Three DSP blocks, one per multiply. And the register section names the
73 flip-flops, which says where Vitis cut the computation:

```text
+-------------------+----+----+-----+-----------+
|        Name       | FF | LUT| Bits| Const Bits|
+-------------------+----+----+-----+-----------+
|ap_CS_fsm          |   3|   0|    3|          0|
|mul_ln29_reg_122   |  22|   0|   22|          0|
|sext_ln26_reg_112  |  16|   0|   16|          0|
|x_w1_reg_127       |  16|   0|   16|          0|
|xsq_reg_117        |  16|   0|   16|          0|
+-------------------+----+----+-----+-----------+
```

`xsq`, `x_w1` and `mul_ln29` (the product `w2*xsq`, named after its source
line) are each held in a register between cycles. `ap_CS_fsm` is the
small state machine that steps through the cycles.

### The schedule: what happens in each cycle

The cycle-by-cycle schedule is in
`quad_proj/p10/.autopilot/db/quad.verbose.sched.rpt`. Stripped of its
bookkeeping, it reads:

```text
State 1 <Delay = 4.53>
    xsq      = mul x, x                       4.53 ns   (DSP)
State 2 <Delay = 4.58>
    mul_ln29 = mul xsq, w2                    4.58 ns   (DSP)
    x_w1     = mul w1, x                      4.53 ns   (DSP)
State 3
    y        = add mul_ln29, x_w1, w0         4.10 ns   (three-input adder)
    ret y
```

This is the lecture's critical-path reasoning, done by the tool. Each
operation takes about 4.5 ns, and the budget per cycle is 7.3 ns, so:

- `x*x` and `w2*xsq` are in series, and 4.53 + 4.58 = 9.1 ns does not
  fit in one cycle: they go in different cycles.
- `w1*x` does not depend on `xsq`, so it shares a cycle with `w2*xsq`.
- The adder needs both products, so it goes in a third cycle.

Three states is two clock edges from start to done: a latency of 2. The
estimated period, 4.586 ns, is the slowest state.

### Reading the report from Python

`quad_timing.py` reads every number above with waveflow's report parser,
`waveflow.utils.csynthparse`. You can try it yourself:

```python
>>> from waveflow.utils.csynthparse import synth_target, module_latency, CsynthParser
>>> rdir = "quad_proj/p10/syn/report"
>>> synth_target(rdir)
{'part': 'xc7z020-clg484-1', 'target_period_ns': 10.0, 'estimated_period_ns': 4.586,
 'fmax_mhz': 218.05}
>>> module_latency(rdir, "quad")
{'latency_min': 2, 'latency_max': 2, 'interval_min': 3, 'interval_max': 3}
>>> p = CsynthParser(report_path=rdir)
>>> p.get_total_resources()
>>> p.total_resources
{'DSP': 3, 'FF': 73, 'LUT': 66, 'BRAM_18K': 0, 'URAM': 0}
```

They read `csynth.xml` and `quad_csynth.xml`, the machine-readable
versions of the report beside the `.rpt` files. `fmax_mhz` is
1 / 4.586 ns: the fastest clock the estimate would allow if there were no
uncertainty.

The function in `quad_timing.py` that collects them, one row per solution:

```python
def read_solution(root: Path, period_ns: float, pipelined: bool = False) -> dict:
    from waveflow.utils.csynthparse import CsynthParser, module_latency, synth_target

    rdir = report_dir(root, period_ns, pipelined)
    clock = synth_target(rdir)                  # target, estimated period, part
    lat = module_latency(rdir, TOP)             # latency and interval, in cycles
    parser = CsynthParser(report_path=str(rdir))
    parser.get_total_resources()                # DSP, FF, LUT, ...
    ...
```

## Step 3: RTL co-simulation (`cosim_slow`, `verify_cosim_slow`)

`cosim_slow` runs the *same* testbench against the RTL synthesized for
10 ns. Each call to `quad()` becomes a handshake on the RTL's ports: the
testbench puts x and the weights on their wires, raises `ap_start`, and
waits for `ap_done`. `verify_cosim_slow` checks the outputs against the
Python model again.

Co-simulation also reports what it measured, in
`quad_proj/p10/sim/report/quad_cosim.rpt`:

```text
|          |          |      Latency(Clock Cycles)    |     Interval(Clock Cycles)    | Total Execution Time |
|          |          |   min   |   avg   |   max     |   min   |   avg   |   max     |    (Clock Cycles)    |
|   Verilog|      Pass|        2|        2|        2  |        3|        3|        3  |                    14|
```

The minimum, average and maximum latency are all 2 cycles, and the
interval 3, exactly what synthesis predicted, now measured on the RTL.
The five calls take 14 cycles in all.

## Step 4: the timing diagram (`vcd_slow`, `timing_slow`)

Co-simulation stores its waveforms in a `.wdb` file, which only the Vivado
viewer opens. `vcd_slow` re-runs the simulation with logging to a VCD
file, an open text format, in `vcd/slow.vcd`. `timing_slow` draws it,
with waveflow's `TimingDiagram`, as `results/timing_slow.png`:

<img src="images/quad_timing_100mhz.png" alt="Timing diagram at 100 MHz: ap_start rises with x = 10, and ap_done rises 2 cycles later with y = 434 on ap_return" width="100%"/>

Read it from the green line, where `ap_start` rises with x = 10 on its
wire, to the purple line, two rising edges later, where `ap_done` rises
with y = 434 on `ap_return`: the latency of 2 cycles, 20 ns.

`y` is only meaningful while `ap_done` is high. Between calls the wire
can show a half-finished value: the 264 at the right mixes the next x,
3, with the previous call's weights. A caller reads `ap_return` only when
`ap_done` says it is ready.

Next: [the same, at clocks from 50 to 400 MHz](sweep.md).
