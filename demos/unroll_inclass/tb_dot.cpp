// Testbench for the in-class exercise, for C simulation and RTL
// co-simulation alike.  It is given a data directory (`-argv <dir>`):
//
//   <dir>/cases.txt     the N values of a, then the N values of b, read in
//   <dir>/results.json  the dot product, written out for the build to compare
//                       against golden.py
#include <cstdio>
#include <fstream>
#include <string>

#include "dot.h"

int main(int argc, char** argv) {
    std::string dir = argc > 1 ? argv[1] : ".";
    short a[N], b[N];
    std::ifstream f((dir + "/cases.txt").c_str());
    for (int i = 0; i < N; i++) {
        int v;
        a[i] = (f >> v) ? (short)v : (short)(i % 16 - 8);     // no file: a fixed ramp
    }
    for (int i = 0; i < N; i++) {
        int v;
        b[i] = (f >> v) ? (short)v : (short)(3 - i % 7);
    }

    int result = dot(a, b);

    FILE* out = std::fopen((dir + "/results.json").c_str(), "w");
    if (!out) {
        std::printf("cannot write %s/results.json\n", dir.c_str());
        return 1;
    }
    std::fprintf(out, "{\n  \"n\": %d,\n  \"dot\": %d\n}\n", N, result);
    std::fclose(out);
    std::printf("dot: %d, written to %s/results.json\n", result, dir.c_str());
    return 0;
}
