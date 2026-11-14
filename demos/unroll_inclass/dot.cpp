// YOUR KERNEL.  This is the only file you edit.
//
// It starts as a copy of the reference loop (dot_ref.cpp), which takes one
// sample per clock cycle.  Your goal is four samples per cycle: about a
// quarter of the cycles.  Build it as is first, then follow the steps on the
// exercise page, building after each one:
//
//     python dot_build.py
//
// Rules: keep the interface pragmas (a and b stay single-port memories, but
// you may partition them), and the result must match the Python model
// exactly -- the build checks.
#include "dot.h"

int dot(const short a[N], const short b[N]) {
#pragma HLS INTERFACE mode=ap_memory port=a storage_type=ram_1p
#pragma HLS INTERFACE mode=ap_memory port=b storage_type=ram_1p

    // ---- edit from here ----
    int sum = 0;
    dot_loop: for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
        sum += a[i] * b[i];
    }
    return sum;
    // ---- to here ----
}
