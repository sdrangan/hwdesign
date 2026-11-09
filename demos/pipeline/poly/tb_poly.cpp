// Testbench for the pipelining demo.
//
// The same file serves C simulation and RTL co-simulation: Vitis compiles it
// against the C++ kernel for `csim_design`, and against the synthesized RTL
// for `cosim_design`.  In co-simulation the call to poly() becomes one
// ap_start / ap_done handshake, with x, y and coeffs as memories the RTL
// reads and writes through its ap_memory ports.
//
// It is given a data directory on the command line (`-argv <dir>`):
//
//   <dir>/cases.txt     the test vector, read in: nsamp, then the four
//                       coefficients, then nsamp values of x
//   <dir>/results.json  the outputs, written out, for the build to compare
//                       against the Python model in golden.py

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "poly.h"

// The float's bit pattern: what the comparison with Python uses, since two
// FP32 results that print alike are not always the same number.
static uint32_t bits(float v) {
    uint32_t u;
    std::memcpy(&u, &v, sizeof(u));
    return u;
}

// The reference, in the testbench's own words: Horner's method in the same
// order as the kernel, so an FP32 kernel has to match it bit for bit.
static float horner_ref(const float c[NCOEFF], float x) {
    return ((c[3] * x + c[2]) * x + c[1]) * x + c[0];
}

// Used when no cases.txt is available, e.g. when run from the Vitis GUI.
static void default_case(int& nsamp, float c[NCOEFF], std::vector<float>& x) {
    const float c0[NCOEFF] = {1.0f, -2.0f, -3.0f, 4.0f};
    std::memcpy(c, c0, sizeof(c0));
    nsamp = 16;
    x.resize(nsamp);
    for (int i = 0; i < nsamp; i++) x[i] = (float)i / nsamp;
}

static bool load_case(const std::string& data_dir, int& nsamp, float c[NCOEFF],
                      std::vector<float>& x) {
    std::ifstream f((data_dir + "/cases.txt").c_str());
    if (!f || !(f >> nsamp) || nsamp < 0 || nsamp > MAX_NSAMP) return false;
    for (int j = 0; j < NCOEFF; j++) {
        if (!(f >> c[j])) return false;
    }
    x.resize(nsamp);
    for (int i = 0; i < nsamp; i++) {
        if (!(f >> x[i])) return false;
    }
    return true;
}

static void write_results(const std::string& data_dir, const float* y, int n) {
    const std::string path = data_dir + "/results.json";
    FILE* f = std::fopen(path.c_str(), "w");
    if (!f) {
        std::cout << "Could not write " << path << std::endl;
        return;
    }
    std::fprintf(f, "{\n  \"n\": %d,\n  \"y\": [", n);
    for (int i = 0; i < n; i++) std::fprintf(f, "%s%.9g", i ? ", " : "", y[i]);
    std::fprintf(f, "],\n  \"y_bits\": [");
    for (int i = 0; i < n; i++) std::fprintf(f, "%s%u", i ? ", " : "", (unsigned)bits(y[i]));
    std::fprintf(f, "]\n}\n");
    std::fclose(f);
    std::cout << "Wrote " << path << std::endl;
}

int main(int argc, char** argv) {
    const std::string data_dir = (argc > 1) ? argv[1] : ".";

    int nsamp = 0;
    float c[NCOEFF];
    std::vector<float> xv;
    if (!load_case(data_dir, nsamp, c, xv)) {
        std::cout << "No usable cases.txt in " << data_dir
                  << "; using the built-in test vector." << std::endl;
        default_case(nsamp, c, xv);
    }

    // The kernel's arrays are MAX_NSAMP long, whatever nsamp is.
    static float x[MAX_NSAMP];
    static float y[MAX_NSAMP];
    for (int i = 0; i < MAX_NSAMP; i++) {
        x[i] = (i < nsamp) ? xv[i] : 0.0f;
        y[i] = 0.0f;
    }

    // The call under test: the C++ kernel in C simulation, the RTL in
    // co-simulation.
    poly(c, x, y, nsamp);

    int nfail = 0;
    for (int i = 0; i < nsamp; i++) {
        const float y_exp = horner_ref(c, x[i]);
        if (bits(y[i]) != bits(y_exp)) {
            if (nfail < 5) {
                std::cout << "Sample " << i << ": x=" << x[i] << " got " << y[i]
                          << ", expected " << y_exp << "  FAIL" << std::endl;
            }
            nfail++;
        }
    }
    std::cout << nsamp << " samples, " << nfail << " mismatches." << std::endl;

    write_results(data_dir, y, nsamp);
    std::cout << (nfail == 0 ? "All tests passed." : "Some tests failed.") << std::endl;

    // A non-zero return fails csim_design and cosim_design.
    return nfail == 0 ? 0 : 1;
}
