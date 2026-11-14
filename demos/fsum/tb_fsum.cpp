// Testbench for the float-sum demo, for C simulation and RTL co-simulation.
//
// It is given a data directory on the command line (`-argv <dir>`):
//
//   <dir>/cases.txt     the N values of x
//   <dir>/results.json  the sum, as a float and as its bit pattern, for the
//                       build to compare against golden.py
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>

#include "fsum.h"

static uint32_t bits(float v) {
    uint32_t u;
    std::memcpy(&u, &v, sizeof(u));
    return u;
}

int main(int argc, char** argv) {
    std::string dir = argc > 1 ? argv[1] : ".";
    static float x[N];
    std::ifstream f((dir + "/cases.txt").c_str());
    for (int i = 0; i < N; i++) {
        if (!(f >> x[i])) x[i] = (float)(i % 16) / 8.0f - 1.0f;   // no file: a fixed ramp
    }

    float s = fsum(x);

    FILE* out = std::fopen((dir + "/results.json").c_str(), "w");
    if (!out) {
        std::printf("cannot write %s/results.json\n", dir.c_str());
        return 1;
    }
    std::fprintf(out, "{\n  \"n\": %d,\n  \"sum\": %.9g,\n  \"sum_bits\": %u\n}\n", N, s,
                 (unsigned)bits(s));
    std::fclose(out);
    std::printf("fsum: %.9g, written to %s/results.json\n", s, dir.c_str());
    return 0;
}
