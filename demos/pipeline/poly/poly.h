#ifndef POLY_H
#define POLY_H

// The kernel: a cubic, y[i] = c[0] + c[1]*x[i] + c[2]*x[i]^2 + c[3]*x[i]^3,
// evaluated in FP32 for every sample of an array.  See poly.cpp.

// The arrays' size: the largest call the kernel takes.  A call processes the
// first nsamp entries.
#define MAX_NSAMP 1024
#define NCOEFF 4

// The loop optimizations, one macro each, so one source builds every variant.
// run.tcl sets them per project with -D flags; the defaults here are the
// pipelined loop, II = 1, with no unrolling.
//
//   POLY_PIPELINE   1: #pragma HLS PIPELINE II=1      0: #pragma HLS PIPELINE off
//   POLY_UNROLL     the factor in #pragma HLS UNROLL factor=..., 1 for none
//   POLY_PARTITION  1: split x and y into POLY_UNROLL memories (cyclic)
//                   0: leave each in one memory, with one port
#ifndef POLY_PIPELINE
#define POLY_PIPELINE 1
#endif
#ifndef POLY_UNROLL
#define POLY_UNROLL 1
#endif
#ifndef POLY_PARTITION
#define POLY_PARTITION 1
#endif

void poly(const float coeffs[NCOEFF], const float x[MAX_NSAMP], float y[MAX_NSAMP],
          int nsamp);

#endif  // POLY_H
