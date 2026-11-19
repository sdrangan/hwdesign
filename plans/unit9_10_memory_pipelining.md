# Units 9–10: kernels and shared memory, and task pipelining

## Overview

Unit 8 ends with pipelining and loop unrolling. Unit 9 is currently *Shared
Memory Transactions* (`units/unit09_sharedmem/sharedmem.pptx`): about 35 slides
on memory architecture, interconnect topologies and AXI signals, followed by a
Vitis host-launched `m_axi` histogram. It explains what shared memory *is*, but
not how to design *around* it.

What the projects need most is **load-compute-store (LCS)** and, more generally,
**task-level pipelining**. That rests on two ideas, so it is split into two
units:

| Unit | Topic | Question it answers |
|---|---|---|
| 9  | Kernels and shared memory | How does my kernel talk to memory and to the host? |
| 10 | Task-level pipelining and LCS | How do I keep the compute busy while memory is slow? |
| 11 | Systolic arrays (moved from unit 10) | — |

Both units move away from Vitis host-activated kernels to **free-running
kernels** (`ap_ctrl_none` `hls::task`) simulated under **XSI**, which is
Waveflow's preferred flow. A kernel's logic sees only streams; memory is reached
through Waveflow's **adaptors**, which turn each interaction with memory into a
command–response exchange over streams.

Why this order works:

- Unit 9 absorbs the machinery (adaptors, commands, completions, slave views),
  so unit 10 can be purely about scheduling and overlap.
- Unit 4 (procif) and unit 5 (fifo) already taught streams and command–response,
  so the stream-only kernel is not a new interface style.
- Units 7–8 taught II and pipelining inside a loop. Task pipelining is the same
  idea one level up: throughput is set by the slowest stage.
- A systolic array is the compute stage of a tiled LCS design, so unit 11
  starts from something the students already have.

## Decisions

- **Use Waveflow's existing names.** Do not rename anything in Waveflow for the
  course. Each slide that introduces a Waveflow term also gives the industry
  term, and says in a word where Waveflow's version is narrower (see
  [Terminology](#terminology)).
- **No Waveflow modelling by students.** No DES (pysim), no `FreeRunMod`
  Python models. Students write `hls::task` bodies in C++; Waveflow supplies the
  adaptors, the generated top and the XSI testbench. Waveflow's DES can
  simulate the pipelining, but the course does not need it.
- **Give as much machinery as possible.** Students focus on the compute and on
  the transactional interface to memory. Everything else is pre-built.
- **The design example is built fresh**, not adapted from Waveflow's legacy
  histogram (`examples/shared_mem`, direct `m_axi` via `MMIFMaster`). The
  legacy version is not shown.
- **Any block-processing kernel will do** for unit 10. It does not have to be
  the interleaver.

## Unit 9: Kernels and shared memory

### 1. Shared memory and interconnects

Skills:

- Select between shared and dedicated memory.
- Select between master and slave.
- Analyze protocols with bus and full-crossbar interconnects.

Notes:

- Give one concrete calculation for bus vs. crossbar: N masters on a bus share
  one channel's bandwidth; on a crossbar they run in parallel unless two target
  the same slave.
- Built (2026-11-17): the bus-vs-crossbar rule is taught on one flow
  (B = 4, 2, 3 cycles, frames A, B, C) over four slides -- bus, crossbar (the
  transfers pipeline: period max B, latency sum B), a half-duplex DDR, and a
  block that appears twice -- with timelines computed by a scheduler in
  `tools/build_sharedmem_slides.py`. Master/slave is recapped, not
  re-assessed (unit 4 covered it).
- Pending: a crossbar-vs-bus area and latency demo on the Zynq-7020, from
  Waveflow's `xbar_profile` (SAMD vs SASD), placed after the crossbar timeline.

### 2–3. Transactions and the data mover; concurrent tasks (the histogram)

Skills:

- Design a transactional master interface with a streaming interface to the
  kernel.
- Write a kernel's tasks against that interface.
- Draw simple timing diagrams to estimate when transactions and a job complete.

Structure (revised 2026-11-17): the old section 2 grew to 31 slides and was
split in two. One running example, a **histogram**, carries both.

Section 2, transactions and the data mover:

1. The motivating example (`histogram_stream`: command and response on streams,
   driven directly by the testbench).
2. The steps of the protocol (the kept command / compute / response phase
   slides), then the histogram's command and response formats.
3. The data mover; the read and write transactions as sequence diagrams.
4. A toy kernel, `summem` (one task and a read mover): diagram, code, timeline.
5. Practice pairs: write `maxmem` (its (c) shows why a kernel must drain every
   word it asked for), and draw the activity of a two-read kernel (previews
   outstanding requests).

Section 3, concurrent tasks on the histogram (reworked 2026-11-18 onto
`hist_simple`):

1. Concurrent tasks, `hls::task`, the histogram's top colour-mapped against its
   diagram (one kernel task between the two adaptors), the rules for streams
   between tasks.
2. The kernel's code in two halves: command, read and bin; then write, **wait
   for the write's completion**, respond. One job, task by task.
3. Timing: a burst, then a histogram job (compute overlaps the read; the
   counts wait for the last sample), then jobs back to back: **one at a time**,
   the read port idle while each job's counts are written. A practice pair,
   "Where the time goes", computes that idle time and what overlapping jobs
   would save. This is unit 10's motivation.

**Decision (2026-11-18): unit 9's histogram is `hist_simple`.** Three tasks:
the read adaptor, one kernel task, the write adaptor. The kernel runs a whole
job in order (command, read, bin, write, wait, respond), so there are no tags,
no job descriptors and no overlap between jobs: unit 9 teaches the transaction
mechanics, and unit 10 starts from its serial timeline. Since Waveflow PR #315
(2026-11-19) the plain movers carry no tag at all -- `MRCmd`/`MWCmd` are
`{addr, len}`, `MemComplete` is `{len}` -- and unit 10 correlates by framing a
descriptor (the in-band protocol), not by `xfer_msg`. The five-task version
(control, compute and response tasks, tags in `xfer_msg` -- a field that no
longer exists, so that tag does not build against current Waveflow -- jobs overlapping) and
its slides are kept at the git tag `unit9-hist-multitask`; the descriptor
version (framed movers, one `HistDesc` per job) lives on as
`demos/histogram` `hist_pipeline`, a unit 10 reference. Unit 9's homework
focuses on transaction mechanics, transaction-level interfaces and timing
transactions.

The y = a·x + b practice pairs were dropped as duplicates of `maxmem` and the
two-reads problem.

`demos/histogram` holds three designs: `hist_simple` (sections 2–3),
`hist_mmqueue` (section 5: the same kernel with the command and response in
memory-mapped queues) and `hist_pipeline` (unit 10). The slides take their
code and measured numbers from the first two.

Notes:

- The first concurrent tasks in the course: the kernel and its two adaptors
  run at once. Three slides introduce them: concurrent tasks, `hls::task` in
  Vitis (a copy kernel's top), and the rules for streams between tasks (streams
  only, plus a `stable`, `offset=off` `m_axi` pointer; no shared variables; one
  owner per `m_axi` port), why streams make concurrency safe, and deadlock as
  the cost.

- Open with *why* a transactional interface, before how: the kernel never sees
  addresses, every write returns a completion, and an arbiter can merge
  many requesters (Waveflow `docs/guide/interface/axi_mm/master.md`, which
  since PR #315 leads with the in-band protocol: the reader relays a
  descriptor ahead of the data and the writer echoes it as the completion).
- The adaptors are `MemRStream` / `MemWStream`. A kernel talks to one over
  three streams: `m_cmd` (an `MRCmd`/`MWCmd` per burst: `addr`, `len`), the
  data stream, and the completion stream (`MemComplete`: `len`). The
  completion endpoint is **`m_done`** (renamed from `s_done` in Waveflow
  PR #312; `s_done` remains as a deprecated alias).
- Addresses are word offsets from a bound base, not bytes.
- The generated C++ still names the completion stream `s_done` (the rename was
  Python-only so far); slides name streams by role (`rd_cmd`, `rd_data`,
  `rd_done`).

- Timing model, from Waveflow's `MemoryMod`: a burst of n words costs about
  `latency_init + n * latency_per_word` cycles, plus bus request and return
  latency. Unit 10 then asks what happens when the phases overlap across jobs.

### 4. AXI4 under the hood

A short section of signal-level reference, kept from the old deck: AXI family,
AXI4-MM features, the AXI4-Lite review, burst signals, the write example. The
homework's AXI waveform problems point here. The write example's figure
disagrees with its bullets and with AXI (`AWLEN` is beats - 1): fix the figure.

### 5. MM queues and credit (and histogram_mm)

Frame as **how others reach your kernel**: the slave views (register bank,
queue in, queue out, BRAM window).

Notes:

- A free-running kernel cannot use `s_axilite` (it cannot see a write happen).
  That is why slave views replace the AXI-Lite registers from unit 4.
- The slave adaptor is hand-written RTL in Waveflow. Students *use* the views;
  they do not build them.
- Motivate credits by the failure: ordinary back-pressure does not cross a
  shared bus, so a write into a full slave queue stalls the bus and can
  deadlock the system. The credit pattern: the producer writes only what fits,
  and the consumer returns a cumulative count of words consumed
  (`credit::Producer` / `credit::Consumer` in HLS).

### Design example: histogram (now the running example of sections 2-3)

Built fresh in the new style:

- the command arrives in an **MM slave queue**;
- samples and bin edges are read, and counts written, through **`MemRStream` /
  `MemWStream`**;
- the response is returned to the host (see the open choice below).

For the lecture this is presented on slides (architecture diagram, command and
response formats, a timing diagram). The working version is built later, for
the lab or as the starting point of unit 10.

Open design choice: does the response go into a slave **queue out** that the
host reads, or does the kernel write it into **host memory** with a master
write? The second is how NVMe and NIC completion queues work (an industry
tie-in), but the host must then poll memory or receive an interrupt.

Caution: the bin update is a read-modify-write, so consecutive samples in the
same bin can stop the loop from reaching II = 1. In unit 9 keep the compute out
of focus; the interfaces are the point.

### Pacing

Five sections is more than one lecture. If time is short, compress section 1
and the AXI signal slides of section 3; sections 2 and 4 are the new material.

## Unit 10: Task-level pipelining and LCS

### Progression

1. Memory is slow and shared: latency vs. bandwidth, bursts (recap of unit 9).
2. The naive version: unit 9's `hist_simple` timeline, one job at a time, with
   the read port idle while each job's results are written. Unit 10 opens on
   it.
3. Load → compute → store as separate tasks with local buffers.
4. Ping-pong (double) buffering, so the stages overlap: task pipelining.
   Throughput = the slowest stage.
5. Stage balancing, FIFO depth, deadlock.
6. Free-running stream module + memory adaptors + XSI simulation.

### What Waveflow already provides

- **Visible latency.** Memory latency shows up in XSI: in the interleaver's RTL
  trace each reader firing takes about 151 cycles, so the naive version will
  visibly stall.
- **Ping-pong is built in.** `hls::stream_of_blocks` is a ping-pong pair with a
  lock handshake: the load stage fills the next job's block while compute reads
  the current one.
- **A bottleneck lesson.** The interleaver's steady-state period is about
  302 cyc/job, set by the reader (it fires twice per job, P then X, over one
  `m_axi` bus), not by the compute. pysim matches RTL to about 1%. An assignment
  can be: find the bottleneck, fix it (e.g. a second read bundle), measure the
  new period.
- **Why random access needs a block.** A stream cannot be indexed backwards, so
  data that is read at random must be landed in on-chip block RAM first. This is
  the reason for the *load* in LCS.

### The lab shell

Waveflow's generated artifacts are plain C++, and the XSI testbench depends only
on the kernel's boundary ports, never on its internal stages. Every example
(`interleaver_inband`, `fir_block`) uses the same four boundary ports:
`s_cmd` (axis), `m_in` (`m_axi`, gmem0), `m_out` (`m_axi`, gmem1), `s_done`
(axis). (The boundary `s_done` is the kernel's own port, unaffected by the
`m_done` rename.)

Pre-built, generated once by the instructor:

- the read/write adaptor headers (`mem_r_stream*_task.h`,
  `mem_w_stream*_task.h`), the command and completion types (`m_r_cmd.h`,
  `mem_complete.h`, ...) and `streamutils`;
- the top: the fixed boundary signature, internal streams, block buffers and
  one `hls::task` per stage (about 25 lines, see
  `examples/interleaver/gen/interleaver_inband.cpp` in Waveflow);
- the XSI harness and port map (`*_tb_harness.h`, `*_ports.h`);
- a short Python script that writes the input vectors, runs XSI, and checks the
  dumped output against a NumPy golden.

Written by students, as `hls::task` bodies:

- **control** -- read the job command; issue the read command(s) to the reader,
  the write command to the writer, and a job descriptor to compute. This is the
  transactional interface to memory.
- **load** -- read the stream into a ping-pong block buffer.
- **compute** -- block in, block out. Reuses unit 7–8 pipelining and unrolling.
- **store** -- write the block back onto the writer's data stream.

Choices to make:

1. **Plain or framed commands.** The examples use framed in-band descriptors,
   which keep the job information welded to the data; robust but heavier to
   read. The plain `MRCmd` reader is simpler, but then the control task must
   keep the command streams in step itself. Leaning: keep framing, with the
   helpers pre-written.
2. **Who writes the top.** Students may restructure the stages (e.g. add a
   second reader) as long as the four boundary ports stay fixed; otherwise
   regenerate it for them.
3. **The block kernel.** `fir_block` streams through its compute stage with no
   block buffer, so LCS and the overlap are not visible. Prefer a kernel that
   needs random access within a block: histogram, transpose, block reversal,
   sort.

   **Leaning (2026-11-18): a 2-D rotation**, `y1 = x1·cos + x2·sin`,
   `y2 = −x1·sin + x2·cos`, with x1, x2, y1, y2 in separate (planar) arrays and
   cos and sin computed by the host and sent in the command. Reading x1 then x2
   forces a block buffer for x1 and another for y2, and load and store are both
   2n words, so overlapping jobs gains about 1.5× (3n serial against a 2n
   period) -- far more than the histogram, whose store is only 32 words. The
   obvious objection, "read x1 and x2 in alternating chunks", is tiling, and
   belongs in the stage-balancing section rather than being avoided. The
   alternative, if the motivation must be airtight, is a two-pass kernel
   (normalise by max |x|) that cannot emit anything before it has read every
   input. Unit 10 also introduces the framed descriptor: the one way a
   completion names its job since Waveflow dropped `xfer_msg` (PR #315).

### Risks

- **Deadlocks hang rather than fail.** A dropped token in a free-running design
  gives a hang, not a wrong answer. XSI runs a fixed number of cycles, and the
  Python check must assert counts, since a deadlock can look like success. This
  will be the hardest part for students to debug.
- **Contention is invisible under XSI.** XSI's memory (`FlatMemory`) is
  un-arbitrated, so masters competing for bandwidth "look clean under XSI and
  honest under pysim". Any assignment that depends on bus contention must say
  so.
- **The mental-model shift.** Explain why there is no `ap_start`/`ap_done` and
  who decides when work begins; otherwise students carry over the host-call
  model.

## Terminology

Waveflow names are kept. The slides give the industry term alongside:

| Waveflow | Industry term | Where Waveflow is narrower |
|---|---|---|
| `MemRStream` / `MemWStream` + `MRCmd`/`MWCmd` | DMA engine driven by descriptors (e.g. AXI DataMover) | no scatter-gather |
| framed descriptor echoed by the write mover | transaction tag / completion-queue entry | travels in-band with the data, not an AXI ID |
| slave queue, register bank, BRAM window | doorbells, memory-mapped queues, CSRs | |
| credit streams | credit-based flow control (PCIe, NoCs) | |
| `stream_of_blocks` ping-pong | ping-pong / double buffering; PIPO in Vitis `DATAFLOW` | |
| free-running `hls::task` | Vitis free-running / `ap_ctrl_none` kernels | |

Waveflow-only words to define on first use: *firing* (one execution of a task
body, i.e. one job), *framed* / *in-band* (packets delimited by TLAST, with a
header ahead of the data), *timed phase*, *transactional arbiter*, *boundary
port*.

## Open items

- [ ] Waveflow `docs/examples/interleaver/interleaver.md` says the in-band
      descriptor paces the pipeline to "one job in flight" (around line 87),
      while line 66 and the ~302 cyc/job period show that the stages overlap.
      Reword before students read it ("one job per stage").
- [ ] Confirm whether Vitis C simulation of `hls::task` is reliable enough as a
      quick check before XSI. The generated files warn that `ap_ctrl_none`
      cosim is unreliable; without a C-sim check, XSI is the only debugging loop.
- [ ] Decide where the histogram's response goes (slave queue out vs. a master
      write to host memory).
- [x] Build the histogram in the new style: `hist_simple` and `hist_mmqueue`
      for unit 9, `hist_pipeline` kept for unit 10 (2026-11-18).
- [ ] Unit 10's example: the rotation kernel (see "The block kernel" above).
- [ ] Rework `units/unit09_sharedmem/sharedmem.pptx`; create unit 10; renumber
      systolic arrays (`unit10_arrays`) to unit 11.
- [ ] Possibly a Waveflow glossary page mapping its terms to industry terms
      (deferred; the course slides carry the mapping for now).
