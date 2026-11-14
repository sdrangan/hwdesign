---
title: The Kernel
parent: "FIR: Nested Loops"
nav_order: 1
has_children: false
---

# The Kernel

## The interface

```cpp
void fir(const short h[NTAPS], const short x[MAX_NSAMP], int y[MAX_NSAMP], int nsamp) {
    #pragma HLS INTERFACE mode=ap_memory  port=h storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_memory  port=x storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_memory  port=y storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_none    port=nsamp
    #pragma HLS INTERFACE mode=ap_ctrl_hs port=return
```

As in the [poly kernel](../loopopt/kernel.md): every array is a memory port
to a **single-port** block RAM, one read or one write per cycle, `nsamp` is
a plain input wire, and the call is the `ap_start` / `ap_done` handshake.
`NTAPS` is 16 and `MAX_NSAMP` 1024. The samples and coefficients are 16-bit
integers, so each product fits one DSP block and each addition takes one
cycle: no loop here is limited by a loop-carried dependency. What limits
them is the shape of the nest and the memory ports.

One source builds all four variants: the macro `FIR_VARIANT`, set per Vitis
project with a `-D` flag, picks the code, as `POLY_*` did in the poly demo.

## `inner` and `flat`: pipeline the tap loop

```cpp
sample_loop: for (int n = 0; n < nsamp; n++) {
    int acc = 0;
    tap_loop: for (int k = 0; k < NTAPS; k++) {
        #pragma HLS PIPELINE II=1
        #pragma HLS LOOP_FLATTEN off        // inner only
        int xk = (n - k >= 0) ? (int)x[n - k] : 0;
        acc += h[k] * xk;
    }
    y[n] = acc;
}
```

The obvious code. Each tap reads one `x` and one `h`, from two different
memories, and does one multiply-add: the tap loop pipelines to II = 1, one
tap per cycle. The sample loop is not pipelined.

As written, every output sample runs the tap loop from the start: enter it,
fill its pipeline, run 16 taps, drain it, leave it, write `y[n]`, and go
round again. That is the `inner` variant, with `LOOP_FLATTEN off` to keep
the two loops as two.

Without that pragma Vitis does better on its own: it **flattens** the nest
into one loop of `nsamp × 16` iterations, `sample_loop_tap_loop`, with the
`acc = 0` and the write to `y` folded in as conditions on `k`, and
pipelines that once. That is the `flat` variant: the same code, left to the
tool.

## `outer`: pipeline the sample loop

```cpp
short c[NTAPS];
#pragma HLS ARRAY_PARTITION variable=c type=complete
coeff_loop: for (int k = 0; k < NTAPS; k++) c[k] = h[k];

sample_loop: for (int n = 0; n < nsamp; n++) {
    #pragma HLS PIPELINE II=1
    int acc = 0;
    tap_loop: for (int k = 0; k < NTAPS; k++) {
        int xk = (n - k >= 0) ? (int)x[n - k] : 0;
        acc += c[k] * xk;
    }
    y[n] = acc;
}
```

Move the `PIPELINE` pragma to the sample loop. A pipelined loop's body must
be straight-line code, so Vitis **unrolls the tap loop completely**: 16
multipliers and an adder tree, one output per iteration, if each iteration
can start a cycle after the last.

The coefficients are copied once into `c`, fully partitioned into 16
registers, so all 16 are available in the same cycle. `x` is not: each
iteration reads `x[n]`, `x[n-1]`, ..., `x[n-15]` from one memory with one
port.

## `delay`: keep the samples in a delay line

```cpp
short xdly[NTAPS];
#pragma HLS ARRAY_PARTITION variable=xdly type=complete
// ... xdly cleared to 0: x[n] = 0 for n < 0

sample_loop: for (int n = 0; n < nsamp; n++) {
    #pragma HLS PIPELINE II=1
    for (int k = NTAPS - 1; k > 0; k--)   // shift, oldest end first
        xdly[k] = xdly[k - 1];
    xdly[0] = x[n];                       // the one read of x
    int acc = 0;
    for (int k = 0; k < NTAPS; k++)       // xdly[k] holds x[n-k]
        acc += c[k] * xdly[k];
    y[n] = acc;
}
```

Each sample `x[n]` is used by 16 consecutive outputs, `y[n]` to `y[n+15]`.
The `outer` variant reads it 16 times. The delay line reads it **once**,
and keeps the last 16 samples in `xdly`, fully partitioned into 16
registers that shift by one every iteration. The shift runs from the oldest
end first, so each register takes its neighbour's old value; written the
other way round, `x[n]` would be copied into all 16.

This is the hardware a DSP engineer would draw for an FIR, the "direct
form": a shift register of samples, a multiplier per tap, an adder tree.

## The build

```bash
(env) python fir_build.py --list-steps
```

```
make_inputs -> csim -> verify_csim_<variant> (x4) -> synth -> report
                                                          -> cosim -> verify_cosim -> vcd -> timing
```

- `make_inputs` writes the test vector from `golden.py`: a 16-tap smoothing
  filter and 1024 samples of a noisy square wave.
- `csim` runs **each variant** in C simulation, and `verify_csim_<variant>`
  checks each against the Python model, exactly: they are different C++,
  and an integer filter has one right answer.
- `synth` synthesizes the four variants, one Vitis project each,
  `proj_<variant>`.
- `report` reads the four synthesis reports into `results/fir.md`,
  `fir.json` and `fir.png`.
- `cosim` runs the RTL of one variant, the delay line unless
  `--sim-variant` says otherwise, and `timing` draws its memory ports.
