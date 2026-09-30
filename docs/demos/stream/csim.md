---
title: C Simulation
parent: AXI4-Streaming
nav_order: 4
has_children: false
---

# C Simulation

The first check is **functional**: does the C++ kernel compute the same
thing as the Python model? In C simulation nothing is hardware yet. Vitis
compiles the testbench and the kernel together into an ordinary program
and runs it on your computer. It takes seconds, which is why it comes
first.

Run everything below from `hwdesign/demos/stream/avgfilt`, in the
[virtual environment](../../support/repo/package.md) that has `waveflow`.
From here on you also need Vitis HLS installed. The build script finds it
the same way as in the [scalar function demo](../procif/vitis_ip.md).

## Step 3: Run C simulation (`csim`)

~~~bash
(env) python avgfilt_build.py --through csim
~~~

~~~text
csim:
    vectors\tv_csim.csv
    RUNNING...
Vitis HLS stage 'csim' done; log in results\csim\vitis.log
    PASSED
~~~

Vitis prints a great deal, mostly compiler warnings from its own header
files, so the build script saves it all to `results/csim/vitis.log` rather
than filling your terminal. Open the log and look for the testbench's
lines:

~~~text
INFO: [SIM 211-2] *************** CSIM start ***************
...
Wrote 200 samples to C:/.../demos/stream/avgfilt/vectors/tv_csim.csv
tb_avgfilt PASSED (200 samples)
...
INFO: [SIM 211-1] CSim done with 0 errors.
~~~

To watch the output as it runs instead, add `--live-output`.

The step produced `vectors/tv_csim.csv`, in the same `n,x,y` format as the
golden vectors. Its `y` column is what the C++ kernel computed.

### Under the hood: the build step

~~~python
@dataclass(kw_only=True)
class CSimStep(BuildStep):
    """Compile the testbench against the C++ kernel and run it on the vectors."""

    description = "Run Vitis C simulation; the testbench writes vectors/tv_csim.csv."
    consumes = ["avgfilt_cpp", "avgfilt_h", "tb_avgfilt", "run_tcl", "py_vectors"]
    produces = {"csim_vectors": Path("vectors/tv_csim.csv")}
    params = {"live_output": False}

    def run(self, config: BuildConfig, live_output, **_) -> dict:
        out = config.root_dir / "vectors" / "tv_csim.csv"
        # Removed first, so a file from an earlier run cannot pass for this one's.
        out.unlink(missing_ok=True)
        _run_stage(config, "csim", live_output)
        if not out.exists():
            raise RuntimeError(f"C simulation ran but the testbench wrote no {out}.")
        return {"csim_vectors": out}
~~~

It **consumes** the kernel, the header, the testbench, the Vitis script,
and `py_vectors`, so editing any of them makes C simulation stale. It is
also why `--through csim` ran `pysim` first if you had not already.

`run()` deletes the old output before starting. Without that, a
testbench that crashed before writing anything would leave the *previous*
run's file in place, and the comparison below would check stale results
and pass.

`_run_stage` sets `AVGFILT_STAGE=csim` and runs `run.tcl` through
`vitis-run`. Doing the same by hand:

~~~powershell
$env:AVGFILT_STAGE = "csim"
vitis-run --mode hls --tcl run.tcl
~~~

That is the same simulation. What you give up is the comparison below,
and the skipping.

## Step 4: Compare against the model (`verify_csim`)

The testbench printed `PASSED`, but it checked the kernel against its own
C++ calculation of the expected values. If you misunderstood the filter,
you would write the kernel and the testbench with the same mistake, and it
would still print `PASSED`. So we compare against the independent Python
model:

~~~bash
(env) python avgfilt_build.py --through verify_csim
~~~

~~~text
csim:
    vectors\tv_csim.csv
    UP-TO-DATE
verify_csim:
    results\verify_csim.json
    RUNNING...
tv_csim.csv vs the model: 200 of 200 samples bit-exact, max |error| = 0
    PASSED
~~~

C simulation was skipped, since nothing it depends on changed. The
comparison found every one of the 200 samples **bit-exact**: the C++
kernel and the Python model agree to the last bit. That is because the
model computes in `float32` and adds in the same order as the kernel.

The report is in `results/verify_csim.json`:

~~~json
{
  "pass": true,
  "actual": "tv_csim.csv",
  "nsamp": 200,
  "exact_matches": 200,
  "max_abs_err": 0.0,
  "rtol": 1e-05,
  "atol": 1e-06,
  "failures": []
}
~~~

The step **passes** as long as every sample is within a small tolerance
(`rtol`, `atol`), not only when it is exact. Bit-exact agreement is a
property of this kernel, where both sides do the same float operations in
the same order. A kernel that reorders its additions to go faster is still
correct, but may differ in the last bit.

The check also confirms that the testbench wrote the right number of
samples and ran the golden inputs. A testbench that silently fell back to
its built-in vector would fail here.

### Make it fail

A check you have never seen fail is a check you do not yet know is
working. In `avgfilt.cpp`, change the delay-line update to drop the oldest
sample:

~~~cpp
        xsq1 = 0;   // was: xsq1 = xsq0;
~~~

and run `--through verify_csim` again. C simulation re-runs, because
`avgfilt.cpp` changed. The testbench's own check fails first, and the
build stops with the testbench's FAIL lines:

~~~text
RuntimeError: Vitis HLS stage 'csim' failed (exit 1):
  y[2] = 0.142282, expected 0.142382  FAIL
  y[3] = 0.0687756, expected 0.143697  FAIL
  y[4] = 0.0515306, expected 0.118891  FAIL
  ...
  ERROR: [SIM 211-100] 'csim_design' failed: nonzero return value.
~~~

The first two outputs are still right, because the delay line starts at
zero either way. The error appears from sample 2, the first output that
needs $x[k-2]$.

Put the line back before continuing.

---

Go to [Synthesis and RTL Simulation](./rtlsim.md)
