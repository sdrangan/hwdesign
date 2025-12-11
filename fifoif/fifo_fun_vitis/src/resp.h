#ifndef RESP_H
#define RESP_H

#include <hls_stream.h>
#include <ap_int.h>
#include <ap_axi_sdata.h>
#include <string>
#include <sstream>

class Resp {
public:

    ap_int<16> trans_id;
    ap_int<32> c;
    ap_int<32> d;
    ap_int<8> err_code;

    template<typename Tstream>
    bool stream_read_32(hls::stream<Tstream>& in) {
        constexpr int bus_bits = decltype(Tstream::data)::width;
        static_assert(bus_bits == 32, "Only 32-bit stream supported in Resp::stream_read_32");

        Tstream w0 = in.read();
        trans_id = w0.data.range(15, 0);
        Tstream w1 = in.read();
        c = w1.data;
        Tstream w2 = in.read();
        d = w2.data;
        Tstream w3 = in.read();
        err_code = w3.data.range(7, 0);
        bool tlast = w3.last;

        return tlast;
    }

    template<typename Tstream>
    void stream_write_32(hls::stream<Tstream>& out, bool tlast = true) const {
        constexpr int bus_bits = decltype(Tstream::data)::width;
        static_assert(bus_bits == 32, "Only 32-bit stream supported in Resp::stream_write_32");

        Tstream w0;
        w0.data = 0;
        w0.keep = -1;
        w0.strb = -1;
        w0.data.range(15, 0) = trans_id;
        w0.last = false;
        out.write(w0);

        Tstream w1;
        w1.data = 0;
        w1.keep = -1;
        w1.strb = -1;
        w1.data = c;
        w1.last = false;
        out.write(w1);

        Tstream w2;
        w2.data = 0;
        w2.keep = -1;
        w2.strb = -1;
        w2.data = d;
        w2.last = false;
        out.write(w2);

        Tstream w3;
        w3.data = 0;
        w3.keep = -1;
        w3.strb = -1;
        w3.data.range(7, 0) = err_code;
        w3.last = tlast;
        out.write(w3);
    }

    template<typename Tstream>
    void stream_write(hls::stream<Tstream>& out, bool tlast = true) const {
        constexpr int bus_bits = decltype(Tstream::data)::width;
        if constexpr (bus_bits == 32) {
            stream_write_32(out, tlast);
        } else {
            static_assert(bus_bits == 32, 
                         "Unsupported bus width. Supported widths: 32");
        }
    }

    template<typename Tstream>
    bool stream_read(hls::stream<Tstream>& in) {
        constexpr int bus_bits = decltype(Tstream::data)::width;
        if constexpr (bus_bits == 32) {
            return stream_read_32(in);
        } else {
            static_assert(bus_bits == 32, 
                         "Unsupported bus width. Supported widths: 32");
            return false;
        }
    }

    bool operator==(const Resp& other) const {
        return (this->trans_id == other.trans_id) && (this->c == other.c) && (this->d == other.d) && (this->err_code == other.err_code);
    }

    std::string to_string() const {
        std::ostringstream oss;
        oss << "{";
        oss << "trans_id: " << trans_id << ", ";
        oss << "c: " << c << ", ";
        oss << "d: " << d << ", ";
        oss << "err_code: " << err_code;
        oss << "}";
        return oss.str();
    }

};

#endif // RESP_H
