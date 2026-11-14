#include "fsum.h"

// The sum of N floats, four ways.  A float add takes several cycles (four at
// 100 MHz on the Zynq-7020), and each iteration's add needs the sum the last
// one produced: a loop-carried dependency through a 4-cycle operation, so the
// rolled loop reaches II = 4, as in unit 7.  What does unrolling do?
//
// x is one memory with one port, as in the other demos: one read per cycle.

float fsum(const float x[N]) {
    #pragma HLS INTERFACE mode=ap_memory  port=x storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_ctrl_hs port=return

    float sum = 0;

#if FSUM_VARIANT == 0
    // rolled: one add per iteration, each waiting for the last: II = 4.
    sum_loop: for (int i = 0; i < N; i++) {
        #pragma HLS PIPELINE II=1
        sum += x[i];
    }

#elif FSUM_VARIANT == 1
    // pragma: unrolled by 4.  Vitis keeps the order of the float additions,
    // since reordering them could change the rounding: the body becomes
    // (((sum + x0) + x1) + x2) + x3, four adds in a chain through sum.  The
    // recurrence is now 4 adds long: II = 16, a quarter of the iterations, and
    // no faster at all.
    sum_loop: for (int i = 0; i < N; i++) {
        #pragma HLS PIPELINE II=1
        #pragma HLS UNROLL factor=4
        sum += x[i];
    }

#elif FSUM_VARIANT == 2
    // tree: unrolled by hand, with the four samples added among themselves
    // first.  Only the last add is on the recurrence: II = 4 again, but for
    // four samples, so one sample per cycle.  The four reads of x share one
    // port, but they fit in the 4 cycles the recurrence takes anyway.
    sum_loop: for (int i = 0; i < N; i += 4) {
        #pragma HLS PIPELINE II=1
        sum += (x[i] + x[i + 1]) + (x[i + 2] + x[i + 3]);
    }

#else
    // lanes: four partial sums, one per sample of the unrolled iteration,
    // combined at the end.  Each is still a 4-cycle recurrence: II = 4, one
    // sample per cycle, the same as the tree.
    float part[4] = {0, 0, 0, 0};
    #pragma HLS ARRAY_PARTITION variable=part type=complete
    sum_loop: for (int i = 0; i < N; i += 4) {
        #pragma HLS PIPELINE II=1
        lane_loop: for (int j = 0; j < 4; j++) {
            part[j] += x[i + j];
        }
    }
    sum = (part[0] + part[1]) + (part[2] + part[3]);
#endif

    return sum;
}
