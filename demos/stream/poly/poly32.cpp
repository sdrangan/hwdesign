#include "poly.hpp"

// The polynomial kernel for a 32-bit stream, with everything written out.
//
// This is the same kernel as poly.cpp, specialized to WORD_BW = 32 and with
// no help from the generated headers: every message is unpacked and packed
// here, word by word, and every TLAST is checked by hand.  Read this one
// first.  poly64.cpp does the same for a 64-bit stream, and poly.cpp is the
// general version the others lead up to.
//
// One transaction is
//
//   in_stream:   PolyCmdHdr         |  x[0] ... x[nsamp-1]
//   out_stream:  PolyRespHdr  |  y[0] ... y[nsamp-1]  |  PolyRespFtr
//
// where every `|` is a TLAST.  With 32-bit words, each field and each
// sample gets a word of its own:
//
//   PolyCmdHdr, 6 words:   tx_id | coeffs[0] | coeffs[1] | coeffs[2] | coeffs[3] | nsamp
//   PolyRespHdr, 1 word:   tx_id
//   PolyRespFtr, 1 word:   nsamp_read in bits 15:0, error in bits 18:16
//
// These positions are the ones the generated headers use, so this kernel
// talks to the same testbench as poly.cpp.

static_assert(WORD_BW == 32, "poly32.cpp is written for a 32-bit stream: build with --word-bw 32");

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
static ap_uint<32> read_word(hls::stream<axis_word_t>& s, bool& last) {
#pragma HLS INLINE
    axis_word_t w = s.read();
    last = w.last;
    return w.data;
}

// Write one word to the stream, with TLAST set to `last`.  TKEEP and TSTRB
// mark every byte of the word as valid.
static void write_word(hls::stream<axis_word_t>& s, ap_uint<32> data, bool last) {
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

    // ----- The response header: 1 word -----
    ap_uint<32> resp_hdr = 0;
    resp_hdr.range(15, 0) = tx_id;
    write_word(out_stream, resp_hdr, true);

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

    // ----- The response footer: 1 word -----
    // This simple version only reports a misplaced TLAST.  It does not
    // recover from one -- that is what poly.cpp adds.
    ap_uint<32> resp_ftr = 0;
    resp_ftr.range(15, 0) = nsamp_read;
    resp_ftr.range(18, 16) = static_cast<unsigned int>(error);
    write_word(out_stream, resp_ftr, true);
}
