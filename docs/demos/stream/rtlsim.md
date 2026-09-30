---
title: Synthesis and RTL Simulation
parent: AXI4-Streaming
nav_order: 5
has_children: false
---

# Synthesis and RTL Simulation

C simulation showed that the C++ is right. It said nothing about hardware,
because it ran the C++ on your processor. This page turns the kernel into
RTL and checks that the RTL still computes the same thing.

Run everything below from `hwdesign/demos/stream/avgfilt`, as before.

## Step 5: Synthesize the kernel (`csynth`)

~~~bash
(env) python avgfilt_build.py --through csynth
~~~

~~~text
csynth:
    results\csynth\avgfilt_csynth.rpt
    RUNNING...
Vitis HLS stage 'csynth' done; log in results\csynth\vitis.log
    PASSED
~~~

This takes a minute or so. The generated Verilog is in
`avgfilt_proj/solution1/syn/verilog`:

~~~text
avgfilt.v
avgfilt_fadd_32ns_32ns_32_5_full_dsp_1.v
avgfilt_fmul_32ns_32ns_32_4_max_dsp_1.v
avgfilt_regslice_both.v
~~~

* `avgfilt.v` is the kernel: the pipeline and the delay-line registers.
* `avgfilt_fadd_...` and `avgfilt_fmul_...` are the **floating-point
  adder and multiplier**. You can read their properties off the names:
  32-bit, with a latency of 5 cycles for the adder and 4 for the
  multiplier.
* `avgfilt_regslice_both.v` is a **register slice** on each AXI4-Stream
  port, which buffers `TDATA`/`TVALID`/`TREADY` so the stream timing does
  not depend on the logic inside.

The build script copies the synthesis report to
`results/csynth/avgfilt_csynth.rpt`. Three parts of it are worth reading.

### The interface

~~~text
+-------------------+-----+-----+--------------+--------------+
|     RTL Ports     | Dir | Bits|   Protocol   | Source Object|
+-------------------+-----+-----+--------------+--------------+
|ap_clk             |   in|    1|  ap_ctrl_none|       avgfilt|
|ap_rst_n           |   in|    1|  ap_ctrl_none|       avgfilt|
|in_stream_TDATA    |   in|   32|          axis|     in_stream|
|in_stream_TVALID   |   in|    1|          axis|     in_stream|
|in_stream_TREADY   |  out|    1|          axis|     in_stream|
|out_stream_TDATA   |  out|   32|          axis|    out_stream|
|out_stream_TVALID  |  out|    1|          axis|    out_stream|
|out_stream_TREADY  |   in|    1|          axis|    out_stream|
+-------------------+-----+-----+--------------+--------------+
~~~

This is the whole interface of the IP: a clock, a reset, and two
AXI4-Stream ports with three signals each. There is **no TLAST**, because
pure streaming has no frames. There is **no `ap_start` or `ap_done`**,
because `ap_ctrl_none` removed them. Compare this with the scalar function
IP, where everything went through AXI4-Lite registers.

### The pipeline

~~~text
+-------------------+---------+---------+----------+-----------+-----------+------+----------+
|                   |  Latency (cycles) | Iteration|  Initiation Interval  | Trip |          |
|     Loop Name     |   min   |   max   |  Latency |  achieved |   target  | Count| Pipelined|
+-------------------+---------+---------+----------+-----------+-----------+------+----------+
|- VITIS_LOOP_25_1  |        ?|        ?|        19|          1|          1|   inf|       yes|
+-------------------+---------+---------+----------+-----------+-----------+------+----------+
~~~

* **Initiation interval, achieved: 1.** The `PIPELINE II=1` pragma was met:
  a new sample enters every clock cycle. At the 100 MHz clock in `run.tcl`,
  that is 100 million samples per second.
* **Iteration latency: 19.** Each sample takes 19 cycles to get from input
  to output. That is the multiplier (4) for the square, two adders (5 + 5),
  and the multiplier (4) for the `1/3`, plus a cycle to read. Pipelining
  means those 19 cycles overlap: 19 samples are in flight at once.
* **Trip count: inf**, and the overall latency is `?`. The loop never ends,
  so there is no total to report. This is what `while (1)` looks like to
  the tool.

### The resources

~~~text
|       Name      | BRAM_18K| DSP |   FF   |  LUT  | URAM|
|Total            |        0|   10|     973|   1670|    0|
~~~

Most of this is the two float adders and two float multipliers, which use
10 of the FPGA's DSP blocks between them. Floating point is expensive in
hardware.

### Under the hood: the build step

~~~python
@dataclass(kw_only=True)
class CSynthStep(BuildStep):
    """Synthesize the kernel to RTL."""

    description = "Run Vitis C synthesis; the report is copied to results/csynth/."
    consumes = ["avgfilt_cpp", "avgfilt_h", "run_tcl", "verify_csim_report"]
    produces = {"csynth_report": Path("results/csynth/avgfilt_csynth.rpt")}
    params = {"live_output": False}
~~~

It consumes the kernel but **not the testbench**, since the testbench is
not synthesized. It also consumes **`verify_csim_report`**, the output of
the comparison on the previous page. Synthesis does not read that file.
Consuming it is how the graph expresses an ordering: **never synthesize a
kernel that has not been verified**. Otherwise you can spend time
debugging RTL for a bug that was in the C++ all along.

The price is that anything that re-runs C simulation also re-runs
synthesis, because the comparison's report is rewritten.

By hand:

~~~powershell
$env:AVGFILT_STAGE = "csynth"
vitis-run --mode hls --tcl run.tcl
~~~

## Step 6: Co-simulate the RTL (`cosim`)

**C/RTL co-simulation** runs the *same* testbench again, but the call to
`avgfilt()` is now served by the synthesized RTL in a Verilog simulator
instead of by the C++ function.

~~~bash
(env) python avgfilt_build.py --through cosim
~~~

~~~text
cosim:
    vectors\tv_cosim.csv
    RUNNING...
Vitis HLS stage 'cosim' done; log in results\cosim\vitis.log
    PASSED
~~~

This is the slowest step, a few minutes. Open `results/cosim/vitis.log`
and you will find the testbench ran **twice**:

~~~text
INFO: [COSIM 212-302] Starting C TB testing ...
Wrote 200 samples to .../vectors/tv_cosim.csv
tb_avgfilt PASSED (200 samples)
...
INFO: [COSIM 212-15] Starting XSIM ...
...
INFO: [COSIM 212-316] Starting C post checking ...
Wrote 200 samples to .../vectors/tv_cosim.csv
tb_avgfilt PASSED (200 samples)
...
INFO: [COSIM 212-1000] *** C/RTL co-simulation finished: PASS ***
~~~

1. **C TB testing.** The testbench runs against the C++ kernel while Vitis
   records every sample written to `in_stream`.
2. **XSIM.** Those samples are driven into the RTL's `in_stream` AXI4-Stream
   port in the Verilog simulator, and everything the RTL produces on
   `out_stream` is recorded.
3. **C post checking.** The testbench's `main()` runs a second time, but
   now `out_stream` holds what the *hardware* produced.

The second pass overwrites `vectors/tv_cosim.csv`, so the file you are
left with describes the RTL, not the C++. That is the file the next step
checks.

Co-simulation also **records the waveforms** of the IP's ports as it runs,
because the build passes `-trace_level port` (the `--trace-level` option).
The [next page](./timing.md) turns that recording into a timing diagram.

The step consumes the synthesis report, which puts it after synthesis in
the graph. It writes `tv_cosim.csv`, a different file from C simulation's
`tv_csim.csv`, so the two runs can be checked separately rather than one
overwriting the other's evidence.

By hand:

~~~powershell
$env:AVGFILT_STAGE = "cosim"
vitis-run --mode hls --tcl run.tcl
~~~

## Step 7: Compare against the model (`verify_cosim`)

~~~bash
(env) python avgfilt_build.py --through verify_cosim
~~~

~~~text
verify_cosim:
    results\verify_cosim.json
    RUNNING...
tv_cosim.csv vs the model: 200 of 200 samples bit-exact, max |error| = 0
    PASSED
~~~

This is the same comparison as `verify_csim`, pointed at the other file.
It answers a different question. `verify_csim` asked whether the C++ is
right; `verify_cosim` asks whether the synthesized hardware still does
what the C++ did. That is not guaranteed, and a mismatch here is a bug
you would otherwise find much later, on the board.

The RTL matches the Python model bit for bit, just as the C++ did. The
floating-point cores Vitis generated are IEEE-754 compliant, so the same
operations in the same order give the same bits.

---

Go to [Viewing the Timing Diagram](./timing.md)
