---
title: "In class: parts 1 and 2"
parent: Command-Response Mini-Project
nav_order: 2
has_children: false
---

# In class: prompt design and C simulation

In class you work in pairs on a deliberately simple accelerator, so the time
goes into the specification rather than the arithmetic.

## Pick an operation

Choose one. All three use 32-bit floating point, so there is no rounding or
saturation to specify, and all three need a `CONFIG` command, a `DATA` command
and `END`.

| Operation | `CONFIG` carries | `DATA` computes | Other commands |
| --- | --- | --- | --- |
| **Scale and offset** | `a`, `b` | `y[i] = a * x[i] + b` | |
| **Clamp and count** | `lo`, `hi` | `y[i] = min(max(x[i], lo), hi)` | `COUNT`: returns how many samples have been clipped since `CONFIG` |
| **Running sum** | an initial value `s0` | `y[i]` = the running sum of everything since `CONFIG`, starting from `s0`; the sum carries over from one `DATA` command to the next | |

For clamp and count, notice that the count cannot go in `DATA`'s response
header: the header is sent before the samples are processed. That is why the
count is a command of its own.

## Part 1: Prompt design

Write `prompt.md` for your operation, following the
[command-response pattern](./pattern.md). It must tell the agent to:

* follow the Waveflow
  [streaming polynomial example](https://sdrangan.github.io/waveflow/docs/examples/stream_inband/),
  and follow the command-response pattern where the two differ: configuration
  is a command on the stream, not an AXI-Lite write;
* write a bit-exact Python model and the Vitis HLS kernel;
* run the Python model and C simulation, and check that they agree bit for bit,
  and **stop once C simulation passes**: no synthesis or co-simulation today;
* write `results.md` (below).

And it must specify:

* **the commands:** each command type, its code, and its header fields;
* **the responses:** what the kernel sends back for each command;
* **the errors:** each error case and its code in the status registers,
  including a `DATA` command before any `CONFIG`, a sample burst whose TLAST
  comes early, and one whose TLAST is missing;
* **the test cases:** the scenarios C simulation runs. Each error ends its
  activation, and is followed by a fresh activation that must work;
* **the results:** what goes in `results.md`. At least a table of every
  scenario with PASS or FAIL, and **a list of every place the prompt was silent
  or ambiguous, and what the agent chose**.

Paste your prompt into the LLM grader (**Command-Response Mini-Project**, part 1)
and revise it with the feedback. Two or three rounds is typical.

### Trade prompts

Swap prompts with another pair. Read theirs as if you were the agent, and write
down every decision it leaves to you: What does `CONFIG` send back, if anything?
What happens with `nsamp = 0`? If a header has two problems, which error code
wins? Give them your list, and fix your own prompt with the list you get back.
Keep the list: you will compare it with the agent's in part 2.

## Part 2: Implementation to C simulation

1. In your course repository, create the folder `cmdresp/inclass/` and put
   `prompt.md` in it. Commit and push it **before** the agent starts.
2. Open your agent in that folder and give it this message:

   > Build the accelerator specified in prompt.md, in this folder, with
   > Waveflow: its MCP server is available, and its stream_inband example is
   > the reference design to follow. Stop once C simulation passes, and write
   > results.md.

3. While it runs, watch what it does. Which example files does it read through
   the MCP server? Where does it get stuck?
4. When it finishes, read `results.md`. Compare its list of open decisions with
   the list from trading prompts. Which did you predict? Which did you not?
5. Commit and push the folder, then paste `results.md` into the LLM grader
   (part 2).

If the agent does not finish in class, finish at home.

---

Next: [Take-home: parts 3 and 4 →](./takehome.md)
