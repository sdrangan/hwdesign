# The `poly` demo

A streaming polynomial with an **in-band command protocol**. The kernel
evaluates a cubic,

```
y = c[0] + c[1]*x + c[2]*x^2 + c[3]*x^3
```

on a stream of float samples. The coefficients arrive on the same stream
as the data, in a command header, so each transaction can use a different
polynomial. One transaction is:

```
in_stream:   PolyCmdHdr         |  x[0] ... x[nsamp-1]
out_stream:  PolyRespHdr  |  y[0] ... y[nsamp-1]  |  PolyRespFtr
```

Every `|` is a TLAST.

- `PolyCmdHdr` carries a transaction ID, the four coefficients and the
  number of samples.
- `PolyRespHdr` echoes the transaction ID, so the host can match the output
  to its command.
- `PolyRespFtr` says how many samples were read and whether anything went
  wrong, such as a TLAST in the wrong place or the wrong number of samples.

The kernel has no start or done (`ap_ctrl_none`): it handles one
transaction and is immediately ready for the next.

## What is hand-written and what is generated

| File | What it is |
| --- | --- |
| `poly32.cpp` | the kernel for a 32-bit stream, everything unpacked by hand, **hand-written** |
| `poly64.cpp` | the same for a 64-bit stream, two samples per word, **hand-written** |
| `poly.cpp`, `poly.hpp` | the general kernel, any width, using the generated headers, **hand-written** |
| `tb_poly.cpp` | the testbench, used for both C simulation and co-simulation, **hand-written** |
| `run.tcl` | the Vitis HLS script, one stage per invocation, **hand-written** |
| `poly_schema.py` | the messages, as waveflow data schemas |
| `poly_golden.py` | the test transactions and the Python golden model |
| `poly_timing.py` | decodes the messages from the VCD and plots them |
| `include/` | **generated** from `poly_schema.py` by the `gen_include` step |

The only generated code is the packing. Each schema becomes a C++ struct
with `read_axi4_stream<W>` / `write_axi4_stream<W>` methods, and
`float32_array_utils.h` does the same for arrays of float samples, all on
top of waveflow's `streamutils`. The Python side packs the same messages
with the same schemas. So the kernel, the testbench and the model cannot
disagree about which bits mean what, and none of them packs anything by
hand.

## Three versions of the kernel

The three kernel files each define the same `poly()`, and `--kernel` picks
which one is built. They are meant to be read in order:

1. **`poly32.cpp`** is for a 32-bit stream, with everything written out.
   It unpacks the command header word by word, converts each sample with
   `streamutils::uint_to_float`, packs the response header and footer by
   hand, and checks each TLAST itself.
2. **`poly64.cpp`** is the same for a 64-bit stream. The only new idea is
   two values per word: two samples per loop iteration, and two
   coefficients per header word.
3. **`poly.cpp`** is the general kernel. The generated headers do all the
   packing, and `pf`, the samples per word, covers both widths with one
   loop. It also recovers from a misplaced TLAST by flushing to the next
   one, which the teaching versions only report.

All three talk to the same testbench, and all are checked against the
same model.

```bash
python poly_build.py --kernel poly32 --force-step csim     # 32-bit, written out
python poly_build.py --kernel poly64 --force-step csim     # 64-bit, written out
python poly_build.py --force-step csim                     # the general kernel
```

`--kernel poly32` and `--kernel poly64` set the word width themselves.
`--force-step csim` is needed because an option is not a file: without it,
a build that is already up to date would not notice the change.

## The stream word width

`WORD_BW` is 32 or 64. `run.tcl` passes it to both the kernel and the
testbench as `-DWORD_BW=...`. A 32-bit word carries one float sample; a
64-bit word carries two, and the kernel evaluates both at once. The
kernel's only dependence on the width is `pf`, the samples per word. The
generated headers handle the rest: the command header is 6 words at 32
bits and fewer at 64.

**Known issue at 64 bits.** At `WORD_BW=64` the flow passes through
`verify_cosim`, but `timing_diagram` fails on the command header. For a
message that contains an array, waveflow's generated C++ currently packs
64-bit words differently from its Python schema, so the Python decoder
misreads `PolyCmdHdr` off the wires. The kernel and testbench are
unaffected, since both use the C++. The bug is written up in the pysilicon
repo as `plans/stream_array_alignment.md`. `poly64.cpp` unpacks the
command header by hand, in the layout the generated C++ uses today:
`[tx_id] [c0|c1] [c2|c3] [nsamp]`. If the fix changes that layout,
`poly64.cpp` has to change with it.

The test-vector files are sequences of 32-bit words, whatever the stream
width. The testbench packs them into stream words itself.

## Running it

Use the environment that has `waveflow` (`hwdesign-venv`). From `csim` on,
you also need Vitis HLS installed.

```bash
python poly_build.py --list-steps              # the sequence
python poly_build.py --through plot_python     # Python only, no Vitis
python poly_build.py --through verify_csim     # fast: no synthesis
python poly_build.py                           # the whole flow
```

A step is skipped when the files it depends on have not changed. Options
are not files, so an option only takes effect when its step runs, which
you force with `--force-step`:

```bash
python poly_build.py --word-bw 64 --force-step csim         # the general kernel at 64 bits
python poly_build.py --trace-level all --force-step cosim
python poly_build.py --trange 100 700 --force-step timing_diagram
```

`--force` re-runs everything, and `--status` says what is stale.
`--live-output` streams Vitis's output to the terminal; otherwise it is
saved to `results/<stage>/vitis.log`.

## The steps

```
gen_include --+
pysim --------+-> csim -> verify_csim -> csynth -> cosim -> verify_cosim
      |                                                  -> extract_vcd -> timing_diagram
      +-> plot_python
                                                    (all of it) -> report
```

- **gen_include** generates `include/` from `poly_schema.py`.
- **pysim** writes three test transactions to `vectors/`, each a command
  header and its samples, and the responses the model expects to
  `results/golden/`. The model is purely functional: it says what the
  responses contain, not when they appear.
- **plot_python** plots each transaction's polynomial to
  `results/poly_python.png`.
- **csim** runs the testbench against the C++ kernel. The testbench sends
  each command, calls `poly()` once per transaction, checks the response
  itself, and writes it to `results/csim/`.
- **verify_csim** compares every field of every response against the
  model: the echoed transaction ID, the footer, and each sample.
- **csynth** synthesizes the kernel. It waits for `verify_csim`.
- **cosim** runs the same testbench against the RTL, writing
  `results/cosim/` and recording the ports for the VCD.
- **verify_cosim** is the same comparison, for the RTL.
- **extract_vcd** re-runs the RTL simulation to get `vcd/dump.vcd`.
- **timing_diagram** splits each port into its TLAST-terminated bursts and
  unpacks each burst into its message with the schemas. It writes:
  - `results/timing_diagram.png`: transaction 0 cycle by cycle, with each
    burst shaded by the message it carries;
  - `results/transactions.png`: every message of every transaction on
    both ports, with stalls hatched;
  - `results/stream_timing.json`: the latency and transaction length per
    transaction.

  It fails if the messages on the wires are not the test vectors going in
  and the model's responses coming out.
- **report** collects the verdicts and the timing into
  `results/summary.json`.

## What the timing shows

At 32 bits, the first output sample appears 34 cycles after the first
input sample: the pipeline through three multiplies and three adds. After
that, one sample moves per cycle.

Transactions do not overlap. The next command header is accepted only once
the kernel has written the previous transaction's footer, so every
transaction pays the pipeline's fill and drain again. This shows as the
stalled command headers in `results/transactions.png`.
