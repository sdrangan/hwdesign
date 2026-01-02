module tb_poly_fun;

    localparam WIDTH = 16;
    localparam time CLK_PERIOD = 10ns;  // 100 MHz clock

    logic clk = 0;
    logic rst = 1;
    logic signed [WIDTH-1:0] x_in;
    logic signed [WIDTH-1:0] y_out;

    // Clock generation
    always #(CLK_PERIOD/2) clk = ~clk;

    // Instantiate DUT
    poly_fun #(
        .WIDTH(WIDTH),
        .W2(3),
        .W1(2),
        .W0(4)
    ) dut (
        .clk(clk),
        .rst(rst),
        .x(x_in),
        .y(y_out)
    );

    // Test vector structure
    typedef struct {
        logic signed [WIDTH-1:0] x;
    } test_vector_t;

    initial begin
        // Define test vectors
        test_vector_t test_vectors[] = '{
            '{x: 5},
            '{x: -3},
            '{x: 10},
            '{x: 100},
            '{x: 0},
            '{x: 255}
        };

        // Local temporaries for expected value computation
        logic signed [WIDTH-1:0] x;
        logic signed [WIDTH-1:0] y_exp;

        // Reset for a few cycles
        repeat (3) @(posedge clk);
        rst = 0;

        // Because poly_fun has 3 pipeline stages:
        //   Stage 0: register x
        //   Stage 1:  compute x_sq and w1_x
        //   Stage 2: compute final y
        // → Latency = 3 cycles
        //
        // So after applying x_in, we wait 3 cycles before reading y_out.

        for (int i = 0; i < test_vectors.size(); i++) begin

            #(0.1*CLK_PERIOD) // hold time before changing input
            x_in = 'x;  // initial intedeterminate value
            #(0.15*CLK_PERIOD);  // Small delay for propagation time (before clock edge)
            x_in = test_vectors[i].x;

            // Clock cylce
            @(posedge clk);

            // Compute expected value for verification (optional)
            x  = test_vectors[i].x;
            y_exp = (3 * (x * x)) + (2 * x) + 4;

            $display("Test %0d: x_in=%0d, y_out=%0d, y_exp=%0d",
                     i, x, y_out, y_exp);
        end

        // Display y_out for the remaining pipeline stages
        for (int j = 0; j < 3; j++) begin
            @(posedge clk);
            $display("Pipeline flush %0d: y_out=%0d", j, y_out);
        end

        repeat (3) @(posedge clk);
        $finish;
    end

endmodule