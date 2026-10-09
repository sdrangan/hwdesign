---
title: Polynomial example
parent: Loop optimization
nav_order: 1
has_children: false
---

# Polynomial example

We  return to the polynomial example in the [command fifo demo](../fifoif/)  As described there,
the IP will compute a polynomial function:

```python
y[k] = a[0] + a[1]*x[k] + ... + a[d-1]*x[k]**d
```

Here we will use the pipelining to optimize the loop over the iteration `k`.

## Implementation

> **This demo is being reworked.** Its code has been taken down while it is
> updated for this term, so the walkthrough below has no code to run yet.

The example follows the same protocol as in the command-fifo example:

- The PS sends a `PolyCmdHdr` with the coefficients, `coeffs`, number of samples, `nsamp`, and a transaction ID, `tx_id`.
- The IP repsonds with a `PolyRespHdr` message with the transcation ID, `tx_id`.  This ensures that the IP is in sync and has received the data.
- The PS then sends a vector of samples `x`.
- The IP computes the output data vector `y`
- When complete the IP sends a `PolyRespFtr` message with an indication of the number of samples and any error code.


The Vitis kernel is mostly identical to the polynomial example in the command-response FIFO example, except here we store the data in arrays before performing the computation. This is not the most efficient solution, but will also us to examine the loop without having to consider the streaming interfaces in the compute loop.  The C code is as follows.  The `ARRAY_PARTITION` pragma divides the arrays in blocks that can be accessed in parallel.

```c
float x[max_nsamp];
float y[max_nsamp];
#pragma HLS ARRAY_PARTITION variable=x type=cyclic factor=UNROLL_FACTOR  dim=1
#pragma HLS ARRAY_PARTITION variable=y type=cyclic factor=UNROLL_FACTOR  dim=1
```

Once the data is in the local storage, we can run the compute loop:

```c
    compute_loop:  for (int i = 0; i < nsamp; ++i) {
#pragma HLS loop_tripcount min=1 max=max_nsamp
#if UNROLL_FACTOR > 1
#pragma HLS unroll factor=UNROLL_FACTOR        
#else
#pragma HLS pipeline II=1
#endif
        y[i] = eval_poly_horner(cmd_hdr.coeffs.data, x[i]);
    }
```


The compile directive enable control of the unroll factor

## Running the notebook

Going through the jupyter notebook, you will see:

- Construct data schemas for the input and output of the IP
- Autogenerate the include file
- Implement partitioned local storage in the IP
- Create a TCL file with that sweeps over different unroll factors
- Parse the synthesis reports and measure latency and resource utilization as a function of the unroll factor


