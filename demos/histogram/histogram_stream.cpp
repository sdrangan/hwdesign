// histogram_stream.cpp -- the histogram kernel with its command and response on AXI4-Streams.
//
// Free-running (ap_ctrl_none): five hls::tasks, each re-fired by the runtime whenever its
// input arrives, joined by FIFOs.  Memory is reached only through Waveflow's adaptors:
//
//   s_cmd -> control --rd_cmd--> mem_r_stream --rd_data--> compute --wr_data--> mem_w_stream_done
//               |                   (m_rd)                    ^                  (m_wr)   |
//               +-------------------- job --------------------+                  wr_done |
//                                                                                         v
//                                                               s_done <- response <------+
//
// The task bodies are in hist_*.h and the adaptors in include/mem_{r,w}_stream*_task.h, so the
// memory-mapped version (histogram_mm.cpp) changes only this file.
#include "hist_types.h"
#include "hist_control.h"
#include "hist_compute.h"
#include "hist_response.h"
#include "mem_r_stream_task.h"
#include "mem_w_stream_done_task.h"
#include <hls_task.h>

void histogram_stream(hls::stream<word_t>& s_cmd, const word_t* m_rd, word_t* m_wr,
                      hls::stream<word_t>& s_done) {
#pragma HLS INTERFACE axis port=s_cmd
#pragma HLS INTERFACE m_axi port=m_rd offset=off bundle=gmem0 depth=65536
#pragma HLS stable variable=m_rd
#pragma HLS INTERFACE m_axi port=m_wr offset=off bundle=gmem1 depth=65536
#pragma HLS stable variable=m_wr
#pragma HLS INTERFACE axis port=s_done
#pragma HLS INTERFACE ap_ctrl_none port=return
    // Deep enough for one whole adaptor command (MRCmd/MWCmd: 11 words), so control can
    // queue the next job's commands while the adaptors are still busy with this one.
    hls_thread_local hls::stream<word_t, 16> rd_cmd, wr_cmd;
    hls_thread_local hls::stream<word_t> rd_data, wr_data, wr_done;
    hls_thread_local hls::stream<HistJob, 2> job;

    hls_thread_local hls::task t_ctrl(hist_control, s_cmd, rd_cmd, job, wr_cmd);
    hls_thread_local hls::task t_rd(mem_r_stream_task<MEM_DW>, rd_cmd, m_rd, rd_data);
    hls_thread_local hls::task t_comp(hist_compute, job, rd_data, wr_data);
    hls_thread_local hls::task t_wr(mem_w_stream_done_task<MEM_DW>, wr_cmd, wr_data, m_wr, wr_done);
    hls_thread_local hls::task t_resp(hist_response, wr_done, s_done);
}
