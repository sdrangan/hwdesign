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
  over a window), a histogram, a small matrix-vector product, a 2-D max pool
  with non-overlapping windows, or a piecewise function with programmable
  breakpoints.

You have not covered pipelining yet, so you cannot tell in advance which of
these is easy to build at full speed and which is hard. That is fine: the
grader's feedback on your prompt will warn you if what you ask for is far
beyond the course, and a target you miss costs nothing if it is reported
honestly (below).

The operation's parameters (sizes, strides, coefficients, modes) travel on the
stream, in one of two ways:

* **In the header of the command that uses them.** A 2-D max pool can carry the
  image size and the window size in every `COMPUTE` header, so one data
  command and `END` are enough.
* **In a separate configuration command.** A FIR filter sends its taps once in
  `CONFIG`, and every `PROCESS` command after it uses them. This is the right
  choice when the configuration is large or state carries from one command to
  the next.

Either way, the prompt says which parameter values are invalid (a zero-sized
window, a window larger than the image, a size too large for the kernel's
buffers) and
which error code each raises.

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

Keep the prompt short. The agent can choose command codes, header layouts, how
values pack into words, and file formats on its own, and it keeps them
consistent between the model, the kernel and the testbench. Spend your words on
what it cannot know or check:

* **What the operation means**, precisely enough to work an example by hand:
  the formula, the boundary behavior, and what state carries from one command
  to the next. A guess here is consistent with itself, so every test passes
  and nothing tells you it is wrong.
* **What the application requires:** the data formats (for fixed point, the
  rounding and the saturation), the largest sizes the hardware must handle
  (the largest image, window or tap count, which set the size of its buffers),
  and a throughput or latency target. The agent has no way to know these. The
  part and the clock come from the reference example, so you do not need to
  name them. The target is something to measure against, not something you
  must meet: the agent reports it as met or not, and a miss reported honestly
  costs nothing.
* **The course pattern:** parameters travel on the stream, in the command that
  uses them or in a configuration command; which values are invalid; and on an
  error, the kernel reports it in the status registers, closes its output
  burst and returns.
* **An independent check of the model:** a few hand-computed examples, or a
  NumPy or SciPy reference. A model checked only against itself proves
  nothing. For a 2-D max pool, for example, NumPy has no pooling function, but
  a `reshape` followed by `max` gives one in a line.
* **The scenarios an agent would not think of:** sizes at your limits, a
  change of parameters between commands within one activation, and each
  error followed by a fresh activation that must work.

The prompt must also tell the agent to give `results.md` **three sections, by
these names**, because the Part 4 grader reads them:

* **Assumptions:** every place the prompt was silent or ambiguous, and what the
  agent chose. Every item here is a decision you left to the agent. In a test
  run, even a careful prompt left a dozen of them, and some were real design
  holes.
* **Open Items:** questions the agent could not settle, and anything that
  failed or was not done.
* **Run History:** one row per run, with the prompt version, what was built or
  changed, and what passed. This is what lets the next run, or another agent,
  pick up where the last one stopped.

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
2. Run the agent in that folder, and give it this message:

   > Build the accelerator specified in prompt.md, in this folder, with
   > Waveflow: its MCP server is available, and its stream_inband example is
   > the reference design to follow. Run C simulation, co-simulation and
   > synthesis, and write results.md. Report the achieved II, latency and
   > estimated clock as measured. If a target is missed, report it as a FAIL
   > rather than reworking the kernel to close timing, and do not build a
   > timing model in Python.

   The last sentence keeps the run to the size of this project. Without it, an
   agent that misses a target may spend an hour restructuring the kernel to
   close timing, which is a skill this course has not covered yet.
3. Read `results.md`, then iterate with the agent as described below until
   nothing consequential is left open.
4. Commit and push the folder, and submit its link (part 4).

### Iterating with the agent

Expect the first run to come back with assumptions and open items. That is not
a sign the prompt failed: an agent that has never seen your application has to
guess somewhere, and it tells you where. Working through those guesses with
the agent is the assignment, and the Part 4 grader checks that you did it.

For each run:

1. **Read Assumptions and Open Items.** Most assumptions are minor: names, codes,
   how values are packed into words. Leave those alone. An assumption is
   **consequential** if it changes an output value, which conditions are errors,
   what the kernel sends before or after an error, the throughput, or what a
   host has to do. Every open item needs an answer.
2. **Settle each consequential one in `prompt.md`.** If you agree with the
   agent's choice, write it into the prompt as a requirement. If you do not,
   write what you want instead. Answer each open item there too.
3. **Add a row to the revision history** at the end of `prompt.md`, written by
   you, saying what changed and pointing at what the run did:

   | Version | Change | Why |
   | --- | --- | --- |
   | 1 | First version | |
   | 2 | Throughput is one input word (two samples) per clock | Run 1 read "one sample per clock" as one word every 2 cycles: assumption 2 in its `results.md` |
   | 2 | The output after an early TLAST is specified | Run 1 had to choose it (assumption 11); I kept its choice |

4. **Commit `prompt.md`** with the reason as the commit message. Keep one
   `prompt.md` and one `results.md`: git keeps every version, and the
   revision history and Run History are the parts a reader, and the grader,
   can see at a glance.
5. **Run the agent again in the same folder**, continuing from what it built,
   with this message:

   > prompt.md has been revised; the revision history at its end says what
   > changed and why. Read results.md, including its Run History, and update
   > the design in this folder to match the new prompt. Rerun every check the
   > change affects, through C simulation, co-simulation and synthesis, and
   > update results.md, including a new row in its Run History. Report the
   > achieved II, latency and estimated clock as measured. If a target is
   > missed, report it as a FAIL rather than reworking the kernel to close
   > timing, and do not build a timing model in Python.

   A follow-up run changes only what the revision touches, so it is usually
   much shorter than the first. It works in a new session too: everything it
   needs is in `prompt.md`, `results.md` and the code.

Stop when every remaining assumption is minor and there are no open items. A
first prompt that gets there in one run needs no revisions at all.

### What `results.md` must contain

`results.md` is what gets graded, and the grader cannot run your code. Your
prompt asks the agent for:

* **Results:** a table of each target and scenario with the measured value,
  PASS or FAIL, and the file each number came from, with timing from
  co-simulation and resources from synthesis. Anything that does not meet the
  spec is a FAIL.
* **Assumptions**, **Open Items** and **Run History**, as described in Part 3.

Commit the raw evidence `results.md` cites: the simulation logs, the comparison
outputs and the synthesis reports. Do not commit Vitis project directories or
bulky logs that nothing cites.

---

Next: [Submission →](./submit.md)
