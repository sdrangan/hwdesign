`timescale 1ns/1ps
// -----------------------------------------------------------------------------
// subc_divide:  integer division by conditional subtraction
//
//   Computes z such that  z/2**nbits  <=  a/b  <  z/2**nbits + 2**-nbits,
//   for 0 <= a < b.  This is the same algorithm as subc_divide.py, and the lab
//   checks that the two agree on every case.
//
//   The operation takes a variable number of clock cycles -- one per quotient
//   bit -- so inputs and outputs are transferred with a handshake rather than
//   being available every cycle:
//
//       inputs   accepted when  inready  & invalid
//       output   accepted when  outvalid & outready
//
//   Three states manage it.  IDLE asserts inready and waits for invalid; RUN
//   performs one iteration per clock for nbits clocks; DONE asserts outvalid
//   and waits for outready.  The lab page works through each one.
// -----------------------------------------------------------------------------

module subc_divide(
    input  logic         clk,
    input  logic         rst,

    // Handshake for inputs
    input  logic         invalid,
    output logic         inready,

    // Inputs
    input  logic [31:0]  a,
    input  logic [31:0]  b,
    input  logic [5:0]   nbits,     // runtime number of iterations (0–32)

    // Handshake for outputs
    input  logic         outready,
    output logic         outvalid,

    // Output
    output logic [31:0]  z
);

    // Internal registers
    logic [31:0] a_reg, b_reg;
    logic [31:0] z_reg;
    logic [5:0]  count;

    typedef enum logic [1:0] {
        IDLE,
        RUN,
        DONE
    } state_t;

    state_t state, state_next;
    logic [31:0] z_next, a_next, b_next;
    logic [5:0]  count_next;

    // TODO:  Complete the code for the divide operation.  See the block below.
    // Write two blocks: an `always_comb` that computes the next value of every
    // register from the current ones, and an `always_ff @(posedge clk)` that
    // commits them.  Splitting it that way is the standard shape for a state
    // machine -- the decisions are in one place and the clocking in another.
    //
    // The combinational block must assign *every* _next signal on *every* path,
    // or you infer a latch.  The usual way is to start with defaults that hold
    // the current value, then override them per state:
    //
    //     a_next = a_reg;  b_next = b_reg;  z_next = z_reg;
    //     count_next = count;  state_next = state;
    //
    // Then, per state:
    //
    //   IDLE  -- when invalid, register a, b into a_reg, b_reg, clear z_next
    //            and count_next, and go to RUN.
    //
    //   RUN   -- one iteration of the algorithm, exactly as in subc_divide.py:
    //            shift z_reg and a_reg left by one, and if the shifted a is at
    //            least b_reg, subtract b_reg from it and set the low bit of z.
    //            Increment count.  After nbits iterations, go to DONE.
    //
    //            Careful: compare the *shifted* value against b_reg, not a_reg.
    //
    //   DONE  -- when outready, go back to IDLE.
    //
    // Then drive the three outputs from the *current* state, not the next one:
    //
    //     inready  = (state == IDLE);
    //     outvalid = (state == DONE);
    //     z        = z_reg;
    //
    // The sequential block resets state to IDLE and the registers to zero when
    // rst is high, and otherwise copies each _next signal into its register.
    //
    // Delete the placeholder block below when you write yours -- the outputs
    // must be driven in exactly one always_comb.
    // Placeholder: drives the outputs so the module elaborates and the
    // testbench runs to completion.  It computes nothing.
    always_comb begin
        a_next     = a_reg;
        b_next     = b_reg;
        z_next     = z_reg;
        count_next = count;
        state_next = state;

        inready  = 1'b1;
        outvalid = 1'b0;
        z        = 32'd0;
    end

endmodule
