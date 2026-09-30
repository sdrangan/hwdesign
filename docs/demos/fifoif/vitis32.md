---
title: Writing the Vitis Kernel
parent: Command-Response FIFO Interface
nav_order: 4
has_children: false
---

# Writing the Vitis Kernel

We start with the simplest case: a kernel for a **32-bit stream**, with
`WORD_BW = 32`. Every message is unpacked and packed by hand, word by
word, and every TLAST is checked by hand. Nothing is hidden. The code is
in `poly32.cpp`.

## The messages in 32-bit words

With 32-bit stream words, every field of every message, and every sample,
gets a word of its own:

~~~text
PolyCmdHdr, 6 words:
    word 0:  tx_id       in bits 15:0
    word 1:  coeffs[0]   all 32 bits: a float
    word 2:  coeffs[1]
    word 3:  coeffs[2]
    word 4:  coeffs[3]
    word 5:  nsamp       in bits 15:0, with TLAST

samples, 1 word each:     x[i], all 32 bits: a float; TLAST on the last

PolyRespHdr, 1 word:      tx_id in bits 15:0, with TLAST
PolyRespFtr, 1 word:      nsamp_read in bits 15:0, error in bits 18:16, with TLAST
~~~

`tx_id`, `nsamp` and `nsamp_read` are 16 bits, so they use the low half of
their word and leave the rest zero. Each coefficient and each sample is a
32-bit float, so it fills a word exactly.

## Reading and writing one word

A word on an AXI4-Stream port is an `ap_axis` struct, which `poly.hpp`
calls `axis_word_t`. It has the data, `.data`, and the TLAST bit, `.last`,
along with TKEEP and TSTRB, which mark which bytes of the word are valid.
Two small helpers read and write one word:

~~~cpp
// Read one word from the stream.  Returns its data; `last` is its TLAST.
static ap_uint<32> read_word(hls::stream<axis_word_t>& s, bool& last) {
    axis_word_t w = s.read();
    last = w.last;
    return w.data;
}

// Write one word to the stream, with TLAST set to `last`.  TKEEP and TSTRB
// mark every byte of the word as valid.
static void write_word(hls::stream<axis_word_t>& s, ap_uint<32> data, bool last) {
    axis_word_t w;
    w.data = data;
    w.last = last;
    w.keep = -1;
    w.strb = -1;
    s.write(w);
}
~~~

## Unpacking the command header

~~~cpp
    // ----- The command header: 6 words -----
    // TLAST must be on the sixth word and on no other.
    ap_uint<32> w = read_word(in_stream, last);
    ap_uint<16> tx_id = w.range(15, 0);
    bool tlast_early = last;

    float coeffs[4];
    for (int k = 0; k < 4; k++) {
        w = read_word(in_stream, last);
        coeffs[k] = streamutils::uint_to_float(w);   // the word's 32 bits ARE the float
        tlast_early = tlast_early || last;
    }

    w = read_word(in_stream, last);
    ap_uint<16> nsamp = w.range(15, 0);
    if (tlast_early) {
        error = PolyError::TLAST_EARLY_CMD_HDR;
    } else if (!last) {
        error = PolyError::NO_TLAST_CMD_HDR;
    }
~~~

The code follows the layout above, one word at a time:

* **`w.range(15, 0)`** picks bits 15 down to 0 out of the word. That is
  all that "unpacking a field" means.
* **`streamutils::uint_to_float(w)`** does not *convert* a number to a
  float. It *reinterprets* the 32 bits. The word already holds the
  float's IEEE-754 bit pattern, and this tells the compiler to treat those
  bits as a float. In hardware it costs nothing, since it is just wires.
* **TLAST is checked by hand.** It must be set on the sixth word and on no
  other. The kernel records which way it went wrong, if it did, and the
  footer will report it.

Sending the response header is the same operation in reverse: start from a
zero word, put `tx_id` in its bits, and write it with TLAST set:

~~~cpp
    // ----- The response header: 1 word -----
    ap_uint<32> resp_hdr = 0;
    resp_hdr.range(15, 0) = tx_id;
    write_word(out_stream, resp_hdr, true);
~~~

## Processing the samples, one at a time

The sample loop is the whole accelerator. Each iteration reads one word,
reinterprets it as a float, evaluates the cubic, and writes the result
back:

~~~cpp
    // ----- The samples: one per word -----
    // Skipped if the header was malformed, since nsamp cannot be trusted.
    int nsamp_read = 0;
    if (error == PolyError::NO_ERROR) {
        for (int i = 0; i < nsamp; i++) {
#pragma HLS PIPELINE II=1
            float x = streamutils::uint_to_float(read_word(in_stream, last));
            float y = eval_poly_horner(coeffs, x);

            // TLAST goes on the last sample, in and out.
            const bool last_sample = (i == nsamp - 1);
            write_word(out_stream, streamutils::float_to_uint(y), last_sample);
            nsamp_read++;

            if (last && !last_sample) {
                error = PolyError::TLAST_EARLY_SAMP_IN;
            } else if (!last && last_sample) {
                error = PolyError::NO_TLAST_SAMP_IN;
            }
        }
    }
~~~

* **`PIPELINE II=1`** starts a new iteration, and so a new sample, every
  clock. Each sample takes many cycles to get through the arithmetic, but
  a new one starts every cycle.
* **`float_to_uint(y)`** is the reverse reinterpretation: the float's bits
  become the word written to the stream.
* **TLAST** is set on the output word for the last sample, and checked on
  the input word for the last sample.

The polynomial is evaluated by **Horner's rule**, three multiply-adds from
the highest coefficient down:

~~~cpp
static float eval_poly_horner(const float coeff[4], float x) {
#pragma HLS INLINE
    float y = coeff[3];
    y = y * x + coeff[2];
    y = y * x + coeff[1];
    y = y * x + coeff[0];
    return y;
}
~~~

## The footer

~~~cpp
    // ----- The response footer: 1 word -----
    ap_uint<32> resp_ftr = 0;
    resp_ftr.range(15, 0) = nsamp_read;
    resp_ftr.range(18, 16) = static_cast<unsigned int>(error);
    write_word(out_stream, resp_ftr, true);
~~~

Two fields share one word here: `nsamp_read` in bits 15:0, and the 3-bit
error code in bits 18:16.

## The function itself

The pieces above make up the body of

~~~cpp
void poly(hls::stream<axis_word_t>& in_stream, hls::stream<axis_word_t>& out_stream) {
#pragma HLS INTERFACE axis port=in_stream
#pragma HLS INTERFACE axis port=out_stream
#pragma HLS INTERFACE ap_ctrl_none port=return
    ...
}
~~~

Like the averaging filter, the kernel has **no start or done**
(`ap_ctrl_none`). When the function finishes one transaction, the
hardware simply runs it again, and it waits on `in_stream` for the next
command header. One call is one transaction.

This version **reports** a misplaced TLAST but does not **recover** from
one. If a message is cut short, the next words belong to the next
message, and the kernel will misread them. Recovering is one of the
things the [general version](./vitis_general.md) adds.

To build and test this kernel, pass `--kernel poly32` to the build, as
described in [C Simulation](./poly_csim.md#choosing-the-kernel).

---

Go to [Using a Wider Bitwidth](./vitis64.md)
