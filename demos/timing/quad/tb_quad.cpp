// Testbench for the quad demo.
//
// The same file serves C simulation and RTL co-simulation: Vitis compiles
// it against the C++ kernel for `csim_design`, and against the synthesized
// RTL for `cosim_design`.  In co-simulation each call below becomes one
// ap_start / ap_done handshake on the RTL's ports.
//
// It is given a data directory on the command line (`-argv <dir>`):
//
//   <dir>/cases.txt    test vectors, read in
//   <dir>/results.json outputs, written out, for the build to compare
//                      against the Python model in golden.py

#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "quad.h"

struct TestCase {
    int x, w2, w1, w0;
};

// Used when no cases.txt is available, e.g. when run from the Vitis GUI.
static const TestCase kDefaultCases[] = {
    {10, 5, -7, 4},
    {-4, 5, -7, 4},
    {8, 5, -7, 4},
    {3, 2, 1, 0},
    {-6, -1, 3, 9},
};

// cases.txt is one count on the first line, then that many "x w2 w1 w0" lines.
static std::vector<TestCase> load_cases(const std::string& data_dir) {
    std::vector<TestCase> cases;
    std::ifstream f((data_dir + "/cases.txt").c_str());
    if (f) {
        int n = 0;
        f >> n;
        for (int i = 0; i < n; i++) {
            TestCase c;
            if (!(f >> c.x >> c.w2 >> c.w1 >> c.w0)) break;
            cases.push_back(c);
        }
    }
    if (cases.empty()) {
        std::cout << "No cases.txt in " << data_dir
                  << "; using the built-in test vector." << std::endl;
        const int n = sizeof(kDefaultCases) / sizeof(TestCase);
        cases.assign(kDefaultCases, kDefaultCases + n);
    }
    return cases;
}

static void write_results(const std::string& data_dir,
                          const std::vector<TestCase>& cases,
                          const std::vector<int>& y) {
    const std::string path = data_dir + "/results.json";
    std::ofstream f(path.c_str());
    if (!f) {
        std::cout << "Could not write " << path << std::endl;
        return;
    }
    const size_t n = cases.size();
    f << "{\n  \"n\": " << n << ",\n  \"y\": [";
    for (size_t i = 0; i < n; i++) f << y[i] << (i + 1 < n ? ", " : "");
    f << "]\n}\n";
    std::cout << "Wrote " << path << std::endl;
}

int main(int argc, char** argv) {
    const std::string data_dir = (argc > 1) ? argv[1] : ".";
    const std::vector<TestCase> cases = load_cases(data_dir);

    std::vector<int> y_out(cases.size(), 0);
    bool all_passed = true;

    for (size_t i = 0; i < cases.size(); i++) {
        const TestCase& c = cases[i];
        const int y_exp = c.w2 * c.x * c.x + c.w1 * c.x + c.w0;

        // The call under test: the C++ kernel in C simulation, the RTL in
        // co-simulation.
        const int y = (int)quad(c.x, c.w2, c.w1, c.w0);
        y_out[i] = y;

        std::cout << "Test " << i << ": x=" << c.x << " w2=" << c.w2 << " w1=" << c.w1
                  << " w0=" << c.w0 << " got " << y << ", expected " << y_exp
                  << (y == y_exp ? "  PASS" : "  FAIL") << std::endl;
        if (y != y_exp) all_passed = false;
    }

    write_results(data_dir, cases, y_out);
    std::cout << (all_passed ? "All tests passed." : "Some tests failed.") << std::endl;

    // A non-zero return fails csim_design and cosim_design.
    return all_passed ? 0 : 1;
}
