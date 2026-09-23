"""Decode AXI4-Lite transactions out of the co-simulation VCD.

A transfer happens on the clock edge where a channel's ``VALID`` and ``READY``
are both high.  That is the whole rule, and this module is little more than a
loop applying it.

One subtlety is worth knowing, because getting it wrong silently loses
transfers.  RTL signals settle *after* a clock edge and are read at the *next*
one, and the simulator timestamps them a fraction of a nanosecond after the
edge.  Sampling exactly at the edge therefore straddles the transition and
misses some handshakes -- in this design it found 16 of the 20 write-address
beats.  Sampling one picosecond *before* the edge reads the values that were
stable going into it, which is what the hardware sees.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Sample this far before each rising edge (in ps).  See the module docstring.
SETUP_PS = 1

CHANNELS = {
    "AW": ("AWVALID", "AWREADY", "AWADDR"),
    "W": ("WVALID", "WREADY", "WDATA"),
    "B": ("BVALID", "BREADY", None),
    "AR": ("ARVALID", "ARREADY", "ARADDR"),
    "R": ("RVALID", "RREADY", "RDATA"),
}


@dataclass
class Beat:
    """One completed transfer."""

    ns: float
    channel: str
    value: int | None = None


@dataclass
class Call:
    """One invocation of the kernel: its writes, then its reads."""

    beats: list[Beat] = field(default_factory=list)

    @property
    def start_ns(self) -> float:
        return self.beats[0].ns

    @property
    def end_ns(self) -> float:
        return self.beats[-1].ns

    @property
    def load_end_ns(self) -> float:
        """Last write-response beat -- the host has finished handing over."""
        return max(b.ns for b in self.beats if b.channel == "B")

    @property
    def read_start_ns(self) -> float:
        """First read-address beat -- the host starts asking for the result."""
        return min(b.ns for b in self.beats if b.channel == "AR")

    def count(self, channel: str) -> int:
        return sum(1 for b in self.beats if b.channel == channel)


def _signal(vcd, prefix: str, name: str) -> str | None:
    want = prefix + name
    for s in vcd.signals:
        if s == want or s.startswith(want + "["):
            return s
    return None


def decode(vcd_path: Path, top: str = "simp_fun", bundle: str = "s_axi_CTRL") -> list[Call]:
    """Return one :class:`Call` per kernel invocation found in the VCD."""
    from vcdvcd import VCDVCD

    vcd = VCDVCD(str(vcd_path), signals=None, store_tvs=True)
    prefix = f"apatb_{top}_top.AESL_inst_{top}.{bundle}_"
    clk = _signal(vcd, f"apatb_{top}_top.AESL_inst_{top}.", "ap_clk")
    if clk is None:
        raise RuntimeError(f"No ap_clk in {vcd_path}; is this a port-level trace?")

    tv = {}
    for chan, (vld, rdy, data) in CHANNELS.items():
        for nm in (vld, rdy, data):
            if nm is None:
                continue
            sig = _signal(vcd, prefix, nm)
            if sig is not None:
                tv[nm] = [(int(t), x) for t, x in vcd[sig].tv]

    def val_at(nm: str, t: int) -> str | None:
        last = None
        for tt, x in tv.get(nm, ()):
            if tt <= t:
                last = x
            else:
                break
        return last

    def as_int(bits: str | None) -> int | None:
        if bits is None:
            return None
        bits = bits.replace("x", "0").replace("z", "0")
        n = int(bits, 2)
        # 32-bit data buses carry signed values in this design.
        if len(bits) >= 32 and bits[0] == "1":
            n -= 1 << len(bits)
        return n

    edges = [int(t) for t, x in vcd[clk].tv if x == "1"]

    beats: list[Beat] = []
    for t in edges:
        s = t - SETUP_PS
        for chan, (vld, rdy, data) in CHANNELS.items():
            if val_at(vld, s) == "1" and val_at(rdy, s) == "1":
                beats.append(Beat(ns=t / 1000.0, channel=chan,
                                  value=as_int(val_at(data, s)) if data else None))
    beats.sort(key=lambda b: (b.ns, b.channel))

    # A call is writes then reads; the next write after a read starts a new one.
    calls: list[Call] = []
    current = Call()
    seen_read = False
    for b in beats:
        if b.channel in ("AW", "W") and seen_read:
            calls.append(current)
            current = Call()
            seen_read = False
        if b.channel in ("AR", "R"):
            seen_read = True
        current.beats.append(b)
    if current.beats:
        calls.append(current)
    return calls
