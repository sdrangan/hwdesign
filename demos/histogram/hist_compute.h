// hist_compute.h -- the compute task: [descriptor | samples] in, [write command | descriptor |
// counts] out.  Streams only: it never sees an address of its own, only the one the
// descriptor carries for the write mover.
//
// It frames the write before it bins: the MemWCmd and the descriptor go out as soon as the
// descriptor is read, so the write mover is waiting for the counts before the first sample
// arrives, and the write command is not on the critical path.
//
// counts[] is partitioned into NBINS registers.  The increment is a read-modify-write, and a
// sample landing in the same bin as the one before depends on it: the loop can start a sample
// every cycle (II=1) only if read, add and write fit in one.  In registers they do.  (Left in a
// BRAM, Vitis still schedules II=1 but warns the chain misses a 10 ns clock: HLS 200-887.)
#ifndef HIST_COMPUTE_H
#define HIST_COMPUTE_H
#include "hist_types.h"

static void hist_compute(hls::stream<frame_t>& rd_data, hls::stream<frame_t>& wr_data) {
    HistDesc d;
    d.read_framed_stream<MEM_DW>(rd_data);      // the header the read mover relayed
    const bool ok = (d.status == HistStatus::OK);

    MemWCmd wc;                                 // write NBINS counts to cnt_addr, and
    wc.addr = d.cnt_addr;                       // echo the one burst behind this when done
    wc.len = ok ? NBINS : 0;
    wc.fwd_bursts = 1;
    wc.write_framed_stream<MEM_DW>(wr_data);
    d.write_framed_stream<MEM_DW>(wr_data);     // that burst: the same descriptor, passed on

    count_t counts[NBINS];
#pragma HLS ARRAY_PARTITION variable=counts complete
CLEAR: for (int b = 0; b < NBINS; b++) {
#pragma HLS UNROLL
        counts[b] = 0;
    }
SAMPLES: for (int i = 0; i < (int)d.n; i++) {
#pragma HLS PIPELINE II=1
        bool last;
        const word_t x = streamutils::read_boundary_word<frame_t, MEM_DW>(rd_data, last);
        const word_t bin = x >> d.shift;
        counts[bin < NBINS ? (int)bin : NBINS - 1]++;
    }
    if (ok) {
    COUNTS: for (int b = 0; b < NBINS; b++) {
#pragma HLS PIPELINE II=1
            streamutils::write_boundary_word<frame_t, MEM_DW>(wr_data, counts[b], b == NBINS - 1);
        }
    }
}

#endif  // HIST_COMPUTE_H
