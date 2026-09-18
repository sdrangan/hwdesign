`timescale 1ns/1ps
// -----------------------------------------------------------------------------
// cubic_fixed:  a monic cubic polynomial in fixed point
//
//     y = x**3 + a2*x**2 + a1*x + a0
//
//   Every port is Q(WID, FBITS): a signed WID-bit integer standing for the real
//   number (integer / 2**FBITS).  The module is the same arithmetic as
//   cubic_fixed() in cubic_model.py, and the lab checks that the two agree
//   exactly -- including on the cases where a value does not fit and has to be
//   clamped.  "Nearly the same" is not a passing answer here: an off-by-one in
//   a shift shows up as a few hundred disagreeing cases, and a missing
//   saturation shows up only at FBITS=12.
//
//   Two facts drive the whole implementation:
//
//     * A product of two Q(WID, FBITS) values has 2*FBITS fractional bits, so
//       it must be shifted right by FBITS to be Q(., FBITS) again.  `>>>` is
//       the *arithmetic* shift: it copies the sign bit down, which is what a
//       signed value needs and what Python's `>>` also does.
//
//     * That product also needs more integer bits than WID has.  The
//       intermediates are therefore held in WID_ACC bits, which is wide enough
//       that nothing wraps on the way, and the `sat` function below clamps back
//       to WID at each point where the model does.
//
//   The three-stage pipeline
//   ------------------------
//   Stage 0 registers the inputs.  Stage 1 computes the square and the linear
//   term, and carries x and a2 forward for the stage that needs them.  Stage 2
//   is combinational: it builds the cubic and quadratic terms from the
//   registered square and sums everything.
//
//     stage 0:  x_s0, a0_s0, a1_s0, a2_s0            <= x, a0, a1, a2
//     stage 1:  x2_s1  <= sat((x_s0*x_s0) >>> FBITS)
//               ax1_s1 <= sat(((a1_s0*x_s0) >>> FBITS) + a0_s0)
//               x_s1, a2_s1 <= x_s0, a2_s0
//     stage 2:  x3    = sat((x_s1*x2_s1) >>> FBITS)
//               ax2   = sat((a2_s1*x2_s1) >>> FBITS)
//               y     = sat(x3 + ax2 + ax1_s1)
//
//   Note that x3 and ax2 are built from the *saturated* x2_s1, not from a fresh
//   product.  Your Python does the same thing, and if one of them re-derives
//   the square the two will differ on exactly the cases that saturate.
//
//   WID_ACC is chosen for you and is not something to tune.  You should not
//   need to change any declaration in this file -- only the marked assignments.
// -----------------------------------------------------------------------------
module cubic_fixed #(
    parameter int WID     = 16,   // total bit width
    parameter int FBITS   = 8     // fractional bits
)(
    input  logic                        clk,
    input  logic                        rst,

    // Inputs in Q(WID, FBITS)
    input  logic signed [WID-1:0]       x,
    input  logic signed [WID-1:0]       a0,
    input  logic signed [WID-1:0]       a1,
    input  logic signed [WID-1:0]       a2,

    // Output in Q(WID, FBITS)
    output logic signed [WID-1:0]       y
);

    // Accumulator width: wide enough that a product of two WID-bit values, and
    // then a sum of three of them, cannot wrap before `sat` gets to decide what
    // to do about it.  Floored at 32 so the arithmetic below is done in at
    // least an int's worth of bits whatever WID and FBITS are set to.
    localparam int WID_ACC1 = 2*WID - FBITS + 2;
    localparam int WID_ACC  = (WID_ACC1 > 32) ? WID_ACC1 : 32;

    // Stage 0 registers:  Q(WID, FBITS)
    logic signed [WID-1:0] x_s0, a0_s0, a1_s0, a2_s0;

    // Stage 1 registers, held wide:  Q(WID_ACC, FBITS), but every one of them
    // holds a value that `sat` has already clamped to WID bits.
    logic signed [WID_ACC-1:0] a2_s1, x_s1, x2_s1, ax1_s1;

    // Stage 1 next values
    logic signed [WID_ACC-1:0] x2_s1_next, ax1_s1_next;

    // Stage 2 combinational signals
    logic signed [WID_ACC-1:0] ax2, x3, yfull;

    // -------------------------------------------------------------------------
    // Saturation: clamp to the signed WID-bit range.
    //
    // This is the SystemVerilog spelling of waveflow's `saturate(value, wid)`,
    // which cubic_model.py uses.  Given -- but read it, because where you call
    // it is the design decision, and the two files have to make the same one.
    // -------------------------------------------------------------------------
    function automatic logic signed [WID_ACC-1:0] sat (
        input logic signed [WID_ACC-1:0] in_val
    );
        logic signed [WID_ACC-1:0] max_val, min_val;
        begin
            max_val = (WID_ACC'(1) <<< (WID - 1)) - 1;
            min_val = -(WID_ACC'(1) <<< (WID - 1));
            if (in_val > max_val)
                sat = max_val;
            else if (in_val < min_val)
                sat = min_val;
            else
                sat = in_val;
        end
    endfunction

    // -------------------------------------------------------------------------
    // Stage 1 next values, and the stage 2 combinational output
    // -------------------------------------------------------------------------
    always_comb begin

        // TODO:  Compute the stage 1 next values and the stage 2 output.
        //
        //     x2_s1_next  = ...    x**2
        //     ax1_s1_next = ...    a1*x + a0
        //     ax2         = ...    a2*x**2
        //     x3          = ...    x**3
        //     yfull       = ...    the sum of the three terms
        //     y           = ...    yfull, in WID bits
        //
        // The pattern for one product is
        //
        //     sat( (p * q) >>> FBITS )
        //
        // Four things to be careful about:
        //
        //   * `>>>` is the arithmetic shift.  `>>` would shift zeros into the
        //     top of a negative value and turn it into a large positive one.
        //
        //   * a0 is not a product.  Add it *after* the shift, not before.
        //
        //   * Parenthesise.  `>>>` binds looser than `+` in SystemVerilog, so
        //     `(a1_s0 * x_s0) >>> FBITS + a0_s0` shifts by `FBITS + a0_s0`,
        //     which is not what you meant and will not warn you.
        //
        //   * Build x**3 from `x_s1 * x2_s1`, the registered square -- not from
        //     a fresh `x_s1 * x_s1 * x_s1`, which needs a different shift and
        //     saturates in a different place from your Python model.
        //
        // `yfull` is WID_ACC bits and `y` is WID.  `sat` has already brought the
        // value into range, so taking the low WID bits is safe -- but take them
        // explicitly (`yfull[WID-1:0]`) rather than relying on the assignment to
        // truncate quietly.
        x2_s1_next  = '0;
        ax1_s1_next = '0;
        ax2         = '0;
        x3          = '0;
        yfull       = '0;
        y           = '0;
    end

    // -------------------------------------------------------------------------
    // The pipeline registers
    // -------------------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (rst) begin
            x_s0   <= '0;
            a0_s0  <= '0;
            a1_s0  <= '0;
            a2_s0  <= '0;

            a2_s1  <= '0;
            x_s1   <= '0;
            x2_s1  <= '0;
            ax1_s1 <= '0;
        end else begin
            // TODO:  Commit both pipeline stages.
            //
            //   Stage 0 -- register the four inputs into their _s0 copies:
            //
            //       x_s0  <= ...
            //       a0_s0 <= ...
            //       ...
            //
            //   Stage 1 -- register the two values the always_comb above
            //   computed, and carry x and a2 forward one more stage, since
            //   stage 2 needs them alongside the square:
            //
            //       x2_s1  <= ...
            //       ax1_s1 <= ...
            //       x_s1   <= ...
            //       a2_s1  <= ...
            //
            // Use `<=` here, not `=`.  Every right-hand side in this block must
            // read the value a signal had *before* this clock edge; with `=`,
            // `x_s1 <= x_s0` would pick up the x_s0 assigned two lines earlier
            // and the pipeline would collapse into a single stage.
            x_s0   <= x_s0;
            a0_s0  <= a0_s0;
            a1_s0  <= a1_s0;
            a2_s0  <= a2_s0;
            a2_s1  <= a2_s1;
            x_s1   <= x_s1;
            x2_s1  <= x2_s1;
            ax1_s1 <= ax1_s1;
        end
    end

endmodule
