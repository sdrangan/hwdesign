#ifndef SQSUM_H
#define SQSUM_H

// The in-class exercise: for i = 0 .. N-1,
//
//     y[i] = x[i]^2 + x[i-1]^2,    with x[-1] = 0
//
// x and y are block RAMs with one port each: one read or one write per
// clock cycle.  sqsum_ref.cpp is the obvious loop; sqsum.cpp is yours.
#define N 256

void sqsum(const float x[N], float y[N]);

#endif
