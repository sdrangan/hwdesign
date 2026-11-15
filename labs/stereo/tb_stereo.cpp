// Testbench for the stereo lab: one file for both kernels, stereo_base.cpp and
// stereo.cpp, in C simulation and RTL co-simulation alike.
//
// It does three things:
//
//   1. reads the left and right images your golden model wrote,
//      vectors/left.txt and vectors/right.txt: IMG_H rows of IMG_W pixel values each
//   2. streams them into stereo() as IMG_H*IMG_W words -- left pixel in bits 7:0,
//      right pixel in bits 15:8, raster order -- and reads IMG_H*IMG_W disparities back
//   3. writes the disparities to vectors/disp_<tag>.txt, in the same layout
//
// It does not decide whether the disparities are right: the build compares
// them with your model's.  It returns non-zero only when it could not do its
// job at all -- a missing input file, a short output stream -- because a
// non-zero return makes Vitis discard the output that says what was wrong.
//
// <tag> is the one argument the build passes: base_csim, csim or cosim.  The
// paths are found from this file's own location, because Vitis runs the
// testbench from deep inside the project, and from a different place for
// co-simulation than for C simulation.
//
// You do not need to edit this file.

#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "stereo.h"

static std::string source_dir() {
    const std::string path = __FILE__;
    const size_t pos = path.find_last_of("/\\");
    return (pos == std::string::npos) ? "." : path.substr(0, pos);
}

static bool read_image(const std::string &path, std::vector<int> &img) {
    std::ifstream f(path.c_str());
    if (!f) {
        std::cerr << "tb_stereo: cannot open " << path << "\n";
        return false;
    }
    img.assign(IMG_H * IMG_W, 0);
    for (int k = 0; k < IMG_H * IMG_W; k++) {
        if (!(f >> img[k])) {
            std::cerr << "tb_stereo: " << path << " has " << k << " pixels; expected "
                      << IMG_H * IMG_W << " (" << IMG_H << " rows of " << IMG_W << ")\n";
            return false;
        }
    }
    return true;
}

int main(int argc, char **argv) {
    const std::string tag = (argc > 1) ? argv[1] : "csim";
    const std::string dir = source_dir() + "/vectors/";

    std::vector<int> left, right;
    if (!read_image(dir + "left.txt", left) || !read_image(dir + "right.txt", right)) {
        return 1;
    }

    hls::stream<in_word_t> tb_pix("tb_pix");
    hls::stream<out_word_t> tb_disp("tb_disp");
    for (int k = 0; k < IMG_H * IMG_W; k++) {
        in_word_t w;
        w.data = (ap_uint<16>(right[k] & 0xff) << 8) | ap_uint<16>(left[k] & 0xff);
        w.keep = -1;
        w.strb = -1;
        w.last = (k == IMG_H * IMG_W - 1);
        tb_pix.write(w);
    }

    stereo(tb_pix, tb_disp);

    const std::string path = dir + "disp_" + tag + ".txt";
    std::ofstream f(path.c_str());
    if (!f) {
        std::cerr << "tb_stereo: cannot write " << path << "\n";
        return 1;
    }
    int nlast = 0;
    for (int y = 0; y < IMG_H; y++) {
        for (int x = 0; x < IMG_W; x++) {
            if (tb_disp.empty()) {
                std::cerr << "tb_stereo: the kernel wrote only " << y * IMG_W + x << " of "
                          << IMG_H * IMG_W << " disparities\n";
                return 1;
            }
            out_word_t w = tb_disp.read();
            nlast += w.last ? 1 : 0;
            f << int(w.data) << (x == IMG_W - 1 ? "\n" : " ");
        }
    }
    if (!tb_disp.empty()) {
        std::cerr << "tb_stereo: the kernel wrote more than " << IMG_H * IMG_W << " disparities\n";
    }
    if (nlast != 1) {
        std::cerr << "tb_stereo: TLAST was set on " << nlast << " words; expected 1, the last\n";
    }
    std::cout << "tb_stereo: wrote " << path << "\n";
    return 0;
}
