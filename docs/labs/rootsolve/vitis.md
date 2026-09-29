---
title: The Vitis kernel
parent: Root Solver
nav_order: 3
has_children: false
---

# Stage 3: The Vitis kernel

Now the same solver in C++, as a Vitis HLS kernel, and a testbench that runs it
on your vectors.

## The kernel: `fsolve.cpp`

The interface is given in `fsolve.h`:

```cpp
void fsolve(float a0, float a1, float a2, float x0, float tol, int max_iter,
            float step, float &x, float &fx, int &niter);
```

Seven inputs, three outputs — the outputs are references, which is how a C++
function returns more than one value, and how Vitis knows they are outputs.
You write two things.

**The interface pragmas.** Every argument becomes a register in an AXI4-Lite
register map, exactly as in the [scalar_fun demo](../../demos/procif/vitis_ip.md):

```cpp
#pragma HLS interface s_axilite port=a0
...
#pragma HLS interface s_axilite port=return bundle=CTRL
```

one for each argument, and one for `return`, which puts the block's control
signals — `ap_start`, `ap_done` and the rest — in the same register map.

**The loop.** The same iteration as your Python, with the same three rules:
`fx` is `f` at the returned `x`, `niter` counts updates, and the stopping test
comes *before* each update. In C++ that is a `for` loop over `max_iter` with a
`break`:

```cpp
solve_loop: for (int i = 0; i < max_iter; i++) {
    #pragma HLS loop_tripcount min=1 avg=80 max=500
    if (/* converged */) break;
    // update xk, recompute fk, count it
}
```

`fcubic()` is given, and evaluates the polynomial in the same order as the
Python one. Use it rather than writing the polynomial again.

Two things about this loop are new compared with the [scalar_fun
demo](../../demos/procif/):

* **Its trip count is data.** `max_iter` is a register, and the `break` depends
  on the values being computed, so synthesis cannot know how long the loop runs.
  It builds the loop anyway — that is fine — but it cannot report a latency.
  `loop_tripcount` tells the report what to *assume*. It does not change the
  hardware.
* **Each iteration needs the one before.** The next `x` depends on this `f(x)`,
  which depends on this `x`. So the iterations cannot overlap, and one iteration
  takes as long as its chain of floating-point multiplies and adds — tens of
  clock cycles. Look for this in the synthesis report: for the reference
  kernel it gives a worst case of about 14,500 cycles for the 500-update
  budget, which is roughly **29 cycles per update** at 100 MHz. Making loops
  like this faster is the subject of a later unit.

## The testbench: `tb_fsolve.cpp`

The testbench reads `vectors/tv_python.csv`, calls `fsolve()` once per vector,
and writes what came back. Reading the file is given. You write the loop body:
the call, and one output row.

```cpp
fsolve(v.a0, ...,  x, fx, niter);
out << std::setprecision(9) << v.a0 << "," << ... << niter << "\n";
```

The row echoes the vector's seven inputs, then the kernel's `x`, `fx` and
`niter` — the same columns as the vector file, so [stage 4](./evaluate.md) can
read the kernel's answer exactly as it reads the model's. The inputs are echoed
so that a row written out of order, or a call with two arguments swapped, is
caught rather than scored as a wrong answer.

**Use `std::setprecision(9)`.** Nine significant digits is what it takes for
every `float` to survive the trip through text unchanged. The default of six
would round away the last few bits, and a kernel that matches your model exactly
would look like it was off by a rounding error.

Three things about the testbench are deliberate, and worth understanding:

* **It does not judge the answers.** The testbench prints each vector's `x` and
  `niter` beside the model's, for you to read while debugging, but deciding
  whether they agree is [stage 4](./evaluate.md)'s job. That way the tolerances
  live in one place.
* **It returns non-zero only when it cannot do its job** — no vector file, or
  an output it cannot write. Returning non-zero on a *wrong answer* would make
  Vitis report the co-simulation as failed and discard the output file that says
  which vectors were wrong.
* **It finds its files relative to itself**, not to the working directory,
  because Vitis runs the testbench from deep inside the project — and from a
  different place for co-simulation than for C simulation. The one argument it
  takes, `csim` or `cosim`, picks the output file: `vectors/tv_csim.csv` or
  `vectors/tv_cosim.csv`.

## Running it

There are three Vitis steps, and you can stop after any of them:

```bash
python rootsolve_build.py --through csim     # C simulation only: fast
python rootsolve_build.py --through csynth   # ... then synthesis
python rootsolve_build.py --through cosim    # ... then co-simulation
```

| Step | What Vitis does | Writes |
| --- | --- | --- |
| `csim` | Compiles the testbench with `fsolve.cpp` as ordinary C++ and runs it | `vectors/tv_csim.csv` |
| `csynth` | Synthesizes `fsolve()` to RTL | `results/csynth/fsolve_csynth.rpt` |
| `cosim` | Runs the *same* testbench, with `fsolve()` replaced by the RTL | `vectors/tv_cosim.csv` |

C simulation checks that your C++ does what you meant. Co-simulation checks that
the hardware Vitis *built* from it still does — which is not implied, and is the
failure that costs the most time to find later. That is why both are compared
with your model in [stage 4](./evaluate.md), separately.

The build runs `run.tcl` for each step, with `vitis-run`. You need Vitis on your
path — follow the [instructions](../../support/amd/launching.md) — and on
Windows, run the build from a command prompt rather than PowerShell. Expect
C simulation to take under a minute and co-simulation a few.

```
csim:
    vectors\tv_csim.csv
    results\csim\status.json
    RUNNING...
    the testbench recorded 20 vectors in vectors\tv_csim.csv
    PASSED
```

Everything Vitis printed goes to `results/<step>/vitis.log`. To watch it as it
runs instead, add `--live-output`.

### When a step fails

A Vitis step that fails does **not** stop the build. It records what went wrong,
prints the first few error lines — the compiler's own first, since they name the
line to fix — and the steps after it say they were skipped:

```
csim:
    RUNNING...
    ✗ Vitis exited with status 1:
      ../../../../fsolve.cpp:69:12: error: expected ';' after expression
      ERROR: [SIM 211-100] 'csim_design' failed: compilation error(s).
    the tool output is in results\csim\vitis.log
```

(The `../../../../` is because Vitis compiles from inside `fsolve_proj/`; the
file is your `fsolve.cpp`.) Everything else Vitis said is in the log. Fix the file and run again — a failed
step always re-runs on the next build, even if you changed nothing, so a failure
caused by your setup (Vitis not on the path, say) clears as soon as the setup is
fixed.

{: .warning }
> If C simulation passes and co-simulation fails almost immediately with
> `C/RTL co-simulation file generation failed` and nothing else, look at the
> names in your testbench. Co-simulation rewrites every call to `fsolve()`, and in
> Vitis 2025.1 that rewrite fails when a struct field has the same name as one of
> `fsolve()`'s output arguments — `x`, `fx` or `niter`. That is why the given
> `Vector` struct calls the model's answer `x_model`, `fx_model`, `niter_model`.

### Running Vitis by hand

`run.tcl` is an ordinary Vitis script, one stage per run, chosen by an
environment variable. The build does nothing you could not type:

```bash
ROOTSOLVE_STAGE=csim vitis-run --mode hls --tcl run.tcl            # bash
$env:ROOTSOLVE_STAGE="csim"; vitis-run --mode hls --tcl run.tcl    # PowerShell
```

On the [NYU server](../../support/nyuremote/), which has the older 2023.2 tools,
the command is `vitis_hls -f run.tcl`. The project it builds is `fsolve_proj/`,
which you can also open in the Vitis GUI to look at the synthesis reports.

----

Go to [comparing kernel and model](./evaluate.md).
