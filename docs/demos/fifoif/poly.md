---
title: The Polynomial Example
parent: Command-Response FIFO Interface
nav_order: 2
has_children: false
---

# The Polynomial Example

We illustrate the command-response design with a simple polynomial
accelerator. It evaluates a cubic on a stream of samples:

$$y[k] = c_0 + c_1\,x[k] + c_2\,x[k]^2 + c_3\,x[k]^3$$

The coefficients are not fixed in the hardware. They arrive in each
command, so every transaction can use a different polynomial.

The files are in `hwdesign/demos/stream/poly`.

## The protocol

One **transaction** is a command from the host and the IP's response:

~~~text
in_stream:   PolyCmdHdr          |  x[0], x[1], ..., x[nsamp-1]
out_stream:  PolyRespHdr  |  y[0], y[1], ..., y[nsamp-1]  |  PolyRespFtr
~~~

Every `|` is a **TLAST**. In the [AXI4-Streaming demo](../stream/) the
stream had no TLAST, because it was one endless sequence of samples. Here
the stream carries *messages*, and TLAST marks where each one ends. That
is what lets the IP tell a header from the samples that follow it.

1. The host sends a **`PolyCmdHdr`**: a transaction ID `tx_id`, the four
   coefficients `coeffs`, and the number of samples `nsamp`.
2. The host streams the `nsamp` input samples `x`.
3. The IP answers with a **`PolyRespHdr`** that echoes `tx_id`, so the host
   can match the output to its command.
4. As the samples stream in, the IP streams out the results `y`.
5. The IP finishes with a **`PolyRespFtr`**: `nsamp_read`, the number of
   samples it read, and an `error` code.

The error code is how the IP reports a malformed command, such as a TLAST
arriving too early or not at all. A command-response IP cannot just stop
on bad input, since the next command is already queued behind it. It has
to say what went wrong.

## The messages

The messages are defined in Python, in `poly_schema.py`, as
[waveflow data schemas](https://sdrangan.github.io/waveflow/docs/guide/schema/).
A schema lists a message's fields and gives each one a type and a bit
width:

~~~python
class PolyCmdHdr(DataList):
    """The command: which transaction, which polynomial, how many samples follow."""

    elements = {
        "tx_id": {"schema": TxId, "description": "Transaction ID"},
        "coeffs": {"schema": CoeffArray, "description": "Polynomial coefficients"},
        "nsamp": {"schema": Nsamp, "description": "Number of samples that follow"},
    }


class PolyRespHdr(DataList):
    elements = {
        "tx_id": {"schema": TxId, "description": "Echo of the command's transaction ID"},
    }


class PolyRespFtr(DataList):
    elements = {
        "nsamp_read": {"schema": Nsamp, "description": "Number of samples read"},
        "error": {"schema": PolyErrorField, "description": "Error code"},
    }
~~~

`TxId` and `Nsamp` are 16-bit unsigned integers, `CoeffArray` is an array
of four `float32` values, and `PolyErrorField` is an enumeration:

~~~python
class PolyError(IntEnum):
    NO_ERROR = 0
    TLAST_EARLY_CMD_HDR = 1   # TLAST arrived before the whole command header
    NO_TLAST_CMD_HDR = 2      # the command header ended without TLAST
    TLAST_EARLY_SAMP_IN = 3   # TLAST arrived before nsamp samples
    NO_TLAST_SAMP_IN = 4      # nsamp samples arrived without TLAST
    WRONG_NSAMP = 5           # the number of samples read is not nsamp
~~~

The Python model uses these classes to write the test vectors, on the
[next page](./poly_python.md). The Vitis kernel has to agree with them
about where each field sits in the stream words. We will first write that
by hand, in [Writing the Vitis Kernel](./vitis32.md), and then see how
waveflow can generate it, in [Using Waveflow](./vitis_general.md).

## The files

| File | What it is |
| --- | --- |
| `poly_schema.py` | the messages, as data schemas |
| `poly_golden.py` | the test transactions and the Python golden model |
| `poly32.cpp` | the kernel for a 32-bit stream, every message unpacked and packed by hand |
| `poly64.cpp` | the same for a 64-bit stream, where each word holds two values |
| `poly.cpp`, `poly.hpp` | the general kernel: either width, with generated code doing the packing |
| `tb_poly.cpp` | the testbench, for all three kernels |
| `run.tcl`, `poly_build.py` | the Vitis script and the build script |

The three kernel files each define the same function, `poly()`, and the
build picks one with `--kernel`.

---

Go to [Headers and the Golden Model](./poly_python.md)
