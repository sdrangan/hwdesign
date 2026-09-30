#include "poly.hpp"

// The polynomial kernel for a 64-bit stream, with everything written out.
//
// The same kernel as poly32.cpp, for WORD_BW = 64.  Read poly32.cpp first:
// this file changes only what a wider word changes.  A 64-bit word holds
// two 32-bit values, so
//
//   * each stream word carries TWO samples: x[i] in bits 31:0 and x[i+1] in
//     bits 63:32.  The loop reads one word and evaluates two samples, so the
//     kernel handles twice the samples per clock.  When nsamp is odd, the
//     last word holds just one sample, in bits 31:0.
//   * the command header packs two coefficients per word:
//
//       PolyCmdHdr, 4 words:  tx_id | coeffs[0], coeffs[1] | coeffs[2], coeffs[3] | nsamp
//
//     (lower bits first within a word).  PolyRespHdr and PolyRespFtr each
//     still fit in one word, in the same bit positions as before.
//
// These positions are the ones the generated headers use, so this kernel
// talks to the same testbench as poly.cpp.

static_assert(WORD_BW == 64, "poly64.cpp is written for a 64-bit stream: build with --word-bw 64");

// y = c[0] + c[1] x + c[2] x^2 + c[3] x^3, by Horner's rule.
static float eval_poly_horner(const float coeff[4], float x) {
#pragma HLS INLINE
    float y = coeff[3];
    y = y * x + coeff[2];
    y = y * x + coeff[1];
    y = y * x + coeff[0];
    return y;
}

// Read one word from the stream.  Returns its data; `last` is its TLAST.
static ap_uint<64> read_word(hls::stream<axis_word_t>& s, bool& last) {
#pragma HLS INLINE
    axis_word_t w = s.read();
    last = w.last;
    return w.data;
}

// Write one word to the stream, with TLAST set to `last`.
static void write_word(hls::stream<axis_word_t>& s, ap_uint<64> data, bool last) {
#pragma HLS INLINE
    axis_word_t w;
    w.data = data;
    w.last = last;
    w.keep = -1;
    w.strb = -1;
    s.write(w);
}

void poly(hls::stream<axis_word_t>& in_stream, hls::stream<axis_word_t>& out_stream) {
#pragma HLS INTERFACE axis port=in_stream
#pragma HLS INTERFACE axis port=out_stream
#pragma HLS INTERFACE ap_ctrl_none port=return

    bool last;
    PolyError error = PolyError::NO_ERROR;

    // ----- The command header: 4 words -----
    ap_uint<64> w = read_word(in_stream, last);
    ap_uint<16> tx_id = w.range(15, 0);
    bool tlast_early = last;

    float coeffs[4];
    for (int k = 0; k < 4; k += 2) {
        w = read_word(in_stream, last);
        coeffs[k]     = streamutils::uint_to_float(w.range(31, 0));    // lower half
        coeffs[k + 1] = streamutils::uint_to_float(w.range(63, 32));   // upper half
        tlast_early = tlast_early || last;
    }

    w = read_word(in_stream, last);
    ap_uint<16> nsamp = w.range(15, 0);
    if (tlast_early) {
        error = PolyError::TLAST_EARLY_CMD_HDR;
    } else if (!last) {
        error = PolyError::NO_TLAST_CMD_HDR;
    }

    // ----- The response header: 1 word -----
    ap_uint<64> resp_hdr = 0;
    resp_hdr.range(15, 0) = tx_id;
    write_word(out_stream, resp_hdr, true);

    // ----- The samples: two per word -----
    int nsamp_read = 0;
    if (error == PolyError::NO_ERROR) {
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

            if (last && !last_word) {
                error = PolyError::TLAST_EARLY_SAMP_IN;
            } else if (!last && last_word) {
                error = PolyError::NO_TLAST_SAMP_IN;
            }
        }
    }

    // ----- The response footer: 1 word -----
    ap_uint<64> resp_ftr = 0;
    resp_ftr.range(15, 0) = nsamp_read;
    resp_ftr.range(18, 16) = static_cast<unsigned int>(error);
    write_word(out_stream, resp_ftr, true);
}
