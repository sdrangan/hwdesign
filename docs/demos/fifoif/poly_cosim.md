---
title: Synthesis and Co-simulation
parent: Command-Response FIFO Interface
nav_order: 8
has_children: false
---

# Synthesis and Co-simulation

C simulation showed that the kernel computes the right responses. This
page synthesizes it to RTL, runs the same testbench against the RTL, and
checks every response against the Python model again. It ends by
comparing what the three kernels synthesize to.

Run everything below from `hwdesign/demos/stream/poly`, as before. The
steps use the default kernel, the general one at 32 bits, unless you
[choose another](./poly_csim.md#choosing-the-kernel).

## Step 6: Synthesize (`csynth`)

~~~bash
(env) python poly_build.py --through csynth
~~~

The report is copied to `results/csynth/poly_csynth.rpt`. Synthesis waits
for `verify_csim`, so it never synthesizes a kernel that computes the
wrong thing.

### The interface

~~~text
+-------------------+-----+-----+--------------+
|     RTL Ports     | Dir | Bits|   Protocol   |
+-------------------+-----+-----+--------------+
|ap_clk             |   in|    1|  ap_ctrl_none|
|ap_rst_n           |   in|    1|  ap_ctrl_none|
|in_stream_TDATA    |   in|   32|          axis|
|in_stream_TVALID   |   in|    1|          axis|
|in_stream_TREADY   |  out|    1|          axis|
|in_stream_TLAST    |   in|    1|          axis|
|in_stream_TKEEP    |   in|    4|          axis|
|in_stream_TSTRB    |   in|    4|          axis|
|out_stream_TDATA   |  out|   32|          axis|
|out_stream_TVALID  |  out|    1|          axis|
|out_stream_TREADY  |   in|    1|          axis|
|out_stream_TLAST   |  out|    1|          axis|
|out_stream_TKEEP   |  out|    4|          axis|
|out_stream_TSTRB   |  out|    4|          axis|
+-------------------+-----+-----+--------------+
~~~

Compare this with the [averaging filter's](../stream/rtlsim.md#the-interface).
Each stream now has **TLAST**, because it carries messages, and **TKEEP**
and **TSTRB**, which mark which bytes of a word are valid. They come from
`streamutils::axi4s_word`, the full AXI4-Stream word, and the kernel sets
them to all ones. There is still no `ap_start` or `ap_done`, and no
AXI4-Lite port at all: the coefficients arrive on the stream, not through
registers.

### The pipeline

The sample loop is synthesized as its own pipelined block. Its report,
`poly_proj/solution1/syn/report/poly_Pipeline_VITIS_LOOP_67_1_csynth.rpt`
(the loop is on line 67 of `poly.cpp`), shows:

~~~text
|                   |  Latency (cycles) | Iteration|  Initiation Interval  | Trip |          |
|     Loop Name     |   min   |   max   |  Latency |  achieved |   target  | Count| Pipelined|
|- VITIS_LOOP_67_1  |        ?|        ?|        30|          1|          1|     ?|       yes|
~~~

* **II achieved: 1.** One stream word per clock, so at 32 bits one sample
  per clock.
* **Iteration latency: 30.** That is Horner's rule: three multiplies and
  three adds in a chain, each waiting for the one before.
* **Trip count: `?`.** It is `nsamp`, which the tool cannot know, since it
  arrives in each command.

The top-level report lists two more pipelined loops, whose names point
into the generated headers. They move the four coefficients in and out of
the command header.

### The resources

~~~text
|       Name      | BRAM_18K| DSP |   FF   |  LUT  | URAM|
|Total            |        0|   15|    2113|   3166|    0|
~~~

Three float multipliers and three float adders make up most of the
DSPs. That is one of each for every Horner step, because the steps are
pipelined rather than shared.

## Step 7: Co-simulate (`cosim`)

~~~bash
(env) python poly_build.py --through cosim
~~~

~~~text
cosim:
    results\cosim
    RUNNING...
Vitis HLS stage 'cosim' done (kernel general, WORD_BW=32); log in results\cosim\vitis.log
    PASSED
~~~

As in the [averaging filter](../stream/rtlsim.md#step-6-co-simulate-the-rtl-cosim),
the testbench runs twice. The first pass records what goes into the
kernel. The second, after the Verilog simulation, runs `main()` again with
the RTL's outputs. The three calls to `poly()` become three back-to-back
transactions on the RTL's stream ports. The kernel handles them with no
start signal at all, just by reading the next command header when it has
finished the last.

Co-simulation also records the ports' waveforms, for the
[next page](./poly_timing.md).

> **If co-simulation fails with "file generation failed" (`COSIM 212-5`).**
> On Windows this happens now and then, before any simulation starts, and
> goes away when the step is simply run again. It is most likely a
> generated file briefly locked by another program. The build retries it
> once, automatically, and says so. A real failure reports a different
> error.

## Step 8: Compare against the model (`verify_cosim`)

~~~bash
(env) python poly_build.py --through verify_cosim
~~~

~~~text
txn 0 (tx_id 0x10): 40 of 40 samples bit-exact, max |error| = 0; tx_id echoed 0x10, footer 40 read, NO_ERROR
txn 1 (tx_id 0x11): 64 of 64 samples bit-exact, max |error| = 0; tx_id echoed 0x11, footer 64 read, NO_ERROR
txn 2 (tx_id 0x12): 25 of 25 samples bit-exact, max |error| = 0; tx_id echoed 0x12, footer 25 read, NO_ERROR
~~~

The same comparison, now for the RTL. Every message matches the model,
and every sample is bit-exact.

## Comparing the kernels

The steps above built the general kernel, `poly.cpp`, at 32 bits. To
build one of the others, name it with `--kernel`,
and force the build to redo everything from C simulation on:

~~~bash
(env) python poly_build.py --through verify_cosim --kernel poly32 --force-step csim
(env) python poly_build.py --through verify_cosim --kernel poly64 --force-step csim
(env) python poly_build.py --through verify_cosim --word-bw 64 --force-step csim   # general, 64 bits
(env) python poly_build.py --through verify_cosim --force-step csim                # back to the default
~~~

All four combinations pass C simulation and co-simulation, bit for bit,
from the same test vectors. The testbench packs the vectors into 32- or
64-bit words itself. Because the testbench uses the generated headers and
the hand-written kernels do not, a pass also shows that the hand-written
unpacking matches the generated layout.

Their synthesis reports compare like this:

| Kernel | Word | Loop II | Iteration latency | DSP | FF | LUT |
| --- | --- | --- | --- | --- | --- | --- |
| `poly32` | 32 | 1 | 29 | 15 | 1755 | 2924 |
| general | 32 | 1 | 30 | 15 | 2113 | 3166 |
| `poly64` | 64 | 1 | 29 | 30 | 3242 | 5349 |
| general | 64 | 1 | 29 | 30 | 4133 | 5965 |

* **At the same width, the arithmetic is the same.** The DSPs, the II and
  the latency match. They are the same Horner datapath however the code is
  written. The general kernel uses somewhat more flip-flops and LUTs. That
  is the cost of its generality and of recovering from framing errors,
  which the hand-written versions only report.
* **At 64 bits, the stream ports are twice as wide,** and the sample loop
  still achieves **II = 1**. Each iteration now evaluates **two** samples,
  one per 32-bit half of the word, so the kernel handles twice the samples
  per clock.
* **The DSPs double, from 15 to 30.** Each of the two samples gets its own
  Horner datapath: `poly64` writes the two calls out, and the general
  kernel's `UNROLL` over the lane does the same. Twice the throughput costs
  twice the arithmetic.

---

Go to [Viewing the Timing Diagram](./poly_timing.md)
