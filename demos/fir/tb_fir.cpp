// Testbench for the FIR demo, for C simulation and RTL co-simulation alike.
//
// It is given a data directory on the command line (`-argv <dir>`):
//
//   <dir>/cases.txt     the test vector: nsamp, then the NTAPS coefficients,
//                       then nsamp samples of x
//   <dir>/results.json  y, written out for the build to compare against the
//                       Python model in golden.py
#include <cstdio>
#include <fstream>
#include <string>

#include "fir.h"

int main(int argc, char** argv) {
    std::string dir = argc > 1 ? argv[1] : ".";
    static short h[NTAPS], x[MAX_NSAMP];
    static int y[MAX_NSAMP];
    int nsamp = 0;

    std::ifstream f((dir + "/cases.txt").c_str());
    bool ok = (bool)(f >> nsamp) && nsamp > 0 && nsamp <= MAX_NSAMP;
    for (int k = 0; ok && k < NTAPS; k++) {
        int v;
        ok = (bool)(f >> v);
        h[k] = (short)v;
    }
    for (int n = 0; ok && n < nsamp; n++) {
        int v;
        ok = (bool)(f >> v);
        x[n] = (short)v;
    }
    if (!ok) {                       // no file, e.g. run from the Vitis GUI: an impulse
        nsamp = 32;
        for (int k = 0; k < NTAPS; k++) h[k] = (short)(k + 1);
        for (int n = 0; n < nsamp; n++) x[n] = (short)(n == 0);
    }

    fir(h, x, y, nsamp);

    FILE* out = std::fopen((dir + "/results.json").c_str(), "w");
    if (!out) {
        std::printf("cannot write %s/results.json\n", dir.c_str());
        return 1;
    }
    std::fprintf(out, "{\n  \"nsamp\": %d,\n  \"y\": [", nsamp);
    for (int n = 0; n < nsamp; n++) std::fprintf(out, "%s%d", n ? ", " : "", y[n]);
    std::fprintf(out, "]\n}\n");
    std::fclose(out);
    std::printf("fir: %d outputs written to %s/results.json\n", nsamp, dir.c_str());
    return 0;
}
