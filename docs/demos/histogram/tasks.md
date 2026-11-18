---
title: The Tasks and Messages
parent: "Histogram: Transactional Memory"
nav_order: 1
has_children: false
---

# The Tasks and Messages

Everything on this page is shared by every version of the kernel. A version differs only in
how the command reaches the control task and how the response leaves the response task: on
AXI4-Streams in the [stream version](stream.md), through queues a host reaches over the bus in
the [memory-mapped version](mm.md).

## The messages

All words are 32 bits, and every address is a **word offset**, not a byte address: the data
movers take word offsets, and the kernel's memory ports start at address 0.

**The command**, `HistCmd`, one per job, five words:

| Word | Field | Meaning |
| --- | --- | --- |
| 0 | `job_id` | echoed in the response |
| 1 | `data_addr` | word offset of the first sample |
| 2 | `n` | number of samples |
| 3 | `cnt_addr` | word offset of the 32 counts |
| 4 | `shift` | `bin = min(x >> shift, 31)` |

**The response**, `HistResp`, one per job, two words: `job_id`, and a `status`: `OK` (0), or
`N_TOO_LARGE` (1) when `n` is more than `MAX_N` = 65535, the most a 16-bit counter can hold.
A refused job reads nothing and writes nothing, but still gets its response.

Both are declared once, in Python (`hist_schema.py`). The build generates the C++ structs,
`HistCmd` and `HistResp` with their `read_stream` / `write_stream` methods, and the testbenches
pack and unpack the same words with the same schemas, so no side can disagree about which bit
means what.

**The memory commands** are Waveflow's, and the data movers are the only parts of the kernel
that touch memory:

| Message | To | Fields used here | Words |
| --- | --- | --- | --- |
| `MRCmd` | the read mover | `addr`, `len` | 11 |
| `MWCmd` | the write mover | `addr`, `len`, and a cookie, `xfer_msg` | 11 |
| `MemComplete` | from the write mover | the cookie, echoed back | 10 |

The cookie, `xfer_msg`, is up to eight words the write mover hands back untouched when the
write is done. That is how the response task learns *which* job finished: the control task
puts the job ID and the status in it.

## The control task

```cpp
static void hist_control(hls::stream<word_t>& cmd_in, hls::stream<word_t>& rd_cmd,
                         hls::stream<HistJob>& job, hls::stream<word_t>& wr_cmd) {
    HistCmd cmd;
    cmd.read_stream<MEM_DW>(cmd_in);
    const bool ok = (cmd.n <= MAX_N);

    if (ok) {                                   // read n samples from data_addr
        MRCmd rc;
        rc.addr = cmd.data_addr;  rc.len = cmd.n;  rc.xfer_len = 0;
        rc.write_stream<MEM_DW>(rd_cmd);
    }
    HistJob j;                                  // a refused job reads 0 and emits nothing
    j.n = ok ? (int)cmd.n : 0;  j.shift = cmd.shift;  j.emit = ok;
    job.write(j);

    MWCmd wc;                                   // write NBINS counts to cnt_addr
    wc.addr = cmd.cnt_addr;  wc.len = ok ? NBINS : 0;  wc.xfer_len = 2;
    wc.xfer_msg.data[XFER_JOB_ID] = cmd.job_id;
    wc.xfer_msg.data[XFER_STATUS] = (int)(ok ? HistStatus::OK : HistStatus::N_TOO_LARGE);
    wc.write_stream<MEM_DW>(wr_cmd);
}
```

One firing per job: one command in, and three messages out that start the job. It owns no
memory port. A refused job still sends a job descriptor and a write command, of length 0, so
every task downstream fires once per job and the response count always equals the command
count.

## The compute task

```cpp
static void hist_compute(hls::stream<HistJob>& job, hls::stream<word_t>& samples,
                         hls::stream<word_t>& counts_out) {
    count_t counts[NBINS];
#pragma HLS ARRAY_PARTITION variable=counts complete
    const HistJob j = job.read();
CLEAR: for (int b = 0; b < NBINS; b++) {
#pragma HLS UNROLL
        counts[b] = 0;
    }
SAMPLES: for (int i = 0; i < (int)j.n; i++) {
#pragma HLS PIPELINE II=1
        const word_t x = samples.read();
        const word_t bin = x >> j.shift;
        counts[bin < NBINS ? (int)bin : NBINS - 1]++;
    }
    if (j.emit) {
    COUNTS: for (int b = 0; b < NBINS; b++) {
#pragma HLS PIPELINE II=1
            counts_out.write(counts[b]);
        }
    }
}
```

Samples in, counts out: it never sees an address, so it is the same task however the samples
reach it.

**The loop-carried dependence.** `counts[bin]++` reads a count, adds one and writes it back.
If the next sample lands in the same bin, its read must see this write, so a new sample can
start every cycle only if read, add and write fit in one cycle. With the counts partitioned
into 32 registers they do: Vitis schedules `SAMPLES` at **II=1** (iteration latency 5), and the
whole design at an estimated 137 MHz. Left in a block RAM instead, Vitis still reports II=1, but
only by chaining the RAM read, the add and the RAM write into one cycle, and it warns that this
path, 9.4 ns, does not meet the 10 ns clock (`HLS 200-887`).

## The response task

```cpp
static void hist_response(hls::stream<word_t>& wr_done, hls::stream<word_t>& resp_out) {
    MemComplete done;
    done.read_stream<MEM_DW>(wr_done);
    HistResp resp;
    resp.job_id = done.xfer_msg.data[XFER_JOB_ID];
    resp.status = (HistStatus)(int)done.xfer_msg.data[XFER_STATUS];
    resp.write_stream<MEM_DW>(resp_out);
}
```

One write completion in, one response out. It waits for the write mover, not for the compute
task, because a job is done only when its counts are in memory: the write mover sends its
completion only after the memory acknowledges the last write (see the
[stream page](stream.md#the-response-and-the-write-acknowledgement)).

## The data movers

The two memory tasks are Waveflow's, used as they are:

- `mem_r_stream_task<32>`: read one `MRCmd`, then burst `len` words from `m_rd[addr]` onto
  `rd_data`, one per cycle.
- `mem_w_stream_done_task<32>`: read one `MWCmd`, write `len` words from `wr_data` to
  `m_wr[addr]`, wait for the memory's last write response, then send a `MemComplete` carrying
  the command's cookie.

Each owns one `m_axi` port and touches nothing else but streams. That split is a rule, not a
style: a task that owns a memory port should do nothing but move words, so the tasks that hold
state never wait on the bus, and two tasks never share one port.
