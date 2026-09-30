#ifndef AVGFILT_H
#define AVGFILT_H

#include <hls_stream.h>

// Pure-streaming moving average of the last win_size squared inputs:
//
//     y[k] = (x[k]^2 + x[k-1]^2 + x[k-2]^2) / win_size
//
// One output per input, no TLAST, no start or done: see avgfilt.cpp.
void avgfilt(hls::stream<float> &in_stream,
             hls::stream<float> &out_stream);

// The window length.  avgfilt.cpp keeps an explicit two-deep delay line, so
// changing this alone does not change the filter -- and avgfilt_golden.py
// has its own copy, WIN_SIZE, which has to match.
constexpr int win_size = 3;

#endif  // AVGFILT_H
