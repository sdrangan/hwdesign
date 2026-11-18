// hist_control.h -- the control task: one command in, one framed read request out.
//
// It builds the job's descriptor, HistDesc, with everything a later task needs, and frames it
// behind the read command: [MemRCmd(fwd_bursts = 1) | HistDesc].  The read mover relays the
// descriptor, unread, ahead of the samples it fetches.  The control task owns no memory port,
// and it is the only task that sees the HistCmd.
#ifndef HIST_CONTROL_H
#define HIST_CONTROL_H
#include "hist_types.h"

static void hist_control(hls::stream<word_t>& cmd_in, hls::stream<frame_t>& rd_cmd) {
    HistCmd cmd;
    cmd.read_stream<MEM_DW>(cmd_in);
    const bool ok = (cmd.n <= MAX_N);

    HistDesc d;                                 // the job, as every later task needs it
    d.job_id = cmd.job_id;
    d.status = ok ? HistStatus::OK : HistStatus::N_TOO_LARGE;
    d.n = ok ? (int)cmd.n : 0;                  // a refused job reads nothing
    d.shift = cmd.shift;
    d.cnt_addr = cmd.cnt_addr;

    MemRCmd rc;                                 // read n samples from data_addr,
    rc.addr = cmd.data_addr;                    // after relaying the one burst behind this
    rc.len = d.n;
    rc.fwd_bursts = 1;
    rc.write_framed_stream<MEM_DW>(rd_cmd);
    d.write_framed_stream<MEM_DW>(rd_cmd);      // that burst: the descriptor
}

#endif  // HIST_CONTROL_H
