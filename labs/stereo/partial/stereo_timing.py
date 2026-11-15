"""Where a call to the kernel spends its time: load, compute, store.

The build co-simulates your stereo.cpp, records its ports, and writes one row
per clock cycle of the call to results/cosim/signals.csv:

    cycle       0 at the first rising edge where ap_start is 1, or where a word
                is taken, whichever is first (see below)
    ap_start    the block-level handshake
    ap_done
    in_valid    pix_in_TVALID     a pixel word is offered to the kernel
    in_ready    pix_in_TREADY     the kernel takes it
    out_valid   disparity_TVALID  the kernel offers a disparity
    out_ready   disparity_TREADY  the testbench takes it

A word moves on an AXI4-Stream in the cycles where VALID and READY are both 1:
a *handshake*.  The first two input handshakes come a cycle or two *before*
ap_start: Vitis puts a register slice on each stream port, and it takes words
as soon as they are offered.  That is all you need to find the three phases:

    load     from the first input handshake to the last, inclusive
    store    from the first output handshake to the last, inclusive
    compute  the cycles strictly between the last input handshake and the
             first output handshake

You write find_phases(), which finds them, and plot_phases(), which draws them.
The build grades find_phases() against its own reading of the same table.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def find_phases(sig: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """The first and last cycle of each phase, as {"load": (first, last), ...}.

    Keys "load", "compute" and "store"; each value a pair of ints, both
    inclusive, in the table's `cycle` numbering.  If the kernel never takes or
    never gives a word, there is nothing to find: raise ValueError.
    """
    # TODO:  Find the cycles with an input handshake (in_valid and in_ready
    # both 1) and those with an output handshake, and from them the three
    # phases as the docstring at the top of this file defines them.
    raise ValueError("find_phases is not written yet")


def plot_phases(sig: pd.DataFrame, phases: dict[str, tuple[int, int]],
                path: str | Path) -> None:
    """A timing diagram of the whole call, with the three phases marked.

    Plot, against the cycle, at least the input handshake (in_valid and
    in_ready), the output handshake (out_valid and out_ready), and ap_done,
    as 0/1 traces stacked one above the other.  Shade or label the load,
    compute and store phases, and give each its length in cycles.  Save the
    figure to `path`.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # TODO:  Draw the diagram.  A step plot per signal (plt.step, or
    # ax.fill_between for a filled trace) at a different height for each,
    # and ax.axvspan for the phases, is one way.
