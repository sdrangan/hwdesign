`timescale 1ns/1ps
// -----------------------------------------------------------------------------
// Module: poly_fun
// Description:
//   Computes the polynomial
//        y = W2*x^2 + W1*x + W0
//   using signed arithmetic with fixed WIDTH-bit results.
//   Pipeline:
//     Stage 0: register x
//     Stage 1:  compute x_sq and w1_x
//     Stage 2: compute final y
//   Bitwidths are constant, so arithmetic may overflow.
// -----------------------------------------------------------------------------
module poly_fun #(
    parameter int WIDTH = 16,
    parameter signed [WIDTH-1:0] W2 = 3,
    parameter signed [WIDTH-1:0] W1 = 2,
    parameter signed [WIDTH-1:0] W0 = 4
) (
    input  logic clk,
    input  logic rst,
    input  signed  [WIDTH-1:0] x,   
    output logic signed  [WIDTH-1:0] y
);

    // -------------------------
    // Stage 0: register x
    // -------------------------
    logic signed [WIDTH-1:0] x_s0;

    always_ff @(posedge clk) begin
        if (rst)
            x_s0 <= '0;
        else
            x_s0 <= x;
    end

    // -------------------------
    // Stage 1: compute x_sq and w1_x
    // -------------------------
    logic signed [WIDTH-1:0] x_sq_s1;
    logic signed [WIDTH-1:0] w1_x_s1;

    always_ff @(posedge clk) begin
        if (rst) begin
            x_sq_s1 <= '0;
            w1_x_s1 <= '0;
        end else begin
            x_sq_s1 <= x_s0 * x_s0;   // WIDTH-bit wraparound
            w1_x_s1 <= W1 * x_s0;     // WIDTH-bit wraparound
        end
    end

    // -------------------------
    // Stage 2: compute final y
    // -------------------------
    always_comb begin
        y = (W2 * x_sq_s1) + w1_x_s1 + W0;  // WIDTH-bit wraparound
    end

endmodule