---
title: System Verilog Implementation
parent: Conditional Subtraction Division
nav_order: 4
has_children: false
---

# Stage 3: The SystemVerilog Implementation

This stage has two halves, and they are in two different files. The **module**
(`subc_divide.sv`) is the state machine that does the arithmetic. The
**testbench** (`tb_subc_divide.sv`) is what hands it work and collects the
answers. You write a piece of each, because the protocol between them only makes
sense if you have implemented both ends of it.

## Handshaking protocol

Since the operation takes a variable number of clock cycles, the transfer of
inputs and outputs uses a **handshaking protocol**. For the inputs:

* `output inready`: Indicates that the module is ready for the next set of inputs, `a`, `b` and `nbits`
* `input invalid`: Set to indicate that there are valid data values for `a`, `b`, and `nbits`. The module will start processing the data when `inready=invalid=1`.

For the outputs:

* `output outvalid`: Indicates that the module processing is complete and a valid output `z` is available.
* `input outready`: Indicates to the module that the data is ready to be accepted. The module will consider the data as transferred when `outready=outvalid=1`.

The pattern — a `valid` from the sender, a `ready` from the receiver, transfer on
the cycle both are high — is worth recognising. It is the same one AXI-Stream and
most other on-chip interfaces use, and you will meet it again.

## State machine

We can manage the handshaking protocol in the module by using three states:

* `IDLE`:  Waiting for inputs.  
    - In this state, the module outputs `inready=1` and `outvalid=0`.  
    - The module waits until the signal `invalid=1`.  
    - When `invalid=1`, the inputs `a`, `b`, and `nbits` should be registered to the internal registers and the module should move to the state `RUN`.
* `RUN`:  The module is performing the division over multiple iterations.
    - You can use the variable `count` for the iteration number and stop after the correct number of iterations.
    - While running, `inready=0` and `outvalid=0`
    - After completing the `nbits` iterations, the module should move to `DONE`.
* `DONE`:  The results are ready.  
    - The module asserts `outvalid=1` and `inready=0` to indicate the results are ready, and that it is not yet ready for new inputs.
    - When the signal `outready=1` the module assumes the outputs have been read,
    and moves to the `IDLE` state in the next iteration.

## Writing the module

Complete the section marked `TODO` in `subc_divide.sv`. You write two blocks:

* an `always_comb` that computes the next value of every register from the
  current ones, and
* an `always_ff @(posedge clk)` that commits them.

Splitting it that way is the standard shape for a state machine — the decisions
in one place, the clocking in another.

The combinational block must assign *every* `_next` signal on *every* path, or you
infer a latch. The usual way is to start with defaults that hold the current
value, then override them per state:

```systemverilog
a_next = a_reg;  b_next = b_reg;  z_next = z_reg;
count_next = count;  state_next = state;
```

The `RUN` state is one iteration of exactly the algorithm you already wrote in
Python. Two things to watch:

* **Compare the shifted value against `b_reg`, not `a_reg`.** The comparison is on
  the remainder after the shift, which is the whole point of "bring down the next
  bit".
* **Drive the outputs from the *current* state, not the next one.** `inready`,
  `outvalid` and `z` describe what the module is doing now:

```systemverilog
inready  = (state == IDLE);
outvalid = (state == DONE);
z        = z_reg;
```

## Writing the testbench

The reading of the test vectors, the writing of the results and the counting of
clock cycles are all given. What you write is the handshake itself — the `TODO` in
`tb_subc_divide.sv` marks it. Four things have to happen, in order:

1. Wait until the module is ready (`inready`), then hold `invalid` high across one
   posedge and drop it again.
2. Wait for `outvalid`, counting posedges into `cycle_count`.
3. Sample `zgot = z` **while `outvalid` is still high** — that is the only time the
   module promises `z` means anything.
4. Hold `outready` high across one posedge and drop it, which is how the module
   learns the answer has been taken.

{: .important }
> **Bound the wait loop.** Write step 2 as
> `while (!outvalid && cycle_count < MAX_WAIT)`, not as `while (!outvalid)`.
>
> A module that never asserts `outvalid` — which is exactly what a half-finished
> state machine is — would otherwise hang the simulation, and a simulator that
> never returns looks precisely like one that is working hard. A failed case is
> far more useful than a run that never ends. If the loop times out, increment
> `timeouts` and leave `zgot` and `cycle_count` alone; the build scores an
> unanswered case as the failure it is.

There is a watchdog in the testbench as a backstop, outside the part you write. If
the whole simulation is still going after 500 µs it prints a diagnosis and stops,
so a stuck design costs you seconds rather than a coffee break. If you see

```
TIMEOUT: still running after 500 us of simulated time.
```

then the module stopped handshaking: check that the state machine leaves `RUN`
after `nbits` iterations, asserts `outvalid` in `DONE`, and returns to `IDLE` once
`outready` is seen.

## Running the stage

```bash
python subc_build.py --through svsim
```

This compiles both files, runs the simulation, and compares the result against
your Python — you do not invoke the simulator yourself. If the compile fails, that
is reported as a score of zero with the tool output attached, rather than as a
traceback that leaves you with no submission.

```
SystemVerilog divider: 10/10
  ✓ (6/6) SystemVerilog matches your Python model
  ✓ (4/4) Each case finishes within nbits + 2 cycles
```

Both are scored proportionally, and the feedback names the first case that failed
with its `a`, `b` and `nbits`, what Python said and what the simulation said.

The latency check is only credited on cases that were **answered correctly**. Fast
and wrong is not a design, and timing a case whose answer is wrong measures
nothing. A correct machine spends one cycle in `IDLE`, `nbits` in `RUN` and one in
`DONE`, so `nbits + 2` is a comfortable allowance rather than a tight one.

{: .warning }
> The comparison is against *your* Python model, not against ours. That means two
> unimplemented halves would agree with each other perfectly — so if your Python
> returns the same `z` for every case, this stage scores zero regardless of what
> the simulation did, and says so. Fix `subc_divide.py` first.

## Running on the NYU server

If you are on the [NYU server](../../support/nyuremote/), follow the
[python instructions](../../support/nyuremote/python.md) to log in, clone the
repository, install `uv`, and create and activate the virtual environment. Then
run the build through `uv`:

```bash
uv run python subc_build.py --through svsim
```

## Using the Vivado GUI

The flow above is command line only. If you prefer, you can follow the
[instructions for using the Vivado GUI](../../support/amd/sv_build.md), and you
can edit your SystemVerilog in the Vivado editor. Run the build afterwards to be
scored.

---

Go to [grading and submission](./submit.md)
