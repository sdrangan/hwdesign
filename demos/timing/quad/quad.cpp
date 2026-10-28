#include "quad.h"

// The quadratic from unit 6:  y = w2*x^2 + w1*x + w0.
//
// Three multiplications and two additions, with no loop -- the circuit the
// unit draws by hand.  What Vitis HLS decides is how to spread it over clock
// cycles: at a slow clock the whole expression fits in one clock period, at
// a fast one it is split across many, like the two-cycle design in the
// slides.  The build synthesizes it at several clock periods to show that.
//
// The interface is deliberately the simplest one Vitis HLS has.  The
// project is built for the Vivado IP flow (run.tcl), where a scalar argument
// is a plain input wire (ap_none) and the return value is an output wire,
// ap_return.  The block-level protocol, ap_ctrl_hs, adds four control
// signals: the caller raises ap_start, and the IP raises ap_done when
// ap_return holds the answer.  The cycles between the two are the latency.
out_t quad(in_t x, in_t w2, in_t w1, in_t w0) {

    #pragma HLS INTERFACE mode=ap_none    port=x
    #pragma HLS INTERFACE mode=ap_none    port=w2
    #pragma HLS INTERFACE mode=ap_none    port=w1
    #pragma HLS INTERFACE mode=ap_none    port=w0
    #pragma HLS INTERFACE mode=ap_ctrl_hs port=return

    // Each product is declared just wide enough, so nothing is truncated.
    ap_int<16> xsq = x * x;
    ap_int<24> xsq_w2 = w2 * xsq;
    ap_int<16> x_w1 = w1 * x;
    return xsq_w2 + x_w1 + w0;
}
