---
title: "Take-home: parts 3 and 4"
parent: Command-Response Mini-Project
nav_order: 3
has_children: false
---

# Take-home: your own accelerator

The take-home parts repeat the in-class workflow on an accelerator you choose,
carried all the way through co-simulation and synthesis.

## Choosing the operation

Choose something that interests you, at the right size:

* **Too small:** anything as simple as the in-class menu, or anything with no
  state and no configuration.
* **Too large:** an FFT, or anything you could not check by hand on a small
  input.
* **About right:** a FIR filter, a running statistic (mean, variance, min/max
  over a window), a histogram, a small matrix-vector product, or a piecewise
  function with programmable breakpoints.

The operation must need **at least two command types that do different things
to the kernel's state or output**, besides `END`. For example, `CONFIG` followed
by any number of `PROCESS` commands, or `PROCESS` plus a `STATUS` command that
reports counters.

Decide whether your data is floating point or fixed point. Floating point is
easier. Fixed point means you must specify the formats, the rounding and the
saturation exactly, because the model and the hardware have to agree bit for
bit.

## Part 3: Prompt design

Your prompt follows the [command-response pattern](./pattern.md) and tells the
agent to:

* follow the Waveflow
  [streaming polynomial example](https://sdrangan.github.io/waveflow/docs/examples/stream_inband/),
  and the command-response pattern where the two differ;
* write a bit-exact Python model and the Vitis HLS kernel;
* run the Python model, C simulation and RTL co-simulation, and check that all
  of them agree bit for bit;
* measure latency and throughput from co-simulation, and resources from
  synthesis.

The agent does not need to build a timing model in Python; co-simulation timing
is enough.

The prompt must specify:

* **The data:** the input and output data and their formats.
* **The operation:** precisely. If it is fixed point, give the formats, the
  rounding and the saturation.
* **The commands:** every command type, its code and its header fields.
* **The responses:** what the kernel sends back on the stream for each command,
  including the response header format.
* **The errors:** every error case and its code in the status registers.
* **Targets:** the part (`xc7z020clg400-1`), the clock (10 ns), the stream
  width, and a throughput target you choose. The agent reports whether each one
  is met.
* **Model verification:** how the Python model is checked independently of
  itself, for example hand-computed worked examples, or comparison against a
  NumPy reference. A model checked only against itself proves nothing.
* **Test cases:** scenarios that cover every command and every error case, and
  the ones used to measure timing. Each error ends its activation and is
  followed by a fresh activation that must work.
* **The results:** what goes in `results.md` (below).

The prompt must also ask the agent to **list every place the prompt was silent
or ambiguous, and what it chose**. Every item on that list is a decision you
left to the agent. In a test run, even a careful prompt left twelve of them,
and some were real design holes.

Finally, the prompt ends with a **revision history**: a table with one row per
version, saying what changed and why. Engineering specifications carry one, so
that a reader can see how the design got to where it is. Start it with
version 1:

| Version | Change | Why |
| --- | --- | --- |
| 1 | First version | |

Paste the prompt into the LLM grader (part 3) and revise it with the feedback
before you start the agent.

## Part 4: Implementation

1. In your course repository, create `cmdresp/takehome/` and put `prompt.md` in
   it. Commit and push it **before** the first agent run.
2. Run the agent in that folder, with the same message as in class but without
   the instruction to stop after C simulation.
3. Read `results.md` and the agent's list of open decisions. Revise the prompt
   to close the ones that matter, and run again. Revising the prompt after
   seeing what the agent does is the main skill this project teaches.
4. For each revision, add a row to the prompt's revision history, written by
   you, not the agent. Say what you changed and why, pointing at what the
   agent did:

   | Version | Change | Why |
   | --- | --- | --- |
   | 1 | First version | |
   | 2 | `nsamp = 0` is valid and returns `RespHdr` alone | Run 1 had to guess: open decision 3 in its `results.md` |
   | 3 | Header errors are checked in code order; the lowest code wins | Run 2 checked them in an order I did not intend |

5. Commit each version of `prompt.md` before its run, with the same reason as
   the commit message. Git keeps the full history; the table is the part a
   reader, and the grader, can see at a glance.

### What `results.md` must contain

`results.md` is what gets graded, and the grader cannot run your code. Ask the
agent to put in it:

* a results table: criterion, target, measured value, PASS or FAIL, and the
  file each number came from;
* the word layout of every message;
* the timing and synthesis results;
* the list of open decisions, and what was chosen for each;
* anything that does not meet the spec, stated as a FAIL.

Commit the raw evidence `results.md` cites: the simulation logs, the comparison
outputs and the synthesis reports. Do not commit Vitis project directories or
bulky logs that nothing cites.

---

Next: [Submission →](./submit.md)
