`timescale 1ns/1ps

module simp_fun #(
    parameter WIDTH = 16
)(
    input  logic              clk,
    input  logic              rst,   // synchronous reset
    input  logic [WIDTH-1:0]  a_in,
    input  logic [WIDTH-1:0]  b_in,
    output logic [WIDTH-1:0]  c_out
);

    // Registered inputs
    logic [WIDTH-1:0] a_reg, b_reg;

    // Register the inputs
    always_ff @(posedge clk) begin
        if (rst) begin
            a_reg <= '0;
            b_reg <= '0;
        end else begin
            a_reg <= a_in;
            b_reg <= b_in;
        end
    end

    // Registered output
    always_comb begin
        c_out = a_reg * b_reg;
    end

endmodule