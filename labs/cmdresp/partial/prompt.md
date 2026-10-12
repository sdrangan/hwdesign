# TODO: name your accelerator

Build a Vitis HLS kernel in this folder following the Waveflow stream_inband
example (https://sdrangan.github.io/waveflow/docs/examples/stream_inband/) and
the command-response pattern.

## Operation
TODO: What the kernel computes, exactly enough to work an example by hand:
the formula, the boundary behavior (what happens at the edges, or with
leftover samples), and any state that carries from one command to the next.

## Requirements
TODO: The data formats (for fixed point, the rounding and the saturation);
the largest sizes the hardware must handle, which set its buffers; and a
throughput or latency target, saying what "per clock" counts if several
values share a word.

## Commands and parameters
TODO: Each command, the parameters it carries (in its own header, or in a
separate configuration command), what follows it, and its response.  Say
which parameter values are invalid, and that they are checked before any
data is read.

## Errors
Errors go in AXI-Lite status registers (halted, error code, tx_id).  On an
error the kernel closes any output burst it started with TLAST and returns
without reading more input.  Nothing persists between activations: the status
registers are cleared at the start of each one.

TODO: Which conditions are errors (at least an unknown command, invalid
parameters, and a burst whose TLAST comes early or is missing); which error
wins if several apply; and what the kernel sends before reporting each one.

## Verification
TODO: How the Python model is checked independently of itself: a few
hand-computed examples, and a NumPy or SciPy reference if there is one.
The scenarios: sizes at your limits, a change of parameters between
commands in one activation, edge cases of the operation, and one
activation per error, each followed by a fresh activation that must pass.

Compare the model, C simulation and co-simulation bit for bit.  Run
co-simulation once: one testbench run that walks through every scenario in
order, calling the kernel once per activation with fresh streams, including
each error activation and the fresh activation after it.

## results.md
Write results.md with these sections:
- Interface: the command and response layouts, how values pack into words,
  the status registers and the error codes.
- Design: the loop structure, where state is kept, and how the throughput
  target is reached.
- Targets: each target above with the required value, the measured value,
  PASS/FAIL and the file it came from (co-simulation for timing; synthesis
  for clock, II and resources).
- Verification: the model's check against the hand-computed examples and the
  reference; then one row per scenario saying whether the model, C simulation
  and co-simulation agree, and for each error scenario the status it set and
  whether the fresh activation after it passed. Name the source file of each.
- Assumptions: every place this prompt was silent or ambiguous and what you
  chose, apart from interface details already given under Interface.
- Open Items: questions you could not settle, and anything that failed or was
  not done.
- Run History: one row per run, with the prompt version, what was built or
  changed, and what passed, so that a later run can continue from here.

## Revision history
| Version | Change | Why |
| --- | --- | --- |
| 1 | First version | |
