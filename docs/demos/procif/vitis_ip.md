---
title: Creating the Vitis IP
parent: Bus Basics and Memory‑Mapped Interfaces
nav_order: 1
has_children: false
---

# Creating the Vitis IP

## Scalar Function Example

We will illustrate the IP with a simple scalar function — a single artificial
neuron,

$$y = \max(wx + b,\ 0)$$

It is small on purpose. Everything interesting in this unit is in the
*interface*, not the arithmetic.

The files are in `hwdesign/demos/scalar_fun/scalar_fun_vitis`. They are already
in the git repo, so you do not need to write them. Everything in this demo is
**written by hand** — none of it is generated.

In `src/scalar_fun.cpp`:

~~~c
void simp_fun(int x, int w, int b, int& y) {

    #pragma HLS INTERFACE s_axilite port=x      bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=w      bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=b      bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=y      bundle=CTRL
    #pragma HLS INTERFACE s_axilite port=return bundle=CTRL

    int act_in = w * x + b;
    if (act_in > 0)
        y = act_in;
    else
        y = 0;
}
~~~

Every argument is bound to the same AXI4‑Lite bundle, `CTRL`. So is `return`,
which is how the function's start/done handshake is exposed. Vitis HLS turns
that bundle into the **register map** the processor reads and writes — we will
see the actual addresses later, in the timing diagram.

> The function is called `simp_fun`, not `scalar_fun`. That name is baked into
> the pre-built bitstream and the PYNQ overlay, so renaming it would mean
> rebuilding the FPGA image.

## A Simple Testbench

A **testbench** is a program that tests the IP by giving it inputs and checking
the outputs against expected results. Ours is in
`testbench/tb_scalar_fun.cpp`. It reads a list of test cases, calls the IP on
each, and compares:

~~~c
int y_exp = w * x + b;
if (y_exp < 0) y_exp = 0;

int y = 0;
simp_fun(x, w, b, y);

if (y != y_exp) all_passed = false;
~~~

Two details matter more than they look:

* It **returns a non-zero exit code** when a test fails. Vitis reads that
  return code — a testbench that always returns `0` passes forever, no matter
  what the hardware does.
* It **writes its outputs to a file**, `results.json`, as well as printing
  them. Nothing downstream can read a console log, so anything that wants to
  check the results automatically needs a file.

## A Reference Model

`golden.py` holds the test vector and computes the expected answers in Python:

~~~python
def scalar_fun(x: int, w: int, b: int) -> int:
    act_in = w * x + b
    return act_in if act_in > 0 else 0
~~~

Why compute the same thing twice? Because the testbench checks the IP against
*its own* idea of the right answer. If you misunderstand the specification, you
will write the kernel and the testbench with the same misunderstanding, and the
testbench will happily print `PASS`. A model written separately from the
hardware is what catches that.

`golden.py` is also the single source of the test vector: it writes both
`data/cases.txt`, which the testbench reads, and the expected `results.json`.
They cannot drift apart because they come from the same place.

## The Build Script

Rather than driving Vitis by hand through the GUI, this demo uses a build
script, `scalar_fun_build.py`. It is built on the
[waveflow build system](https://sdrangan.github.io/waveflow/docs/guide/build/),
which models a build as a **directed acyclic graph** of steps. Each step
declares the named **artifacts** it *consumes* and *produces*, and the graph
works out the order for you.

Three properties of that model matter in practice:

* **Auto-wired dependencies.** You never say "run C synthesis after C
  simulation"; you say C synthesis consumes what C simulation produces. See
  [Core Components](https://sdrangan.github.io/waveflow/docs/guide/build/corecomp.html)
  for `consumes` / `produces` / `params`.
* **Incremental rebuilds.** A step whose inputs have not changed is skipped.
  Edit the testbench and C simulation re-runs; synthesis does not.
* **Subgraph execution.** You can ask for any step and get everything it needs,
  and nothing else.

The Vitis half of this pattern — invoking C simulation and synthesis and
parsing the reports — is described in
[Vitis Pattern](https://sdrangan.github.io/waveflow/docs/guide/build/vitis.html),
and the `run.tcl` this demo hands to Vitis follows
[Authoring run.tcl](https://sdrangan.github.io/waveflow/docs/guide/build/tcl.html).

### Setting up

Use the [virtual environment](../../support/repo/package.md) that has
`waveflow`, and make sure Vitis is installed. Then:

~~~bash
cd hwdesign/demos/scalar_fun/scalar_fun_vitis
~~~

Before running anything, look at what the build is made of:

~~~bash
(env) python scalar_fun_build.py --list-steps
~~~

~~~text
scalar_fun_cpp
scalar_fun_h
scalar_fun_tb
run_tcl
golden_py
timing_diagram_py
make_inputs
csim
verify_csim
csynth
cosim
extract_cosim_timing
verify_cosim
extract_vcd
timing_diagram
report
~~~

The first six are the hand-written source files. The rest are the work. To see
what each one needs and makes:

~~~bash
(env) python scalar_fun_build.py --list-steps-verbose
(env) python scalar_fun_build.py --list-artifacts
~~~

And to ask what is currently out of date, without building anything:

~~~bash
(env) python scalar_fun_build.py --status
~~~

### Generating the test vector

The first real step writes the inputs and the expected results:

~~~bash
(env) python scalar_fun_build.py --through make_inputs
~~~

This produces `data/cases.txt` and `results/golden/results.json`. Open both —
the second one is the answer key the rest of the flow is checked against.

> **Using the Vitis GUI instead.** You can still open this component in the
> Vitis GUI and press Run; the testbench falls back to a built-in test vector
> when it is not given `cases.txt`. Follow the
> [instructions](../../support/amd/vitis_build.md) to create the project with
> top function `simp_fun`, design file `src/scalar_fun.cpp`, and testbench
> `testbench/tb_scalar_fun.cpp`. The build script is the path we will use from
> here on, because it also does the checking.

---
Go to [The Vitis TCL script](./tcl.md)
