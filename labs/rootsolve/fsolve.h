#ifndef FSOLVE_H
#define FSOLVE_H

// The kernel: a root of f(x) = a0 + a1*x + a2*x^2 + x^3, found by the
// iteration x <- x - step*f(x).  See fsolve.cpp, and fsolve() in fsolve.py,
// which is the specification this has to match.
//
// Inputs:
//   a0, a1, a2  the coefficients
//   x0          the starting point
//   tol         stop once |f(x)| < tol
//   max_iter    the most updates to make
//   step        the step size
//
// Outputs:
//   x           the final estimate of the root
//   fx          f(x) at that estimate
//   niter       the number of updates made
//
// Every argument is a register in the AXI4-Lite map: the processor writes
// the inputs, starts the kernel, waits for it to finish and reads the three
// outputs back.
void fsolve(float a0, float a1, float a2, float x0, float tol, int max_iter,
            float step, float &x, float &fx, int &niter);

#endif  // FSOLVE_H
