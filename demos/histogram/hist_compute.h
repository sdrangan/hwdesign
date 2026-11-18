// hist_compute.h -- the compute task: samples in, counts out.  Streams only: it never sees an
// address, so it is the same task whichever way the samples reach it.
//
// counts[] is partitioned into NBINS registers.  The increment is a read-modify-write, and a
// sample landing in the same bin as the one before depends on it: the loop can start a sample
// every cycle (II=1) only if read, add and write fit in one.  In registers they do.  (Left in a
// BRAM, Vitis still schedules II=1 but warns the chain misses a 10 ns clock: HLS 200-887.)
#ifndef HIST_COMPUTE_H
#define HIST_COMPUTE_H
#include "hist_types.h"

static void hist_compute(hls::stream<HistJob>& job, hls::stream<word_t>& samples,
                         hls::stream<word_t>& counts_out) {
    count_t counts[NBINS];
#pragma HLS ARRAY_PARTITION variable=counts complete
    const HistJob j = job.read();
CLEAR: for (int b = 0; b < NBINS; b++) {
#pragma HLS UNROLL
        counts[b] = 0;
    }
SAMPLES: for (int i = 0; i < (int)j.n; i++) {
#pragma HLS PIPELINE II=1
        const word_t x = samples.read();
        const word_t bin = x >> j.shift;
        counts[bin < NBINS ? (int)bin : NBINS - 1]++;
    }
    if (j.emit) {
    COUNTS: for (int b = 0; b < NBINS; b++) {
#pragma HLS PIPELINE II=1
            counts_out.write(counts[b]);
        }
    }
}

#endif  // HIST_COMPUTE_H
