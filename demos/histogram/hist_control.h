// hist_control.h -- the control task: one command in, one command to each adaptor and a job
// descriptor to compute.  It owns no memory port; it only turns a HistCmd into the three
// messages that start a job.
#ifndef HIST_CONTROL_H
#define HIST_CONTROL_H
#include "hist_types.h"

static void hist_control(hls::stream<word_t>& cmd_in, hls::stream<word_t>& rd_cmd,
                         hls::stream<HistJob>& job, hls::stream<word_t>& wr_cmd) {
    HistCmd cmd;
    cmd.read_stream<MEM_DW>(cmd_in);
    const bool ok = (cmd.n <= MAX_N);

    if (ok) {                                   // read n samples from data_addr
        MRCmd rc;
        rc.addr = cmd.data_addr;  rc.len = cmd.n;  rc.xfer_len = 0;
        rc.write_stream<MEM_DW>(rd_cmd);
    }
    HistJob j;                                  // a refused job reads 0 and emits nothing
    j.n = ok ? (int)cmd.n : 0;  j.shift = cmd.shift;  j.emit = ok;
    job.write(j);

    MWCmd wc;                                   // write NBINS counts to cnt_addr
    wc.addr = cmd.cnt_addr;  wc.len = ok ? NBINS : 0;  wc.xfer_len = 2;
    wc.xfer_msg.data[XFER_JOB_ID] = cmd.job_id;
    wc.xfer_msg.data[XFER_STATUS] = (int)(ok ? HistStatus::OK : HistStatus::N_TOO_LARGE);
    wc.write_stream<MEM_DW>(wr_cmd);
}

#endif  // HIST_CONTROL_H
