#include "fifofun.h"
#include "cmd.h"
#include "resp.h"

void simp_fun(
    hls::stream<stream_t>& cmd_stream,
    hls::stream<stream_t>& result_stream,
    int& cmd_count
) {
#pragma HLS INTERFACE axis port=cmd_stream
#pragma HLS INTERFACE axis port=result_stream
#pragma HLS INTERFACE s_axilite port=cmd_count
#pragma HLS INTERFACE s_axilite port=return
#pragma HLS INTERFACE ap_ctrl_chain port=return

    // Initialize static counter (persists across calls)
    static int count = 0;
    
    while (!cmd_stream.empty()) {
        Cmd cmd;

        // Read command from input FIFO using stream_read
        bool tlast_ok = cmd.stream_read<stream_t>(cmd_stream);

        if (!tlast_ok) {
            // Report error
            Resp res;
            res.trans_id = cmd.trans_id;
            res.err_code = 1;  // TLAST mismatch

            // Drain until TLAST to resync
            while (!cmd_stream.empty()) {
                auto w = cmd_stream.read();
                if (w.last) break;
            }

            // Write error response
            res.stream_write<stream_t>(result_stream);
            continue; // skip normal processing
        }


        // Update status registers
        count++;
        cmd_count = count;

        // Perform calculation
        Resp res;
        res.trans_id = cmd.trans_id;
        res.c = cmd.a * cmd.b;
        res.d = cmd.a + cmd.b;
        res.err_code = 0; // No error

        // Write result to output FIFO
        res.stream_write<stream_t>(result_stream, true); // Assert TLAST on final word
    }
}