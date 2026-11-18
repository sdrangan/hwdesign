// histogram_stream.cpp -- the histogram kernel with its command and response on AXI4-Streams.
//
// Free-running (ap_ctrl_none): five hls::tasks, each re-fired by the runtime whenever its
// input arrives, joined by FIFOs.  Memory is reached only through Waveflow's framed adaptors.
// One descriptor per job (HistDesc) is built by the control task and rides every stream:
//
//   s_cmd -> control -[MemRCmd|desc]-> mem_r_stream_framed -[desc|samples]-> compute
//                                          (m_rd)                               |
//                                                      [MemWCmd|desc|counts]   v
//   s_done <- response <---desc--- mem_w_stream_framed_done <-------------------+
//                                          (m_wr)
//
// No side streams: every task learns about its job from the descriptor in front of its data.
// The task bodies are in hist_*.h and the adaptors in include/mem_*_framed*_task.h, so the
// memory-mapped version (histogram_mm.v) wraps this top unchanged.
#include "hist_types.h"
#include "hist_control.h"
#include "hist_compute.h"
#include "hist_response.h"
#include "mem_r_stream_framed_task.h"
#include "mem_w_stream_framed_done_task.h"
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
    // Every framed FIFO holds a whole header (a memory command and the descriptor) with room to
    // spare, so a task can pass the next job's header on while the task after it is still busy
    // with this one.  rd_data matters most: if the read mover cannot relay job k+1's descriptor
    // past the end of job k's samples, it cannot issue job k+1's read until compute is done.
    static const int HDR = MemWCmd::nwords<MEM_DW>() + HistDesc::nwords<MEM_DW>();
    hls_thread_local hls::stream<frame_t, 2 * HDR> rd_cmd, rd_data, wr_data;
    hls_thread_local hls::stream<word_t> wr_done;

    hls_thread_local hls::task t_ctrl(hist_control, s_cmd, rd_cmd);
    hls_thread_local hls::task t_rd(mem_r_stream_framed_task<MEM_DW>, rd_cmd, m_rd, rd_data);
    hls_thread_local hls::task t_comp(hist_compute, rd_data, wr_data);
    hls_thread_local hls::task t_wr(mem_w_stream_framed_done_task<MEM_DW, HistDesc::nwords<MEM_DW>()>,
                                    wr_data, m_wr, wr_done);
    hls_thread_local hls::task t_resp(hist_response, wr_done, s_done);
}
