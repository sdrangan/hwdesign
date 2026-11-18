---
title: The Stream Version
parent: "Histogram: Transactional Memory"
nav_order: 2
has_children: false
---

# The Stream Version

In this version the command arrives on an AXI4-Stream, `s_cmd`, and the response leaves on
another, `s_done`. The samples and counts are in memory, reached through two AXI4 master
ports: `m_rd` for reading and `m_wr` for writing.

## The top

```cpp
void histogram_stream(hls::stream<word_t>& s_cmd, const word_t* m_rd, word_t* m_wr,
                      hls::stream<word_t>& s_done) {
#pragma HLS INTERFACE axis port=s_cmd
#pragma HLS INTERFACE m_axi port=m_rd offset=off bundle=gmem0 depth=65536
#pragma HLS stable variable=m_rd
#pragma HLS INTERFACE m_axi port=m_wr offset=off bundle=gmem1 depth=65536
#pragma HLS stable variable=m_wr
#pragma HLS INTERFACE axis port=s_done
#pragma HLS INTERFACE ap_ctrl_none port=return
    hls_thread_local hls::stream<word_t, 16> rd_cmd, wr_cmd;
    hls_thread_local hls::stream<word_t> rd_data, wr_data, wr_done;
    hls_thread_local hls::stream<HistJob, 2> job;

    hls_thread_local hls::task t_ctrl(hist_control, s_cmd, rd_cmd, job, wr_cmd);
    hls_thread_local hls::task t_rd(mem_r_stream_task<MEM_DW>, rd_cmd, m_rd, rd_data);
    hls_thread_local hls::task t_comp(hist_compute, job, rd_data, wr_data);
    hls_thread_local hls::task t_wr(mem_w_stream_done_task<MEM_DW>, wr_cmd, wr_data, m_wr, wr_done);
    hls_thread_local hls::task t_resp(hist_response, wr_done, s_done);
}
```

- **`ap_ctrl_none`**: no start or done signal. The kernel never stops; each task is
  **re-fired** by the runtime whenever its input arrives.
- **One `hls::task` per task**, joined by `hls_thread_local` FIFOs. The command FIFOs hold 16
  words, more than one 11-word memory command, so the control task can queue the next job's
  commands while the data movers are still busy with this one.
- **`m_axi` with `offset=off` and `stable`**: the only form in which Vitis supports a memory
  pointer passed to an `hls::task`. There is no base-address register: the bus address is the
  command's word offset times 4, from address 0. With `offset=slave`, Vitis would add a hidden
  FIFO of pointers for each task, and a design whose tasks fire different numbers of times per
  job deadlocks on it, at RTL only.
- **Two bundles**, `gmem0` and `gmem1`: one read owner and one write owner. On the board both
  would reach the same DRAM, and the testbench serves both from one memory.

## How it is checked

Five jobs, sent back to back:

| Job | `n` | `shift` | Samples | Expected |
| --- | --- | --- | --- | --- |
| 1 | 256 | 11 | uniform over 16 bits | `OK` |
| 2 | 1024 | 11 | a bell curve | `OK` |
| 3 | 700 | 10 | uniform; half saturate the top bin | `OK` |
| 4 | 70000 | 11 | none: `n > MAX_N` | `N_TOO_LARGE`, nothing written |
| 5 | 1024 | 11 | a decaying exponential | `OK` |

`hist_build.py` runs them twice:

1. **C simulation** (Vitis `csim`). The testbench pushes all five commands, calls the top once,
   and reads five responses: the tasks run as threads. It works, and takes about 12 seconds,
   so it is the quick check while writing a task.
2. **RTL simulation through XSI.** Vitis co-simulation of an `ap_ctrl_none` design is not
   reliable, so the synthesized Verilog is driven directly, cycle by cycle, with Waveflow's
   bus models: a stream master on `s_cmd`, an AXI4 read slave on `m_axi_gmem0` and a write
   slave on `m_axi_gmem1` over one memory, and a stream slave on `s_done`. It runs twice:
   with the five commands back to back, and with each job alone (1500 idle cycles between
   commands).

After each run, every count is compared with NumPy's `bincount`, the refused job's counts
must be untouched, and there must be exactly five responses, in order, with the right status.
A deadlock would show up as a missing response, never as a pass. All three runs pass.

## The timing of a job

From the waveform of the run with each job alone, in clock cycles (100 MHz) after the
command's last word was accepted:

| `n` | first sample (L) | last sample | last count | first write request | last write ack (B) | response |
| --- | --- | --- | --- | --- | --- | --- |
| 256 | 23 | 293 | 335 | 325 | 360 | 355 |
| 1024 | 23 | 1109 | 1151 | 1141 | 1176 | 1171 |
| 700 | 23 | 765 | 807 | 797 | 832 | 827 |
| 70000 (refused) | - | - | - | - | - | 38 |

Reading one row, `n` = 256:

- **Latency to the first sample, L = 23 cycles**, the same for every size. Most of it is the
  command path, not the memory: the control task writes the 11-word `MRCmd` (cycles 1 to 13),
  the read mover reads it as it arrives, issues the read request 8 cycles later (cycle 22), and
  the testbench's memory answers on the next cycle (23). Eight of those 11 words are the
  unused cookie.
- **The read**: 256 samples from cycle 23 to 293. The read mover asks for 16 words at a time
  (`ARLEN` = 15), and the testbench's memory serves one burst at a time, so each burst of 16
  takes 17 cycles: 16 burst requests for 256 samples, 64 for 1024. (Job 5's 1024 samples
  take 65, one cycle longer: they start at word 1980 and cross a 4 KB boundary at word 2048,
  which no AXI burst may cross, so the mover splits one burst in two.)
- **The compute** starts 5 cycles after the first sample and keeps pace with the read, one
  sample per cycle, then writes its 32 counts: the last at cycle 335, 42 after the last sample.
- **The write**: 32 counts in two bursts of 16. The write mover's first request goes out
  before the compute is done (cycle 325), as soon as it has buffered a burst; the memory
  acknowledges the last burst at cycle 360.
- **The response** leaves at cycle 355.

A refused job never touches memory; its response comes 38 cycles after its command.

![Each job's phases, measured from the RTL](images/timeline_stream.png)

## Do consecutive jobs overlap?

Yes. The top of the figure is the back-to-back run. The control task accepts the next command
as soon as it has sent this one's, so job 2's memory commands are already queued when job 1's
read finishes. Job 2's read starts at cycle 324, while job 1 is still computing its counts
(last at 341), writing them (to 366) and sending its response (361): the end of each job hides
behind the start of the next.

The **read port** is the bottleneck. It is busy from one job's first sample to its last, then
idle for 25 cycles while the read mover takes its next 11-word command and issues the first
request; the compute task follows it sample for sample. All five jobs finish at cycle 3354,
against 3563 for the same jobs one at a time.

## The response and the write acknowledgement

In every job, the response leaves **5 cycles before the memory acknowledges the last count**
(`BVALID`): 355 against 360 for `n` = 256. The write mover sends its `MemComplete` as soon as
its loop has handed the last count to the `m_axi` port, in the same state where it waits for
the acknowledgement, so the completion does not wait for it. On a real bus, a host that reads
the counts the instant it gets the response could read them before they land. This is the
behavior of Waveflow's write mover as it is today, not of the histogram's tasks.

## What the testbench's memory hides

The memory model answers a read request on the next cycle and serves one burst at a time. A
DRAM behind an interconnect takes tens of cycles to answer, but accepts several requests at
once. So on the board `L` would be longer, while the one idle cycle per 16-word burst would
disappear.
