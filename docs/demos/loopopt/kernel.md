---
title: The Kernel
parent: Loop Optimization
nav_order: 1
has_children: false
---

# The Kernel

## The computation

The kernel evaluates a cubic at every sample of an array, by **Horner's
method**, as in the lecture:

```
y = ((c3*x + c2)*x + c1)*x + c0
```

Three multiplies and three adds per sample, in single-precision floating
point (FP32), and every one of them depends on the one before. A
floating-point operation is itself a small pipeline: at 100 MHz a multiply
takes 4 clock cycles and an add 5. So one sample takes about 30 cycles
from reading `x` to writing `y`, and that is the number this demo tries
to get around.

```cpp
static float horner(const float c[NCOEFF], float x) {
#pragma HLS INLINE
    float y = c[3];
    y = y * x + c[2];
    y = y * x + c[1];
    y = y * x + c[0];
    return y;
}
```

`INLINE` puts the function's body into the loop that calls it, so Vitis
schedules its operations together with the loop's own.

## The interface: memories, not AXI

```cpp
void poly(const float coeffs[NCOEFF], const float x[MAX_NSAMP], float y[MAX_NSAMP],
          int nsamp) {
    #pragma HLS INTERFACE mode=ap_memory  port=coeffs storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_memory  port=x      storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_memory  port=y      storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_none    port=nsamp
    #pragma HLS INTERFACE mode=ap_ctrl_hs port=return
```

As in the [timing demo](../timing/kernel.md), the project is built for the
Vivado IP flow, so there is no AXI. What is new is the arrays. Each array
argument becomes an **`ap_memory`** port: the wires of a block RAM that
sits outside the kernel. For `x`:

| Port | Direction | What it carries |
| --- | --- | --- |
| `x_address0` | out | which word to read |
| `x_ce0` | out | chip enable: read this cycle |
| `x_q0` | in | the word, one cycle later |

and for `y`, `y_address0`, `y_ce0`, `y_we0` (write enable) and `y_d0`
(the word to write). `storage_type=ram_1p` says the RAM has **one port**:
one read or one write per clock cycle. That limit is what part 2 runs
into. `MAX_NSAMP` is 1024; a call processes the first `nsamp` samples.

The coefficients are read once, into registers, before the sample loop,
so the loop never waits on the coefficient memory:

```cpp
    float c[NCOEFF];
    #pragma HLS ARRAY_PARTITION variable=c type=complete
    coeff_loop: for (int j = 0; j < NCOEFF; j++) {
        c[j] = coeffs[j];
    }
```

`ARRAY_PARTITION ... complete` makes each element of `c` a register of its
own, rather than a word in a memory, so all four can be read in the same
cycle.

## The loop, and its pragmas

```cpp
    sample_loop: for (int i = 0; i < nsamp; i++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_NSAMP
#if POLY_PIPELINE
        #pragma HLS PIPELINE II=1
#else
        #pragma HLS PIPELINE off
#endif
#if POLY_UNROLL > 1
        #pragma HLS UNROLL factor=POLY_UNROLL
#endif
        y[i] = horner(c, x[i]);
    }
```

- `sample_loop:` is a **label**. Vitis names the loop after it in every
  report. An unlabelled loop gets a name from its line number, like
  `VITIS_LOOP_65_1`, which changes whenever the file above it does.
- `LOOP_TRIPCOUNT` tells the report how many times the loop runs. `nsamp`
  is only known at run time, so without it Vitis cannot give a latency in
  cycles. It changes nothing in the hardware.
- `PIPELINE II=1` asks for a new iteration every clock cycle. `PIPELINE
  off` asks for none. Without either, Vitis pipelines loops on its own
  (the report shows `coeff_loop`, which has no pragma, pipelined), and
  part 1 needs an unpipelined loop to compare against.
- `UNROLL factor=N` makes `N` copies of the body, for part 2.

And before the loop, for part 2, the partitioning of `x` and `y`:

```cpp
#if POLY_PARTITION && POLY_UNROLL > 1
    #pragma HLS ARRAY_PARTITION variable=x type=cyclic factor=POLY_UNROLL
    #pragma HLS ARRAY_PARTITION variable=y type=cyclic factor=POLY_UNROLL
#endif
```

### One source, several variants

The `#if` lines choose which pragmas the compiler sees. The macros are
defined in `poly.h`, with defaults, and `run.tcl` sets them per build with
`-D` flags:

| Variant | `POLY_PIPELINE` | `POLY_UNROLL` | `POLY_PARTITION` | Pragmas in effect |
| --- | --- | --- | --- | --- |
| `nopipe` | 0 | 1 | 0 | `PIPELINE off` |
| `pipe` | 1 | 1 | 0 | `PIPELINE II=1` |
| `u2`, `u4`, `u8` | 1 | 2, 4, 8 | 1 | `PIPELINE II=1`, `UNROLL`, `ARRAY_PARTITION` |
| `u4_nopart` | 1 | 4 | 0 | `PIPELINE II=1`, `UNROLL` |

A `-D` flag belongs to a Vitis *project*, not to a solution, so each
variant is a project of its own, `proj_<variant>`. In `run.tcl`:

```tcl
proc open_variant {name pipeline unroll partition reset} {
    global script_dir
    set cflags "-I$script_dir -DPOLY_PIPELINE=$pipeline -DPOLY_UNROLL=$unroll -DPOLY_PARTITION=$partition"
    ...
    open_project -reset proj_$name
    set_top poly
    add_files [file join $script_dir poly.cpp] -cflags $cflags
    add_files -tb [file join $script_dir tb_poly.cpp] -cflags $cflags
}
```

The macros are only a convenience for the demo. In your own code, write
the pragma you want directly in the loop.

## The testbench and the golden model

`tb_poly.cpp` reads a test vector from `cases.txt` (the number of samples,
the four coefficients, then the `x` values), calls `poly()` once, and
writes `results.json` with every `y`. In C simulation the call runs the
C++; in co-simulation it runs the RTL, with the testbench's arrays standing
in for the block RAMs.

`golden.py` writes the test vector, 64 samples evenly spaced over
[−1, 1) with coefficients 1, −2, −3, 4, and the expected results from a
Python model of the same Horner evaluation, every step rounded to FP32:

```python
def poly(coeffs, x: np.ndarray) -> np.ndarray:
    c = np.asarray(coeffs, dtype=np.float32)
    x = np.asarray(x, dtype=np.float32)
    y = np.full_like(x, c[3])
    for k in (2, 1, 0):
        y = (y * x).astype(np.float32)
        y = (y + c[k]).astype(np.float32)
    return y
```

Because the operations happen in the same order with the same rounding,
the hardware must agree with this model **bit for bit**. The testbench
writes each result's bit pattern, `y_bits`, and the build compares those,
not printed decimals that could agree while the numbers differ in the last
bit.

Next: [pipelining the loop](pipeline.md).
