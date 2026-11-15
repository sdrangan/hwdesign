// The optimized kernel: the same three phases as stereo_base.cpp, the same
// answer bit for bit, and the compute phase at one pixel per clock cycle.
//
//   load     read the IMG_H*IMG_W input words into L and R, one per cycle
//   compute  slide a 5x5 window across each row of L, and a 5 x (5+NDISP-1)
//            window across the same rows of R, one new column per cycle, and
//            compute all NDISP SADs and their minimum every cycle
//   store    write the IMG_H*IMG_W disparities out, one per cycle
//
// The phases run one after the other, so a call takes about 3*IMG_H*IMG_W cycles.
// Overlapping them is the next unit's subject.
#include "stereo.h"

static pix_t absdiff(pix_t a, pix_t b) {
    return (a > b) ? pix_t(a - b) : pix_t(b - a);
}

// The right window is the left one plus NDISP-1 columns: shifted d to the
// left, the 5 columns for disparity d start NDISP-1-d columns in.
#define RWIN (WIN + NDISP - 1)

void stereo(hls::stream<in_word_t> &pix_in, hls::stream<out_word_t> &disparity) {
#pragma HLS INTERFACE mode=axis port=pix_in
#pragma HLS INTERFACE mode=axis port=disparity
#pragma HLS INTERFACE mode=ap_ctrl_hs port=return

    pix_t L[IMG_H][IMG_W], R[IMG_H][IMG_W];
    disp_t D[IMG_H][IMG_W];
    // TODO:  The compute phase reads a column of 5 pixels, rows y-HALF to
    // y+HALF, from each image every cycle.  Partition L and R on their row
    // dimension so that any 5 consecutive rows are in 5 different memories.
    // Use a power of two for the factor, so finding the bank is a bit select.

    // ---- load ---------------------------------------------------------------
    load_y: for (int y = 0; y < IMG_H; y++) {
        load_x: for (int x = 0; x < IMG_W; x++) {
#pragma HLS PIPELINE II=1
            in_word_t w = pix_in.read();
            L[y][x] = w.data.range(7, 0);
            R[y][x] = w.data.range(15, 8);
        }
    }

    // ---- compute ------------------------------------------------------------
    // lwin[i][j]: row y-HALF+i of L, column x-WIN+1+j, where x is the newest
    // column read.  The window's centre column is xc = x - HALF.
    // rwin[i][k]: row y-HALF+i of R, column x-RWIN+1+k.  For disparity d the
    // window's columns xc-HALF-d .. xc+HALF-d are k = NDISP-1-d .. NDISP-1-d+WIN-1.
    pix_t lwin[WIN][WIN], rwin[WIN][RWIN];
    // TODO:  The two windows are read and shifted in full every cycle.  Make
    // each of them registers.

    // Only the interior rows are computed; the store phase writes 0 for the
    // rest.  Within a row the window fills as x runs from 0, and every column
    // the first interior pixel needs has been read by then, so the windows are
    // never cleared between rows.
    comp_y: for (int y = HALF; y < IMG_H - HALF; y++) {
        comp_x: for (int x = 0; x < IMG_W; x++) {
            // TODO:  Pipeline this loop at II = 1.  Then, every iteration:
            //   1. shift both windows one column left, and read the new column,
            //      rows y-HALF .. y+HALF at column x, into the last column of each
            //   2. if the centre column xc = x - HALF is an interior column,
            //      compute the SAD for every d, and keep the smallest (the
            //      smallest d on a tie), and write it to D[y][xc]
            // Every loop inside this one must be unrolled -- the PIPELINE
            // pragma does that for you, as long as the bounds are constants.
        }
    }

    // ---- store --------------------------------------------------------------
    store_y: for (int y = 0; y < IMG_H; y++) {
        store_x: for (int x = 0; x < IMG_W; x++) {
#pragma HLS PIPELINE II=1
            out_word_t w;
            w.data = interior(y, x) ? D[y][x] : disp_t(0);
            w.keep = -1;
            w.strb = -1;
            w.last = (y == IMG_H - 1 && x == IMG_W - 1);
            disparity.write(w);
        }
    }
}
