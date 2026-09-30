---
title: Using Waveflow
parent: Command-Response FIFO Interface
nav_order: 6
has_children: false
---

# Using Waveflow

The two hand-written kernels work, but look at what they had to know:
which bits of which word hold `tx_id`, that the coefficients pair up at
64 bits, where `error` sits in the footer. That knowledge is written out
in the kernel. The testbench needs the same knowledge to build the
messages, and so does the Python model to write the test vectors.

Writing serialization and deserialization by hand like this is
**time-consuming and error-prone**:

* The same layout is written out three times, in the kernel, the
  testbench and Python, and all three must agree to the bit. A mistake in
  one of them rarely crashes anything. It usually just produces wrong
  numbers.
* Every change multiplies. Adding a field to `PolyCmdHdr`, or widening
  `nsamp` to 32 bits, means finding and changing every place that packs
  or unpacks the message, for every word width.
* A new word width means new code, as `poly64.cpp` showed.

[Waveflow](https://sdrangan.github.io/waveflow/docs/guide/schema/) takes
the message definitions in `poly_schema.py` as the **single description**
of the layout, and generates the packing code from them for every word
width, in both C++ and Python. This page shows what it generates, and the
general kernel, `poly.cpp`, that uses it.

## The generated headers

The build's `gen_include` step, which you ran on the
[Headers and the Golden Model](./poly_python.md#step-1-generate-the-headers-gen_include)
page, turns each schema into a C++ header in `include/`. For
`PolyCmdHdr`, `include/poly_cmd_hdr.h` defines:

~~~cpp
struct PolyCmdHdr {
    ap_uint<16> tx_id;  // Transaction ID
    CoeffArray coeffs;  // Polynomial coefficients
    ap_uint<16> nsamp;  // Number of samples that follow

    template<int word_bw>
    void write_axi4_stream(hls::stream<streamutils::axi4s_word<word_bw>> &s,
                           bool tlast = true) const;
    template<int word_bw>
    void read_axi4_stream(hls::stream<streamutils::axi4s_word<word_bw>> &s,
                          streamutils::tlast_status &tl);
    // ... and the same for plain streams, arrays and memory
};
~~~

The struct has the schema's fields, with the descriptions as comments.
Its methods are the serialization:

* **`read_axi4_stream<W>(s, tl)`** reads the message from an AXI4-Stream
  of `W`-bit words and unpacks every field. At `W = 32` it does exactly
  what `poly32.cpp`'s header code did, word by word. At `W = 64` it does
  what `poly64.cpp`'s did. It also checks TLAST for you and reports where
  it fell as a `streamutils::tlast_status`: `tlast_at_end` if the message
  ended with TLAST on its last word, `tlast_early` if TLAST came too soon,
  or `no_tlast` if it never came.
* **`write_axi4_stream<W>(s, tlast)`** packs and sends the message, with
  TLAST on its last word.
* The same struct has methods for other interfaces too: a plain
  `hls::stream<ap_uint<W>>`, an array of words, and memory.

The word width is a **template parameter**, so one generated header
serves both 32- and 64-bit streams.

A companion header, `poly_cmd_hdr_tb.h`, adds methods that only a
testbench needs, such as reading a message from a file. The
[C simulation](./poly_csim.md#the-testbench) page uses them.

For arrays of samples, the generated `float32_array_utils.h` does the same
job. It packs `float` values into stream words, as many per word as fit:

* **`pf<W>()`**, the *packing factor*: the number of samples per `W`-bit
  word. It is 1 at 32 bits and 2 at 64.
* **`read_axi4_stream_lane<W>(s, x_lane, n, tl)`** reads one word and
  unpacks its samples into `x_lane[0 .. pf-1]`. A **lane** is one word's
  worth of samples. `n` says how many samples remain, so a half-full last
  word is handled.
* **`write_axi4_stream_lane<W>(y_lane, s, tlast, n)`** does the reverse.
* **`write_axi4_stream<W>(s, x, tlast, n)`** and
  **`read_axi4_stream<W>(s, x, tl, n)`** move a whole array of `n`
  samples at once. The testbench uses these.

Everything sits on waveflow's `streamutils_hls.h`. It provides the stream
word type, `streamutils::axi4s_word<W>` (that is the `axis_word_t` in
`poly.hpp`), the `tlast_status` bookkeeping, and the `uint_to_float` and
`float_to_uint` that the hand-written kernels used.

On the Python side, the same schema classes pack and unpack the same
messages, with `PolyCmdHdr().write_uint32_file(...)`,
`serialize(word_bw=...)` and `deserialize(...)`. That is how the golden
model wrote the test vectors, and how the timing step will decode the
messages off the wires.

## The general kernel

With the packing generated, the kernel in `poly.cpp` only has to say what
the protocol *does*:

~~~cpp
void poly(hls::stream<axis_word_t>& in_stream, hls::stream<axis_word_t>& out_stream) {
#pragma HLS INTERFACE axis port=in_stream
#pragma HLS INTERFACE axis port=out_stream
#pragma HLS INTERFACE ap_ctrl_none port=return

    // ----- The command header -----
    PolyCmdHdr cmd_hdr;
    streamutils::tlast_status cmd_hdr_tlast = streamutils::tlast_status::no_tlast;
    cmd_hdr.read_axi4_stream<WORD_BW>(in_stream, cmd_hdr_tlast);

    // ----- The response header -----
    PolyRespHdr resp_hdr;
    resp_hdr.tx_id = cmd_hdr.tx_id;
    resp_hdr.write_axi4_stream<WORD_BW>(out_stream, true);

    // ----- The samples -----
    static const int pf = float32_array_utils::pf<WORD_BW>();
    float x_lane[pf];
    float y_lane[pf];
    ...
    for (int i = 0; i < cmd_hdr.nsamp && read_samples; i += pf) {
#pragma HLS PIPELINE II=1
        const int nrem = cmd_hdr.nsamp - i;
        float32_array_utils::read_axi4_stream_lane<WORD_BW>(in_stream, x_lane, nrem, lane_tlast);
        for (int k = 0; k < pf; ++k) {
#pragma HLS UNROLL
            if (k < lane_count) {
                y_lane[k] = eval_poly_horner(cmd_hdr.coeffs.data, x_lane[k]);
            }
        }
        const bool out_tlast = (nrem <= pf);
        float32_array_utils::write_axi4_stream_lane<WORD_BW>(y_lane, out_stream, out_tlast, nrem);
        ...
    }

    // ----- The response footer -----
    PolyRespFtr resp_ftr;
    resp_ftr.nsamp_read = nsamp_read;
    resp_ftr.error = PolyError::NO_ERROR;
    ...   // classify framing errors, and flush to the next TLAST if needed
    resp_ftr.write_axi4_stream<WORD_BW>(out_stream, true);
}
~~~

Compare it with the two hand-written versions:

* **Each message is one call.** `cmd_hdr.read_axi4_stream<WORD_BW>(...)`
  replaces `poly32.cpp`'s six `read_word` calls and their `range()`s, and
  it works at either width. `cmd_hdr.tx_id` and `cmd_hdr.coeffs` are
  ordinary struct fields.
* **`pf` generalizes the sample loop.** At `WORD_BW = 32`, `pf` is 1 and
  this is `poly32.cpp`'s loop. At 64, `pf` is 2 and it is `poly64.cpp`'s.
  The inner loop over the lane is marked `UNROLL`, so HLS builds `pf`
  copies of the Horner datapath. That is the unrolling `poly64.cpp` did by
  hand.
* **It recovers from a framing error.** If a message never ended with
  TLAST, the kernel reads and discards words up to the next TLAST, so the
  next command starts aligned. It also reports `WRONG_NSAMP` if the count
  comes out wrong.

The header `poly.hpp` fixes the word width, for all three kernels:

~~~cpp
#ifndef WORD_BW
#define WORD_BW 32
#endif
static_assert(WORD_BW == 32 || WORD_BW == 64, "WORD_BW must be 32 or 64");

using axis_word_t = streamutils::axi4s_word<WORD_BW>;
~~~

The build passes `-DWORD_BW=32` or `-DWORD_BW=64` to both the kernel and
the testbench. Changing the width of the general kernel is just that
flag.

## In the waveflow guide

* [Data schemas](https://sdrangan.github.io/waveflow/docs/guide/schema/):
  the overview.
* [Data lists](https://sdrangan.github.io/waveflow/docs/guide/schema/python/datalists.html)
  and [data arrays](https://sdrangan.github.io/waveflow/docs/guide/schema/python/dataarrays.html):
  defining messages like `PolyCmdHdr` and arrays like `CoeffArray` in
  Python.
* [Code generation](https://sdrangan.github.io/waveflow/docs/guide/schema/hls/codegen.html):
  generating the Vitis HLS headers from the schemas, as `gen_include` does.
* [Serialization](https://sdrangan.github.io/waveflow/docs/guide/schema/hls/serialization.html):
  what the generated `read_*` and `write_*` methods do, in Vitis HLS and
  in Python.
* [Array serialization](https://sdrangan.github.io/waveflow/docs/guide/vectorization/hls/arrayutils.html):
  the array routines, including the lane loop the general kernel uses.
* [Test data files](https://sdrangan.github.io/waveflow/docs/guide/schema/hls/tbutils.html):
  passing messages between Python and a Vitis testbench through files, as
  this demo's testbench does.

---

Go to [C Simulation](./poly_csim.md)
