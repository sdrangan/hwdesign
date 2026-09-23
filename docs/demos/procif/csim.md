---
title: C Simulation
parent: Bus Basics and Memory‑Mapped Interfaces
nav_order: 3
has_children: false
---

# C Simulation

Our first task is to check **functional correctness**: does the C++ do what we
meant? At this stage nothing is hardware. The testbench is compiled against the
C++ kernel and both run as an ordinary program on your processor. It is fast —
seconds — which is why it comes first.

Run everything below from `hwdesign/demos/scalar_fun/scalar_fun_vitis`, in the
[virtual environment](../../support/repo/package.md) that has `waveflow`.

~~~bash
(env) python scalar_fun_build.py --through csim
~~~

In amongst the Vitis output:

~~~text
Test 0: x=3 w=2 b=4 got 10, expected 10  PASS
Test 1: x=-1 w=5 b=0 got 0, expected 0  PASS
Test 2: x=10 w=-2 b=3 got 0, expected 0  PASS
Test 3: x=0 w=1 b=-5 got 0, expected 0  PASS
Test 4: x=7 w=7 b=7 got 56, expected 56  PASS
All tests passed.
~~~

Notice you did not have to run `make_inputs` first. `csim` consumes the test
vector that step produces, so asking for `csim` ran it too. That is what
`--through` means: run everything this step needs, and stop there.

The outputs land in `results/csim/results.json`.

## Under the hood: the build step

Here is the entire step that did that:

~~~python
@dataclass(kw_only=True)
class CSimStep(BuildStep):
    """Compile the testbench against the C++ kernel and run it."""

    description = "Run Vitis HLS C simulation into results/csim."
    consumes = ["scalar_fun_cpp", "scalar_fun_h", "scalar_fun_tb", "run_tcl", "cases"]
    produces = {"csim_dir": Path("results/csim")}
    params = {"clk_period_ns": 10.0, "live_output": False}

    def run(self, config: BuildConfig, cases, clk_period_ns, live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "csim"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cases.txt").write_bytes(Path(cases).read_bytes())
        _run_stage(config, "csim", out_dir, clk_period_ns=clk_period_ns,
                   live_output=live_output)
        return {"csim_dir": out_dir}
~~~

Four class attributes describe the step, and `run()` does the work. See
[Core Components](https://sdrangan.github.io/waveflow/docs/guide/build/corecomp.html#buildstep)
for the full contract.

**`consumes`** lists artifacts by name. This is the whole dependency
declaration — you never write "run after `make_inputs`". You say this step
needs `cases`, something else produces `cases`, and the graph works out the
order. A name nothing produces is an error when the graph is assembled, not
half an hour into a build.

It lists the sources too, which is what makes rebuilds correct: edit
`tb_scalar_fun.cpp` and this step is stale, because `scalar_fun_tb` is newer
than what the step produced.

**`produces`** maps artifact names to paths. Downstream steps ask for
`csim_dir`; they never hard-code `results/csim`. Every name here must appear in
the dict `run()` returns, or the graph raises an error — a step cannot quietly
fail to make what it promised.

**`params`** are the knobs, injected into `run()` as keyword arguments. They
are what `--clk-period-ns` on the command line ends up setting.

**`run()`** stages `cases.txt` into the output directory (the testbench reads
its vector from the directory it writes to), then calls `_run_stage`, which is
just the environment-variable plumbing from the [previous page](./tcl.md):

~~~python
env = {
    "SCALAR_FUN_STAGE": stage,
    "SCALAR_FUN_OUT_DIR": out_dir.as_posix(),
    "SCALAR_FUN_CLK_PERIOD_NS": f"{clk_period_ns:g}",
    ...
}
toolchain.run_vitis_hls(config.root_dir / "run.tcl", work_dir=config.root_dir, env=env)
~~~

`run_vitis_hls` finds your Vitis installation and runs
`vitis-run --mode hls --tcl run.tcl`. Which is exactly what you would type
yourself — see
[Vitis Pattern](https://sdrangan.github.io/waveflow/docs/guide/build/vitis.html).

### Doing it without waveflow

~~~powershell
$env:SCALAR_FUN_STAGE   = "csim"
$env:SCALAR_FUN_OUT_DIR = "$PWD/results/csim"
& "C:/Xilinx/2025.1/Vitis/bin/vitis-run.bat" --mode hls --tcl run.tcl
~~~

That is the same simulation. What you give up is everything on this page after
it: the checking, the record of what was built from what, and the skipping.

## Verifying the result

The testbench printed `PASS`, but it graded its own work. It compared against
expected values computed in the testbench itself — so if you misread the
specification, you would write the kernel and the testbench with the same
misunderstanding, and it would still print `PASS`.

So we compare against the independent Python model in `golden.py`:

~~~bash
(env) python scalar_fun_build.py --through verify_csim
~~~

C simulation is **skipped** this time — nothing it depends on changed:

~~~text
csim:
    results\csim
    UP-TO-DATE
verify_csim:
    results\verify_csim.json
    RUNNING...
    PASSED
~~~

That skipping is the
[incremental rebuild](https://sdrangan.github.io/waveflow/docs/guide/build/corecomp.html#incremental-rebuild)
model: freshness is decided by file timestamps, and only stale steps re-run.
Edit `tb_scalar_fun.cpp` and run the same command — now C simulation runs
again, because the artifact it consumes is newer than the one it produced.

### Under the hood: the verify step

This step is not hand-written; it is a waveflow built-in, configured:

~~~python
dag.add(FunctionalVerifyStep(
    name="verify_csim",
    golden_dir_artifact="golden_dir",
    actual_dir_artifact="csim_dir",
    jsons=[{"filename": "results.json", "compare_fields": ["y"]}],
    report_path="results/verify_csim.json",
))
~~~

It compares two *directories* — which is why the testbench had to write a file
rather than only print. The manifest says: in `results.json`, compare the field
`y`. It writes a report either way, and raises if anything differs.

Make it fail on purpose. Change one expected value in `golden.py` and re-run:

~~~text
RuntimeError: FunctionalVerifyStep 'verify_csim' failed:
results.json.y: golden=[10, 0, 0, 0, 56] vs actual=[10, 0, 0, 0, 55]
~~~

Put it back before continuing. A check you have never seen fail is a check you
do not yet know is working.

---
Go to [C Synthesis](./csynth.md)
