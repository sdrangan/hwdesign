// hist_types.h -- what every task of the pipelined histogram kernel shares.
//
// The messages come from generated headers (include/, by hist_build.py):
//   HistCmd, HistDesc, HistResp   this kernel's command, job descriptor and response   (hist_schema.py)
//   MemRCmd, MemWCmd              the framed memory adaptors' commands                  (waveflow)
#ifndef HIST_TYPES_H
#define HIST_TYPES_H

#include <ap_int.h>
#include <hls_stream.h>
#include "streamutils_hls.h"
#include "hist_cmd.h"
#include "hist_desc.h"
#include "hist_resp.h"
#include "mem_r_cmd.h"
#include "mem_w_cmd.h"

static const int MEM_DW = 32;       // memory and stream word: one sample, or one count
static const int NBINS = 32;        // bins, each a register in the compute task
static const int MAX_N = 65535;     // the counters are 16 bits: a longer job could overflow one

typedef ap_uint<MEM_DW> word_t;
typedef ap_uint<16> count_t;

// A word on an internal framed stream: the data and a `last` bit that ends a burst.  The
// framed adaptors count bursts by `last`, which is how they skip a header they do not read.
typedef streamutils::framed_word<MEM_DW> frame_t;

#endif  // HIST_TYPES_H
