// The baseline kernel: stereo block matching, written the obvious way, with
// every loop left unpipelined.  It is the specification in C++, and the
// starting point you measure the optimized kernel (stereo.cpp) against.
//
// Three phases, one after the other, as every version of this lab's kernel
// has:
//
//   load     read the IMG_H*IMG_W input words into the arrays L and R
//   compute  the disparity of every pixel into the array D
//   store    write D out, IMG_H*IMG_W words, with TLAST on the last
//
// Every loop carries `#pragma HLS PIPELINE off`.  Vitis pipelines innermost
// loops on its own unless told not to, and this version is the reference
// point: one operation at a time.
#include "stereo.h"

// |a - b| for two pixels, without going through a signed type.
static pix_t absdiff(pix_t a, pix_t b) {
    return (a > b) ? pix_t(a - b) : pix_t(b - a);
}

void stereo(hls::stream<in_word_t> &pix_in, hls::stream<out_word_t> &disparity) {
#pragma HLS INTERFACE mode=axis port=pix_in
#pragma HLS INTERFACE mode=axis port=disparity
#pragma HLS INTERFACE mode=ap_ctrl_hs port=return

    pix_t L[IMG_H][IMG_W], R[IMG_H][IMG_W];
    disp_t D[IMG_H][IMG_W];

    // ---- load ---------------------------------------------------------------
    load_y: for (int y = 0; y < IMG_H; y++) {
#pragma HLS PIPELINE off
        load_x: for (int x = 0; x < IMG_W; x++) {
#pragma HLS PIPELINE off
            in_word_t w = pix_in.read();
            L[y][x] = w.data.range(7, 0);
            R[y][x] = w.data.range(15, 8);
        }
    }

    // ---- compute ------------------------------------------------------------
    // TODO:  For every pixel, the disparity the specification in stereo.h
    // defines: 0 outside the interior, and inside it the d in 0 .. NDISP-1
    // with the smallest SAD, the smallest d on a tie.  Loop over d, and for
    // each d over the 5x5 window, reading L and R directly.  Use absdiff()
    // and sad_t.  Label the loops comp_y, comp_x, disp_loop, win_i and win_j,
    // and put `#pragma HLS PIPELINE off` in every one of them, as in the
    // load loops.

    // ---- store --------------------------------------------------------------
    store_y: for (int y = 0; y < IMG_H; y++) {
#pragma HLS PIPELINE off
        store_x: for (int x = 0; x < IMG_W; x++) {
#pragma HLS PIPELINE off
            out_word_t w;
            w.data = D[y][x];
            w.keep = -1;
            w.strb = -1;
            w.last = (y == IMG_H - 1 && x == IMG_W - 1);
            disparity.write(w);
        }
    }
}
