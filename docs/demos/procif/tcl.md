---
title: The Vitis TCL Script
parent: Bus Basics and Memory‑Mapped Interfaces
nav_order: 2
has_children: false
---

# The Vitis TCL Script

Vitis HLS is driven by **TCL**. Whether you click buttons in the GUI or run a
build script, the same TCL commands end up being executed — the GUI just writes
them for you, somewhere you do not see.

In this demo the TCL is written by hand, in `run.tcl`. Nothing generates it.
That is deliberate: it is the whole interface between our project and the tool,
and it is short enough to read in one sitting. If you can read this file, you
know exactly what Vitis has been told to do.

See also the waveflow guide on
[Authoring run.tcl](https://sdrangan.github.io/waveflow/docs/guide/build/tcl.html).

## Setting up the project

The first block describes *what* to build:

~~~tcl
open_project scalar_fun_proj
set_top simp_fun
add_files src/scalar_fun.cpp -cflags "-Isrc"
add_files -tb testbench/tb_scalar_fun.cpp -cflags "-Isrc"
~~~

| Command | What it does |
|---|---|
| `open_project` | creates (or re-opens) the project directory `scalar_fun_proj` |
| `set_top` | names the function to synthesize into hardware — the **top** |
| `add_files` | adds design sources; these become hardware |
| `add_files -tb` | adds testbench sources; these stay software and are never synthesized |

The `-tb` distinction is the important one. `simp_fun` becomes an FPGA circuit;
`main()` stays an ordinary program that drives it. Mixing them up is a common
first mistake — anything you `add_files` without `-tb` must be synthesizable
C++, so no `iostream`, no `new`, no unbounded loops.

`-cflags "-Isrc"` just puts `src/` on the include path so both files can find
`scalar_fun.h`.

## Choosing the target

~~~tcl
open_solution "solution1"
set_part {xc7z020clg484-1}
create_clock -period 10
~~~

A **solution** is one set of build settings; a project can hold several, which
is how you compare optimization strategies later in the course. `set_part`
names the FPGA — this one is the Zynq device on the PYNQ‑Z2 board.
`create_clock -period 10` asks for a 10 ns period, i.e. 100 MHz; synthesis will
tell us whether the design actually meets it.

## Running a stage

The last block does the work. There are three commands, and our script runs
exactly one per invocation:

~~~tcl
csim_design -argv "$out_dir"                          ;# C simulation
csynth_design                                          ;# C synthesis
cosim_design -argv "$out_dir" -trace_level $trace_level ;# RTL co-simulation
~~~

`-argv` is how the testbench is given its data directory — it arrives as
`argv[1]` in `main()`. This is why the testbench can read `cases.txt` and write
`results.json` somewhere useful, and why C simulation and co-simulation can be
pointed at *different* directories so their results can be compared separately.

Which stage runs is chosen by an environment variable:

~~~tcl
set stage [env_or SCALAR_FUN_STAGE "csim"]
~~~

with `env_or` a three-line helper that reads `::env(...)` if it is set and
returns a default otherwise. The same pattern supplies the output directory,
the clock period, the part, and the trace level — so every knob can be changed
from outside without editing the file.

One subtlety worth noticing:

~~~tcl
if {$stage eq "csim"} {
    open_project -reset scalar_fun_proj
} else {
    open_project scalar_fun_proj
}
~~~

`-reset` wipes the project and starts clean. C simulation is the first stage,
so it resets; synthesis and co-simulation re-open what the earlier stages
built. Without that distinction, running synthesis would delete the project it
is supposed to synthesize.

## Running it without Python at all

You do not need the build script to use this file. Set the environment
variables and call the Vitis launcher directly.

On Windows PowerShell:

~~~powershell
$env:SCALAR_FUN_STAGE   = "csim"
$env:SCALAR_FUN_OUT_DIR = "$PWD/results/csim"
& "C:/Xilinx/2025.1/Vitis/bin/vitis-run.bat" --mode hls --tcl run.tcl
~~~

On Linux:

~~~bash
SCALAR_FUN_STAGE=csim SCALAR_FUN_OUT_DIR="$PWD/results/csim" \
    vitis-run --mode hls --tcl run.tcl
~~~

You will get the same output the build script shows you:

~~~text
INFO: [SIM 211-2] *************** CSIM start ***************
Test 0: x=3 w=2 b=4 got 10, expected 10  PASS
...
All tests passed.
SCALAR_FUN_SUCCESS: stage 'csim' completed.
~~~

Change `SCALAR_FUN_STAGE` to `csynth` or `cosim` for the other stages. Note
`--tcl` is required; `vitis-run --mode hls run.tcl` alone is an error.

> **Watch out.** Because the `csim` stage resets the project, running it by
> hand after you have synthesized will delete the synthesized solution, and the
> co-simulation stage will then have nothing to simulate. Re-run synthesis
> afterwards. The build script sequences the stages so this does not happen to
> you.

> The GUI is a third way to run the same thing. Open the component and press
> **C Simulation → Run**. It works, and for a first look it is a perfectly good
> way to see what the tool does. What it will not do is run the checks, keep a
> record of what was built from what, or skip work that does not need redoing.

## How the build script uses this file

`run.tcl` is registered with the build graph as a **source**:

~~~python
dag.add(SourceStep(artifact="run_tcl", path=_SOURCE_DIR / "run.tcl"))
~~~

A [`SourceStep`](https://sdrangan.github.io/waveflow/docs/guide/build/corecomp.html#sourcestep)
is a file that the build does not produce but does depend on. Every step that
invokes Vitis lists `run_tcl` among the artifacts it consumes, so editing this
file marks those steps stale and they run again next time. That is all the
bookkeeping there is to it.

---
Go to [C Simulation](./csim.md)
