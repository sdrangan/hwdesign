# In-class exercise: unrolling a dot product

`dot = a[0]*b[0] + ... + a[N-1]*b[N-1]`, with `a` and `b` in single-port
memories.  The plain loop takes one sample per cycle.  Rewrite the loop in
`dot.cpp` (the only file you edit) to take four samples per cycle, then run:

```bash
python dot_build.py                    # check, synthesize, compare: about a minute
python dot_build.py --through timing   # also RTL co-simulation and a timing diagram
```

The walkthrough is
[docs/demos/loopopt/inclass_unroll.md](../../docs/demos/loopopt/inclass_unroll.md),
the last page of the loop optimization demo.  Run it in `hwdesign-venv`, with
Vitis HLS installed.
