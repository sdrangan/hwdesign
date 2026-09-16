"""subc_divide — integer division by conditional subtraction, in Python.

This is the golden model.  You will write the same algorithm as a state machine
in SystemVerilog, and the lab checks that the two agree exactly, case for case.

Given unsigned integers ``a`` and ``b`` with ``0 <= a < b``, the algorithm
produces an integer ``z`` such that

    qhat = z / 2**nbits  ~=  a/b

and the approximation is **one-sided**:

    qhat  <=  a/b  <  qhat + 2**-nbits

That one-sidedness is the whole content of the algorithm, and it is what the
lab checks.  A bit is only set in the quotient once the subtraction that pays
for it has succeeded, so the result can never overshoot ``a/b`` — it only ever
falls short, and by less than one unit in the last place.

The algorithm itself is the long division you learned in school, in base 2.  At
each step you shift the remainder left (bring down the next bit), ask whether
the divisor fits, and if it does, subtract it and record a 1.  ``nbits`` steps
produce ``nbits`` quotient bits.  The theory page works it through.
"""
from __future__ import annotations

import numpy as np


def subc_divide(
        a : np.uint32,
        b : np.uint32,
        nbits : int = 16
    ) -> np.int32:
    """
    Perform integer division of using conditional subtraction.

    Given two unsigned integers `a` and `b`, with `b > a >= 0`, the function
    computes a rational approximation of the division:

        a/b ~= qhat = z/(2^nbits)

    The approximation is one-sided -- qhat never overshoots a/b:

        qhat  <=  a/b  <  qhat + 2^(-nbits)

    Parameters
    ----------
    a : np.uint32
        The dividend.
    b : np.uint32
        The divisor.
    nbits : int, optional
        The number of bits for the fractional part of the quotient. Default is 16.

    Returns:
    ------
    z: int:
        The numerator of the rational approximation of the quotient.
    """
    if b == 0:
        raise ValueError("Division by zero is not allowed.")
    if (a >= b) or (a < 0):
        raise ValueError("We must have a < b and a >= 0.")

    # TODO: Implement the conditional subtraction division algorithm
    #
    #     z = np.uint32(0)
    #     for ... in range(nbits):
    #         ...
    #     return z
    #
    # One iteration produces one quotient bit, most significant first.  Each
    # one does four things, in this order:
    #
    #   * shift z left, to make room for the bit you are about to decide
    #   * shift a left, which is "bring down the next bit" of long division
    #   * if the shifted a is now at least b, subtract b from it
    #   * if you subtracted, set the low bit of z
    #
    # `a` is the running remainder, so it is the shifted-and-subtracted value
    # that carries into the next iteration — not the original dividend.
    #
    # `|= 1` sets the low bit, and `<<= 1` shifts in place.  Keep everything as
    # np.uint32: the SystemVerilog you write next has fixed-width registers,
    # and a model using Python's unbounded integers would hide an overflow the
    # hardware cannot.
    return np.uint32(0)


if __name__ == "__main__":
    # Handy while you are working: run this file directly to see the algorithm
    # converge on one example, without going through the build.
    a, b = np.uint32(3), np.uint32(10)
    print(f"  a/b = {a}/{b} = {a / b:.6f}")
    for nbits in (1, 2, 4, 8, 16):
        z = subc_divide(a, b, nbits)
        if z is None:
            print(f"  nbits={nbits:2d}  (not implemented yet)")
            continue
        print(f"  nbits={nbits:2d}  z={int(z):6d}  qhat={int(z) / 2**nbits:.6f}")
