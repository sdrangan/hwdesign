// hist_simple.cpp -- the unit 9 histogram: one kernel task and two plain data movers.
//
//   s_cmd -> +---------+ -MRCmd-> mem_r_stream (m_rd) -samples-+
//            |         | <-------------------------------------+
//            | compute |
//            |         | -MWCmd + counts-> mem_w_stream_done (m_wr) -+
//   s_done <-+---------+ <-------------- MemComplete ----------------+
//
// The compute task handles one job per firing, start to finish: load, bin, store, wait for
// the write to be acknowledged, respond.  Jobs never overlap (unit 10 overlaps them).
#include "hist_simple.h"
#include "mem_r_stream_task.h"
#include "mem_w_stream_done_task.h"
#include <hls_task.h>

static void hist_compute(hls::stream<word_t>& s_cmd, hls::stream<word_t>& s_done,
                         hls::stream<word_t>& rd_cmd, hls::stream<word_t>& rd_data,
                         hls::stream<word_t>& wr_cmd, hls::stream<word_t>& wr_data,
                         hls::stream<word_t>& wr_done) {
    HistCmd cmd;
    cmd.read_stream<MEM_DW>(s_cmd);
    HistResp resp;
    resp.job_id = cmd.job_id;
    resp.status = (cmd.n <= MAX_N) ? HistStatus::OK : HistStatus::N_TOO_LARGE;

    if (resp.status == HistStatus::OK) {        // a refused job touches no memory
        MRCmd rc;                               // load: n samples from data_addr
        rc.addr = cmd.data_addr;
        rc.len = cmd.n;
        rc.write_stream<MEM_DW>(rd_cmd);

        count_t counts[NBINS];
#pragma HLS ARRAY_PARTITION variable=counts complete
    CLEAR: for (int b = 0; b < NBINS; b++) {
#pragma HLS UNROLL
            counts[b] = 0;
        }
    SAMPLES: for (int i = 0; i < (int)cmd.n; i++) {       // compute
#pragma HLS PIPELINE II=1
            const word_t bin = rd_data.read() >> cmd.shift;
            counts[bin < NBINS ? (int)bin : NBINS - 1]++;
        }

        MWCmd wc;                               // store: NBINS counts to cnt_addr
        wc.addr = cmd.cnt_addr;
        wc.len = NBINS;
        wc.write_stream<MEM_DW>(wr_cmd);
    COUNTS: for (int b = 0; b < NBINS; b++) {
#pragma HLS PIPELINE II=1
            wr_data.write(counts[b]);
        }

        MemComplete done;                       // wait: the counts are in memory
        done.read_stream<MEM_DW>(wr_done);
    }
    resp.write_stream<MEM_DW>(s_done);
}

void hist_simple(hls::stream<word_t>& s_cmd, const word_t* m_rd, word_t* m_wr,
                 hls::stream<word_t>& s_done) {
#pragma HLS INTERFACE axis port=s_cmd
#pragma HLS INTERFACE m_axi port=m_rd offset=off bundle=gmem0 depth=65536
#pragma HLS stable variable=m_rd
#pragma HLS INTERFACE m_axi port=m_wr offset=off bundle=gmem1 depth=65536
#pragma HLS stable variable=m_wr
#pragma HLS INTERFACE axis port=s_done
#pragma HLS INTERFACE ap_ctrl_none port=return
    hls_thread_local hls::stream<word_t> rd_cmd, rd_data, wr_cmd, wr_data, wr_done;

    hls_thread_local hls::task t_rd(mem_r_stream_task<MEM_DW>, rd_cmd, m_rd, rd_data);
    hls_thread_local hls::task t_comp(hist_compute, s_cmd, s_done,
                                      rd_cmd, rd_data, wr_cmd, wr_data, wr_done);
    hls_thread_local hls::task t_wr(mem_w_stream_done_task<MEM_DW>, wr_cmd, wr_data, m_wr, wr_done);
}
