#include <iostream>
#include <thread>
#include "fifofun.h"
#include "cmd.h"
#include "resp.h"

int main() {
    // Create input and output streams (now 32-bit AXI streams)
    hls::stream<stream_t> cmd_stream;
    hls::stream<stream_t> result_stream;
    
    // Control registers
    int cmd_count = 0;
    
    // Test cases
    Cmd test_cases[] = {
        {0, 3, 4},      
        {1, 7, 8},      
        {2, -5, 6},     
        {3, 0, 100},    
        {4, 15, -2}     
    };
   
    
    int num_tests = sizeof(test_cases) / sizeof(Cmd);
    int passed = 0;
    int failed = 0;
    
    std::cout << "Starting testbench for simp_fun()" << std::endl;
    std::cout << "====================================" << std::endl;
    
    // Push all test cases into the input FIFO using stream_write
    for (int i = 0; i < num_tests; i++) {
        Cmd cmd = test_cases[i];   
        cmd.stream_write<stream_t>(cmd_stream, true); // Assert TLAST on final word
        std::cout << "Wrote command " << i+1 << ": a=" << cmd.a << ", b=" << cmd.b << std::endl;
    }
    
    // Call simp_fun (processes all commands in the stream)
    simp_fun(cmd_stream, result_stream, cmd_count);        
    
    // Read and verify results using stream_read
    for (int i = 0; i < num_tests; i++) {
        // Read result from output stream
        Resp res, exp_res;
        bool tlast = res.stream_read<stream_t>(result_stream);

        // Expected results
        exp_res.trans_id = test_cases[i].trans_id;
        exp_res.c = test_cases[i].a * test_cases[i].b;
        exp_res.d = test_cases[i].a + test_cases[i].b;
        exp_res.err_code = 0; // No error expected
        
        // Check result
        std::cout << "Test " << i  << ":"; 
        
        if (res == exp_res) {
            std::cout << " [PASS]";
            passed++;
        } else {
            std::cout << " [FAIL]";
            failed++;
        }
        std::cout << "  Result: " << res.to_string();
        std::cout << "  Expected: " << exp_res.to_string();
        std::cout << "  TLAST: " << tlast << std::endl;
    }
    
    std::cout << "====================================" << std::endl;
    std::cout << "Tests passed: " << passed << "/" << num_tests << std::endl;
    std::cout << "Tests failed: " << failed << "/" << num_tests << std::endl;

    std::cout << "\nFinal control register states:" << std::endl;
    std::cout << "cmd_count: " << cmd_count << std::endl;
    
    
    if (failed == 0) {
        std::cout << "All tests passed!" << std::endl;
        return 0;
    } else {
        std::cout << "Some tests failed!" << std::endl;
        return 1;
    }

   
}