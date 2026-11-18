---
title: The Memory-Mapped Version
parent: "Histogram: Transactional Memory"
nav_order: 3
has_children: false
---

# The Memory-Mapped Version

In the [stream version](stream.md) the commands arrive on an AXI4-Stream. Something has to
drive that stream, and a processor cannot: it talks to a peripheral with bus reads and writes.
In this version the host does exactly that. It **writes** each command into a queue at an
address, and **reads** each response out of another queue. The kernel is the stream
version's kernel, unchanged, synthesized from the same C++.

## The top

The new part is the RTL top, `histogram_mm.v`. It puts Waveflow's **memory-mapped slave
adaptor** in front of the kernel:

```
host --AXI4--> axi_slave_front --> decoder --+--> mm_queue_in  (qcmd,  0x0000) --s_cmd--> kernel
                                             +--> mm_queue_out (qresp, 0x1000) <-s_done-- kernel
```

| Address | View | The host | The kernel |
| --- | --- | --- | --- |
| `0x0000` | `qcmd`, queue in | writes a packet `[len, 5 command words]`; a read returns the free room | reads `HistCmd` words from `s_cmd` |
| `0x0800` | `qcmd` control | writes the room threshold for `irq_cmd` | |
| `0x1000` | `qresp`, queue out | each read pops one response word | writes `HistResp` words to `s_done` |
| `0x1800` | `qresp` status | a read returns the words waiting; a write sets the threshold for `irq_resp` | |

- **`axi_slave_front`** is the only part that speaks AXI. It serves one bus transaction at a
  time, so the queues see the host's writes and reads in the order the bus accepted them.
- **The decoder** sends each request to one of the two 4 KB views by address bit 12.
- **`mm_queue_in`** drops each packet's length word and pushes the rest onto `s_cmd`. A full
  queue holds the bus's write ready low, so a host must wait for room. This host waits on
  `irq_cmd`, which is high while the room is at least the threshold it set.
- **`mm_queue_out`** buffers the responses. Reading the empty queue returns an error rather
  than stalling the bus, so the host waits for `irq_resp`, high while at least the threshold
  is waiting.
- **The kernel** is `histogram_stream`, instantiated as it is. Its two `m_axi` ports, the data
  movers', go straight out to memory.

Waveflow generates this adaptor for kernels it builds itself, but not yet for an HLS kernel with
its own memory ports. So `histogram_mm.v` assembles it by hand, following Waveflow's generated
one-front adaptor. The adaptor modules are Waveflow's, used as they are.

## The host

At RTL the host is a C++ model on the top's AXI slave port, in `tb_xsi_histogram_mm.cpp`. It is
written as two threads that block, on Waveflow's host runtime (`xsi_sw.h`):

```cpp
void writer() {                                 // queue every command, as soon as there is room
    for (const auto& cmd : scenario_bursts())
        qcmd.write(cmd);                        // waits on irq_cmd, then writes [len | 5 words]
}
void reader() {                                 // one response per job, in whatever order
    for (long k = 0; k < njobs; ++k)
        resp = qresp.get(2);                    // sleeps on irq_resp, then pops 2 words
}
```

The writer does not wait for a job to finish before sending the next command. The host learns
which job a response belongs to only by reading its `job_id`.

## How it is checked

The same five jobs as the stream version, run twice under XSI: with every command queued at
once, and with each job alone. Each time, every count is checked against NumPy's `bincount`
and the refused job's counts must be untouched. Each response is **matched to its job by
`job_id`**, not by position: every job must get exactly one response, with the right status.
Both runs pass.

There is no C simulation of this version. Its kernel is the stream version's, which has one,
and the adaptor is RTL.

## The timing, seen from the host

With every command queued at once, in absolute clock cycles (100 MHz):

| Job | Host writes the command | Kernel takes it (last word) | Kernel sends the response | Host has read it |
| --- | --- | --- | --- | --- |
| 1 (n = 256) | 10 to 17 | 17 | 379 | 385 |
| 2 (n = 1024) | 19 to 26 | 26 | 1487 | 1493 |
| 3 (n = 700) | 28 to 35 | 35 | 2251 | 2257 |
| 4 (refused) | 37 to 44 | 311 | 2278 | 2284 |
| 5 (n = 1024) | 46 to 53 | 1419 | 3380 | 3386 |

- **All five commands are in by cycle 53.** Each is one 6-beat burst (the length word, then the 5
  command words), 7 cycles with its write response. The kernel takes job 2's and job 3's
  commands as soon as they arrive, because its control task frames each one into the 16-word
  FIFO in front of the read mover and is free again. Jobs 4 and 5 wait **in the queue**, for 267
  and 1366 cycles, until the kernel has room.
- **The kernel runs exactly as in the stream version.** Its phases match the stream version's
  cycle for cycle, 11 cycles later: L = 16, last count 328, response 362 after the command.
- **The host has a response 6 cycles after the kernel sends it**: `irq_resp` rises, then a 2-beat
  read.
- **Nothing is polled.** The host writes each threshold once, at cycles 3 and 6, and otherwise
  only moves commands and responses.

With each job alone, a job costs the host 7 cycles to send and 6 to collect, on top of the
kernel's own time. For `n` = 256: 375 cycles from the start of the command's write to the
response read, against 362 from command to response in the stream version.
