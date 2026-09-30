---
title: Using a Wider Bitwidth
parent: Command-Response FIFO Interface
nav_order: 5
has_children: false
---

# Using a Wider Bitwidth

The 32-bit kernel moves one sample per clock, because one sample fills one
stream word. A wider stream moves more: a 64-bit word holds **two** 32-bit
values. This page takes the 32-bit kernel to `WORD_BW = 64`. The code is
in `poly64.cpp`, and it changes only what the wider word changes.

## How the packing changes

Two 32-bit values share each 64-bit word, the first in the lower half:

~~~text
PolyCmdHdr, 4 words:
    word 0:  tx_id                   in bits 15:0
    word 1:  coeffs[0] | coeffs[1]   bits 31:0 | bits 63:32
    word 2:  coeffs[2] | coeffs[3]   bits 31:0 | bits 63:32
    word 3:  nsamp                   in bits 15:0, with TLAST

samples, 2 per word:      x[i] in bits 31:0, x[i+1] in bits 63:32
                          TLAST on the word holding the last sample

PolyRespHdr, 1 word:      tx_id in bits 15:0, as before
PolyRespFtr, 1 word:      nsamp_read in bits 15:0, error in bits 18:16, as before
~~~

The command header shrinks from 6 words to 4, since the four coefficients
now pack two to a word. The response header and footer still fit in a
single word, in the same bit positions.

When `nsamp` is **odd**, the samples do not fill the last word. It holds
just one sample, in the lower half, and the upper half is unused.

## Unpacking two values per word

The coefficients now come two per word, from the two halves:

~~~cpp
    float coeffs[4];
    for (int k = 0; k < 4; k += 2) {
        w = read_word(in_stream, last);
        coeffs[k]     = streamutils::uint_to_float(w.range(31, 0));    // lower half
        coeffs[k + 1] = streamutils::uint_to_float(w.range(63, 32));   // upper half
        tlast_early = tlast_early || last;
    }
~~~

This is the same `range()` and `uint_to_float` as before. Now each word is
split into two 32-bit slices first. `read_word` and `write_word` are the
same helpers, with `ap_uint<64>` in place of `ap_uint<32>`.

## Processing two samples per iteration

The sample loop reads one word and evaluates **two** samples:

~~~cpp
        for (int i = 0; i < nsamp; i += 2) {
#pragma HLS PIPELINE II=1
            const bool has_second = (i + 1 < nsamp);   // false only for an odd nsamp's last word

            ap_uint<64> xw = read_word(in_stream, last);
            float x0 = streamutils::uint_to_float(xw.range(31, 0));
            float x1 = streamutils::uint_to_float(xw.range(63, 32));

            // Two evaluations per iteration.  HLS builds two copies of the
            // Horner datapath so both happen in the same cycle.
            float y0 = eval_poly_horner(coeffs, x0);
            float y1 = eval_poly_horner(coeffs, x1);

            ap_uint<64> yw = 0;
            yw.range(31, 0) = streamutils::float_to_uint(y0);
            if (has_second) {
                yw.range(63, 32) = streamutils::float_to_uint(y1);
            }

            // TLAST goes on the word holding the last sample.
            const bool last_word = (i + 2 >= nsamp);
            write_word(out_stream, yw, last_word);
            nsamp_read += has_second ? 2 : 1;
            ...
        }
~~~

* **The loop steps by 2**, `i += 2`, and each iteration handles `x[i]` and
  `x[i+1]`.
* **The loop still runs at `II = 1`**, one iteration per clock. But each
  iteration now carries two samples, so the kernel's **throughput
  doubles**, to two samples per clock.
* **There are two calls to `eval_poly_horner`**, and they have to happen
  in the same cycle. So HLS builds **two copies** of the Horner datapath,
  twice the multipliers and adders. Twice the throughput costs twice the
  arithmetic.
* **`has_second`** handles the odd case: the last word of an odd-length
  burst carries only one sample, so only `y0` is packed and `nsamp_read`
  counts one.

Writing out the work for several loop iterations, here two samples, in a
single iteration, so that it all happens in parallel, is called **loop
unrolling**. Here we unrolled by hand. Vitis HLS can also do it for you,
with `#pragma HLS UNROLL`, and we will come back to it in more detail when
we discuss loop optimizations. The general kernel on the
[next page](./vitis_general.md) uses exactly that pragma.

## The rest is unchanged

The response header, the TLAST checks and the footer are the same as in
the 32-bit kernel, only in 64-bit words. `poly64.cpp` checks at compile
time that it is built for the width it was written for:

~~~cpp
static_assert(WORD_BW == 64, "poly64.cpp is written for a 64-bit stream: build with --word-bw 64");
~~~

To build and test this kernel, pass `--kernel poly64` to the build, as
described in [C Simulation](./poly_csim.md#choosing-the-kernel).

---

Go to [Using Waveflow](./vitis_general.md)
