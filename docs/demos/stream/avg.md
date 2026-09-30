---
title: The Averaging Kernel
parent: AXI4-Streaming
nav_order: 2
has_children: false
---

# The Averaging Kernel

## What it computes

The kernel is a moving average of the squares of its input:

$$y[k] = \frac{1}{3}\left(x[k]^2 + x[k-1]^2 + x[k-2]^2\right)$$

Each output is the average power of the last three input samples. This is
a small example of a **filter**: a stream in, a stream out, one output per
input, with a little memory of the past.

The files are in `hwdesign/demos/stream/avgfilt`.

## The Vitis HLS kernel

The whole kernel, from `avgfilt.cpp`:

~~~cpp
void avgfilt(
    hls::stream<float>& in_stream,
    hls::stream<float>& out_stream)
{

#pragma HLS INTERFACE axis port=in_stream
#pragma HLS INTERFACE axis port=out_stream
#pragma HLS INTERFACE ap_ctrl_none port=return

    // Last squared values
    static float xsq0 = 0.;
    static float xsq1 = 0.;

    constexpr float inv_win_size = 1/static_cast<float>(win_size);

    while (1) {
        // Exit when in_stream is empty.  This is for C simulation
        // only to support Vitis C call convention.
#ifndef __SYNTHESIS__
        if (in_stream.empty()) {
            break;
        }
#endif

#pragma HLS PIPELINE II=1
        // Read value
        float xi = in_stream.read();
        float xsq = xi*xi;

        // Output value
        float yi = (xsq + xsq0 + xsq1)*inv_win_size;
        out_stream.write(yi);

        // Update delay line
        xsq1 = xsq0;
        xsq0 = xsq;

    }

}
~~~

Each piece of it has a job:

* **`hls::stream<float>`** is a FIFO. In C++ it behaves like a queue, with
  `read()` popping the front and `write()` pushing onto the back. In
  hardware it becomes a stream port.
* **`#pragma HLS INTERFACE axis`** makes each stream an **AXI4-Stream**
  port, with `TDATA`, `TVALID` and `TREADY` signals. A `read()` waits for
  a transfer on the input, and a `write()` waits for one on the output.
* **`#pragma HLS INTERFACE ap_ctrl_none port=return`** removes the start and
  done handshake. The scalar function IP had `ap_start` and `ap_done`
  because the processor started each call. This kernel is never started
  and never finishes: it just runs.
* **`while (1)`** is that "just runs". In hardware the loop never exits.
* **`static float xsq0, xsq1`** are the **delay line**: the squares of the
  previous two inputs. They are `static` so they keep their values between
  iterations, and in hardware they become two 32-bit registers.
* **`#pragma HLS PIPELINE II=1`** asks for an **initiation interval** of 1:
  start a new loop iteration every clock cycle. One sample in and one out
  per clock is what makes streaming fast.
* **The `#ifndef __SYNTHESIS__` block** exists only for C simulation. There,
  the kernel is an ordinary C++ function that the testbench calls once,
  and it has to return. So it stops when the input runs dry. Synthesis
  never sees these lines.

`win_size = 3` is defined in `avgfilt.h`. The kernel keeps an explicit
two-deep delay line, so changing `win_size` alone does not give a longer
filter.

## The testbench

The testbench, `tb_avgfilt.cpp`, is a C++ program with a `main()`. Vitis
uses the same testbench twice: once against the C++ kernel in **C
simulation**, and again against the synthesized hardware in
**co-simulation**. It:

1. Reads the input samples `x` from `vectors/tv_python.csv`, which the
   Python golden model writes on the [next page](./python.md).
2. Pushes them all into `in_stream`, then calls `avgfilt()` once.
3. Recomputes each expected output itself, reads the actual output from
   `out_stream`, and prints `FAIL` for any sample that differs.
4. Writes the samples it got back to `vectors/tv_csim.csv` or
   `vectors/tv_cosim.csv`.
5. Returns non-zero if anything failed. Vitis reads this return code, so a
   failing testbench fails the Vitis run.

The core of it is:

~~~cpp
for (size_t i = 0; i < nsamp; i++) in_stream.write(x[i]);

avgfilt(in_stream, out_stream);

for (size_t i = 0; i < nsamp; i++) {
    const float xsq = x[i] * x[i];
    const float y_exp = (xsq + xsq0 + xsq1) * inv_win_size;
    ...
    const float yi = out_stream.read();
    y.push_back(yi);
    ...
}
~~~

Step 4 matters more than it looks. A `PASS` printed on the console cannot
be checked by anything downstream. The file can: the build script compares
it against the Python model, which catches a testbench that is wrong in
the same way as the kernel.

The two file paths arrive as command-line arguments, which `run.tcl`
passes through `-argv`. They are absolute paths because co-simulation runs
the testbench from deep inside the Vitis project directory, not from
`avgfilt/`. If you open the component in the Vitis GUI and press Run, no
arguments are passed, and the testbench falls back to a short built-in
test vector.

## The Vitis script

`run.tcl` runs **one** Vitis stage per invocation, chosen by the
`AVGFILT_STAGE` environment variable: `csim`, `csynth` or `cosim`. It is
the same pattern as the [scalar function demo's script](../procif/tcl.md).
Running the stages separately is what lets the build script check each
one's output before starting the next.

You will not usually run `run.tcl` yourself; the build script does. But
you can, from `demos/stream/avgfilt`:

~~~powershell
$env:AVGFILT_STAGE = "csim"
vitis-run --mode hls --tcl run.tcl
~~~

---

Go to [The Python Golden Model](./python.md)
