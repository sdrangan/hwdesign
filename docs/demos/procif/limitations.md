---
title: Limitations of This Design
parent: Bus Basics and Memory‑Mapped Interfaces
nav_order: 7
has_children: false
---

# Limitations of This Design

The demo works. It is also, as a way of doing computation, close to the worst
possible arrangement — and seeing exactly *why* is the point of having built
it.

All the numbers below are measured from the co-simulation, at 100 MHz
(10 ns clock).

## It takes a long time to move each value

One call moves four 32-bit words — `x`, `w`, `b` in, `y` out — plus a start and
a status check. On the wire:

| Quantity | Measured |
|---|---|
| Register writes per call | 4 (`x`, `w`, `b`, start) |
| Register reads per call | 2 (status, `y`) |
| Cycles per individual write | ~3 |
| Cycles from first write to result read | **22** |
| Cycles the kernel actually computes | **5** |

So roughly **four cycles of bus traffic for every cycle of useful work**. The
`transaction_cycles: 5` in `results/summary.json` is the kernel; everything
else is the cost of talking to it.

And the bus cost does not shrink if the kernel gets cleverer. Make the
arithmetic ten times more complicated and those 22 cycles are unchanged — you
would simply have a better ratio. Make it *simpler* and the ratio gets worse.
Here the kernel is a single multiply-add, so the interface dominates
completely.

Put it in throughput terms. Calls repeat every 27 cycles, so at 100 MHz this
IP sustains about **3.7 million calls per second** — 3.7 million multiply-adds
per second. A single DSP block on this FPGA, driven properly, does 100 million.
We are using well under a twentieth of *one* multiplier, on a device that has
hundreds.

## The processor has to poll

The host cannot know when the kernel is finished. It writes `ap_start` and then
asks, repeatedly, by reading the control register at `0x00` until `ap_done`
comes back set.

In our trace that costs exactly one read, because the kernel finishes in 5
cycles — sooner than the processor can get around to asking. That is
misleadingly cheap. For a kernel that runs for thousands of cycles, the
processor spins on the bus the entire time, and each poll is a full AXI4‑Lite
read transaction. The processor is not just waiting; it is generating traffic
in order to wait.

Interrupts are the usual escape — that is what the `interrupt` port is for, and
why `port=return` exists. But an interrupt costs a context switch, which for a
5-cycle kernel is far more expensive than the work itself.

The deeper problem is structural: **the processor is in the loop for every
single value.** Nothing happens without it.

## Why this design is still worth knowing

Everything above argues against using AXI4‑Lite for data. That is the correct
conclusion, and it is not an argument against AXI4‑Lite — it is an argument
about *what it is for*.

AXI4‑Lite is designed for slowly varying items: configuration, control, status.
Set a gain once and run for a million samples. Read an error counter. Start and
stop a pipeline. For those jobs the 22-cycle cost is irrelevant, because it
happens once, and the simplicity is worth a great deal — you wrote four pragmas
and got a complete, correct bus interface with no handshaking code at all.

The mistake is using a control interface as a data interface.

## What comes next

The fix is to stop moving data one register at a time, and to take the
processor out of the inner loop:

* **AXI4‑Stream** — data flows into and out of the IP continuously, with the
  same `VALID`/`READY` handshake you already know, but one transfer per cycle
  and no addresses at all. This is the next unit.
* **Free-running kernels** — instead of being started per call, the IP waits on
  data and runs whenever data arrives. No `ap_start` per item, no polling.
* **AXI4 (full) and DMA** — the IP reads and writes memory itself in bursts,
  rather than being spoon-fed by the processor.

In each case AXI4‑Lite does not disappear. It keeps doing the job it is good
at — configuration and status — while the data takes a different path.

---
Go to [Packaging the Vitis IP](./add_ip.md)
