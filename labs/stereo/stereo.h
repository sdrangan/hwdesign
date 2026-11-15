#ifndef STEREO_H
#define STEREO_H

// The kernel: stereo block matching.  For every pixel (y, x) of the left
// image, find the disparity d in 0 .. NDISP-1 whose 5x5 window in the right
// image, shifted d pixels to the left, best matches the 5x5 window around
// (y, x) in the left image:
//
//     SAD(y, x, d) = sum over i, j in -HALF .. HALF of
//                    | L[y+i][x+j] - R[y+i][x+j-d] |
//
//     disp[y][x]   = the d with the smallest SAD; on a tie, the smallest d
//
// A pixel whose window, or whose shifted window for some d, would fall off the
// image gets disparity 0.  So the interior, where a disparity is computed, is
//
//     HALF <= y < IMG_H - HALF   and   HALF + NDISP - 1 <= x < IMG_W - HALF
//
// This is the specification disparity_map() in stereo.py has to meet, and the
// kernel has to match it exactly.
//
// The interface is AXI4-Stream, as in unit 5.  The kernel reads IMG_H*IMG_W words from pix_in, one
// per pixel in raster order (y outer, x inner), each carrying the left pixel
// in bits 7:0 and the right pixel in bits 15:8.  It writes IMG_H*IMG_W words of
// disparity, in the same order, with TLAST on the last.  The call is the
// ap_start / ap_done handshake.

#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

// The image size.  Not H and W: the code Vitis generates for co-simulation
// uses those names itself, and a macro called W breaks it -- "C/RTL
// co-simulation file generation failed", with no other message.
#define IMG_H 96
#define IMG_W 128
#define NDISP 16
#define WIN 5
#define HALF 2

typedef ap_uint<8> pix_t;
typedef ap_uint<8> disp_t;
typedef ap_uint<16> sad_t;      // at most WIN*WIN*255 = 6375

typedef hls::axis<ap_uint<16>, 0, 0, 0> in_word_t;
typedef hls::axis<ap_uint<8>, 0, 0, 0> out_word_t;

// Whether (y, x) is in the interior, where a disparity is computed.
static inline bool interior(int y, int x) {
    return y >= HALF && y < IMG_H - HALF && x >= HALF + NDISP - 1 && x < IMG_W - HALF;
}

void stereo(hls::stream<in_word_t> &pix_in, hls::stream<out_word_t> &disparity);

#endif  // STEREO_H
