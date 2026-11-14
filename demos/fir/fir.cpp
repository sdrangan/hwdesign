#include "fir.h"

// A 16-tap FIR filter, four ways.  The arithmetic is the same in all four:
// 16 multiplies and 16 adds per output sample, NTAPS * nsamp of each in all.
// What differs is which loop is pipelined, and where the samples a tap needs
// come from -- and that decides whether the filter takes about 16 cycles per
// sample or one.
//
// The interface is the Vivado IP flow's, as in the poly demo: each array is a
// memory port (ap_memory) to a single-port block RAM, one read or one write
// per cycle; nsamp is a plain input; ap_start / ap_done is the handshake.
//
// Integers throughout (a 16 x 16-bit product fits a DSP), so an addition takes
// one cycle and no loop here is limited by a loop-carried dependency: the
// limits are the loop structure and the memory ports.

void fir(const short h[NTAPS], const short x[MAX_NSAMP], int y[MAX_NSAMP], int nsamp) {
    #pragma HLS INTERFACE mode=ap_memory  port=h storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_memory  port=x storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_memory  port=y storage_type=ram_1p
    #pragma HLS INTERFACE mode=ap_none    port=nsamp
    #pragma HLS INTERFACE mode=ap_ctrl_hs port=return

    if (nsamp > MAX_NSAMP) {
        nsamp = MAX_NSAMP;
    }

#if FIR_VARIANT <= 1
    // inner and flat: the obvious nested loop, with the tap loop pipelined.
    // Each tap reads one x and one h, from two memories: II = 1 for the tap
    // loop.  The sample loop is not pipelined, so as written every output
    // sample starts the tap loop afresh: NTAPS iterations, plus the cycles to
    // fill and drain its pipeline, plus the cycles to enter and leave it.
    //
    // Vitis does better on its own: it flattens the two loops into one loop
    // of nsamp * NTAPS iterations, pipelined once, so the fill and drain are
    // paid once per call.  "inner" forbids that with LOOP_FLATTEN off, to show
    // what it saves; "flat" is the same code, left to Vitis.
    sample_loop: for (int n = 0; n < nsamp; n++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_NSAMP
        int acc = 0;
        tap_loop: for (int k = 0; k < NTAPS; k++) {
            #pragma HLS PIPELINE II=1
#if FIR_VARIANT == 0
            #pragma HLS LOOP_FLATTEN off
#endif
            int xk = (n - k >= 0) ? (int)x[n - k] : 0;
            acc += h[k] * xk;
        }
        y[n] = acc;
    }

#elif FIR_VARIANT == 2
    // outer: pipeline the sample loop instead.  Vitis then unrolls the tap
    // loop completely: 16 multipliers, one output per iteration -- if the
    // iteration can get its 16 samples of x.  It cannot: x is one memory with
    // one port, so the 16 reads take 16 cycles, and the II is 16.  The
    // coefficients are copied into registers first, so h is not the limit.
    short c[NTAPS];
    #pragma HLS ARRAY_PARTITION variable=c type=complete
    coeff_loop: for (int k = 0; k < NTAPS; k++) {
        c[k] = h[k];
    }
    sample_loop: for (int n = 0; n < nsamp; n++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_NSAMP
        #pragma HLS PIPELINE II=1
        int acc = 0;
        tap_loop: for (int k = 0; k < NTAPS; k++) {
            int xk = (n - k >= 0) ? (int)x[n - k] : 0;
            acc += c[k] * xk;
        }
        y[n] = acc;
    }

#else
    // delay: each x[n] is used by 16 consecutive outputs, so read it once and
    // keep the last NTAPS samples in a delay line.  Fully partitioned, the
    // delay line is NTAPS registers, all readable in the same cycle.  One read
    // of x per sample: II = 1, with all 16 multipliers busy every cycle.
    short c[NTAPS];
    #pragma HLS ARRAY_PARTITION variable=c type=complete
    coeff_loop: for (int k = 0; k < NTAPS; k++) {
        c[k] = h[k];
    }
    short xdly[NTAPS];
    #pragma HLS ARRAY_PARTITION variable=xdly type=complete
    clear_loop: for (int k = 0; k < NTAPS; k++) {
        #pragma HLS UNROLL
        xdly[k] = 0;                     // x[n] = 0 for n < 0
    }
    sample_loop: for (int n = 0; n < nsamp; n++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_NSAMP
        #pragma HLS PIPELINE II=1
        // Shift, oldest end first, then put the new sample in.
        shift_loop: for (int k = NTAPS - 1; k > 0; k--) {
            xdly[k] = xdly[k - 1];
        }
        xdly[0] = x[n];
        // xdly[k] now holds x[n-k].
        int acc = 0;
        tap_loop: for (int k = 0; k < NTAPS; k++) {
            acc += c[k] * xdly[k];
        }
        y[n] = acc;
    }
#endif
}
