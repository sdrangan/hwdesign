// tb_xsi_histogram_mm.cpp -- the RTL testbench for histogram_mm, run through XSI.
//
// histogram_mm.v puts Waveflow's memory-mapped slave adaptor in front of the stream kernel, so
// the testbench plays a HOST on its AXI4 slave port, s_axi, instead of driving streams:
//
//   HistHost    a software host (Waveflow's xsi_sw.h: threads that block, run as fibers), two
//               threads on one bus master:
//                 writer  sends every job's HistCmd into the command queue (qcmd, 0x0000), one
//                         packet per command, each as soon as there is room -- so several jobs
//                         are queued at once; cmd_gap idle cycles between commands, if set
//                 reader  sleeps on irq_resp, then takes one HistResp (2 words) from the
//                         response queue (qresp, 0x1000); as many times as there are jobs
//   m_axi_gmem0 an AXI4 read slave  } over ONE flat memory, as in the stream testbench
//   m_axi_gmem1 an AXI4 write slave }
//
// The host does not know which job a response belongs to until it reads it: Python matches each
// response to its job by job_id (hist_golden.check(by_id=True)).  Nothing is checked here.
//
// Out, in vectors/: mem_out (the memory), resp (the response words, with the cycle each read
// finished), cmd_sent (one word per command: the cycle its packet's write finished), and on
// stdout every bus operation the host made.
#include <cstdio>
#include <vector>
#include "xsi_bfm.h"
#include "xsi_sw.h"

using namespace wfbfm;

#ifdef _WIN32
static const char* const DESIGN_DLL = "xsim.dir/histogram_mm/xsimk.dll";
#else
static const char* const DESIGN_DLL = "xsim.dir/histogram_mm/xsimk.so";
#endif

// The two views, as histogram_mm.v places them: 4 KB windows, 32-bit words, QDEPTH words each.
static const uint32_t QDEPTH = 64;
static const MmView QCMD  = {"qcmd",  MmKind::QueueIn,  0x0000, 4096, 4, QDEPTH, 0, 0, 0};
static const MmView QRESP = {"qresp", MmKind::QueueOut, 0x1000, 4096, 4, QDEPTH, 0, 0, 0};
static const long POLL = 8;         // only if an endpoint has no interrupt; both have one here
static const uint32_t RESP_WORDS = 2;

class HistHost : public SwHostModel {
public:
    SwIrq irq_cmd, irq_resp;
    QueueWriter qcmd;
    QueueReader qresp;

    HistHost(Dut& d, long njobs, long gap)
        : SwHostModel(d, "s_axi", 4),
          irq_cmd(sched_, d, "irq_cmd"), irq_resp(sched_, d, "irq_resp"),
          qcmd(sched_, bus_, QCMD, POLL, &irq_cmd), qresp(sched_, bus_, QRESP, POLL, &irq_resp),
          njobs_(njobs), gap_(gap) {
        add_pin(&irq_cmd);
        add_pin(&irq_resp);
        traced("qcmd", &qcmd);
        traced("qresp", &qresp);
    }

    void main() override {
        start("writer", [this] { writer(); });
        reader();
    }

    // The words each response read returned, the cycle it finished, and each command's.
    std::vector<uint64_t> resp_words;
    std::vector<long> resp_cycles, cmd_cycles;

private:
    void writer() {
        const auto& cmds = scenario_bursts();           // one burst per HistCmd
        for (size_t k = 0; k < cmds.size(); ++k) {
            if (k > 0 && gap_ > 0) compute(gap_);
            qcmd.write(cmds[k]);                        // waits for room, then [len | 5 words]
            cmd_cycles.push_back(now());
        }
    }
    void reader() {
        for (long k = 0; k < njobs_; ++k) {
            const std::vector<uint64_t> w = qresp.get(RESP_WORDS);   // sleeps on irq_resp
            resp_words.insert(resp_words.end(), w.begin(), w.end());
            for (size_t i = 0; i < w.size(); ++i) resp_cycles.push_back(now());
        }
    }
    long njobs_, gap_;
};

// Inputs no model drives: the response IDs and codes of the two memory ports.
static const char* const ZERO_PORTS[] = {
    "m_axi_gmem0_RRESP", "m_axi_gmem0_RID", "m_axi_gmem1_BRESP", "m_axi_gmem1_BID",
};

int main() {
    const long mem_words = run_param("mem_words", 8192);
    const long njobs = run_param("njobs", 5);
    const long n_cycles = run_param("n_cycles", 20000);
    const long drain = 50;

    XsiSim sim(DESIGN_DLL, "histogram_mm.wdb");
    FlatMemory mem(mem_words, 4);
    AxiMmReadSlave m_rd(sim.dut(), "m_axi_gmem0", mem);
    AxiMmWriteSlave m_wr(sim.dut(), "m_axi_gmem1", mem);
    HistHost host(sim.dut(), njobs, run_param("cmd_gap", 0));
    sim.pin_low(ZERO_PORTS, sizeof(ZERO_PORTS) / sizeof(ZERO_PORTS[0]));

    mem.load_segs = {{0, 0, "vectors/mem_in"}};
    mem.dump_segs = {{0, 0, "vectors/mem_out"}};
    host.scenario = "vectors/s_cmd";

    XsiSimObj* models[] = {&mem, &m_rd, &m_wr, &host};
    for (auto* m : models) m->pre_sim();
    sim.reset([&] { for (auto* m : models) m->drive(); });
    long c = 0, done_at = -1;
    for (; c < n_cycles; ++c) {
        sim.clock_low();
        for (auto* m : models) m->sample();
        sim.clock_high();
        for (auto* m : models) m->update();
        for (auto* m : models) m->drive();
        if (done_at < 0 && host.done()) done_at = c;
        if (done_at >= 0 && c >= done_at + drain) break;
    }
    for (auto* m : models) m->post_sim();
    BurstBundle::write_capture("vectors/resp", host.resp_words, host.resp_cycles);
    std::vector<uint64_t> cw(host.cmd_cycles.size(), 0);
    BurstBundle::write_capture("vectors/cmd_sent", cw, host.cmd_cycles);
    std::printf("HIST_XSI: %ld cycles, %zu of %ld response words, %zu commands sent, "
                "%d count words written\n", c, host.resp_words.size(), njobs * (long)RESP_WORDS,
                host.cmd_cycles.size(), m_wr.w_count());
    sim.close();
    return 0;
}
