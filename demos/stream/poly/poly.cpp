#include "poly.hpp"

// A streaming polynomial with an in-band command protocol.
//
// Each call handles one transaction:
//
//   in_stream:   PolyCmdHdr         |  x[0] ... x[nsamp-1]
//   out_stream:  PolyRespHdr  |  y[0] ... y[nsamp-1]  |  PolyRespFtr
//
// where every `|` is a TLAST.  The command header carries the polynomial's
// coefficients and the number of samples; the kernel answers with a header
// echoing the transaction ID, evaluates the cubic on each sample as it
// streams through, and finishes with a footer saying how many samples it
// read and whether anything went wrong.
//
// All of the packing -- which bits of which stream word hold tx_id, or the
// coefficients, or two float samples in one 64-bit word -- is done by the
// headers generated from poly_schema.py.  Nothing here depends on WORD_BW
// except the number of samples handled per word, pf.
//
// There is no start or done (ap_ctrl_none): in hardware the function body
// simply runs again as soon as it finishes, ready for the next command.

// y = c[0] + c[1] x + c[2] x^2 + c[3] x^3, by Horner's rule.  poly_golden.py
// computes in the same order, so a correct kernel matches it bit for bit.
static float eval_poly_horner(const float coeff[4], float x) {
#pragma HLS INLINE
    float y = coeff[3];
    y = y * x + coeff[2];
    y = y * x + coeff[1];
    y = y * x + coeff[0];
    return y;
}

void poly(hls::stream<axis_word_t>& in_stream, hls::stream<axis_word_t>& out_stream) {
#pragma HLS INTERFACE axis port=in_stream
#pragma HLS INTERFACE axis port=out_stream
#pragma HLS INTERFACE ap_ctrl_none port=return

    // ----- The command header -----
    // read_axi4_stream also reports where TLAST fell: at the end of the
    // header (right), before it, or not at all.
    PolyCmdHdr cmd_hdr;
    streamutils::tlast_status cmd_hdr_tlast = streamutils::tlast_status::no_tlast;
    cmd_hdr.read_axi4_stream<WORD_BW>(in_stream, cmd_hdr_tlast);

    // ----- The response header -----
    // Sent straight away, so the host can match the output to its command.
    PolyRespHdr resp_hdr;
    resp_hdr.tx_id = cmd_hdr.tx_id;
    resp_hdr.write_axi4_stream<WORD_BW>(out_stream, true);

    // ----- The samples -----
    // pf samples per stream word: 1 for a 32-bit word, 2 for a 64-bit one.
    // Each iteration reads one word's worth, evaluates them in parallel, and
    // writes one word's worth back.
    static const int pf = float32_array_utils::pf<WORD_BW>();
    float x_lane[pf];
    float y_lane[pf];
#pragma HLS ARRAY_PARTITION variable=x_lane complete dim=1
#pragma HLS ARRAY_PARTITION variable=y_lane complete dim=1

    int nsamp_read = 0;
    streamutils::tlast_status samp_in_tlast = streamutils::tlast_status::no_tlast;
    bool read_samples = (cmd_hdr_tlast == streamutils::tlast_status::tlast_at_end)
                        && (cmd_hdr.nsamp > 0);
    for (int i = 0; i < cmd_hdr.nsamp && read_samples; i += pf) {
#pragma HLS PIPELINE II=1
        const int nrem = cmd_hdr.nsamp - i;
        const int lane_count = (nrem < pf) ? nrem : pf;
        streamutils::tlast_status lane_tlast = streamutils::tlast_status::no_tlast;
        float32_array_utils::read_axi4_stream_lane<WORD_BW>(in_stream, x_lane, nrem, lane_tlast);

        for (int k = 0; k < pf; ++k) {
#pragma HLS UNROLL
            if (k < lane_count) {
                y_lane[k] = eval_poly_horner(cmd_hdr.coeffs.data, x_lane[k]);
            }
        }

        // TLAST on the output goes on the word holding the last sample.
        const bool out_tlast = (nrem <= pf);
        float32_array_utils::write_axi4_stream_lane<WORD_BW>(y_lane, out_stream, out_tlast, nrem);

        nsamp_read += lane_count;
        if (lane_tlast == streamutils::tlast_status::tlast_at_end) {
            // TLAST is right only on the word holding the last sample.
            samp_in_tlast = out_tlast ? streamutils::tlast_status::tlast_at_end
                                      : streamutils::tlast_status::tlast_early;
            read_samples = false;
        }
    }

    // ----- The response footer -----
    // Classify what went wrong, if anything, once the loop is done.
    PolyRespFtr resp_ftr;
    resp_ftr.nsamp_read = nsamp_read;
    resp_ftr.error = PolyError::NO_ERROR;
    bool need_flush = false;
    if (cmd_hdr_tlast == streamutils::tlast_status::tlast_early) {
        resp_ftr.error = PolyError::TLAST_EARLY_CMD_HDR;
    } else if (cmd_hdr_tlast == streamutils::tlast_status::no_tlast) {
        resp_ftr.error = PolyError::NO_TLAST_CMD_HDR;
        need_flush = true;
    } else if (cmd_hdr.nsamp == 0) {
        resp_ftr.nsamp_read = 0;
    } else if (samp_in_tlast == streamutils::tlast_status::tlast_early) {
        resp_ftr.error = PolyError::TLAST_EARLY_SAMP_IN;
    } else if (samp_in_tlast == streamutils::tlast_status::no_tlast) {
        resp_ftr.error = PolyError::NO_TLAST_SAMP_IN;
        need_flush = true;
    } else if (nsamp_read != cmd_hdr.nsamp) {
        resp_ftr.error = PolyError::WRONG_NSAMP;
    }

    // A message that never ended with TLAST leaves the rest of it on the
    // input.  Drain to the next TLAST, so the next command starts aligned.
    if (need_flush) {
        streamutils::flush_axi4_stream_to_tlast<WORD_BW>(in_stream);
    }

    resp_ftr.write_axi4_stream<WORD_BW>(out_stream, true);
}
