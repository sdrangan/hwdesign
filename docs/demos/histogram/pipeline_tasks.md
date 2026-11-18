---
title: "hist_pipeline: Tasks and Descriptor"
parent: "Histogram: Transactional Memory"
nav_order: 4
has_children: false
---

# hist_pipeline: Tasks and Descriptor

The task bodies of the unit 10 design, [`hist_pipeline`](pipeline.md), in
`demos/histogram/pipeline/`. Where [`hist_simple`](simple.md) has one compute task that runs a
job start to finish, `hist_pipeline` has a task per step, so each step can work on a different
job.

## One descriptor per job

The kernel is five tasks in a line. The first task builds one **descriptor** for the job,
holding everything any later task will need. Each task after it reads the descriptor, uses the
fields it needs, and passes it on, in front of the data it produces. No task learns about a job
any other way: there are no side streams from the control task to the tasks further down.

```
s_cmd -> control -[MemRCmd|desc]-> mem_r_stream_framed -[desc|samples]-> compute
                                       (m_rd)                               |
                                                   [MemWCmd|desc|counts]   v
s_done <- response <---desc--- mem_w_stream_framed_done <-------------------+
                                       (m_wr)
```

| Stream | From | To | Each job, in order |
| --- | --- | --- | --- |
| `s_cmd` | outside | control | `HistCmd` (5 words) |
| `rd_cmd` | control | read mover | `MemRCmd` (3), then `HistDesc` (5) |
| `rd_data` | read mover | compute | `HistDesc` (5), then `n` samples |
| `wr_data` | compute | write mover | `MemWCmd` (3), then `HistDesc` (5), then 32 counts |
| `wr_done` | write mover | response | `HistDesc` (5), after the counts are in memory |
| `s_done` | response | outside | `HistResp` (2) |

The three streams in the middle are **framed**: every word carries a `last` bit, set on the
final word of each message. That is how the data movers step over a descriptor without reading
it. They count messages by their `last` bits, not by their contents.

Because the descriptor rides in front of the data, it can never be paired with the wrong job's
data. It also paces the kernel: each task fires once per descriptor, so every task fires
exactly once per job, refused jobs included.

## The messages

All words are 32 bits, and every address is a **word offset**, not a byte address: the data
movers take word offsets, and the kernel's memory ports start at address 0.

**The command**, `HistCmd`, one per job:

| Field | Meaning |
| --- | --- |
| `job_id` | echoed in the response |
| `data_addr` | word offset of the first sample |
| `n` | number of samples |
| `cnt_addr` | word offset of the 32 counts |
| `shift` | `bin = min(x >> shift, 31)` |

**The descriptor**, `HistDesc`, built by the control task:

| Field | Who reads it |
| --- | --- |
| `job_id` | the response task |
| `status` | compute (whether to write counts) and the response task |
| `n` | compute: how many samples to bin (0 for a refused job) |
| `shift` | compute |
| `cnt_addr` | compute, for the write command |

**The response**, `HistResp`: `job_id`, and a `status`: `OK` (0), or `N_TOO_LARGE` (1) when `n` is
more than `MAX_N` = 65535, the most a 16-bit counter can hold. A refused job reads nothing and
writes nothing, but still gets its response.

**The memory commands** are Waveflow's: `MemRCmd` and `MemWCmd`, three words each, an `addr`,
a `len`, and `fwd_bursts`, the number of messages that follow the command and are to be
passed along. Here `fwd_bursts` is always 1: the descriptor.

All five messages are declared once, in Python, and the build generates their C++ structs. How
that works, and what the generated methods do, is on the
[messages and serialization](messages.md) page.

## The control task

```cpp
static void hist_control(hls::stream<word_t>& cmd_in, hls::stream<frame_t>& rd_cmd) {
    HistCmd cmd;
    cmd.read_stream<MEM_DW>(cmd_in);
    const bool ok = (cmd.n <= MAX_N);

    HistDesc d;                                 // the job, as every later task needs it
    d.job_id = cmd.job_id;
    d.status = ok ? HistStatus::OK : HistStatus::N_TOO_LARGE;
    d.n = ok ? (int)cmd.n : 0;                  // a refused job reads nothing
    d.shift = cmd.shift;
    d.cnt_addr = cmd.cnt_addr;

    MemRCmd rc;                                 // read n samples from data_addr,
    rc.addr = cmd.data_addr;                    // after relaying the one burst behind this
    rc.len = d.n;
    rc.fwd_bursts = 1;
    rc.write_framed_stream<MEM_DW>(rd_cmd);
    d.write_framed_stream<MEM_DW>(rd_cmd);      // that burst: the descriptor
}
```

One command in, one framed message out: the read command, then the descriptor behind it. The
control task is the only task that sees the `HistCmd`, and it owns no memory port. A refused
job still sends both, with a read of length 0, so the descriptor still goes through.

## The compute task

```cpp
static void hist_compute(hls::stream<frame_t>& rd_data, hls::stream<frame_t>& wr_data) {
    HistDesc d;
    d.read_framed_stream<MEM_DW>(rd_data);      // the header the read mover relayed
    const bool ok = (d.status == HistStatus::OK);

    MemWCmd wc;                                 // write NBINS counts to cnt_addr, and
    wc.addr = d.cnt_addr;                       // echo the one burst behind this when done
    wc.len = ok ? NBINS : 0;
    wc.fwd_bursts = 1;
    wc.write_framed_stream<MEM_DW>(wr_data);
    d.write_framed_stream<MEM_DW>(wr_data);     // that burst: the same descriptor, passed on

    count_t counts[NBINS];
#pragma HLS ARRAY_PARTITION variable=counts complete
CLEAR: for (int b = 0; b < NBINS; b++) {
#pragma HLS UNROLL
        counts[b] = 0;
    }
SAMPLES: for (int i = 0; i < (int)d.n; i++) {
#pragma HLS PIPELINE II=1
        bool last;
        const word_t x = streamutils::read_boundary_word<frame_t, MEM_DW>(rd_data, last);
        const word_t bin = x >> d.shift;
        counts[bin < NBINS ? (int)bin : NBINS - 1]++;
    }
    if (ok) {
    COUNTS: for (int b = 0; b < NBINS; b++) {
#pragma HLS PIPELINE II=1
            streamutils::write_boundary_word<frame_t, MEM_DW>(wr_data, counts[b], b == NBINS - 1);
        }
    }
}
```

**It frames the write before it bins.** The write command and the descriptor go out as soon as
the descriptor is read, before the first sample arrives. The write mover then reads them and
waits for the counts, so the write command is never on the critical path. It can be sent
this early because everything it needs, the address and the length, is in the descriptor.

**The loop-carried dependence.** `counts[bin]++` reads a count, adds one and writes it back.
If the next sample lands in the same bin, its read must see this write, so a new sample can
start every cycle only if read, add and write fit in one cycle. With the counts partitioned
into 32 registers they do: Vitis schedules `SAMPLES` at **II=1** (iteration latency 5). Left
in a block RAM instead, Vitis still reports II=1, but only by chaining the RAM read, the add and
the RAM write into one cycle, and it warns that this path, 9.4 ns, does not meet the 10 ns clock
(`HLS 200-887`).

## The response task

```cpp
static void hist_response(hls::stream<word_t>& wr_done, hls::stream<word_t>& resp_out) {
    HistDesc d;
    d.read_stream<MEM_DW>(wr_done);
    HistResp resp;
    resp.job_id = d.job_id;
    resp.status = d.status;
    resp.write_stream<MEM_DW>(resp_out);
}
```

The descriptor comes back from the write mover, and the response is made from it. It waits for
the write mover, not for the compute task, because a job is done only when its counts are in
memory: the write mover sends the descriptor back only after the memory acknowledges the last
write (see the [hist_pipeline page](pipeline.md#the-response-and-the-write-acknowledgement)).

## The data movers

The two memory tasks are Waveflow's framed adaptors, used as they are:

- `mem_r_stream_framed_task<32>`: read one `MemRCmd`, pass the next `fwd_bursts` messages
  through unread, then burst `len` words from `m_rd[addr]` onto its output, one per cycle.
- `mem_w_stream_framed_done_task<32, 5>`: read one `MemWCmd`, hold the next `fwd_bursts`
  messages (up to 5 words, `HistDesc::nwords<32>()`), write `len` words to `m_wr[addr]`, wait
  for the memory's last write response, then send the held words on `wr_done`.

Neither reads the descriptor; the same two adaptors serve any kernel. Each owns one `m_axi`
port and touches nothing else but streams. That split is a rule, not a style: a task that owns a
memory port should do nothing but move words, so the tasks that hold state never wait on the
bus, and two tasks never share one port.
