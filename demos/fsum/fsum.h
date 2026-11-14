#ifndef FSUM_H
#define FSUM_H

// The kernel: the sum of N floats, sum = x[0] + x[1] + ... + x[N-1], written
// four ways to see what unrolling does to a reduction.  See fsum.cpp.
#define N 1024

// Which way the loop is written, one macro, so one source builds every
// variant.  run.tcl sets it per project with a -D flag:
//
//   FSUM_VARIANT 0  rolled:  sum += x[i], pipelined
//                1  pragma:  the same loop with UNROLL factor=4
//                2  tree:    unrolled by 4 by hand, sum += (x0 + x1) + (x2 + x3)
//                3  lanes:   unrolled by 4 by hand, four partial sums
#ifndef FSUM_VARIANT
#define FSUM_VARIANT 2
#endif

float fsum(const float x[N]);

#endif  // FSUM_H
