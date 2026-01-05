module tb_lin_relu;

    localparam WIDTH = 16;
    localparam time CLK_PERIOD = 10ns;  // 100 MHz clock

    logic clk = 0;
    logic rst = 1;
    logic signed [WIDTH-1:0] x_in;
    logic signed [WIDTH-1:0] w_in;
    logic signed [WIDTH-1:0] b_in;
    logic signed [WIDTH-1:0] y_out;

    // Clock generation
    always #(CLK_PERIOD/2) clk = ~clk;

    // Instantiate DUT
    lin_relu #(
        .WIDTH(WIDTH)
    ) dut (
        .clk(clk),
        .rst(rst),
        .w_in(w_in),
        .b_in(b_in),
        .x_in(x_in),
        .y_out(y_out)
    );

    // Test vector structure
    typedef struct {
        logic signed [WIDTH-1:0] x;
        logic signed [WIDTH-1:0] w;
        logic signed [WIDTH-1:0] b;
    } test_vector_t;

    initial begin
        // Define test vectors
        test_vector_t test_vectors[] = '{
            '{x: 10,  w: 3,  b: 15},
            '{x: -4, w: 10,  b: 4},
            '{x: 8, w: 12,  b: -5}
        };

        // Local temporaries for expected value computation
        logic signed [WIDTH-1:0] x;
        logic signed [WIDTH-1:0] w;
        logic signed [WIDTH-1:0] b;
        logic signed [WIDTH-1:0] y_exp;

        // Reset for a few cycles
        repeat (1) @(posedge clk);
        rst = 0;

        
        for (int i = 0; i < test_vectors.size(); i++) begin

            #(0.1*CLK_PERIOD) // hold time before changing input
            x_in = 'x;  // initial intedeterminate value
            w_in = 'x;
            b_in = 'x;
            #(0.15*CLK_PERIOD);  // Small delay for propagation time (before clock edge)
            x_in = test_vectors[i].x;
            w_in = test_vectors[i].w;
            b_in = test_vectors[i].b;

            // Clock cylce
            @(posedge clk);

            // Compute expected value for verification (optional)
            x  = test_vectors[i].x;
            w  = test_vectors[i].w;
            b  = test_vectors[i].b;
            y_exp = (w * x + b > 0) ? (w * x + b) : 0;

            $display("Test %0d: x_in=%0d, y_out=%0d, y_exp=%0d",
                     i, x, y_out, y_exp);
        end

        // Display y_out for the remaining pipeline stages
        for (int j = 0; j < 2; j++) begin
            @(posedge clk);
            $display("Pipeline flush %0d: y_out=%0d", j, y_out);
        end

        repeat (1) @(posedge clk);
        $finish;
    end

endmodule