// YOUR KERNEL.  This is the only file you edit.
//
// It starts as a copy of the reference loop (sqsum_ref.cpp).  Build it as is
// and read the synthesis report: the loop asks for II = 1 but does not get
// it.  Find out why, then rewrite the loop so it reaches II = 1, and build
// again:
//
//     python sqsum_build.py
//
// Rules: keep the interface pragmas as they are (x and y stay single-port
// memories), and y must match the Python model exactly -- the build checks.
#include "sqsum.h"

void sqsum(const float x[N], float y[N]) {
#pragma HLS INTERFACE mode=ap_memory port=x storage_type=ram_1p
#pragma HLS INTERFACE mode=ap_memory port=y storage_type=ram_1p

    // ---- edit from here ----
    sample_loop: for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
        float prev = (i == 0) ? 0.0f : x[i - 1];
        y[i] = x[i] * x[i] + prev * prev;
    }
    // ---- to here ----
}
