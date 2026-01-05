`timescale 1ns/1ps  

/*  
Linear ReLU Module
    
Performs a linear operation (multiplication) followed by a ReLU activation.

    y  = ReLU(w*x + b) = max(0, w*x + b)   
*/  
module lin_relu #(
    parameter WIDTH = 16
)(
    input  logic              clk,
    input  logic              rst,   // synchronous reset
    input  logic signed [WIDTH-1:0]  w_in,
    input  logic signed [WIDTH-1:0]  b_in,
    input  logic signed [WIDTH-1:0]  x_in,
    output logic signed [WIDTH-1:0]  y_out
);

    // Registered inputs
    logic signed [WIDTH-1:0] w_reg, b_reg, x_reg;

    // Intermediate value
    logic signed [WIDTH-1:0] u;

    // Register the inputs
    always_ff @(posedge clk) begin
        if (rst) begin
            w_reg <= '0;
            b_reg <= '0;
            x_reg <= '0;
        end else begin
            w_reg <= w_in;
            b_reg <= b_in;
            x_reg <= x_in;
        end
    end

    // Combinational output 
    always_comb begin
        u = w_reg * x_reg + b_reg;
        y_out = (u > 0) ? u : 0;
    end

endmodule