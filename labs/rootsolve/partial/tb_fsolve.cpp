// Testbench for the rootsolve lab.
//
// The same file serves C simulation and RTL co-simulation: Vitis compiles it
// against fsolve.cpp for `csim_design`, and against the synthesized RTL for
// `cosim_design`.  It does three things:
//
//   1. reads the test vectors your golden model wrote, vectors/tv_python.csv
//   2. calls fsolve() once per vector
//   3. writes what came back to vectors/tv_csim.csv or vectors/tv_cosim.csv
//
// It does not decide whether the answers are right.  That is fsolve_eval.py's
// job, so that the tolerances live in one place and nothing has to be kept
// in step between a C++ file and a Python one.  The testbench returns
// non-zero only when it could not do its job at all -- a missing vector file,
// an output it could not write.  Returning non-zero on a *wrong answer* would
// make Vitis report the whole co-simulation as failed and throw away the
// output file that says which vectors were wrong.
//
// Which output file is written comes from the one argument the build passes
// (`csim_design -argv csim`, `cosim_design -argv cosim`).  Both paths are
// found relative to this file rather than to the working directory, because
// Vitis runs the testbench from deep inside the project -- and a different
// place for co-simulation than for C simulation.

#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "fsolve.h"

// The directory this file is in.  __FILE__ is the path the compiler was
// given, which for Vitis is absolute.
static std::string source_dir() {
    const std::string path = __FILE__;
    const size_t pos = path.find_last_of("/\\");
    return (pos == std::string::npos) ? "." : path.substr(0, pos);
}

// One row of vectors/tv_python.csv.  The first seven fields are fsolve()'s
// inputs, in its argument order; the last three are the golden model's answer.
//
// The model's answer is `x_model`, not `x`, and that is not just for clarity.
// Co-simulation rewrites every call to fsolve() in this file, and a struct
// field with the same name as one of fsolve()'s output arguments makes that
// rewrite fail -- "C/RTL co-simulation file generation failed", with nothing
// else to go on -- while C simulation runs perfectly.  Keep the names apart.
struct Vector {
    float a0, a1, a2, x0, tol;
    int max_iter;
    float step;
    float x_model, fx_model;
    int niter_model;
};

// The column header both output files carry.  The same names as the vector
// file, so fsolve_eval.py can read the kernel's answer from `x`, `fx` and
// `niter` exactly as it reads the model's.
static const char *kHeader = "a0,a1,a2,x0,tol,max_iter,step,x,fx,niter";

// Parse one CSV line into a Vector.  Returns false on a malformed line.
static bool parse_vector(const std::string &line, Vector &v) {
    std::stringstream ss(line);
    std::string f[10];
    for (int k = 0; k < 10; k++) {
        if (!std::getline(ss, f[k], ',')) return false;
    }
    v.a0 = std::stof(f[0]);
    v.a1 = std::stof(f[1]);
    v.a2 = std::stof(f[2]);
    v.x0 = std::stof(f[3]);
    v.tol = std::stof(f[4]);
    v.max_iter = std::stoi(f[5]);
    v.step = std::stof(f[6]);
    v.x_model = std::stof(f[7]);
    v.fx_model = std::stof(f[8]);
    v.niter_model = std::stoi(f[9]);
    return true;
}

static std::vector<Vector> read_vectors(const std::string &path) {
    std::vector<Vector> vectors;
    std::ifstream in(path.c_str());
    if (!in) return vectors;
    std::string line;
    std::getline(in, line);  // the header
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        Vector v;
        if (parse_vector(line, v)) {
            vectors.push_back(v);
        } else {
            std::cout << "Skipping a malformed line: " << line << std::endl;
        }
    }
    return vectors;
}

int main(int argc, char **argv) {
    // Opening the project in the Vitis GUI and pressing Run passes no
    // argument, and should still work: it writes the C-simulation file.
    const std::string mode = (argc > 1) ? argv[1] : "csim";
    const std::string dir = source_dir() + "/vectors";
    const std::string in_path = dir + "/tv_python.csv";
    const std::string out_path = dir + "/tv_" + mode + ".csv";

    const std::vector<Vector> vectors = read_vectors(in_path);
    if (vectors.empty()) {
        std::cout << "No test vectors in " << in_path
                  << " -- run the build's `vectors` step first." << std::endl;
        return 1;
    }

    std::ofstream out(out_path.c_str());
    if (!out) {
        std::cout << "Could not write " << out_path << std::endl;
        return 1;
    }
    out << kHeader << "\n";

    std::cout << "fsolve testbench (" << mode << "): " << vectors.size()
              << " vectors from " << in_path << std::endl;

    for (size_t i = 0; i < vectors.size(); i++) {
        const Vector &v = vectors[i];
        float x = 0.0f, fx = 0.0f;
        int niter = 0;

        // TODO:  Call the kernel with this vector's inputs, then write one row
        // to `out` in the order of kHeader: the seven inputs, then the x, fx
        // and niter the kernel returned.
        //
        //     fsolve(v.a0, ...,  x, fx, niter);
        //
        // Write the floats with `std::setprecision(9)`.  Nine significant
        // digits is what it takes for every float to survive the round trip
        // through text unchanged; the default of six would make an exact
        // match look like a rounding error.

        // A line per vector, for reading while you debug.  This is not the
        // verdict -- fsolve_eval.py is -- but a root that is visibly wrong,
        // or an iteration count of zero, shows up here first.
        std::cout << "  vector " << std::setw(2) << i
                  << ":  x = " << std::setw(12) << std::setprecision(7) << x
                  << " (model " << std::setw(12) << v.x_model << ")"
                  << "   niter = " << std::setw(4) << niter
                  << " (model " << std::setw(4) << v.niter_model << ")" << std::endl;
    }

    out.close();
    std::cout << "Wrote " << out_path << std::endl;
    return 0;
}
