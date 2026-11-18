// hist_types.h -- what every task of the histogram kernel shares, in both versions.
//
// The messages come from generated headers (include/, by hist_build.py):
//   HistCmd, HistResp            this kernel's command and response   (hist_schema.py)
//   MRCmd, MWCmd, MemComplete    the memory adaptors' commands and completion   (waveflow)
#ifndef HIST_TYPES_H
#define HIST_TYPES_H

#include <ap_int.h>
#include <hls_stream.h>
#include "hist_cmd.h"
#include "hist_resp.h"
#include "m_r_cmd.h"
#include "m_w_cmd.h"
#include "mem_complete.h"

static const int MEM_DW = 32;       // memory and stream word: one sample, or one count
static const int NBINS = 32;        // bins, each a register in the compute task
static const int MAX_N = 65535;     // the counters are 16 bits: a longer job could overflow one

typedef ap_uint<MEM_DW> word_t;
typedef ap_uint<16> count_t;

// What the control task tells the compute task about one job.
struct HistJob {
    ap_uint<32> n;        // samples to read: 0 for a refused job
    ap_uint<5> shift;     // bin = min(x >> shift, NBINS - 1)
    bool emit;            // write the NBINS counts: false for a refused job
};

// The cookie the control task puts in MWCmd.xfer_msg.  The write adaptor echoes it,
// unread, in its MemComplete, which is how the response task learns which job finished.
static const int XFER_JOB_ID = 0;
static const int XFER_STATUS = 1;

#endif  // HIST_TYPES_H
