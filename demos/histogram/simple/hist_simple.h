// hist_simple.h -- the constants and messages of the unit 9 histogram kernel.
//
// Every message is a generated struct (include/, written by hist_build.py):
//   HistCmd, HistResp            this kernel's command and response          (hist_schema.py)
//   MRCmd, MWCmd, MemComplete    the plain data movers' commands and completion   (waveflow)
#ifndef HIST_SIMPLE_H
#define HIST_SIMPLE_H

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

void hist_simple(hls::stream<word_t>& s_cmd, const word_t* m_rd, word_t* m_wr,
                 hls::stream<word_t>& s_done);

#endif  // HIST_SIMPLE_H
