`timescale 1ns/1ps
// -----------------------------------------------------------------------------
// Module: poly_fun
// Description:
//   Computes the polynomial
//        y = W2*x^2 + W1*x + W0
//   using signed arithmetic with fixed WIDTH-bit results.
//   Pipeline:
//     Stage 0: register xreg <= x
//     Stage 1: compute xsq=xreg*xreg and lin_term= W1*xreg+W0
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
    logic signed [WIDTH-1:0] x_reg, lin_term, xsq;
    always_ff @(posedge clk) begin
        if (rst) begin
            x_reg <= '0;
            lin_term <= '0;
            xsq <= '0;
        end else begin
            x_reg <= x;
            lin_term <= (W1 * x_reg) + W0;  // WIDTH-bit wraparound
            xsq <= x_reg * x_reg;   // WIDTH-bit wraparound
        end
    end
    always_comb begin
        y = W2 * xsq + lin_term;  // WIDTH-bit wraparound
    end

endmodule