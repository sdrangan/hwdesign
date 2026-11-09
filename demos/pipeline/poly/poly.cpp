#include "poly.h"

// The cubic from unit 7, by Horner's method:
//
//     y = ((c[3]*x + c[2])*x + c[1])*x + c[0]
//
// Three FP32 multiplies and three FP32 adds per sample, all in series.  Each
// of those operations is itself several clock cycles long at 100 MHz, so one
// sample takes tens of cycles from x to y.  The loop over the samples is
// where the optimizations go:
//
//   * PIPELINE lets sample i+1 start before sample i has finished: one new
//     sample every II cycles instead of one every few dozen.
//   * UNROLL copies the loop body, so several samples start in each cycle --
//     if the memories holding x and y can deliver that many words a cycle.
//   * ARRAY_PARTITION makes sure they can, by splitting each array over
//     several memories.
//
// Which of these are on is set by the POLY_* macros in poly.h, so one source
// builds every variant the demo compares.
//
// The interface is built for the Vivado IP flow (run.tcl), like the quad
// demo in unit 6, but with arrays: each array argument becomes a memory
// port (ap_memory) -- an address out, a data word in or out, and an enable
// -- that the caller connects a block RAM to.  `storage_type=ram_1p` says
// that RAM has one port: one read or one write per cycle.  nsamp is a plain
// input wire, and ap_start / ap_done is the handshake, as in quad.

static float horner(const float c[NCOEFF], float x) {
#pragma HLS INLINE
    float y = c[3];
    y = y * x + c[2];
    y = y * x + c[1];
    y = y * x + c[0];
    return y;
}

void poly(const float coeffs[NCOEFF], const float x[MAX_NSAMP], float y[MAX_NSAMP],
          int nsamp) {
    #pragma HLS INTERFACE mode=ap_memory  port=coeffs storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_memory  port=x      storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_memory  port=y      storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_none    port=nsamp
    #pragma HLS INTERFACE mode=ap_ctrl_hs port=return

#if POLY_PARTITION && POLY_UNROLL > 1
    // Sample i goes to memory i % POLY_UNROLL, so the POLY_UNROLL samples one
    // unrolled iteration needs are in POLY_UNROLL different memories.
    #pragma HLS ARRAY_PARTITION variable=x type=cyclic factor=POLY_UNROLL
    #pragma HLS ARRAY_PARTITION variable=y type=cyclic factor=POLY_UNROLL
#endif

    // The coefficients are read once, into registers, so the sample loop
    // never waits on the coefficient memory.
    float c[NCOEFF];
    #pragma HLS ARRAY_PARTITION variable=c type=complete
    coeff_loop: for (int j = 0; j < NCOEFF; j++) {
        c[j] = coeffs[j];
    }

    if (nsamp > MAX_NSAMP) {
        nsamp = MAX_NSAMP;
    }

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
}
