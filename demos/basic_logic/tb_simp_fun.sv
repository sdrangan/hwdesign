`timescale 1ns/1ps

module tb_simp_fun;

    localparam WIDTH = 8;
    localparam CLK_PERIOD = 10;  // 100 MHz clock

    logic clk = 0;
    logic rst = 1;
    logic [WIDTH-1:0] a_in, b_in;
    logic [WIDTH-1:0] c_out;

    
    always #(CLK_PERIOD/2) clk = ~clk;   

    simp_fun #(
        .WIDTH(WIDTH)
    ) dut (
        .clk(clk),
        .rst(rst),
        .a_in(a_in),
        .b_in(b_in),
        .c_out(c_out)
    );


    initial begin
        // Reset for a few cycles
        repeat (3) @(posedge clk);
        rst = 0;

        // Test 1
        a_in = 5;
        b_in = 7;
        @(posedge clk);
        $display("Test 1: a_in=%0d, b_in=%0d, c_out=%0d", a_in, b_in, c_out);

        

        // Test 2
        a_in = 10;
        b_in = 20;
        @(posedge clk);
        $display("Test 2: a_in=%0d, b_in=%0d, c_out=%0d", a_in, b_in, c_out);

        // Test 3
        a_in = 100;
        b_in = 50;
        @(posedge clk);
        $display("Test 3: a_in=%0d, b_in=%0d, c_out=%0d", a_in, b_in, c_out);

        repeat (3) @(posedge clk);
        $finish;
    end

endmodule