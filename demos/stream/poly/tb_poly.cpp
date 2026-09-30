// Testbench for the poly demo.
//
// Written by hand -- nothing here is generated, though it uses the
// generated headers to pack and unpack messages.  It is the same testbench
// for C simulation and for RTL co-simulation.
//
// It takes two directories on the command line (run.tcl passes them through
// `-argv`):
//
//   argv[1]  the vectors to send, written by poly_golden.py:
//              ntxn.txt, and per transaction k:
//              txn<k>_cmd_hdr.bin, txn<k>_samp_in.bin
//   argv[2]  where to write what came back, per transaction k:
//              txn<k>_resp_hdr.bin, txn<k>_samp_out.bin, txn<k>_resp_ftr.bin
//
// The files are 32-bit words packed by the same schemas the kernel's
// headers are generated from, so they carry no stream word width: the
// generated write_axi4_stream<WORD_BW> packs them into 32- or 64-bit
// stream words here.  The build compares the output files against the
// Python model.  The paths are absolute because co-simulation runs this
// program from deep inside the project directory.

#include <cmath>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

// The testbench-only headers come first.  Each *_tb.h adds file and JSON
// methods to its message struct by including the main header with an extra
// macro defined -- which only works if the main header has not already been
// included, as poly.hpp would.
#include "include/streamutils_tb.h"
#include "include/float32_array_utils_tb.h"
#include "include/poly_cmd_hdr_tb.h"
#include "include/poly_resp_hdr_tb.h"
#include "include/poly_resp_ftr_tb.h"
#include "poly.hpp"

static std::string txn_file(const std::string& dir, int k, const char* what) {
    return dir + "/txn" + std::to_string(k) + "_" + what + ".bin";
}

static int read_ntxn(const std::string& dir) {
    std::ifstream f((dir + "/ntxn.txt").c_str());
    int n = 0;
    if (!(f >> n)) return 0;
    return n;
}

// The expected output, computed here in plain C++ in the kernel's order.
static float horner(const float c[4], float x) {
    float y = c[3];
    y = y * x + c[2];
    y = y * x + c[1];
    y = y * x + c[0];
    return y;
}

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cout << "usage: tb_poly <vector dir> <output dir>  "
                     "-- run it from the build, which passes both." << std::endl;
        return 1;
    }
    const std::string in_dir = argv[1];
    const std::string out_dir = argv[2];

    const int ntxn = read_ntxn(in_dir);
    if (ntxn <= 0) {
        std::cout << "No transactions in " << in_dir << "/ntxn.txt" << std::endl;
        return 1;
    }
    std::cout << "tb_poly: " << ntxn << " transactions, WORD_BW=" << WORD_BW << std::endl;

    hls::stream<axis_word_t> in_stream("in_stream");
    hls::stream<axis_word_t> out_stream("out_stream");
    int nfail = 0;

    for (int k = 0; k < ntxn; k++) {
        // ----- Send one command -----
        PolyCmdHdr cmd_hdr;
        streamutils::read_uint32_file(cmd_hdr, txn_file(in_dir, k, "cmd_hdr").c_str());
        const int nsamp = cmd_hdr.nsamp;
        std::vector<float> x(nsamp), y(nsamp);
        float32_array_utils::read_uint32_file_array(
            x.data(), txn_file(in_dir, k, "samp_in").c_str(), nsamp);

        cmd_hdr.write_axi4_stream<WORD_BW>(in_stream, true);
        float32_array_utils::write_axi4_stream<WORD_BW>(in_stream, x.data(), true, nsamp);

        // One call, one transaction.
        poly(in_stream, out_stream);

        // ----- Receive the response -----
        PolyRespHdr resp_hdr;
        streamutils::tlast_status hdr_tlast = streamutils::tlast_status::no_tlast;
        resp_hdr.read_axi4_stream<WORD_BW>(out_stream, hdr_tlast);

        streamutils::tlast_status samp_tlast = streamutils::tlast_status::no_tlast;
        float32_array_utils::read_axi4_stream<WORD_BW>(out_stream, y.data(), samp_tlast, nsamp);

        PolyRespFtr resp_ftr;
        streamutils::tlast_status ftr_tlast = streamutils::tlast_status::no_tlast;
        resp_ftr.read_axi4_stream<WORD_BW>(out_stream, ftr_tlast);

        streamutils::write_uint32_file(resp_hdr, txn_file(out_dir, k, "resp_hdr").c_str());
        float32_array_utils::write_uint32_file_array(
            y.data(), txn_file(out_dir, k, "samp_out").c_str(), nsamp);
        streamutils::write_uint32_file(resp_ftr, txn_file(out_dir, k, "resp_ftr").c_str());

        // ----- Check it -----
        int nbad = 0;
        const float tol = 1e-5f;
        for (int i = 0; i < nsamp; i++) {
            const float y_exp = horner(cmd_hdr.coeffs.data, x[i]);
            if (std::fabs(y[i] - y_exp) > tol * (1.0f + std::fabs(y_exp))) {
                if (nbad < 5) {
                    std::cout << "  txn " << k << " y[" << i << "] = " << y[i]
                              << ", expected " << y_exp << "  FAIL" << std::endl;
                }
                nbad++;
            }
        }
        const bool framing_ok = hdr_tlast == streamutils::tlast_status::tlast_at_end
                                && samp_tlast == streamutils::tlast_status::tlast_at_end
                                && ftr_tlast == streamutils::tlast_status::tlast_at_end;
        const bool ok = nbad == 0 && framing_ok
                        && resp_hdr.tx_id == cmd_hdr.tx_id
                        && resp_ftr.error == PolyError::NO_ERROR
                        && (int)resp_ftr.nsamp_read == nsamp;

        std::cout << "txn " << k << ": tx_id=0x" << std::hex << (int)cmd_hdr.tx_id
                  << " echoed 0x" << (int)resp_hdr.tx_id << std::dec
                  << ", nsamp=" << nsamp << " nsamp_read=" << (int)resp_ftr.nsamp_read
                  << ", error=" << (int)resp_ftr.error
                  << (framing_ok ? "" : ", TLAST misplaced")
                  << (ok ? "  PASS" : "  FAIL") << std::endl;
        if (!ok) nfail++;
    }

    if (!out_stream.empty()) {
        std::cout << "Unexpected extra words on out_stream" << std::endl;
        nfail++;
    }

    if (nfail == 0) {
        std::cout << "tb_poly PASSED (" << ntxn << " transactions)" << std::endl;
        return 0;
    }
    std::cout << "tb_poly FAILED (" << nfail << " of " << ntxn << " transactions)" << std::endl;
    // A non-zero return fails csim_design and cosim_design.
    return 1;
}
