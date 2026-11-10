// Testbench for the in-class exercise, for C simulation and RTL
// co-simulation alike.  It is given a data directory (`-argv <dir>`):
//
//   <dir>/cases.txt     the N values of x, read in
//   <dir>/results.json  y as floats and as bit patterns, written out for the
//                       build to compare against golden.py
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>

#include "sqsum.h"

static uint32_t bits(float v) {
    uint32_t u;
    std::memcpy(&u, &v, sizeof(u));
    return u;
}

int main(int argc, char** argv) {
    std::string dir = argc > 1 ? argv[1] : ".";
    float x[N], y[N];
    std::ifstream f((dir + "/cases.txt").c_str());
    for (int i = 0; i < N; i++) {
        if (!(f >> x[i])) x[i] = (float)(i % 16) / 4.0f - 2.0f;   // no file: a fixed ramp
    }

    sqsum(x, y);

    FILE* out = std::fopen((dir + "/results.json").c_str(), "w");
    if (!out) {
        std::printf("cannot write %s/results.json\n", dir.c_str());
        return 1;
    }
    std::fprintf(out, "{\n  \"n\": %d,\n  \"y\": [", N);
    for (int i = 0; i < N; i++) std::fprintf(out, "%s%.9g", i ? ", " : "", y[i]);
    std::fprintf(out, "],\n  \"y_bits\": [");
    for (int i = 0; i < N; i++) std::fprintf(out, "%s%u", i ? ", " : "", (unsigned)bits(y[i]));
    std::fprintf(out, "]\n}\n");
    std::fclose(out);
    std::printf("sqsum: %d outputs written to %s/results.json\n", N, dir.c_str());
    return 0;
}
