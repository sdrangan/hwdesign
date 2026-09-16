`timescale 1ns/1ps
// -----------------------------------------------------------------------------
// Testbench: tb_subc_divide
// Description:
//   Reads the test cases your Python model produced, runs each one through
//   subc_divide, and writes what the hardware returned -- together with how
//   many clock cycles it took -- to a CSV the build script scores.
//
//   The file reading, the file writing and the cycle counting are given.  What
//   you write is the **handshake**: how a case is handed to the module and how
//   the answer is collected.  That protocol is half of what this lab is about,
//   and it is the half that does not appear in subc_divide.sv.
//
//   The vector directory arrives as a plusarg from the build script, so this
//   file needs no editing to move it.
// -----------------------------------------------------------------------------

module tb_subc_divide;

    // DUT signals
    logic         clk;
    logic         rst;

    logic         invalid;
    logic         inready;

    logic [31:0]  a;
    logic [31:0]  b;
    logic [5:0]   nbits;

    logic         outready;
    logic         outvalid;

    logic [31:0]  z;

    logic [31:0]  atest, btest;
    logic [5:0]   nbitstest;

    //: The most clock cycles to wait for one case before giving up on it.  A
    //: correct design needs nbits of them -- at most 16 here -- so this is a
    //: four-fold margin.  It is here so that a module which never asserts
    //: outvalid produces a scored failure instead of a run that never ends.
    //:
    //: It also bounds the whole simulation: with this loop bounded, the worst
    //: a broken design can cost is NTEST * MAX_WAIT clocks, about 130 us, which
    //: is what makes the watchdog below able to be short.
    localparam int MAX_WAIT = 64;

    // Instantiate DUT
    subc_divide dut (
        .clk(clk),
        .rst(rst),
        .invalid(invalid),
        .inready(inready),
        .a(a),
        .b(b),
        .nbits(nbits),
        .outready(outready),
        .outvalid(outvalid),
        .z(z)
    );

    // Clock generator
    always #5 clk = ~clk;

    // Plusargs, file handles and bookkeeping
    string  vecdir;
    string  fn, fn_out;

    integer file_handle;
    integer out_file_handle;
    integer scan_result;
    string  header_line;
    integer line_num;
    logic [31:0] z_expected;
    logic [31:0] zgot;
    integer cycle_count;
    integer nvals_correct;
    integer timeouts;

    // -------------------------------------------------------------------------
    // Watchdog
    //
    // This testbench has two places it can wait indefinitely: waiting for
    // outvalid after handing over a case, and waiting for inready before the
    // next one.  A module that never leaves IDLE -- which is exactly what the
    // unedited subc_divide.sv is -- stalls both, and a simulator that never
    // returns looks precisely like one that is working hard.
    //
    // Keep this short.  It bounds *simulated* time, but what a student waits is
    // wall-clock, and the two are not proportional: a stalled design propagates
    // X through the DUT on every clock edge, which simulates far more slowly
    // than a working one.  At 10 ms this fired correctly and took ten and a
    // half minutes to do it.
    //
    // A correct run takes 26 us, and with the wait loop bounded by MAX_WAIT the
    // worst a broken design can cost is about 130 us -- so 500 us clears
    // anything legitimate by a wide margin and still fails in seconds.
    // -------------------------------------------------------------------------
    // It ends with $finish, not $fatal.  $fatal leaves xsim.exe and xsimk.exe
    // alive on Windows, and the build script captures the simulator's output --
    // so it waits on a pipe that never closes, and a run that should fail in a
    // second takes ten minutes to do it.  $finish exits cleanly.
    //
    // Exiting cleanly means the build script sees a *successful* simulation
    // that wrote a short CSV, which is why compare_hardware() in subc_build.py
    // scores a row-count mismatch rather than assuming the run must have
    // crashed.  The two go together: change one and read the other.
    initial begin
        #500_000;
        $display("TIMEOUT: still running after 500 us of simulated time.");
        $display("         The testbench is waiting on inready or outvalid and");
        $display("         neither arrived. In subc_divide.sv, check that the state");
        $display("         machine leaves RUN after nbits iterations, asserts");
        $display("         outvalid in DONE, and returns to IDLE once outready is");
        $display("         seen. No result was recorded for the remaining cases.");
        $fclose(out_file_handle);
        $fclose(file_handle);
        $finish;
    end

    initial begin

        // Initialize
        clk      = 0;
        rst      = 1;
        invalid  = 0;
        outready = 0;
        a        = 0;
        b        = 0;
        nbits    = 0;
        nvals_correct = 0;
        timeouts = 0;

        if (!$value$plusargs("vecdir=%s", vecdir)) vecdir = "vectors";
        fn     = {vecdir, "/tv_python.csv"};
        fn_out = {vecdir, "/tv_sv.csv"};

        // Reset
        repeat (3) @(posedge clk);
        rst = 0;

        // Open the input CSV
        file_handle = $fopen(fn, "r");
        if (file_handle == 0) begin
            $display("FATAL: could not open %s", fn);
            $display("       Run the Python stage first:  python subc_build.py --through pysim");
            $fatal(1);
        end

        // Open the output CSV
        out_file_handle = $fopen(fn_out, "w");
        if (out_file_handle == 0) begin
            $display("FATAL: could not open %s for writing", fn_out);
            $fclose(file_handle);
            $fatal(1);
        end

        // Header.  The build script reads these columns by name.
        $fdisplay(out_file_handle, "a,b,nbits,z_exp,z,cycles");

        // Skip the input header line
        scan_result = $fgets(header_line, file_handle);
        $display("tb_subc_divide: reading %s", fn);
        $display("                writing %s", fn_out);

        line_num = 0;

        while (!$feof(file_handle)) begin

            // Columns are a,b,nbits,z -- written by PySimStep in subc_build.py.
            scan_result = $fscanf(file_handle, "%d,%d,%d,%d\n",
                                  atest, btest, nbitstest, z_expected);

            if (scan_result != 4) begin
                // End of file, or an incomplete final line
                break;
            end

            line_num++;

            // Present the case.  The handshake below is what hands it over.
            a     = atest;
            b     = btest;
            nbits = nbitstest;

            // Defaults, so that a case which is never driven records something
            // obviously wrong rather than a stale value from the case before.
            cycle_count = 0;
            zgot        = 32'hDEADBEEF;

            // TODO:  Drive one case through the handshake.
            //
            // Four things have to happen, in this order:
            //
            //   1. Wait until the module is ready for inputs (`inready`), then
            //      hold `invalid` high across one posedge and drop it again.
            //      a, b and nbits are already driven, above.
            //
            //   2. Wait for `outvalid`, counting posedges into `cycle_count`.
            //      Bound the loop with `cycle_count < MAX_WAIT` as well -- a
            //      module that never asserts outvalid would otherwise hang the
            //      simulation, and a failed case is far more useful than a run
            //      that never ends.  If you time out, increment `timeouts`.
            //
            //   3. Sample `zgot = z` while outvalid is still high.  That is the
            //      only time the module promises z means anything.
            //
            //   4. Hold `outready` high across one posedge and drop it, which
            //      is how the module learns the answer has been taken.
            //
            // Leave `cycle_count` and `zgot` as they are on a timeout -- the
            // build script scores an unanswered case as a failure, which is
            // what it is.
            @(posedge clk);

            if (zgot == z_expected) nvals_correct++;

            // The recording is given, and deliberately outside the block above:
            // these columns are the grading data, and their format has to be
            // right whatever the handshake did.
            $fdisplay(out_file_handle, "%0d,%0d,%0d,%0d,%0d,%0d",
                      atest, btest, nbitstest, z_expected, zgot, cycle_count);
        end

        $fclose(file_handle);
        $fclose(out_file_handle);

        $display("\n=== Test Summary ===");
        $display("Total cases:     %0d", line_num);
        $display("Values correct:  %0d", nvals_correct);
        if (timeouts > 0)
            $display("Timed out:       %0d  (no outvalid within %0d cycles)",
                     timeouts, MAX_WAIT);

        #20;
        $finish;
    end

endmodule
