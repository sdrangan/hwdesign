// hist_response.h -- the response task: one write completion in, one HistResp out.
//
// The write adaptor sends its MemComplete only after the memory acknowledges the job's last
// write (B), so the response means the counts are in memory.  The job id and status ride in
// the cookie the control task put in the MWCmd; the adaptor echoes it without reading it.
#ifndef HIST_RESPONSE_H
#define HIST_RESPONSE_H
#include "hist_types.h"

static void hist_response(hls::stream<word_t>& wr_done, hls::stream<word_t>& resp_out) {
    MemComplete done;
    done.read_stream<MEM_DW>(wr_done);
    HistResp resp;
    resp.job_id = done.xfer_msg.data[XFER_JOB_ID];
    resp.status = (HistStatus)(int)done.xfer_msg.data[XFER_STATUS];
    resp.write_stream<MEM_DW>(resp_out);
}

#endif  // HIST_RESPONSE_H
