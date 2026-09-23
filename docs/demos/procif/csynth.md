---
title: C Synthesis
parent: Bus Basics and Memory‑Mapped Interfaces
nav_order: 4
has_children: false
---

# C Synthesis

**Synthesis** is where the C++ stops being software. Vitis HLS schedules the
operations in `simp_fun` into clock cycles, allocates hardware for them
(adders, multipliers, registers), builds the AXI4‑Lite register map from the
`#pragma HLS INTERFACE` directives, and writes out RTL — Verilog — targeting
the specific FPGA part named in `run.tcl`.

~~~bash
(env) python scalar_fun_build.py --through csynth
~~~

This takes longer than simulation — a minute or two.

## What it produced

The generated Verilog is in:

~~~bash
scalar_fun_proj/solution1/syn/verilog
~~~

~~~text
simp_fun.v
simp_fun_CTRL_s_axi.v
simp_fun_mul_32s_32s_32_2_1.v
~~~

Three files, and each one is worth opening for a moment:

* `simp_fun.v` is the kernel — the datapath and the state machine that
  sequences it.
* `simp_fun_CTRL_s_axi.v` is the **register map**, written for you from the
  four `bundle=CTRL` pragmas. Inside it is an address decoder with the
  constants for `x`, `w`, `b`, `y` and the control register. Those are the
  addresses we will watch on the wire in the [next section](./rtlsim.md).
* `simp_fun_mul_32s_32s_32_2_1.v` is the **multiplier**. The `w * x` in your
  C++ became a piece of hardware with a name, a width, and a latency — you can
  read all three off the file name.

The reports are next door in `solution1/syn/report`, and include the estimated
timing and the resource usage (LUTs, flip-flops, DSPs). They are worth a look,
but treat the latency numbers as *estimates* — the number we actually care
about in this unit is measured in RTL simulation, not predicted here.

## Under the hood: the build step

~~~python
@dataclass(kw_only=True)
class CSynthStep(BuildStep):
    """Synthesize the kernel to RTL."""

    description = "Run Vitis HLS C synthesis."
    consumes = ["scalar_fun_cpp", "scalar_fun_h", "run_tcl", "verify_report"]
    produces = {"report_dir": Path(f"{PROJECT}/{SOLUTION}")}
    params = {"clk_period_ns": 10.0, "live_output": False}

    def run(self, config: BuildConfig, clk_period_ns, live_output, **_) -> dict:
        _run_stage(config, "csynth", config.root_dir / "results" / "csynth",
                   clk_period_ns=clk_period_ns, live_output=live_output)
        report_dir = config.root_dir / PROJECT / SOLUTION
        if not report_dir.exists():
            raise RuntimeError(f"C synthesis produced no solution at {report_dir}.")
        return {"report_dir": report_dir}
~~~

Three things in `consumes` are worth pausing on.

It lists **`scalar_fun_cpp` but not `scalar_fun_tb`**. The testbench is not
synthesized, so editing it does not invalidate the hardware. Change the
testbench and re-run: C simulation runs again, synthesis does not. The
dependency list is a statement about what actually affects the output.

It lists **`verify_report`** — the artifact the verification step produces.
That is not a file synthesis reads; it is an ordering constraint expressed the
only way the graph understands. The effect is that the build refuses to
synthesize code that has not verified. Spending two minutes synthesizing
something already known to be wrong is a waste, and worse, you can end up
debugging RTL for a bug that was in the C++ all along.

**`produces`** is the solution directory, which the co-simulation and
report-parsing steps downstream will consume.

### Doing it without waveflow

~~~powershell
$env:SCALAR_FUN_STAGE = "csynth"
& "C:/Xilinx/2025.1/Vitis/bin/vitis-run.bat" --mode hls --tcl run.tcl
~~~

or in the GUI, **C Synthesis → Run**. Both run the same `csynth_design`
command. Neither will stop you synthesizing code that failed its checks.

## Re-running a step on purpose

Sometimes you want a step to run again although nothing changed — after a tool
upgrade, or just to watch it work:

~~~bash
(env) python scalar_fun_build.py --through csynth --force-step csynth
(env) python scalar_fun_build.py --through csynth --force
~~~

`--force-step` takes one step name and can be repeated; `--force` rebuilds
everything.

---
Go to [Running an RTL simulation](./rtlsim.md)
