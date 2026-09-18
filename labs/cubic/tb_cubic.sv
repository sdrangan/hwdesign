`timescale 1ns/1ps
// -----------------------------------------------------------------------------
// Testbench: tb_cubic
// Description:
//   Reads the cases your Python model produced, runs each one through
//   cubic_fixed, and writes what the hardware returned to a CSV the build
//   script scores.
//
//   The lab uses two fixed-point settings, Q(16,8) and Q(16,12), and FBITS is a
//   module *parameter* -- fixed at elaboration, not something a plusarg can
//   change.  So rather than run the simulator twice, this testbench holds two
//   instances of the DUT, one per setting, driven from the same wires.  Each row
//   of the vector file says which setting it belongs to, and the row is scored
//   against that instance's output.  The other instance computes something
//   meaningless for that row, and nobody looks at it.
//
//   The vector directory arrives as a plusarg from the build script, so this
//   file needs no editing to move it.
//
//   YOU DO NOT NEED TO EDIT THIS FILE.  Your work goes in cubic.sv.
// -----------------------------------------------------------------------------
module tb_cubic;

    localparam int WID         = 16;
    localparam int FBITS_SMALL = 8;
    localparam int FBITS_LARGE = 12;
    localparam time CLK_PERIOD = 10ns;   // 100 MHz

    //: Rows printed to the console.  Every row is written to the file.
    localparam int SHOW = 8;

    //: Clocks to wait after driving a case before sampling y.  The pipeline
    //: registers the inputs on one edge and the stage 1 values on the next, and
    //: y is combinational from there -- so two edges is enough and three is the
    //: margin.  Inputs are held steady across the wait, so waiting longer than
    //: necessary cannot change the answer.
    localparam int PIPE_WAIT = 3;

    logic clk;
    logic rst;
    logic signed [WID-1:0] x, a0, a1, a2;
    logic signed [WID-1:0] y_small, y_large;

    // One instance per setting.  Both see the same inputs; which output is
    // recorded is decided per row, from the file.
    cubic_fixed #(.WID(WID), .FBITS(FBITS_SMALL)) dut_small (
        .clk(clk), .rst(rst), .x(x), .a0(a0), .a1(a1), .a2(a2), .y(y_small));

    cubic_fixed #(.WID(WID), .FBITS(FBITS_LARGE)) dut_large (
        .clk(clk), .rst(rst), .x(x), .a0(a0), .a1(a1), .a2(a2), .y(y_large));

    initial clk = 0;
    always #(CLK_PERIOD/2) clk = ~clk;

    string  vecdir;
    string  fn, fn_out;
    string  rest_of_line;

    integer file_handle;
    integer out_file_handle;
    integer scan_result;
    string  header_line;
    integer line_num;

    int                    fbits_test;
    logic signed [WID-1:0] xint, aint0, aint1, aint2;
    logic signed [WID-1:0] yint_expected;
    logic signed [WID-1:0] y_dut;

    integer num_passed, num_failed, num_unknown;

    // -------------------------------------------------------------------------
    // Watchdog
    //
    // A correct run is about 6 us of simulated time.  This fires only if
    // something is genuinely stuck -- most often a clock that never starts, or
    // a read loop whose terminating condition is never met.
    //
    // It ends with $finish, not $fatal.  $fatal leaves xsim.exe and xsimk.exe
    // alive on Windows, and the build script captures the simulator's output --
    // so it waits on a pipe that never closes, and a run that should fail in a
    // second takes ten minutes to do it.  $finish exits cleanly.
    //
    // Exiting cleanly means the build script sees a *successful* simulation
    // that wrote a short CSV, which is why compare_hardware() in cubic_build.py
    // scores a row-count mismatch rather than assuming the run must have
    // crashed.  The two go together: change one and read the other.
    // -------------------------------------------------------------------------
    initial begin
        #500_000;
        $display("TIMEOUT: still running after 500 us of simulated time.");
        $display("         No result was recorded for the remaining cases.");
        $fclose(out_file_handle);
        $fclose(file_handle);
        $finish;
    end

    initial begin
        rst         = 1;
        x           = 0;
        a0          = 0;
        a1          = 0;
        a2          = 0;
        num_passed  = 0;
        num_failed  = 0;
        num_unknown = 0;

        if (!$value$plusargs("vecdir=%s", vecdir)) vecdir = "vectors";
        fn     = {vecdir, "/cubic_py.csv"};
        fn_out = {vecdir, "/cubic_sv.csv"};

        // Reset both instances.
        repeat (3) @(posedge clk);
        rst = 0;

        file_handle = $fopen(fn, "r");
        if (file_handle == 0) begin
            $display("FATAL: could not open %s", fn);
            $display("       Run the Python stage first:  python cubic_build.py --through pysim");
            $finish;
        end

        out_file_handle = $fopen(fn_out, "w");
        if (out_file_handle == 0) begin
            $display("FATAL: could not open %s for writing", fn_out);
            $fclose(file_handle);
            $finish;
        end

        // Header.  The build script reads these columns by name.
        $fdisplay(out_file_handle, "fbits,xint,aint0,aint1,aint2,yint,y_dut");

        // Skip the input header line.
        scan_result = $fgets(header_line, file_handle);

        $display("tb_cubic: reading %s", fn);
        $display("          writing %s", fn_out);
        $display("   row  F   xint  aint0  aint1  aint2     yint    y_dut");

        line_num = 0;

        while (!$feof(file_handle)) begin

            // The columns are fbits,xint,aint0,aint1,aint2,yint,y,yfix -- written
            // by PySimStep in cubic_build.py.  Only the six integers are read
            // here; the two floating-point columns are for the Python side and
            // are swallowed by the $fgets below.
            //
            // The fields are read one at a time rather than with a single
            // format string, to avoid a Vivado 2023.2 bug in $fscanf when a
            // format contains several negative numbers:
            // https://adaptivesupport.amd.com/s/question/0D54U000080bmlESAQ/
            scan_result  = $fscanf(file_handle, "%d,", fbits_test);
            scan_result += $fscanf(file_handle, "%d,", xint);
            scan_result += $fscanf(file_handle, "%d,", aint0);
            scan_result += $fscanf(file_handle, "%d,", aint1);
            scan_result += $fscanf(file_handle, "%d,", aint2);
            scan_result += $fscanf(file_handle, "%d,", yint_expected);

            if (scan_result != 6) begin
                // End of file, or an incomplete final line.
                break;
            end

            // Swallow the y and yfix columns and the newline.
            scan_result = $fgets(rest_of_line, file_handle);

            line_num++;

            // Drive both instances.  A small delay off the clock edge keeps the
            // inputs away from the setup window of the edge being waited on.
            #(0.1*CLK_PERIOD);
            x  = xint;
            a0 = aint0;
            a1 = aint1;
            a2 = aint2;

            repeat (PIPE_WAIT) @(posedge clk);

            // Take the output of the instance this row belongs to.
            if (fbits_test == FBITS_SMALL)
                y_dut = y_small;
            else if (fbits_test == FBITS_LARGE)
                y_dut = y_large;
            else begin
                // The file asked for a setting no instance was built for.  The
                // row is still written, so the build script sees the right
                // number of rows and reports a mismatch rather than a truncated
                // file.
                y_dut = 'x;
                num_unknown++;
            end

            if (y_dut === yint_expected) num_passed++;
            else                         num_failed++;

            if (line_num <= SHOW)
                $display("  %4d %2d %6d %6d %6d %6d %8d %8d",
                         line_num, fbits_test, xint, aint0, aint1, aint2,
                         yint_expected, y_dut);

            $fdisplay(out_file_handle, "%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                      fbits_test, xint, aint0, aint1, aint2, yint_expected, y_dut);
        end

        $fclose(file_handle);
        $fclose(out_file_handle);

        $display("\n=== Test Summary ===");
        $display("Total cases: %0d", line_num);
        $display("Matched:     %0d", num_passed);
        $display("Differed:    %0d", num_failed);
        if (num_unknown > 0)
            $display("Unknown F:   %0d  (a row asked for a setting with no instance)",
                     num_unknown);
        $display("Results written to %s", fn_out);

        #20;
        $finish;
    end

endmodule
