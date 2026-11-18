---
title: Messages and Serialization
parent: "Histogram: Transactional Memory"
nav_order: 5
has_children: false
---

# Messages and Serialization

This page goes with [`hist_pipeline`](pipeline.md), the unit 10 design, whose descriptor it
uses as its example; the generated API is the same one [`hist_simple`](simple.md) uses for its
messages.

Every task in this kernel talks to the next in **messages**: a command, a descriptor, a memory
command, a response. On the wire each one is a few 32-bit words. Somebody has to decide which
field goes in which bits of which word, and every side has to agree: the control task that
writes a descriptor, the compute task that reads it, the testbench that packs the commands,
the golden model that checks the responses.

Writing that packing by hand is how bugs get in: a field shifted by one word on one side only,
a word count that was right until someone added a field. So nothing in this demo packs a
message by hand. Each message is **declared once**, in Python, and Waveflow generates the C++
struct and its methods, and serializes it in Python with the same layout. This page shows how.

## Declaring a message

The messages are in `hist_schema.py`. Here is the job descriptor:

```python
Word32 = IntField.specialize(bitwidth=32, signed=False, include_dir=INCLUDE_DIR)

class HistStatus(IntEnum):
    OK = 0
    N_TOO_LARGE = 1      # n > MAX_N: refused, nothing read and nothing written

HistStatusField = EnumField.specialize(enum_type=HistStatus, include_dir=INCLUDE_DIR)

class HistDesc(DataList):
    """The job descriptor: built once by the control task, then carried through the kernel."""

    elements = {
        "job_id":   {"schema": Word32, "description": "The command's job ID"},
        "status":   {"schema": HistStatusField, "description": "OK, or why the job was refused"},
        "n":        {"schema": Word32, "description": "Samples to bin: 0 for a refused job"},
        "shift":    {"schema": Word32, "description": "bin = min(x >> shift, NBINS - 1)"},
        "cnt_addr": {"schema": Word32, "description": "Word offset of the NBINS counts"},
    }
    include_dir = INCLUDE_DIR
```

A `DataList` is a record: an ordered list of named fields, each with a schema of its own. A
field can be an integer of any width (`IntField`), an enum (`EnumField`, which takes the
fewest bits that hold every value, here 1), another `DataList`, or an array (`DataArray`).
The order of `elements` is the order on the wire.

The build's `gen_include` step turns each schema into a header:

```python
for cls in schema.SCHEMA_CLASSES:              # HistCmd, HistDesc, HistResp, ...
    inner.add(DataSchemaStep(cls, word_bw_supported=[32, 64],
                             include_dir="include", framed=True))
```

`word_bw_supported` lists the word widths the C++ methods are generated for. `framed=True`
adds the methods for framed streams, below. The output, `include/hist_desc.h`, starts with
the struct itself:

```cpp
struct HistDesc {
    ap_uint<32> job_id;  // The command's job ID
    HistStatus status;  // OK, or why the job was refused
    ap_uint<32> n;  // Samples to bin: 0 for a refused job
    ap_uint<32> shift;  // bin = min(x >> shift, NBINS - 1)
    ap_uint<32> cnt_addr;  // Word offset of the NBINS counts

    static constexpr int bitwidth = 129;
    ...
```

The descriptions become the comments, and the enum becomes a C++ `enum class HistStatus` in
its own header. Everything after the fields is generated methods.

## How a message lays out across words

A message is packed field by field, in order, into words of `MEM_DW` bits. A field never
straddles two words: if it does not fit in what is left of the current word, it starts the
next one. For `HistDesc` (129 bits of fields):

| Word | `MEM_DW` = 32 | `MEM_DW` = 64 |
| --- | --- | --- |
| 0 | `job_id` | `job_id` (bits 31:0), `status` (bit 32) |
| 1 | `status` (bit 0) | `n` (31:0), `shift` (63:32) |
| 2 | `n` | `cnt_addr` |
| 3 | `shift` | |
| 4 | `cnt_addr` | |

So the same message is 5 words on a 32-bit stream and 3 on a 64-bit one. The struct says how
many, at compile time:

```cpp
template<int word_bw>
static constexpr int nwords();      // HistDesc::nwords<32>() == 5, nwords<64>() == 3
```

**Never write a word count as a literal.** Use `nwords<W>()`. The top sizes its FIFOs with it,
and passes it to the write mover as the size of its descriptor buffer:

```cpp
static const int HDR = MemWCmd::nwords<MEM_DW>() + HistDesc::nwords<MEM_DW>();
hls_thread_local hls::stream<frame_t, 2 * HDR> rd_cmd, rd_data, wr_data;
...
hls_thread_local hls::task t_wr(mem_w_stream_framed_done_task<MEM_DW, HistDesc::nwords<MEM_DW>()>,
                                wr_data, m_wr, wr_done);
```

Add a field to `HistDesc` and every one of these follows. The Python side is the same:
`hist_build.py` gets the descriptor's length for its timing analysis from
`len(HistDesc(...).serialize(word_bw=32))`.

## The generated C++ API

Every generated struct has the same methods, each a template on the word width `W`:

| Method | Moves the message to or from |
| --- | --- |
| `write_stream<W>(s)` / `read_stream<W>(s)` | a plain `hls::stream<ap_uint<W>>`: `nwords<W>()` words |
| `write_framed_stream<W>(s)` / `read_framed_stream<W>(s)` | an `hls::stream<framed_word<W>>`: the same words, with `last` set on the final one |
| `write_axi4_stream<W>(s)` / `read_axi4_stream<W>(s)` | an AXI4-Stream port (`TLAST` on the final word) |
| `write_array<W>(x)` / `read_array<W>(x)` | an array of `ap_uint<W>`, starting at `x[0]` |
| `nwords<W>()` | nothing: the number of words, at compile time |

**Plain streams** are for a port where each side knows the length of every message.
`s_cmd` and `s_done` are plain, and so is the write mover's echo to the response task:

```cpp
HistCmd cmd;
cmd.read_stream<MEM_DW>(cmd_in);                // hist_control: 5 words off s_cmd
...
HistDesc d;
d.read_stream<MEM_DW>(wr_done);                 // hist_response: the echoed descriptor
HistResp resp;
resp.job_id = d.job_id;
resp.status = d.status;
resp.write_stream<MEM_DW>(resp_out);            // 2 words onto s_done
```

**Framed streams** are for a stream that carries several messages per job, back to back,
where some task must skip a message without reading it. A `framed_word<W>` is a word plus a
`last` bit; the framed methods set `last` on a message's final word. The data movers count
messages by those bits. The control task frames the read mover's input as two messages:

```cpp
MemRCmd rc;
rc.addr = cmd.data_addr;
rc.len = d.n;
rc.fwd_bursts = 1;                              // pass on the 1 message behind this one
rc.write_framed_stream<MEM_DW>(rd_cmd);         // 3 words, last on the third
d.write_framed_stream<MEM_DW>(rd_cmd);          // 5 words, last on the fifth
```

The read mover reads the `MemRCmd`, copies words through until it has seen one `last`, then
appends the samples. The compute task reads the descriptor back off the framed stream, and
then the samples one word at a time:

```cpp
HistDesc d;
d.read_framed_stream<MEM_DW>(rd_data);
...
const word_t x = streamutils::read_boundary_word<frame_t, MEM_DW>(rd_data, last);
```

Data words that are not a message, like the samples and the counts, go through
`streamutils::read_boundary_word` / `write_boundary_word`, which hand the `last` bit back or
take it as an argument.

**Arrays** are for putting a message inside another message's field, which is what the next
section needs.

## Two ways to carry information with a transfer

A task that hands work to a data mover usually needs something to come out the other side:
the next task has to know which job the data belongs to, or what to do with it. There are two
ways to send it along, and they answer different questions.

### A framed header: describes the job

The header travels **ahead of the data**, on the same stream, and the mover passes it on
without reading it. This is what `hist_pipeline` does: `fwd_bursts = 1` on each memory command, the
descriptor right behind it.

```
rd_cmd:   [ MemRCmd | HistDesc ]                     -> read mover
rd_data:  [ HistDesc | sample 0 ... sample n-1 ]     -> compute
wr_data:  [ MemWCmd | HistDesc | count 0 ... 31 ]    -> write mover
wr_done:  [ HistDesc ]   (after the last write response)
```

Use a header when **the next task needs it to do its work**: the compute task cannot bin
without `n` and `shift`, and cannot frame the write without `cnt_addr`. The header arrives
before the data, so the task has it in time. And it is welded to its data: it cannot be paired
with another job's samples, whatever order things finish in.

The write mover holds its header across the write and sends it on only after the memory has
acknowledged the last word. So the header that comes out of the write mover also says *this
job is done*.

### An `xfer_msg` tag: matches the completion to its job

Waveflow's other pair of movers, `mem_r_stream_task` and `mem_w_stream_done_task` (the ones
[`hist_simple`](simple.md) uses, with no tag: `xfer_len = 0`), take their command on its own stream, `MRCmd` / `MWCmd`,
and carry a **tag**: up to eight 32-bit words, `xfer_msg`, which the write mover hands back,
untouched, in its `MemComplete` once the write is done. The tag does not travel with the data.
It comes back with the **completion**.

Use a tag when **nothing downstream needs to know about the job except whoever waits for it to
finish**: a task that issues a write and later has to match each completion to the write that
caused it. If the task that receives the completion only has to say "job 7 is done", a tag is
enough.

Do not fill a tag by hand. The tag is just an array of words, so the generated `write_array`
packs any message into it, and `read_array` unpacks it at the other end:

```cpp
HistResp tag;                                       // what the completion should say
tag.job_id = cmd.job_id;
tag.status = HistStatus::OK;

MWCmd wc;
wc.addr = cmd.cnt_addr;
wc.len = NBINS;
static_assert(HistResp::nwords<MEM_DW>() <= 8, "the tag must fit in xfer_msg");
tag.write_array<MEM_DW>(wc.xfer_msg.data);
wc.xfer_len = HistResp::nwords<MEM_DW>();
wc.write_stream<MEM_DW>(wr_cmd);

// ... later, in the task that waits for the write:
MemComplete done;
done.read_stream<MEM_DW>(wr_done);
HistResp resp;
resp.read_array<MEM_DW>(done.xfer_msg.data);       // the same job_id and status
```

The elements of `xfer_msg` are 32 bits, so this form works with `MEM_DW` = 32. Check that the
tag fits, with `nwords`, at compile time.

Both approaches cost words. Every `MRCmd`, `MWCmd` and `MemComplete` carries all eight tag words
whether they are used or not: 11, 11 and 10 words. The framed commands are 3 words, and the
header is exactly as long as the descriptor.

## The pattern: one descriptor per job

Put together, this is the shape of the kernel:

1. **The first task builds one descriptor** with everything any later task will need. It is
   the only task that sees the command.
2. **Each task reads the descriptor, uses what it needs, and passes it on** in front of the
   data it produces. A data mover passes it on without reading it.
3. **There are no side streams.** No task learns about a job from anywhere but the descriptor
   in front of its data.
4. **The last task turns the descriptor into the response.**

What that buys:

- **Nothing can be mispaired.** A side stream of job information and a stream of data can
  drift apart by one job, and the kernel then computes the wrong thing with no error. A
  header in front of its data cannot.
- **Every task fires once per job.** A refused job still sends its descriptor through every
  task, with reads and writes of length 0, so there is always exactly one response per command.
- **Adding a field is one edit.** A new parameter for the compute task goes in `HistDesc`,
  is set by the control task and read by the compute task. No stream, no task signature, and
  no word count changes anywhere else.

The cost is that a header sits in every FIFO in front of the data, and the FIFO must be deep
enough to hold it. The [hist_pipeline page](pipeline.md#do-consecutive-jobs-overlap) shows what
happens when it is not: the read mover cannot pass the next job's descriptor on, and the next
job's read waits for the compute task.
