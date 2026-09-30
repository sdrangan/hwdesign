---
title: C Simulation
parent: Command-Response FIFO Interface
nav_order: 7
has_children: false
---

# C Simulation

The first check on any of the three kernels is **C simulation**. Vitis
compiles a testbench together with the kernel into an ordinary program,
and runs it on your computer. This page describes the testbench, runs it,
and compares what came back against the Python model. The steps are the
same as in the [AXI4-Streaming demo](../stream/csim.md). What is new is
what gets checked: whole messages, not just samples.

Run everything below from `hwdesign/demos/stream/poly`, in the
[virtual environment](../../support/repo/package.md) that has `waveflow`,
with Vitis HLS installed.

## The testbench

The testbench, `tb_poly.cpp`, is a C++ program with a `main()`. It serves
all three kernels, since they all define the same `poly()`. It takes two
directories on the command line, which `run.tcl` passes:

* `vectors/`, where it reads the commands the Python model wrote;
* `results/csim/` (or `results/cosim/` in co-simulation), where it writes
  the responses it got back.

Unlike the teaching kernels, the testbench uses the
[generated headers](./vitis_general.md) to pack and unpack messages. The
testbench is not what we are studying. And because it packs with the
generated code while `poly32.cpp` and `poly64.cpp` unpack by hand, a pass
also shows that the hand-written layout matches the generated one.

For each transaction, it does four things.

**1. Send one command.** Read the command header and the input samples
from the files the Python model wrote, and write them to `in_stream`:

~~~cpp
        // ----- Send one command -----
        PolyCmdHdr cmd_hdr;
        streamutils::read_uint32_file(cmd_hdr, txn_file(in_dir, k, "cmd_hdr").c_str());
        const int nsamp = cmd_hdr.nsamp;
        std::vector<float> x(nsamp), y(nsamp);
        float32_array_utils::read_uint32_file_array(
            x.data(), txn_file(in_dir, k, "samp_in").c_str(), nsamp);

        cmd_hdr.write_axi4_stream<WORD_BW>(in_stream, true);
        float32_array_utils::write_axi4_stream<WORD_BW>(in_stream, x.data(), true, nsamp);
~~~

**2. Call the kernel once.** One call is one transaction:

~~~cpp
        poly(in_stream, out_stream);
~~~

**3. Receive the response.** Read the response header, the samples and
the footer from `out_stream`, noting where TLAST fell in each, and write
each to a file:

~~~cpp
        // ----- Receive the response -----
        PolyRespHdr resp_hdr;
        streamutils::tlast_status hdr_tlast = streamutils::tlast_status::no_tlast;
        resp_hdr.read_axi4_stream<WORD_BW>(out_stream, hdr_tlast);

        streamutils::tlast_status samp_tlast = streamutils::tlast_status::no_tlast;
        float32_array_utils::read_axi4_stream<WORD_BW>(out_stream, y.data(), samp_tlast, nsamp);

        PolyRespFtr resp_ftr;
        streamutils::tlast_status ftr_tlast = streamutils::tlast_status::no_tlast;
        resp_ftr.read_axi4_stream<WORD_BW>(out_stream, ftr_tlast);

        streamutils::write_uint32_file(resp_hdr, txn_file(out_dir, k, "resp_hdr").c_str());
        float32_array_utils::write_uint32_file_array(
            y.data(), txn_file(out_dir, k, "samp_out").c_str(), nsamp);
        streamutils::write_uint32_file(resp_ftr, txn_file(out_dir, k, "resp_ftr").c_str());
~~~

**4. Check it.** Compare each sample against the testbench's own Horner
evaluation, and check the echoed `tx_id`, the footer and every TLAST:

~~~cpp
        const bool framing_ok = hdr_tlast == streamutils::tlast_status::tlast_at_end
                                && samp_tlast == streamutils::tlast_status::tlast_at_end
                                && ftr_tlast == streamutils::tlast_status::tlast_at_end;
        const bool ok = nbad == 0 && framing_ok
                        && resp_hdr.tx_id == cmd_hdr.tx_id
                        && resp_ftr.error == PolyError::NO_ERROR
                        && (int)resp_ftr.nsamp_read == nsamp;
~~~

It prints `PASS` or `FAIL` for each transaction. It returns non-zero if
any failed, and Vitis reads that return code, so a failing testbench
fails the Vitis run.

A few details are worth knowing:

* **The files carry no word width.** They are sequences of 32-bit words,
  packed by the schemas. The testbench packs them into 32- or 64-bit
  stream words itself, so the same test vectors serve every kernel.
* **The paths are absolute**, because co-simulation runs the testbench
  from deep inside the Vitis project directory.
* **The `_tb.h` headers must be included before `poly.hpp`:**

  ~~~cpp
  #include "include/streamutils_tb.h"
  #include "include/float32_array_utils_tb.h"
  #include "include/poly_cmd_hdr_tb.h"
  #include "include/poly_resp_hdr_tb.h"
  #include "include/poly_resp_ftr_tb.h"
  #include "poly.hpp"
  ~~~

  Each `_tb.h` adds its testbench-only methods, such as
  `read_uint32_file`, by including the main header with an extra macro
  defined. That only works if the main header has not already been
  included, which `poly.hpp` would do. The wrong order is a compile error
  about "out-of-line definition of `dump_json`".

## Choosing the kernel

The build compiles one of the three kernels, named with `--kernel`:

| `--kernel` | File | Word width |
| --- | --- | --- |
| `poly32` | `poly32.cpp` | 32 |
| `poly64` | `poly64.cpp` | 64 |
| `general` (the default) | `poly.cpp` | 32, or 64 with `--word-bw 64` |

When you switch kernels, add `--force-step csim`:

~~~bash
(env) python poly_build.py --through verify_csim --kernel poly32 --force-step csim
~~~

An option is not a file, so without `--force-step` a build that is
already up to date would not notice that you asked for a different
kernel. Forcing `csim` re-runs it, and every later step re-runs after it.

The steps below use the default, the general kernel at 32 bits. The
three kernels give identical results.

## Step 4: Run C simulation (`csim`)

~~~bash
(env) python poly_build.py --through csim
~~~

~~~text
csim:
    results\csim
    RUNNING...
Vitis HLS stage 'csim' done (kernel general, WORD_BW=32); log in results\csim\vitis.log
    PASSED
~~~

If you have not run the earlier steps, `--through csim` runs `gen_include`
and `pysim` first, because C simulation needs the headers and the
vectors.

Vitis's output goes to `results/csim/vitis.log`. The testbench's own lines
are in there:

~~~text
tb_poly: 3 transactions, WORD_BW=32
txn 0: tx_id=0x10 echoed 0x10, nsamp=40 nsamp_read=40, error=0  PASS
txn 1: tx_id=0x11 echoed 0x11, nsamp=64 nsamp_read=64, error=0  PASS
txn 2: tx_id=0x12 echoed 0x12, nsamp=25 nsamp_read=25, error=0  PASS
tb_poly PASSED (3 transactions)
~~~

The testbench wrote each response to `results/csim/`, under the same file
names as the expected ones in `results/golden/`.

## Step 5: Compare against the model (`verify_csim`)

The testbench checked the kernel against its *own* Horner evaluation. If
you misunderstood the protocol, you could write the kernel and the
testbench with the same mistake, and it would still print `PASS`. So the
build also compares against the independent Python model:

~~~bash
(env) python poly_build.py --through verify_csim
~~~

~~~text
verify_csim:
    results\verify_csim.json
    RUNNING...
txn 0 (tx_id 0x10): 40 of 40 samples bit-exact, max |error| = 0; tx_id echoed 0x10, footer 40 read, NO_ERROR
txn 1 (tx_id 0x11): 64 of 64 samples bit-exact, max |error| = 0; tx_id echoed 0x11, footer 64 read, NO_ERROR
txn 2 (tx_id 0x12): 25 of 25 samples bit-exact, max |error| = 0; tx_id echoed 0x12, footer 25 read, NO_ERROR
    PASSED
~~~

For each transaction, the step unpacks the testbench's response files with
the schemas and compares **every field** against the model's:

* the response header's `tx_id`, which must echo the command's;
* the footer's `nsamp_read` and `error`;
* every output sample, which must be within a small tolerance. It reports
  how many are bit-exact, and all of them are.

Checking the header and footer matters as much as checking the samples. A
kernel that computes the right numbers but echoes the wrong `tx_id` would
have the host file its results under the wrong command, and a correct
`y` would not reveal that.

The full report is in `results/verify_csim.json`. It lists each
transaction's fields and any failures.

---

Go to [Synthesis and Co-simulation](./poly_cosim.md)
