#ifndef FIR_H
#define FIR_H

// The kernel: a 16-tap FIR filter on 16-bit integer samples,
//
//     y[n] = h[0]*x[n] + h[1]*x[n-1] + ... + h[NTAPS-1]*x[n-NTAPS+1],
//
// with x[n] = 0 for n < 0, for every sample n of an array.  A loop over the
// samples, around a loop over the taps: the nested loop of unit 8.  See
// fir.cpp.

#define NTAPS 16
// The arrays' size: the largest call the kernel takes.  A call filters the
// first nsamp samples.
#define MAX_NSAMP 1024

// Which way the nested loop is written, one macro, so one source builds every
// variant.  run.tcl sets it per project with a -D flag:
//
//   FIR_VARIANT 0  inner:  the tap loop pipelined, the sample loop not, and
//                          the nest kept as two loops (LOOP_FLATTEN off)
//               1  flat:   the same code, which Vitis flattens into one
//                          pipelined loop over all n and k
//               2  outer:  the sample loop pipelined; Vitis unrolls the tap
//                          loop, which then reads x NTAPS times per sample
//               3  delay:  the sample loop pipelined, with the last NTAPS
//                          samples kept in a delay line of registers
#ifndef FIR_VARIANT
#define FIR_VARIANT 3
#endif

void fir(const short h[NTAPS], const short x[MAX_NSAMP], int y[MAX_NSAMP], int nsamp);

#endif  // FIR_H
