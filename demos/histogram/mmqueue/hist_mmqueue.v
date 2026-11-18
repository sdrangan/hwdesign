// hist_mmqueue.v -- the unit 9 histogram behind memory-mapped queues: the RTL top.
//
// The kernel is hist_simple's, unchanged: the synthesized hist_simple (../simple), whose command
// arrives on s_cmd and whose response leaves on s_done.  What changes is who is on the other end of
// those two streams.  Here it is Waveflow's memory-mapped slave adaptor, so a host -- a processor on
// an AXI bus -- sends commands and takes responses with ordinary bus writes and reads:
//
//   s_axi  -> axi_slave_front -> decoder -+-> mm_queue_in  (qcmd,  0x0000) -> s_cmd  -> kernel
//                                         +-> mm_queue_out (qresp, 0x1000) <- s_done <- kernel
//
//   qcmd   queue in.   The host writes a packet [len | words] to 0x0000; the queue drops the len
//          and pushes the words onto s_cmd.  A read anywhere in the window returns the free room.
//          irq_cmd is high while the room is at least the threshold the host wrote to 0x0800.
//   qresp  queue out.  The kernel pushes HistResp words; each host read of 0x1000 pops one.  A
//          read of 0x1800 returns how many are waiting.  irq_resp is high while at least the
//          threshold the host wrote to 0x1800 are waiting.
//
// So the host can queue several jobs' commands at once, and sleep on irq_resp until a response
// is waiting.  The kernel's two m_axi ports -- its data movers' -- pass straight through to the
// memory: m_axi_gmem0 reads the samples, m_axi_gmem1 writes the counts.
//
// Waveflow does not generate this top for an HLS kernel yet, so it is hand-assembled, following
// its generated one-front adaptor (waveflow/build/mm_adaptor_gen.py, render_adaptor_slot): one
// front, two 4 KB views selected by address bit 12, and the read response taken from the view
// that accepted the read (the front keeps at most one read outstanding).
`timescale 1ns/1ps
module hist_mmqueue #(
    parameter integer DW      = 32,     // the bus word: the kernel's MEM_DW
    parameter integer S_AW    = 32,     // the host bus's address width
    parameter integer QDEPTH  = 64      // words each queue holds (12 commands, 32 responses)
) (
    input  wire              ap_clk,
    input  wire              ap_rst_n,
    // --- the host's port: AXI4 slave ----------------------------------------------------
    input  wire [0:0]        s_axi_AWID,
    input  wire [S_AW-1:0]   s_axi_AWADDR,
    input  wire [7:0]        s_axi_AWLEN,
    input  wire [2:0]        s_axi_AWSIZE,
    input  wire [1:0]        s_axi_AWBURST,
    input  wire              s_axi_AWVALID,
    output wire              s_axi_AWREADY,
    input  wire [DW-1:0]     s_axi_WDATA,
    input  wire [DW/8-1:0]   s_axi_WSTRB,
    input  wire              s_axi_WLAST,
    input  wire              s_axi_WVALID,
    output wire              s_axi_WREADY,
    output wire [0:0]        s_axi_BID,
    output wire [1:0]        s_axi_BRESP,
    output wire              s_axi_BVALID,
    input  wire              s_axi_BREADY,
    input  wire [0:0]        s_axi_ARID,
    input  wire [S_AW-1:0]   s_axi_ARADDR,
    input  wire [7:0]        s_axi_ARLEN,
    input  wire [2:0]        s_axi_ARSIZE,
    input  wire [1:0]        s_axi_ARBURST,
    input  wire              s_axi_ARVALID,
    output wire              s_axi_ARREADY,
    output wire [0:0]        s_axi_RID,
    output wire [DW-1:0]     s_axi_RDATA,
    output wire [1:0]        s_axi_RRESP,
    output wire              s_axi_RLAST,
    output wire              s_axi_RVALID,
    input  wire              s_axi_RREADY,
    output wire              irq_cmd,       // qcmd has room for a command
    output wire              irq_resp,      // qresp has a response waiting
    // --- the read mover's port: AXI4 master, read channels only ---------------------------
    output wire              m_axi_gmem0_ARVALID,
    input  wire              m_axi_gmem0_ARREADY,
    output wire [63:0]       m_axi_gmem0_ARADDR,
    output wire [0:0]        m_axi_gmem0_ARID,
    output wire [7:0]        m_axi_gmem0_ARLEN,
    output wire [2:0]        m_axi_gmem0_ARSIZE,
    output wire [1:0]        m_axi_gmem0_ARBURST,
    input  wire              m_axi_gmem0_RVALID,
    output wire              m_axi_gmem0_RREADY,
    input  wire [DW-1:0]     m_axi_gmem0_RDATA,
    input  wire              m_axi_gmem0_RLAST,
    input  wire [0:0]        m_axi_gmem0_RID,
    input  wire [1:0]        m_axi_gmem0_RRESP,
    // --- the write mover's port: AXI4 master, write channels only -------------------------
    output wire              m_axi_gmem1_AWVALID,
    input  wire              m_axi_gmem1_AWREADY,
    output wire [63:0]       m_axi_gmem1_AWADDR,
    output wire [0:0]        m_axi_gmem1_AWID,
    output wire [7:0]        m_axi_gmem1_AWLEN,
    output wire [2:0]        m_axi_gmem1_AWSIZE,
    output wire [1:0]        m_axi_gmem1_AWBURST,
    output wire              m_axi_gmem1_WVALID,
    input  wire              m_axi_gmem1_WREADY,
    output wire [DW-1:0]     m_axi_gmem1_WDATA,
    output wire [DW/8-1:0]   m_axi_gmem1_WSTRB,
    output wire              m_axi_gmem1_WLAST,
    input  wire              m_axi_gmem1_BVALID,
    output wire              m_axi_gmem1_BREADY,
    input  wire [1:0]        m_axi_gmem1_BRESP,
    input  wire [0:0]        m_axi_gmem1_BID
);
    localparam integer LAW = 13;            // two 4 KB views: bit 12 picks one

    // ---- the front: AXI4 in, one request at a time out -----------------------------------
    wire            req_valid, req_ready, req_we, rsp_valid, rsp_ready, rsp_err;
    wire [LAW-1:0]  req_addr;
    wire [DW-1:0]   req_wdata, rsp_rdata;

    axi_slave_front #(.DW(DW), .AW(S_AW), .IDW(1), .LAW(LAW)) u_front (
        .ap_clk(ap_clk), .ap_rst_n(ap_rst_n),
        .s_axi_AWID(s_axi_AWID), .s_axi_AWADDR(s_axi_AWADDR), .s_axi_AWLEN(s_axi_AWLEN),
        .s_axi_AWSIZE(s_axi_AWSIZE), .s_axi_AWBURST(s_axi_AWBURST),
        .s_axi_AWVALID(s_axi_AWVALID), .s_axi_AWREADY(s_axi_AWREADY),
        .s_axi_WDATA(s_axi_WDATA), .s_axi_WSTRB(s_axi_WSTRB), .s_axi_WLAST(s_axi_WLAST),
        .s_axi_WVALID(s_axi_WVALID), .s_axi_WREADY(s_axi_WREADY),
        .s_axi_BID(s_axi_BID), .s_axi_BRESP(s_axi_BRESP), .s_axi_BVALID(s_axi_BVALID),
        .s_axi_BREADY(s_axi_BREADY),
        .s_axi_ARID(s_axi_ARID), .s_axi_ARADDR(s_axi_ARADDR), .s_axi_ARLEN(s_axi_ARLEN),
        .s_axi_ARSIZE(s_axi_ARSIZE), .s_axi_ARBURST(s_axi_ARBURST),
        .s_axi_ARVALID(s_axi_ARVALID), .s_axi_ARREADY(s_axi_ARREADY),
        .s_axi_RID(s_axi_RID), .s_axi_RDATA(s_axi_RDATA), .s_axi_RRESP(s_axi_RRESP),
        .s_axi_RLAST(s_axi_RLAST), .s_axi_RVALID(s_axi_RVALID), .s_axi_RREADY(s_axi_RREADY),
        .req_valid(req_valid), .req_ready(req_ready), .req_we(req_we), .req_addr(req_addr),
        .req_wdata(req_wdata), .rsp_valid(rsp_valid), .rsp_ready(rsp_ready),
        .rsp_rdata(rsp_rdata), .rsp_err(rsp_err)
    );

    // ---- the decoder: view 0 (qcmd) at 0x0000, view 1 (qresp) at 0x1000 --------------------
    wire sel = req_addr[12];
    reg  rsel;                              // the view that accepted the outstanding read
    always @(posedge ap_clk) begin
        if (!ap_rst_n)                                 rsel <= 1'b0;
        else if (req_valid && req_ready && !req_we)    rsel <= sel;
    end

    wire            c_req_ready, c_rsp_valid, c_rsp_err, r_req_ready, r_rsp_valid, r_rsp_err;
    wire [DW-1:0]   c_rsp_rdata, r_rsp_rdata;
    assign req_ready = sel  ? r_req_ready : c_req_ready;
    assign rsp_valid = rsel ? r_rsp_valid : c_rsp_valid;
    assign rsp_rdata = rsel ? r_rsp_rdata : c_rsp_rdata;
    assign rsp_err   = rsel ? r_rsp_err   : c_rsp_err;

    // ---- view 0, qcmd: host writes -> s_cmd ----------------------------------------------
    wire [DW-1:0] s_cmd_TDATA;
    wire          s_cmd_TVALID, s_cmd_TREADY;

    mm_queue_in #(.DW(DW), .LAW(12), .DEPTH(QDEPTH)) u_qcmd (
        .ap_clk(ap_clk), .ap_rst_n(ap_rst_n),
        .req_valid(req_valid && !sel), .req_ready(c_req_ready), .req_we(req_we),
        .req_addr(req_addr[11:0]), .req_wdata(req_wdata),
        .rsp_valid(c_rsp_valid), .rsp_ready(rsp_ready && !rsel), .rsp_rdata(c_rsp_rdata),
        .rsp_err(c_rsp_err),
        .m_axis_TDATA(s_cmd_TDATA), .m_axis_TVALID(s_cmd_TVALID), .m_axis_TREADY(s_cmd_TREADY),
        .m_axis_TLAST(),                    // the kernel counts its words; no TLAST
        .irq(irq_cmd)
    );

    // ---- view 1, qresp: s_done -> host reads ---------------------------------------------
    wire [DW-1:0] s_done_TDATA;
    wire          s_done_TVALID, s_done_TREADY;

    mm_queue_out #(.DW(DW), .LAW(12), .DEPTH(QDEPTH)) u_qresp (
        .ap_clk(ap_clk), .ap_rst_n(ap_rst_n),
        .req_valid(req_valid && sel), .req_ready(r_req_ready), .req_we(req_we),
        .req_addr(req_addr[11:0]), .req_wdata(req_wdata),
        .rsp_valid(r_rsp_valid), .rsp_ready(rsp_ready && rsel), .rsp_rdata(r_rsp_rdata),
        .rsp_err(r_rsp_err),
        .s_axis_TDATA(s_done_TDATA), .s_axis_TVALID(s_done_TVALID), .s_axis_TREADY(s_done_TREADY),
        .s_axis_TLAST(1'b0),
        .irq(irq_resp)
    );

    // ---- the kernel: hist_simple, unchanged ---------------------------------------------
    // Each m_axi bundle is used in one direction only, so the other direction's inputs are tied
    // idle and its outputs left open; the sidebands Vitis drives as constants (LOCK, CACHE,
    // PROT, QOS, REGION, USER) are left open too.
    hist_simple u_kernel (
        .ap_clk(ap_clk), .ap_rst_n(ap_rst_n),
        .s_cmd_TDATA(s_cmd_TDATA), .s_cmd_TVALID(s_cmd_TVALID), .s_cmd_TREADY(s_cmd_TREADY),
        .s_done_TDATA(s_done_TDATA), .s_done_TVALID(s_done_TVALID), .s_done_TREADY(s_done_TREADY),
        // gmem0: reads
        .m_axi_gmem0_ARVALID(m_axi_gmem0_ARVALID), .m_axi_gmem0_ARREADY(m_axi_gmem0_ARREADY),
        .m_axi_gmem0_ARADDR(m_axi_gmem0_ARADDR), .m_axi_gmem0_ARID(m_axi_gmem0_ARID),
        .m_axi_gmem0_ARLEN(m_axi_gmem0_ARLEN), .m_axi_gmem0_ARSIZE(m_axi_gmem0_ARSIZE),
        .m_axi_gmem0_ARBURST(m_axi_gmem0_ARBURST),
        .m_axi_gmem0_ARLOCK(), .m_axi_gmem0_ARCACHE(), .m_axi_gmem0_ARPROT(),
        .m_axi_gmem0_ARQOS(), .m_axi_gmem0_ARREGION(), .m_axi_gmem0_ARUSER(),
        .m_axi_gmem0_RVALID(m_axi_gmem0_RVALID), .m_axi_gmem0_RREADY(m_axi_gmem0_RREADY),
        .m_axi_gmem0_RDATA(m_axi_gmem0_RDATA), .m_axi_gmem0_RLAST(m_axi_gmem0_RLAST),
        .m_axi_gmem0_RID(m_axi_gmem0_RID), .m_axi_gmem0_RRESP(m_axi_gmem0_RRESP),
        .m_axi_gmem0_RUSER(1'b0),
        .m_axi_gmem0_AWVALID(), .m_axi_gmem0_AWREADY(1'b0), .m_axi_gmem0_AWADDR(),
        .m_axi_gmem0_AWID(), .m_axi_gmem0_AWLEN(), .m_axi_gmem0_AWSIZE(), .m_axi_gmem0_AWBURST(),
        .m_axi_gmem0_AWLOCK(), .m_axi_gmem0_AWCACHE(), .m_axi_gmem0_AWPROT(),
        .m_axi_gmem0_AWQOS(), .m_axi_gmem0_AWREGION(), .m_axi_gmem0_AWUSER(),
        .m_axi_gmem0_WVALID(), .m_axi_gmem0_WREADY(1'b0), .m_axi_gmem0_WDATA(),
        .m_axi_gmem0_WSTRB(), .m_axi_gmem0_WLAST(), .m_axi_gmem0_WID(), .m_axi_gmem0_WUSER(),
        .m_axi_gmem0_BVALID(1'b0), .m_axi_gmem0_BREADY(), .m_axi_gmem0_BRESP(2'b00),
        .m_axi_gmem0_BID(1'b0), .m_axi_gmem0_BUSER(1'b0),
        // gmem1: writes
        .m_axi_gmem1_AWVALID(m_axi_gmem1_AWVALID), .m_axi_gmem1_AWREADY(m_axi_gmem1_AWREADY),
        .m_axi_gmem1_AWADDR(m_axi_gmem1_AWADDR), .m_axi_gmem1_AWID(m_axi_gmem1_AWID),
        .m_axi_gmem1_AWLEN(m_axi_gmem1_AWLEN), .m_axi_gmem1_AWSIZE(m_axi_gmem1_AWSIZE),
        .m_axi_gmem1_AWBURST(m_axi_gmem1_AWBURST),
        .m_axi_gmem1_AWLOCK(), .m_axi_gmem1_AWCACHE(), .m_axi_gmem1_AWPROT(),
        .m_axi_gmem1_AWQOS(), .m_axi_gmem1_AWREGION(), .m_axi_gmem1_AWUSER(),
        .m_axi_gmem1_WVALID(m_axi_gmem1_WVALID), .m_axi_gmem1_WREADY(m_axi_gmem1_WREADY),
        .m_axi_gmem1_WDATA(m_axi_gmem1_WDATA), .m_axi_gmem1_WSTRB(m_axi_gmem1_WSTRB),
        .m_axi_gmem1_WLAST(m_axi_gmem1_WLAST), .m_axi_gmem1_WID(), .m_axi_gmem1_WUSER(),
        .m_axi_gmem1_BVALID(m_axi_gmem1_BVALID), .m_axi_gmem1_BREADY(m_axi_gmem1_BREADY),
        .m_axi_gmem1_BRESP(m_axi_gmem1_BRESP), .m_axi_gmem1_BID(m_axi_gmem1_BID),
        .m_axi_gmem1_BUSER(1'b0),
        .m_axi_gmem1_ARVALID(), .m_axi_gmem1_ARREADY(1'b0), .m_axi_gmem1_ARADDR(),
        .m_axi_gmem1_ARID(), .m_axi_gmem1_ARLEN(), .m_axi_gmem1_ARSIZE(), .m_axi_gmem1_ARBURST(),
        .m_axi_gmem1_ARLOCK(), .m_axi_gmem1_ARCACHE(), .m_axi_gmem1_ARPROT(),
        .m_axi_gmem1_ARQOS(), .m_axi_gmem1_ARREGION(), .m_axi_gmem1_ARUSER(),
        .m_axi_gmem1_RVALID(1'b0), .m_axi_gmem1_RREADY(), .m_axi_gmem1_RDATA({DW{1'b0}}),
        .m_axi_gmem1_RLAST(1'b0), .m_axi_gmem1_RID(1'b0), .m_axi_gmem1_RUSER(1'b0),
        .m_axi_gmem1_RRESP(2'b00)
    );
endmodule
