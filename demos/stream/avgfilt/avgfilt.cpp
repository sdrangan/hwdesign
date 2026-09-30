#include "avgfilt.h"
/*
Pure streaming window averaging of the 
last win_size=3 squared values:

    y[k] = (x[k]**2 + x[k-1]**2 + x[k-2]**2) / win_size

The value `win_size` is hardcoded
*/
void avgfilt(
    hls::stream<float>& in_stream, 
    hls::stream<float>& out_stream)
{

#pragma HLS INTERFACE axis port=in_stream
#pragma HLS INTERFACE axis port=out_stream
#pragma HLS INTERFACE ap_ctrl_none port=return

    // Last squared values
    static float xsq0 = 0.;
    static float xsq1 = 0.;

    constexpr float inv_win_size = 1/static_cast<float>(win_size);

    while (1) {
        // Exit when in_stream is empty.  This is for C simulation
        // only to support Vitis C call convention.
#ifndef __SYNTHESIS__
        if (in_stream.empty()) {
            break;
        }
#endif

#pragma HLS PIPELINE II=1
        // Read value
        float xi = in_stream.read();
        float xsq = xi*xi;

        // Output value
        float yi = (xsq + xsq0 + xsq1)*inv_win_size;
        out_stream.write(yi);

        // Update delay line
        xsq1 = xsq0;
        xsq0 = xsq;

    }

}

