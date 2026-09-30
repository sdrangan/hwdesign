// Testbench for the avgfilt demo.
//
// Written by hand -- nothing here is generated.  It is the same testbench
// for C simulation and for RTL co-simulation: Vitis compiles it against the
// C++ kernel for `csim_design`, and against the synthesized RTL for
// `cosim_design`.
//
// It takes two paths on the command line (run.tcl passes them through
// `-argv`):
//
//   argv[1]  the vectors to read:  vectors/tv_python.csv, from the golden model
//   argv[2]  the file to write:    vectors/tv_csim.csv or vectors/tv_cosim.csv
//
// Both files have the same columns, `n,x,y`.  The testbench reads only `x`
// from the first -- it recomputes the expected `y` itself -- and writes the
// `y` the kernel returned to the second.  That file is what lets the build
// compare the kernel against the Python model, which a PASS on the console
// cannot do.  The paths are absolute because co-simulation runs this
// program from deep inside the solution directory, not from here.

#include <cmath>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "avgfilt.h"

// Used when no vector file is given -- opening this component in the Vitis
// GUI and pressing Run passes no -argv, and should still do something.
static const float kDefaultX[] = {0.0f, 1.0f, 2.0f, -1.0f, 3.0f, 4.0f};

// Reads the `x` column of an `n,x,y` CSV.  The header line is skipped.
static std::vector<float> read_x(const std::string &path) {
    std::vector<float> x;
    std::ifstream in(path.c_str());
    if (!in) return x;
    std::string line;
    std::getline(in, line);  // header
    while (std::getline(in, line)) {
        int n;
        float xi;
        if (std::sscanf(line.c_str(), "%d,%f", &n, &xi) == 2) x.push_back(xi);
    }
    return x;
}

int main(int argc, char **argv) {
    const std::string in_path = (argc > 1) ? argv[1] : "";
    const std::string out_path = (argc > 2) ? argv[2] : "";

    std::vector<float> x = read_x(in_path);
    if (x.empty()) {
        std::cout << "No vectors in '" << in_path
                  << "'; using the built-in test vector." << std::endl;
        x.assign(kDefaultX, kDefaultX + sizeof(kDefaultX) / sizeof(float));
    }
    const size_t nsamp = x.size();

    // Load the whole input stream, then call the kernel once.  In C
    // simulation the kernel's loop exits when in_stream runs dry; in
    // co-simulation the same call drives the RTL's AXI4-Stream ports.
    hls::stream<float> in_stream("in_stream");
    hls::stream<float> out_stream("out_stream");
    for (size_t i = 0; i < nsamp; i++) in_stream.write(x[i]);

    avgfilt(in_stream, out_stream);

    // Expected output, computed here in plain C++ in the same order as the
    // kernel, so that a correct kernel matches it bit for bit.
    float xsq0 = 0.0f, xsq1 = 0.0f;
    const float inv_win_size = 1.0f / static_cast<float>(win_size);
    const float tol = 1e-5f;

    std::vector<float> y;
    int nfail = 0;
    for (size_t i = 0; i < nsamp; i++) {
        const float xsq = x[i] * x[i];
        const float y_exp = (xsq + xsq0 + xsq1) * inv_win_size;
        xsq1 = xsq0;
        xsq0 = xsq;

        if (out_stream.empty()) {
            std::cout << "Missing output at sample " << i << std::endl;
            nfail++;
            break;
        }
        const float yi = out_stream.read();
        y.push_back(yi);
        if (std::fabs(yi - y_exp) > tol * (1.0f + std::fabs(y_exp))) {
            if (nfail < 10) {
                std::cout << "y[" << i << "] = " << yi << ", expected " << y_exp
                          << "  FAIL" << std::endl;
            }
            nfail++;
        }
    }
    if (!out_stream.empty()) {
        std::cout << "Unexpected extra outputs in out_stream" << std::endl;
        nfail++;
    }

    if (!out_path.empty()) {
        std::FILE *f = std::fopen(out_path.c_str(), "w");
        if (!f) {
            std::cout << "Could not write " << out_path << std::endl;
            return 1;
        }
        std::fprintf(f, "n,x,y\n");
        // %.9g round-trips a float32 exactly, so the comparison sees the
        // kernel's bits rather than a rounded copy of them.
        for (size_t i = 0; i < y.size(); i++) {
            std::fprintf(f, "%d,%.9g,%.9g\n", static_cast<int>(i), x[i], y[i]);
        }
        std::fclose(f);
        std::cout << "Wrote " << y.size() << " samples to " << out_path << std::endl;
    }

    if (nfail == 0) {
        std::cout << "tb_avgfilt PASSED (" << nsamp << " samples)" << std::endl;
        return 0;
    }
    std::cout << "tb_avgfilt FAILED (" << nfail << " of " << nsamp << " samples)"
              << std::endl;
    // A non-zero return fails csim_design and cosim_design.
    return 1;
}
