# In-class exercise: one read per iteration

`y[i] = x[i]^2 + x[i-1]^2`, with `x` and `y` in single-port memories.  The
obvious loop asks for II = 1 and gets 2.  Rewrite the loop in `sqsum.cpp`
(the only file you edit) so it reaches II = 1, then run:

```bash
python sqsum_build.py                    # check, synthesize, compare: under a minute
python sqsum_build.py --through timing   # also RTL co-simulation and a timing diagram
```

The walkthrough is
[docs/demos/loopopt/inclass.md](../../docs/demos/loopopt/inclass.md), the
fourth page of the pipelining demo.  Run it in `hwdesign-venv`, with Vitis
HLS installed.
