---
title: RTL Simulation
parent: Bus Basics and Memory‑Mapped Interfaces
nav_order: 5
has_children: false
---

# RTL Simulation of the Synthesized Vitis IP

C simulation told us the *algorithm* is right. It said nothing about the
hardware: it ran the C++ on a processor. Synthesis then produced RTL, and
nothing so far has checked that the RTL still does the same thing.

That check is **C/RTL co-simulation**. Vitis runs the *same* testbench again,
but the calls to `simp_fun` are served by the synthesized RTL in a simulator
instead of by the C++ function. It is also the first point where we can see the
AXI4‑Lite transactions themselves, which is what this unit is really about.

Run everything below from `hwdesign/demos/scalar_fun/scalar_fun_vitis`.

## Co-simulation

~~~bash
(env) python scalar_fun_build.py --through cosim
~~~

This one is slow — a few minutes. Watch the log and you will see the testbench
run **twice**:

~~~text
INFO: [COSIM 212-302] Starting C TB testing ...
Test 0: x=3 w=2 b=4 got 10, expected 10  PASS
...
INFO: [COSIM 212-15] Starting XSIM ...
INFO: [COSIM 212-316] Starting C post checking ...
Test 0: x=3 w=2 b=4 got 10, expected 10  PASS
...
INFO: [COSIM 212-1000] *** C/RTL co-simulation finished: PASS ***
~~~

The first pass records the inputs your testbench applies. Those recorded
transactions are replayed into the RTL simulator. The second pass — "C post
checking" — runs your `main()` again, except now the value that comes back from
`simp_fun` is the value the *hardware* produced. That is why the results file
it writes, `results/cosim/results.json`, describes the RTL and not the C++.

### Under the hood: the build step

~~~python
@dataclass(kw_only=True)
class CoSimStep(BuildStep):
    """Re-run the same testbench against the synthesized RTL."""

    description = "Run RTL co-simulation into results/cosim, with tracing on."
    consumes = ["scalar_fun_tb", "run_tcl", "cases", "report_dir"]
    produces = {"cosim_dir": Path("results/cosim")}
    params = {"clk_period_ns": 10.0, "trace_level": "port", "live_output": False}
~~~

It consumes `report_dir` — the solution directory that synthesis produced —
which is what puts it after synthesis in the graph. And it produces
`results/cosim`, a *different* directory from C simulation's `results/csim`.
That separation is deliberate: it is what lets the two runs be checked
independently rather than one overwriting the other's evidence.

Running it by hand:

~~~powershell
$env:SCALAR_FUN_STAGE       = "cosim"
$env:SCALAR_FUN_OUT_DIR     = "$PWD/results/cosim"
$env:SCALAR_FUN_TRACE_LEVEL = "port"
& "C:/Xilinx/2025.1/Vitis/bin/vitis-run.bat" --mode hls --tcl run.tcl
~~~

or in the GUI, **C/RTL Simulation → Run**, having first set
**cosim.trace.all** to `port` or `all` in its settings (the gear icon).

## Verifying the co-simulation

Exactly as after C simulation, we compare against the Python model:

~~~bash
(env) python scalar_fun_build.py --through verify_cosim
~~~

This is the check that catches a synthesis-level bug: something the C++ does
correctly that the generated hardware does not. It is a different question from
`verify_csim`, which is why both exist.

It is the same `FunctionalVerifyStep` as before, pointed at the other
directory:

~~~python
dag.add(FunctionalVerifyStep(
    name="verify_cosim",
    golden_dir_artifact="golden_dir",
    actual_dir_artifact="cosim_dir",
    jsons=[{"filename": "results.json", "compare_fields": ["y"]}],
    report_path="results/verify_cosim.json",
    report_artifact="verify_cosim_report",
))
~~~

The golden directory is the same one — the Python model does not care which
implementation produced the answers it is checking.

## How long did it take?

~~~bash
(env) python scalar_fun_build.py --through extract_cosim_timing
~~~

This parses the co-simulation report and writes
`results/cosim_timing.json` with the measured **transaction cycles** — how many
clock cycles one call to the IP took, as observed in RTL simulation rather than
estimated.

## Extracting a VCD file

Co-simulation records the waveforms in a `.wdb` (waveform database) file. That
is an AMD proprietary format; only the Vivado viewer opens it. We want a
[**Value Change Dump**](https://en.wikipedia.org/wiki/Value_change_dump), or
**VCD** — an open format that many programs, including Python, can read.

Getting one means re-running the RTL simulation with VCD logging switched on,
which in turn means editing the generated simulation scripts. That used to be a
page of manual instructions. It is now a step:

~~~bash
(env) python scalar_fun_build.py --through extract_vcd
~~~

~~~text
VCD copied to ...\scalar_fun_vitis\vcd\dump.vcd
VCD has 20 signals.
~~~

The file lands in `vcd/dump.vcd`.

> **What the step does for you.** It finds the generated simulation directory,
> copies the simulator's TCL script, inserts `open_vcd` and a `log_vcd` command
> before the existing `log_wave`, changes `quit` to `close_vcd; quit`, patches
> the launcher batch file so it can be called from elsewhere, re-runs the
> simulation, and collects the resulting VCD. If you ever need to do this by
> hand for a different project, those are the steps.

The demo traces at **port** level, so the VCD contains the IP's interface
signals rather than its several hundred internal ones. Those interface signals
are exactly what we want to look at.

## Viewing the Timing Diagram

~~~bash
(env) python scalar_fun_build.py --through timing_diagram
~~~

This writes two figures, because they answer different questions:

| File | What it shows |
|---|---|
| `results/timing_diagram_call.png` | one call, with its phases shaded |
| `results/timing_diagram.png` | the whole run, with each call marked |

The zoom window for the first is read off the decoded trace rather than being
typed in, so it stays right if the test vector changes. `--trange T0 T1`
overrides it if you want to look somewhere specific.

<img src="images/axi_lite_transaction.png" alt="AXI4-Lite timing diagram for one call to the IP" width="900"/>

### Reading it

The diagram shows the AXI4‑Lite channels: the write address channel
(`AWVALID`/`AWREADY`/`AWADDR`), the write data channel
(`WVALID`/`WREADY`/`WDATA`), the write response channel
(`BVALID`/`BREADY`), the read address channel (`ARVALID`/`ARREADY`/`ARADDR`)
and the read data channel (`RVALID`/`RREADY`/`RDATA`).

You can already see the shape of one call: a burst of writes, a pause, then two
reads. The addresses on `AWADDR` and `ARADDR` are the **register map** the
`bundle=CTRL` pragmas created. Decoding them transfer by transfer is the
subject of the [next page](./execution.md).

One thing to notice now: every transfer completes with `VALID` and `READY` both
high on the same clock edge — the rule from the first half of this unit, on
real hardware.

## Running the whole flow

Every step so far, in one command:

~~~bash
(env) python scalar_fun_build.py --through report
~~~

`report` depends on everything else, so this is the full flow. It ends with a
summary:

~~~json
{
  "top": "simp_fun",
  "transaction_cycles": 5,
  "csim_verified": true,
  "cosim_verified": true,
  "timing_diagram": "results\\timing_diagram.png",
  "calls_decoded": 5
}
~~~

If you have run the steps individually, most of this returns immediately —
only what is stale is redone.

---
Go to [The Execution Model](./execution.md)
