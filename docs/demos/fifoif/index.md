---
title: Command-Response FIFO Interface
parent: Demos
nav_order: 6
has_children: true
---

# The Command-Response FIFO Interface

In the [scalar function example](../procif/), the IP talked to the
processor through AXI4-Lite registers. The processor had to configure the
IP before every operation and poll it for completion, and when the
processor is busy with other work, those delays add up. In the
[AXI4-Streaming demo](../stream/), data flowed efficiently, but there was
no way to tell the IP *what* to do with it.

In this unit, we combine the two into a widely used and efficient design
pattern: the **command-response** structure. Commands and data travel
together on one AXI4-Stream, and responses come back on another.

The example is a **polynomial accelerator**. Each command carries a
cubic's coefficients and the number of samples that follow. The IP
evaluates the cubic on each sample as it streams through, and answers
with a header, the results and a footer.

By working through this unit, you will learn to:

- Design **command** and **response** messages for an IP, and frame them
  on an AXI4-Stream with **TLAST**
- Describe the messages once, as Python **data schemas**, and generate
  the C++ that **serializes** and **deserializes** them for Vitis HLS
- Add **transaction IDs** and **error codes** to command-response pairs
- Make the stream **word width** a parameter, 32 or 64 bits
- Verify the kernel against a Python golden model in C simulation and RTL
  co-simulation
- Decode the messages from an RTL simulation's **VCD**, and read the
  latency and throughput off a **timing diagram**

## Pre-Requirements

You will need the [software set-up](../../support/amd/) for Vitis and
Python, and the [virtual environment](../../support/repo/package.md) that
has `waveflow`. This demo uses the same build-script pattern as the
[AXI4-Streaming demo](../stream/), so do that one first.

## Where the files are

Everything is in `hwdesign/demos/stream/poly`:

| File | What it is |
| --- | --- |
| `poly_schema.py` | the messages, as data schemas |
| `poly.cpp`, `poly.hpp` | the Vitis HLS kernel |
| `tb_poly.cpp` | the testbench, used for both C simulation and co-simulation |
| `poly_golden.py` | the test transactions and the Python golden model |
| `poly_timing.py` | decodes the messages from the RTL simulation's VCD and plots them |
| `run.tcl` | the Vitis HLS script, one stage per invocation |
| `poly_build.py` | the build script that runs the steps in order |

All of them are written by hand and already in the repo. The only
generated code is `include/`, the headers that pack and unpack the
messages, which the build creates from `poly_schema.py`.

---

Go to [Overview](./overview.md)
