#ifndef DOT_H
#define DOT_H

// The in-class exercise: the dot product of two vectors of N samples,
//
//     dot = a[0]*b[0] + a[1]*b[1] + ... + a[N-1]*b[N-1]
//
// a and b are 16-bit integers in block RAMs with one port each: one read per
// clock cycle.  The result is a 32-bit int, returned when the call ends.
// dot_ref.cpp is the plain loop; dot.cpp is yours.
#define N 256

int dot(const short a[N], const short b[N]);

#endif
