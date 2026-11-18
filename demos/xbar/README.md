# Crossbar or shared bus

AMD's `axi_crossbar` IP on the Pynq-Z2's Zynq-7020 at 100 MHz, built two ways
from the same IP: a true crossbar (`SAMD`) and a shared bus (`SASD`). The demo
shows what the crossbar costs (area) and what it buys (transfers to
different slaves overlap):

```bash
python xbar_demo.py                    # area (cached) + latency (live, XSI), 2x2 and 4x4, both modes
python xbar_demo.py --shapes 4x4       # one shape
python xbar_demo.py --through area     # just the area table, instantly
python xbar_demo.py --through synth    # also place and route one crossbar now: about 4 minutes
```

The area comes from `xbar_zynq7020_100mhz.csv`, measured beforehand with
Waveflow's `examples/xbar_profile` sweep, so no one waits for Vivado in class.
`xbar_import.py` rewrites the CSV from a new sweep. `xbar_lut_fit.py` fits
`LUT = a0 + a1*M + a2*S + a3*M*S` to it for each mode, with leave-one-out
cross-validation.

The walkthrough is [docs/demos/xbar/index.md](../../docs/demos/xbar/index.md).
Run it in `hwdesign-venv`, with Vivado installed.
