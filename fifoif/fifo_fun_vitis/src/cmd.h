#ifndef CMD_H
#define CMD_H

#include <hls_stream.h>
#include <ap_int.h>
#include <ap_axi_sdata.h>
#include <string>
#include <sstream>

class Cmd {
public:

    ap_int<16> trans_id;
    ap_int<32> a;
    ap_int<32> b;

    template<typename Tstream>
    bool stream_read_32(hls::stream<Tstream>& in) {
        constexpr int bus_bits = decltype(Tstream::data)::width;
        static_assert(bus_bits == 32, "Only 32-bit stream supported in Cmd::stream_read_32");

        Tstream w0 = in.read();
        trans_id = w0.data.range(15, 0);
        Tstream w1 = in.read();
        a = w1.data;
        Tstream w2 = in.read();
        b = w2.data;
        bool tlast = w2.last;

        return tlast;
    }

    template<typename Tstream>
    void stream_write_32(hls::stream<Tstream>& out, bool tlast = true) const {
        constexpr int bus_bits = decltype(Tstream::data)::width;
        static_assert(bus_bits == 32, "Only 32-bit stream supported in Cmd::stream_write_32");

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
        w1.data = a;
        w1.last = false;
        out.write(w1);

        Tstream w2;
        w2.data = 0;
        w2.keep = -1;
        w2.strb = -1;
        w2.data = b;
        w2.last = tlast;
        out.write(w2);
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

    bool operator==(const Cmd& other) const {
        return (this->trans_id == other.trans_id) && (this->a == other.a) && (this->b == other.b);
    }

    std::string to_string() const {
        std::ostringstream oss;
        oss << "{";
        oss << "trans_id: " << trans_id << ", ";
        oss << "a: " << a << ", ";
        oss << "b: " << b;
        oss << "}";
        return oss.str();
    }

};

#endif // CMD_H
