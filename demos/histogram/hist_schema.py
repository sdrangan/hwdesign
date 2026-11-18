"""The histogram kernel's command and response, as waveflow data schemas.

This file is the single source of their layout.  The build's ``gen_include``
step generates a C++ header from each schema (``hist_cmd.h``,
``hist_desc.h``, ``hist_resp.h``): a struct with the same fields and
``read_stream`` / ``write_stream`` (and framed / array) methods that pack it
into 32-bit words.  The Python side
packs the commands and unpacks the responses with the same schemas, so the
kernel, the testbenches and the golden model cannot disagree about the bits.

Both versions of the kernel use these messages unchanged.  ``histogram_stream``
receives a ``HistCmd`` on an AXI4-Stream and sends a ``HistResp`` on another;
``histogram_mm`` will read and write the same words from queues in memory.

Every address in a command is a **word offset**, not a byte address: the
memory adaptors take word offsets (``MemRCmd.addr``, ``MemWCmd.addr``), and the
kernel's ``m_axi`` ports start at address 0 (``offset=off``).
"""
from __future__ import annotations

from enum import IntEnum

from waveflow.hw.dataschema import DataList, EnumField, IntField

#: Where the generated headers go, relative to this directory.
INCLUDE_DIR = "include"

#: The memory and stream word width, in bits.  One sample or one count per word.
MEM_DW = 32

#: Word widths the generated headers support.  The adaptor headers need 32 and 64.
WORD_BW_SUPPORTED = [32, 64]

Word32 = IntField.specialize(bitwidth=32, signed=False, include_dir=INCLUDE_DIR)


class HistStatus(IntEnum):
    """What the response reports."""

    OK = 0
    N_TOO_LARGE = 1      # n > MAX_N: refused, nothing read and nothing written


HistStatusField = EnumField.specialize(enum_type=HistStatus, include_dir=INCLUDE_DIR)


class HistCmd(DataList):
    """One job: histogram ``n`` samples at word ``data_addr`` into the counts at ``cnt_addr``."""

    elements = {
        "job_id":    {"schema": Word32, "description": "Job ID, echoed in the response"},
        "data_addr": {"schema": Word32, "description": "Word offset of the first sample"},
        "n":         {"schema": Word32, "description": "Number of samples"},
        "cnt_addr":  {"schema": Word32, "description": "Word offset of the NBINS counts"},
        "shift":     {"schema": Word32, "description": "bin = min(x >> shift, NBINS - 1)"},
    }
    include_dir = INCLUDE_DIR


class HistDesc(DataList):
    """The job descriptor: built once by the control task, then carried through the kernel.

    It travels as a framed header ahead of the samples (the read mover relays it), then ahead of
    the counts (the write mover buffers it across the write), and comes back on the write mover's
    done stream once the counts are in memory.  Every task reads what it needs from it; none
    rebuilds it.  A refused job carries ``n = 0`` and ``status = N_TOO_LARGE``.
    """

    elements = {
        "job_id":   {"schema": Word32, "description": "The command's job ID"},
        "status":   {"schema": HistStatusField, "description": "OK, or why the job was refused"},
        "n":        {"schema": Word32, "description": "Samples to bin: 0 for a refused job"},
        "shift":    {"schema": Word32, "description": "bin = min(x >> shift, NBINS - 1)"},
        "cnt_addr": {"schema": Word32, "description": "Word offset of the NBINS counts"},
    }
    include_dir = INCLUDE_DIR


class HistResp(DataList):
    """Sent once per job, after its counts are written."""

    elements = {
        "job_id": {"schema": Word32, "description": "The command's job ID"},
        "status": {"schema": HistStatusField, "description": "OK, or why the job was refused"},
    }
    include_dir = INCLUDE_DIR


#: The kernel's own messages.  The memory commands (MemRCmd, MemWCmd) come from waveflow.
SCHEMA_CLASSES = [HistStatusField, HistCmd, HistDesc, HistResp]
