// Testbench for the scalar_fun demo.
//
// This file is written by hand -- nothing here is generated.  It is the
// same testbench for C simulation and for RTL co-simulation: Vitis compiles
// it against the C++ kernel for `csim_design`, and against the synthesized
// RTL for `cosim_design`.
//
// It is given a data directory on the command line (`csim_design -argv
// <dir>`) and uses it for two things:
//
//   <dir>/cases.txt    test vectors, read in
//   <dir>/results.json outputs, written out
//
// The results file is what lets the build compare this run against an
// independent Python model -- and, because C simulation and co-simulation
// are given different directories, it lets the build check them separately.
// Printing PASS/FAIL is not enough on its own: nothing downstream can read
// a console log.

#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "scalar_fun.h"

struct TestCase {
    int x, w, b;
};

// Used when no cases.txt is available -- opening this component in the
// Vitis GUI and pressing Run passes no -argv, and should still work.
static const TestCase kDefaultCases[] = {
    {3, 2, 4},
    {-1, 5, 0},
    {10, -2, 3},
    {0, 1, -5},
    {7, 7, 7},
};

// cases.txt is one count on the first line, then that many "x w b" lines.
static std::vector<TestCase> load_cases(const std::string& data_dir) {
    std::vector<TestCase> cases;
    std::ifstream f((data_dir + "/cases.txt").c_str());
    if (f) {
        int n = 0;
        f >> n;
        for (int i = 0; i < n; i++) {
            TestCase c;
            if (!(f >> c.x >> c.w >> c.b)) break;
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
    f << "{\n";
    f << "  \"n\": " << n << ",\n";
    const char* names[3] = {"x", "w", "b"};
    for (int k = 0; k < 3; k++) {
        f << "  \"" << names[k] << "\": [";
        for (size_t i = 0; i < n; i++) {
            const int v = (k == 0) ? cases[i].x : (k == 1) ? cases[i].w : cases[i].b;
            f << v << (i + 1 < n ? ", " : "");
        }
        f << "],\n";
    }
    f << "  \"y\": [";
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
        const int x = cases[i].x;
        const int w = cases[i].w;
        const int b = cases[i].b;

        // Expected output, computed here in plain C++.
        int y_exp = w * x + b;
        if (y_exp < 0) y_exp = 0;

        // The call under test.  In C simulation this runs the C++ kernel
        // above; in co-simulation it drives the synthesized RTL over the
        // AXI4-Lite register map.
        int y = 0;
        simp_fun(x, w, b, y);
        y_out[i] = y;

        std::cout << "Test " << i
                  << ": x=" << x << " w=" << w << " b=" << b
                  << " got " << y << ", expected " << y_exp;
        if (y != y_exp) {
            std::cout << "  FAIL" << std::endl;
            all_passed = false;
        } else {
            std::cout << "  PASS" << std::endl;
        }
    }

    write_results(data_dir, cases, y_out);

    if (all_passed) {
        std::cout << "All tests passed." << std::endl;
    } else {
        std::cout << "Some tests failed." << std::endl;
    }

    // Vitis reads the return code: a non-zero value fails csim_design and
    // cosim_design.  Returning 0 unconditionally would make every run look
    // like a pass.
    return all_passed ? 0 : 1;
}
