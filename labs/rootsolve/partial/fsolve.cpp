#include <hls_math.h>

#include "fsolve.h"

// The monic cubic, evaluated in the same order as fcubic() in fsolve.py.
// The order matters: floating-point addition is not associative, and the
// same terms added in a different order can differ in the last bit.  Match
// the Python and the two can agree exactly.
static float fcubic(float x, float a0, float a1, float a2) {
    float x2 = x * x;
    float x3 = x2 * x;
    return a0 + a1 * x + a2 * x2 + x3;
}

void fsolve(float a0, float a1, float a2, float x0, float tol, int max_iter,
            float step, float &x, float &fx, int &niter)
{
    // TODO:  Put every argument on the AXI4-Lite interface, and the block
    // control signals (ap_start, ap_done, ...) with them.  The first one is
    // done for you:
    //
    //     #pragma HLS interface s_axilite port=a0
    //
    // Write one for each remaining argument, then one for `return` in a
    // bundle named CTRL -- the same pattern as the scalar_fun demo.
    #pragma HLS interface s_axilite port=a0

    // The outputs are references, so the kernel works on local copies and
    // writes each output once at the end.  Reading and writing `x` directly
    // inside the loop would be a register-map access on every update.
    float xk = x0;
    float fk = fcubic(xk, a0, a1, a2);
    int k = 0;

    // TODO:  Run the iteration, exactly as fsolve() in fsolve.py does:
    //
    //     for up to max_iter updates:
    //         if |fk| < tol, stop           <- tested before the update
    //         xk = xk - step*fk
    //         fk = fcubic(xk, ...)
    //         count the update in k
    //
    // A `for` loop over max_iter with a `break` is the natural shape in C++.
    // `hls::fabs` is the absolute value.  Label the loop, and put
    //
    //     #pragma HLS loop_tripcount min=1 avg=80 max=500
    //
    // as its first line.  The loop bound is a register, so synthesis cannot
    // know how long the loop runs; the pragma tells the latency report what
    // to assume.  It does not change what the hardware does.

    x = xk;
    fx = fk;
    niter = k;
}
