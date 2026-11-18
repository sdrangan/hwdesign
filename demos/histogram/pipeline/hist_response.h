// hist_response.h -- the response task: the job's descriptor back from the write mover, one
// HistResp out.
//
// The write mover echoes the descriptor only after the memory acknowledges the job's last
// write (B), so the response means the counts are in memory.  The descriptor is the one the
// control task built; the movers carried it without reading it.
#ifndef HIST_RESPONSE_H
#define HIST_RESPONSE_H
#include "hist_types.h"

static void hist_response(hls::stream<word_t>& wr_done, hls::stream<word_t>& resp_out) {
    HistDesc d;
    d.read_stream<MEM_DW>(wr_done);
    HistResp resp;
    resp.job_id = d.job_id;
    resp.status = d.status;
    resp.write_stream<MEM_DW>(resp_out);
}

#endif  // HIST_RESPONSE_H
