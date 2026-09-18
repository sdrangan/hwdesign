`timescale 1ns/1ps
// -----------------------------------------------------------------------------
// Testbench: tb_cubic_sing
// Description:
//   One case, run through cubic_fixed with every pipeline register printed on
//   every clock.  This is the debugging bench, not the grading one:
//
//       python cubic_build.py --through svsing
//
//   When `svsim` tells you that two hundred cases disagree, it cannot tell you
//   *which product overflowed*.  This can.  Set the four inputs at the top to a
//   case you want to look at, complete `expected_y()` to say what your
//   arithmetic should produce for it, and read the register trace.
//
//   Nothing here is graded and nothing here is submitted.  It exists so that
//   the answer to "why is case 37 wrong" is a table rather than a guess.
//
//   Note what completing `expected_y()` actually asks of you.  The real-valued
//   answer is not the right target: the module truncates on every shift and
//   clamps on every saturation, so its output differs from the exact value by a
//   little at F=8 and by a lot at F=12.  Writing the expected value out in
//   integers is how you find out whether you know what your own design does.
// -----------------------------------------------------------------------------
module tb_cubic_sing;

    localparam int WID   = 16;
    localparam int FBITS = 8;
    localparam time CLK_PERIOD = 10ns;   // 100 MHz

    //: Clocks the monitor prints before it checks the result.
    localparam int MONITOR_CYCLES = 10;

    // -------------------------------------------------------------------------
    // The case.  Change these to look at a different one.
    //
    // As given, nothing saturates at F=8 -- a good place to start.  To see the
    // saturating behaviour, set FBITS to 12 above, or push x out towards 2.0.
    // -------------------------------------------------------------------------
    localparam real xr_test  =  2.5;
    localparam real a0r_test =  1.0;
    localparam real a1r_test = -0.5;
    localparam real a2r_test =  0.25;

    // The same values as Q(WID, FBITS) integers -- this is what the DUT sees.
    localparam int x_test  = int'(xr_test  * (1 << FBITS));
    localparam int a0_test = int'(a0r_test * (1 << FBITS));
    localparam int a1_test = int'(a1r_test * (1 << FBITS));
    localparam int a2_test = int'(a2r_test * (1 << FBITS));

    // The exact real-valued answer, printed for comparison only.  It is *not*
    // what the DUT should produce, and the difference between the two is the
    // quantization error this lab is about.
    localparam real yr_test = xr_test**3 + a2r_test*xr_test**2
                              + a1r_test*xr_test + a0r_test;

    logic clk;
    logic rst;
    logic signed [WID-1:0] x, a0, a1, a2, y;

    int y_test;      // the expected output, from expected_y() below

    cubic_fixed #(.WID(WID), .FBITS(FBITS)) dut (
        .clk(clk), .rst(rst), .x(x), .a0(a0), .a1(a1), .a2(a2), .y(y));

    initial clk = 0;
    always #(CLK_PERIOD/2) clk = ~clk;

    // -------------------------------------------------------------------------
    // Saturation, as in cubic.sv.  Given, so that expected_y() below is about
    // the arithmetic rather than about rewriting this.
    // -------------------------------------------------------------------------
    function automatic longint sat_i(input longint v);
        longint max_val, min_val;
        begin
            max_val = (64'sd1 <<< (WID - 1)) - 1;
            min_val = -(64'sd1 <<< (WID - 1));
            if      (v > max_val) sat_i = max_val;
            else if (v < min_val) sat_i = min_val;
            else                  sat_i = v;
        end
    endfunction

    // -------------------------------------------------------------------------
    // What the DUT should produce for this case.
    // -------------------------------------------------------------------------
    function automatic longint expected_y();
        longint x2, ax1, x3, ax2;
        begin
            // TODO:  Compute the expected output in integers, and delete the
            // `expected_y = 0;` below.
            //
            //     x2  = ...        x**2
            //     ax1 = ...        a1*x + a0
            //     x3  = ...        x**3
            //     ax2 = ...        a2*x**2
            //     expected_y = ... the sum of the three terms
            //
            // Use exactly the operations your cubic.sv uses -- the same shifts,
            // the same `sat_i` calls, in the same order.  The point of this
            // function is to state what you believe your design computes; if it
            // disagrees with the DUT, one of the two is where the bug is.
            //
            // Cast one operand of each product to `longint` so the multiply is
            // done in 64 bits: `x_test` and friends are `int`, and two of them
            // multiplied together can overflow 32 bits before the shift gets a
            // chance to bring the value back down.
            expected_y = 0;
        end
    endfunction

    // -------------------------------------------------------------------------
    // Stimulus
    // -------------------------------------------------------------------------
    initial begin
        y_test = int'(expected_y());

        rst = 1;
        x = 0; a0 = 0; a1 = 0; a2 = 0;

        $display("=== Cubic Fixed Point: one case ===");
        $display("Parameters: WID=%0d, FBITS=%0d", WID, FBITS);
        $display("\nTest inputs:");
        $display("  x  = %6d  (%.4f)", x_test,  xr_test);
        $display("  a0 = %6d  (%.4f)", a0_test, a0r_test);
        $display("  a1 = %6d  (%.4f)", a1_test, a1r_test);
        $display("  a2 = %6d  (%.4f)", a2_test, a2r_test);
        $display("\nExact real answer:      %.4f", yr_test);
        $display("Your expected_y():      %6d  (%.4f)",
                 y_test, real'(y_test) / (1 << FBITS));

        repeat (2) @(posedge clk);
        rst = 0;
        @(posedge clk);

        x  = x_test;
        a0 = a0_test;
        a1 = a1_test;
        a2 = a2_test;
    end

    // -------------------------------------------------------------------------
    // Monitor -- runs in parallel, printing the pipeline registers each clock.
    // -------------------------------------------------------------------------
    initial begin
        int cycle;

        $display("\n=== Pipeline registers, cycle by cycle ===");
        $display("Cycle |  x_s0 |  x2_s1 | ax1_s1 |  x_s1 |      y");
        $display("------|-------|--------|--------|-------|-------");

        for (cycle = 0; cycle < MONITOR_CYCLES; cycle++) begin
            @(posedge clk);
            #1;   // sample after the edge has settled
            $display("%5d | %5d | %6d | %6d | %5d | %6d",
                     cycle, dut.x_s0, dut.x2_s1, dut.ax1_s1, dut.x_s1, y);
        end

        // Both sides being zero is not agreement, it is two blanks matching.  The
        // unedited templates give exactly that -- expected_y() returns 0 and the
        // module holds its registers at 0 -- and calling it a pass would be the
        // most misleading thing this file could say to somebody who has not
        // started yet.  x_test is nonzero for any case worth running, so it is
        // what tells the two apart.
        if (y === '0 && y_test == 0 && x_test != 0) begin
            $display("\nNOT STARTED: the DUT gives 0 and expected_y() says 0, for an");
            $display("             input of x = %0d. That is not agreement, it is two",
                     x_test);
            $display("             unwritten TODOs matching. Fill in expected_y() above");
            $display("             and the marked blocks in cubic.sv.");
        end
        else if (y === WID'(y_test))
            $display("\nTEST PASSED: y = %0d, which is what expected_y() said.", y);
        else begin
            $display("\nTEST FAILED: the DUT gives y = %0d, expected_y() says %0d.",
                     y, y_test);
            $display("             One of the two is wrong. The register trace above");
            $display("             shows where they part company: check x2_s1 first,");
            $display("             since every later term is built from it.");
        end

        $display("\n=== Simulation complete ===");
        $finish;
    end

endmodule
