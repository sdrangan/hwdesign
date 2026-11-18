// tb_xsi_hist_simple.cpp -- the RTL testbench for hist_simple, run through XSI.
//
// Drives the synthesized Verilog cycle by cycle with Waveflow's bus models (xsi_bfm.h):
//   s_cmd         an AXI4-Stream master playing every job's HistCmd words, back to back
//   m_axi_gmem0   an AXI4 read slave  } both over ONE flat memory, as the two ports of the
//   m_axi_gmem1   an AXI4 write slave } kernel see a single DRAM on the board
//   s_done        an always-ready AXI4-Stream slave recording each response word and its cycle
//
// The vectors are written by hist_build.py (from hist_golden.py) into vectors/ as burst
// bundles: mem_in and s_cmd in; mem_out and s_done out.  Nothing is checked here; Python checks
// the dumped memory and responses against the NumPy golden.  The run parameter cmd_gap holds
// s_cmd idle between commands: 0 sends them back to back, a large gap runs each job alone.
//
// It runs until every response has arrived and then DRAIN more cycles, so the run ends soon
// after the last job -- or at n_cycles, when one never arrives: a deadlock reads as missing
// responses, not as a hang.
#include <cstdio>
#include "xsi_bfm.h"

using namespace wfbfm;

#ifdef _WIN32
static const char* const DESIGN_DLL = "xsim.dir/hist_simple/xsimk.dll";
#else
static const char* const DESIGN_DLL = "xsim.dir/hist_simple/xsimk.so";
#endif

// Inputs no model drives: the unused half of each m_axi bundle and the response side-bands.
static const char* const ZERO_PORTS[] = {
    "m_axi_gmem0_AWREADY", "m_axi_gmem0_WREADY", "m_axi_gmem0_BVALID", "m_axi_gmem0_BRESP",
    "m_axi_gmem0_BID", "m_axi_gmem0_BUSER", "m_axi_gmem0_RRESP", "m_axi_gmem0_RID",
    "m_axi_gmem0_RUSER",
    "m_axi_gmem1_ARREADY", "m_axi_gmem1_RVALID", "m_axi_gmem1_RDATA", "m_axi_gmem1_RLAST",
    "m_axi_gmem1_RRESP", "m_axi_gmem1_RID", "m_axi_gmem1_RUSER", "m_axi_gmem1_BRESP",
    "m_axi_gmem1_BID", "m_axi_gmem1_BUSER",
};

int main() {
    const long mem_words = run_param("mem_words", 8192);
    const long resp_words = run_param("resp_words", 10);
    const long n_cycles = run_param("n_cycles", 20000);
    const long drain = 50;

    XsiSim sim(DESIGN_DLL, "hist_simple.wdb");
    FlatMemory mem(mem_words, 4);                       // 32-bit words
    AxisMaster s_cmd(sim.dut(), "s_cmd", {});
    AxiMmReadSlave m_rd(sim.dut(), "m_axi_gmem0", mem);
    AxiMmWriteSlave m_wr(sim.dut(), "m_axi_gmem1", mem);
    AxisSlave s_done(sim.dut(), "s_done");
    sim.pin_low(ZERO_PORTS, sizeof(ZERO_PORTS) / sizeof(ZERO_PORTS[0]));

    mem.load_segs = {{0, 0, "vectors/mem_in"}};
    mem.dump_segs = {{0, 0, "vectors/mem_out"}};
    s_cmd.in_bundle = "vectors/s_cmd";                  // one burst per command
    s_cmd.burst_gap_cycles = (int)run_param("cmd_gap", 0);   // idle cycles between commands
    s_done.out_bundle = "vectors/s_done";

    XsiSimObj* models[] = {&mem, &s_cmd, &m_rd, &m_wr, &s_done};
    for (auto* m : models) m->pre_sim();
    sim.reset([&] { for (auto* m : models) m->drive(); });
    long c = 0, done_at = -1;
    for (; c < n_cycles; ++c) {
        sim.clock_low();
        for (auto* m : models) m->sample();
        sim.clock_high();
        for (auto* m : models) m->update();
        for (auto* m : models) m->drive();
        if (done_at < 0 && (long)s_done.count() >= resp_words) done_at = c;
        if (done_at >= 0 && c >= done_at + drain) break;
    }
    for (auto* m : models) m->post_sim();
    std::printf("HIST_XSI: %ld cycles, %zu of %ld response words, %d count words written\n",
                c, s_done.count(), resp_words, m_wr.w_count());
    sim.close();
    return 0;
}
