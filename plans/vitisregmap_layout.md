# How Vitis HLS actually lays out an s_axilite register map

Findings from the `hwdesign` scalar_fun demo, for whoever maintains
`VitisRegMap` in waveflow. **Please confirm these against the model before
acting on them** — everything below is inferred from six synthesis runs on
one tool version, not documentation from AMD. The rule reproduces all 22
ports I have data for, which is evidence, not proof.

Environment for every run: Windows 11, Vitis HLS **2025.1**
(`C:\Xilinx\2025.1`), part `xc7z020clg484-1`, 10 ns clock, `csynth_design`
only. Scalar `s_axilite` ports, one bundle, `ap_ctrl_hs` (the default, via
`port=return`).

## Why this came up

The unit 4 problem set asked students for an IP's register map and its rubric
expected `AP_CTRL` at `0x00` with the arguments at consecutive **4-byte**
offsets. The demo's own co-simulation disagreed: its three inputs sit at
`0x10`, `0x18`, `0x20` and its output at `0x28`. The course material was
wrong and has been fixed. The open question is whether `VitisRegMap` carries
the same assumption.

## What the generated RTL says

Vitis writes the map into the generated `<top>_<bundle>_s_axi.v`, both as
comments and as machine-readable `localparam`s. This is the demo kernel,
`void simp_fun(int x, int w, int b, int& y)`:

```verilog
// 0x00 : Control signals        (ap_start bit 0, ap_done bit 1)
// 0x04 : Global Interrupt Enable Register
// 0x08 : IP Interrupt Enable Register
// 0x0c : IP Interrupt Status Register
// 0x10 : Data signal of x
// 0x14 : reserved
// 0x18 : Data signal of w
// 0x1c : reserved
// 0x20 : Data signal of b
// 0x24 : reserved
// 0x28 : Data signal of y
// 0x2c : Control signal of y
```

Three rules account for it, and they reproduce every map I have generated:

1. **A control block takes the first four registers.** `AP_CTRL`, `GIE`,
   `IP_IER`, `IP_ISR` at `0x00`-`0x0C`. Arguments therefore start at `0x10`,
   never at `0x04`.
2. **Each port takes ceil(W/32) data slots plus one control slot**, 4 bytes
   per slot. For an input the control slot reads `reserved`; for an output it
   carries an `ap_vld` bit. So the stride follows the **port** width, not the
   bus width - the AXI data bus is 32 bits throughout.
3. **An output port reserves two further slots** - 8 bytes - after its
   control slot. Nothing is documented there, and the header comments skip
   straight over it.

As an allocator, starting at `0x10`:

```python
def next_offset(off, width_bits, is_output):
    slots = (width_bits + 31) // 32 + 1 + (2 if is_output else 0)
    return off + 4 * slots
```

Rule 3 is the one worth dwelling on, because it is invisible in the common
case. A kernel whose only output is its last argument - which is most
teaching examples, including our own demo - never shows the gap, because
nothing follows it. It appears the moment a port follows an output.

## The evidence

Six kernels, 22 ports. The rule above predicts every offset:

| kernel | ports (in order) | offsets |
| --- | --- | --- |
| `simp_fun` | `x w b` in, `y` out | `0x10 0x18 0x20 0x28` |
| `diff_eq_solver` | `x0 a b N` in, `xN` out | `0x10 0x18 0x20 0x28 0x30` |
| `width_probe` | `c8 s16 i32 ll64` in, `out32 out64` out | `0x10 0x18 0x20 0x28 0x34 0x44` |
| `p_a` | `a` in, `o64` out | `0x10 0x18` |
| `p_b` | `a` in, `o32 o64` out | `0x10 0x18 0x28` |
| `p_c` | `a` in, `o32a o32b` out, `llin` in, `o64` out | `0x10 0x18 0x28 0x38 0x44` |

The three cases that isolate rule 3 are worth reading together:

- `p_a` - a 64-bit output straight after a 32-bit **input**: no gap, `o64`
  at `0x18`.
- `p_b` - the same 64-bit output after a 32-bit **output**: 8-byte gap,
  `o64` at `0x28`.
- `p_c` - two 32-bit outputs in a row, then a 64-bit **input**: a gap after
  *each* output, and none after the input. `o32a` `0x18`, `o32b` `0x28`,
  `llin` `0x38`, and then `o64` at `0x44` with no gap, because `llin` is an
  input.

So the gap belongs to the output that precedes it, not to the port that
follows, and not to any width or alignment boundary. `out64` at `0x44` in
`width_probe` is not 8-byte aligned, which rules alignment out directly.

## What I am asking you to check

1. **Does `VitisRegMap` assign byte offsets at all**, or only names and
   order? If it never claims an address, there is nothing to fix and this
   document is just useful background.
2. **If it does, what rule does it use?** Specifically whether it starts
   arguments at `0x10` and whether it gives each port a control slot.
3. **Was the model ever diffed against a generated `*_s_axi.v`?** The
   scalar_fun demo validated `transaction_cycles` against the cosim report —
   pure timing — while the addresses only ever appeared as decoded VCD values
   that nothing cross-checked. If the model's validation has the same shape,
   the layout may never have been tested even if the timing was.

## A test worth adding

The offsets are machine-readable, so this does not need a human in the loop.
Parse the `ADDR_*` localparams out of the generated
`<top>_<bundle>_s_axi.v` and compare them against the model:

```python
import re
addrs = dict(
    (m.group(1), int(m.group(2), 16))
    for m in re.finditer(r"ADDR_(\w+)\s*=\s*\d+'h([0-9a-fA-F]+)", verilog_text)
)
```

`p_c` is the fixture I would use — two consecutive outputs, a 64-bit input
after an output, and a 64-bit output after an input, so it exercises all
three rules at once:

```cpp
void p_c(int a, int &o32a, int &o32b, long long llin, long long &o64) {
    #pragma HLS INTERFACE s_axilite port=a      bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=o32a   bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=o32b   bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=llin   bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=o64    bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=return bundle=CTRL
    o32a = a; o32b = a + 1; o64 = llin;
}
```

Expected: `a` `0x10`, `o32a` `0x18`, `o32b` `0x28`, `llin` `0x38`,
`o64` `0x44`. `width_probe` adds the narrow widths (`char`, `short`) if you
want those covered too.

If `VitisRegMap` packs ports without rule 3, the symptom is that every offset
after the first output is short by 8 bytes per preceding output. That is a
quiet failure: the register *names* and their *order* stay correct, so a test
that only checks those will pass.

## Scope — what I did not test

Worth stating plainly, because the rules above may not generalise:

- **One Vitis version** (2025.1) and **one part**. The layout is a tool
  convention and could differ across versions.
- **Scalar ports only.** No arrays, no `m_axi`, no streams.
- **One bundle.** Multiple `s_axilite` bundles were not tried.
- **`ap_ctrl_hs` only.** Under `ap_ctrl_none` there is no `AP_CTRL`
  register, so the control block — and therefore the `0x10` start — is
  probably different.
- **Widths up to 64 bits.** `ap_int<128>` and structs untested; the
  ⌈W/32⌉ rule predicts four data slots plus one control slot, unverified.

## Reproducing

Each probe is a single `.cpp` plus a four-line `run.tcl`, about a minute of
`csynth_design`:

```tcl
open_project -reset probe_proj
set_top width_probe
add_files src/width_probe.cpp
open_solution -reset "solution1"
set_part {xc7z020clg484-1}
create_clock -period 10
csynth_design
exit 0
```

```bash
vitis-run --mode hls --tcl run.tcl      # --tcl is required
grep -E "^// 0x|ADDR_" probe_proj/solution1/syn/verilog/width_probe_CTRL_s_axi.v
```

The demo itself is in `hwdesign/demos/scalar_fun/scalar_fun_vitis`;
`python scalar_fun_build.py --through csynth` regenerates
`simp_fun_CTRL_s_axi.v`, and `docs/demos/procif/execution.md` is where the
course now explains the layout to students.
