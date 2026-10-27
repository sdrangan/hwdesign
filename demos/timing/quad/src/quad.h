#ifndef QUAD_H
#define QUAD_H

#include <ap_int.h>

// The kernel: y = w2*x^2 + w1*x + w0, the quadratic from unit 6.
//
// The inputs are 8-bit signed integers, so every multiplication fits in one
// DSP block and the timing is the circuit's, not a 32-bit multiplier's.
// y needs 2*8 + 8 + 2 = 26 bits to hold every result without overflow.
typedef ap_int<8> in_t;
typedef ap_int<26> out_t;

// No loops and no AXI: every argument is a plain wire, and the function's
// return value comes out on ap_return.  See quad.cpp.
out_t quad(in_t x, in_t w2, in_t w1, in_t w0);

#endif  // QUAD_H
