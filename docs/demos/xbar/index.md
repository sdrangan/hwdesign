---
title: Crossbar or Shared Bus
parent: Demos
nav_order: 10
has_children: true
---

# Crossbar or Shared Bus

Unit 9 connects several masters to several memories. There are two ways to
build the interconnect between them:

- a **crossbar**: every master has a path to every slave, so transfers
  between *different* pairs run at the same time;
- a **shared bus**: one path, which every transfer takes in turn.

This demo measures what each one costs and what each one buys, on the
Pynq-Z2's Zynq-7020 at 100 MHz. Both are built from the same AMD IP,
`axi_crossbar`, which has a setting for exactly this choice:

| `CONNECTIVITY_MODE` | What it builds |
| --- | --- |
| `SAMD` (shared address, multiple data) | a crossbar: each master/slave pair has its own data path |
| `SASD` (shared address, shared data) | a shared bus: one transaction at a time, for the least area |

The demo answers three questions:

1. **Area.** How does each grow with the number of masters and slaves?
   See [Area](area.md).
2. **Throughput.** When several masters transfer at once, how long does it
   take, on each, when they go to different slaves, and when they all go
   to the same one? See [Latency and throughput](latency.md).
3. **Latency.** What does one transfer, on its own, cost on each? Also in
   [Latency and throughput](latency.md).

## What is measured, and how

All the crossbars have 64-bit data, the width of the Zynq-7020's HP ports
into DDR, and 32-bit addresses. Each slave has a 64 KB window.

- **Area** is measured by synthesizing, placing and routing each crossbar
  out of context in Vivado at 100 MHz. That takes about four minutes per
  crossbar, so it was done beforehand for every shape from 1x2 to 4x4,
  both modes, 32 and 64 bits: the results are in
  `demos/xbar/xbar_zynq7020_100mhz.csv`.
- **Latency** is measured live, in the Vivado simulator (XSI). The
  generated crossbar sits between C++ models of the masters (each issues
  AXI4 bursts) and of the memories (each serves one burst at a time). Every
  transfer is checked: a read must return what the matching write stored.
  A latency is counted in clock cycles, from the first address handshake
  to the last response.

## Running it

In `hwdesign-venv`, with Vivado installed, from `hwdesign/demos/xbar`:

```bash
(env) python xbar_demo.py
```

This prints the area table, generates the four crossbars (2x2 and 4x4,
crossbar and shared bus), simulates each, and prints area and latency side
by side. The first run takes about two minutes: about 20 s per crossbar
to generate the IP and about 15 s to compile and simulate it. After that
both are cached, and a second run takes a few seconds; `--fresh`
compiles the four simulations again, about a minute, so the class can
watch them run.

Other options:

```bash
(env) python xbar_demo.py --shapes 4x4                  # one shape, both modes
(env) python xbar_demo.py --through area                # only the cached area table
(env) python xbar_demo.py --fresh                       # compile the simulations again
(env) python xbar_demo.py --through synth               # place and route the 4x4 crossbar now
(env) python xbar_demo.py --through synth --synth-shape 2x2 --synth-mode SASD
```

`--through synth` runs Vivado on one crossbar, which takes about four
minutes, and prints its LUTs, FFs and slack beside the cached row: the
same numbers, measured again. Results go to `demos/xbar/results/`: the
tables in `report.md`, and the figures on the next two pages.

## The files

| File | What it is |
| --- | --- |
| `xbar_demo.py` | the demo: area, IP generation, simulation, the report and the figures |
| `xbar_zynq7020_100mhz.csv` | area (and latency) for every shape, measured beforehand |
| `xbar_import.py` | rewrites the CSV from a new sweep |

The area was measured with Waveflow's crossbar sweep,
`examples/xbar_profile` in the Waveflow repository:

```bash
python -m examples.xbar_profile.xbar_profile_sweep --part xc7z020clg400-1 --clk-mhz 100
python -m examples.xbar_profile.xbar_profile_table --part xc7z020clg400-1 --clk-mhz 100
```
