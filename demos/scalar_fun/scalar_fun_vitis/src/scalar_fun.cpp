#include "scalar_fun.h"

// A single artificial neuron:  y = max(w*x + b, 0).
//
// Every argument, and the function's own start/done handshake (`return`),
// is bound to the same AXI4-Lite bundle.  Vitis HLS turns that bundle into
// the register map the processor reads and writes:  the processor writes
// x, w and b into their registers, sets ap_start, polls ap_done, then
// reads y back out.
void simp_fun(int x, int w, int b, int& y) {

    #pragma HLS INTERFACE s_axilite port=x      bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=w      bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=b      bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=y      bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=return bundle=CTRL

    int act_in = w * x + b;
    if (act_in > 0)
        y = act_in;
    else
        y = 0;
}
