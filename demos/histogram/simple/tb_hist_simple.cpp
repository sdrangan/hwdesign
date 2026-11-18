// tb_hist_simple.cpp -- the C simulation testbench for hist_simple.
//
//   tb_hist_simple <in_dir> <out_dir>
//
// Reads <in_dir>/mem_in.bin (the memory image) and <in_dir>/cmds.bin (every job's HistCmd
// words), written by hist_golden.py.  Pushes all the commands, calls the kernel once -- its
// tasks then run as threads -- and reads one response per job.  Writes the memory and the
// response words to <out_dir>; hist_build.py checks them against the NumPy golden.
#include <cstdio>
#include <cstdint>
#include <string>
#include <vector>
#include "hist_simple.h"

static std::vector<uint32_t> read_raw(const std::string& path) {
    std::vector<uint32_t> v;
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) { std::fprintf(stderr, "cannot open %s\n", path.c_str()); return v; }
    uint32_t w;
    while (std::fread(&w, 4, 1, f) == 1) v.push_back(w);
    std::fclose(f);
    return v;
}

static void write_raw(const std::string& path, const std::vector<uint32_t>& v) {
    FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) { std::fprintf(stderr, "cannot write %s\n", path.c_str()); return; }
    std::fwrite(v.data(), 4, v.size(), f);
    std::fclose(f);
}

int main(int argc, char** argv) {
    const std::string in_dir = argc > 1 ? argv[1] : "vectors";
    const std::string out_dir = argc > 2 ? argv[2] : ".";
    std::vector<uint32_t> mem_in = read_raw(in_dir + "/mem_in.bin");
    std::vector<uint32_t> cmds = read_raw(in_dir + "/cmds.bin");
    const int cmd_words = HistCmd::nwords<MEM_DW>();
    const int resp_words = HistResp::nwords<MEM_DW>();
    if (mem_in.empty() || cmds.empty() || cmds.size() % cmd_words) {
        std::fprintf(stderr, "bad vectors in %s\n", in_dir.c_str());
        return 1;
    }
    const int njobs = (int)(cmds.size() / cmd_words);

    std::vector<word_t> mem(mem_in.begin(), mem_in.end());
    hls::stream<word_t> s_cmd, s_done;
    for (uint32_t w : cmds) s_cmd.write(w);
    hist_simple(s_cmd, mem.data(), mem.data(), s_done);

    std::vector<uint32_t> resp;
    for (int i = 0; i < njobs * resp_words; i++) resp.push_back((uint32_t)s_done.read());
    for (int k = 0; k < njobs; k++)
        std::printf("response %d: job_id %u, status %u\n", k, resp[k * resp_words],
                    resp[k * resp_words + 1]);

    std::vector<uint32_t> mem_out(mem.begin(), mem.end());
    write_raw(out_dir + "/mem_out.bin", mem_out);
    write_raw(out_dir + "/resp.bin", resp);
    std::printf("csim: %d jobs, %d responses\n", njobs, (int)(resp.size() / resp_words));
    return 0;
}
