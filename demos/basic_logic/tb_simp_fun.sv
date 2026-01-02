`timescale 1ns/1ps

module tb_simp_fun;

    localparam WIDTH = 16;
    localparam time CLK_PERIOD = 10ns;  // 100 MHz clock

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


    // Test vector structure
    typedef struct {
        logic [WIDTH-1:0] a;
        logic [WIDTH-1:0] b;
    } test_vector_t;

    initial begin
        // Define test vectors
        test_vector_t test_vectors[] = '{
            '{a: 5, b: 7},
            '{a: 10, b: 20},
            '{a: 100, b: 50},
            '{a: 0, b: 0},
            '{a: 255, b: 255}
        };

        // Reset for a few cycles
        repeat (3) @(posedge clk);
        rst = 0;

        // Loop through test vectors
        for (int i = 0; i < test_vectors.size(); i++) begin

            #(0.1*CLK_PERIOD) // hold time before changing input
            a_in = 'x;  // initial intedeterminate value
            b_in = 'x;  // initial intedeterminate value
            #(0.15*CLK_PERIOD);  // Small delay for propagation time (before clock edge)
            a_in = test_vectors[i].a;
            b_in = test_vectors[i].b;
            @(posedge clk);

            $display("Test %0d: a_in=%0d, b_in=%0d, c_out=%0d", i+1, a_in, b_in, c_out);
        end

        // Display c_out for the remaining pipeline stages
        for (int j = 0; j < 2; j++) begin
            @(posedge clk);
            $display("Pipeline flush %0d: c_out=%0d", j, c_out);
        end

        // Finish simulation
        repeat (3) @(posedge clk);
        $finish;
    end

endmodule