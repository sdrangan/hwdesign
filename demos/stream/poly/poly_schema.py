"""The messages the poly kernel sends and receives, as waveflow data schemas.

This file is the single source of the stream's layout.  The build's
``gen_include`` step generates a C++ header from each schema here -- a
struct with the same fields, plus ``read_axi4_stream`` / ``write_axi4_stream``
methods that pack it into stream words -- and the Python side packs and
unpacks the same messages with the same schemas.  So the C++ kernel, the
C++ testbench and the Python model cannot disagree about which bits mean
what: none of them writes the packing by hand.

One transaction on the streams is:

    in_stream:   PolyCmdHdr          |  x[0], x[1], ..., x[nsamp-1]
    out_stream:  PolyRespHdr  |  y[0], y[1], ..., y[nsamp-1]  |  PolyRespFtr

Each ``|`` is a TLAST: every message and every sample burst is its own
TLAST-terminated burst.
"""
from __future__ import annotations

from enum import IntEnum

from waveflow.hw.dataschema import DataArray, DataList, EnumField, FloatField, IntField

#: Where the generated headers go, relative to this directory.
INCLUDE_DIR = "include"

#: The stream word widths the generated headers support.  The kernel's
#: WORD_BW must be one of these.
WORD_BW_SUPPORTED = [32, 64]

Float32 = FloatField.specialize(bitwidth=32, include_dir=INCLUDE_DIR)
TxId = IntField.specialize(bitwidth=16, signed=False, include_dir=INCLUDE_DIR)
Nsamp = IntField.specialize(bitwidth=16, signed=False, include_dir=INCLUDE_DIR)


class PolyError(IntEnum):
    """What the kernel reports in the response footer."""

    NO_ERROR = 0
    TLAST_EARLY_CMD_HDR = 1   # TLAST arrived before the whole command header
    NO_TLAST_CMD_HDR = 2      # the command header ended without TLAST
    TLAST_EARLY_SAMP_IN = 3   # TLAST arrived before nsamp samples
    NO_TLAST_SAMP_IN = 4      # nsamp samples arrived without TLAST
    WRONG_NSAMP = 5           # the number of samples read is not nsamp


PolyErrorField = EnumField.specialize(enum_type=PolyError, include_dir=INCLUDE_DIR)


class CoeffArray(DataArray):
    """The cubic's four coefficients, constant term first."""

    ncoeffs = 4
    element_type = Float32
    static = True
    max_shape = (ncoeffs,)
    include_dir = INCLUDE_DIR


class PolyCmdHdr(DataList):
    """The command: which transaction, which polynomial, how many samples follow."""

    elements = {
        "tx_id": {"schema": TxId, "description": "Transaction ID"},
        "coeffs": {"schema": CoeffArray, "description": "Polynomial coefficients"},
        "nsamp": {"schema": Nsamp, "description": "Number of samples that follow"},
    }
    include_dir = INCLUDE_DIR


class PolyRespHdr(DataList):
    """Sent before the output samples, so the host knows which command they answer."""

    elements = {
        "tx_id": {"schema": TxId, "description": "Echo of the command's transaction ID"},
    }
    include_dir = INCLUDE_DIR


class PolyRespFtr(DataList):
    """Sent after the output samples: how it went."""

    elements = {
        "nsamp_read": {"schema": Nsamp, "description": "Number of samples read"},
        "error": {"schema": PolyErrorField, "description": "Error code"},
    }
    include_dir = INCLUDE_DIR


#: Every schema the kernel needs a header for.
SCHEMA_CLASSES = [PolyErrorField, CoeffArray, PolyCmdHdr, PolyRespHdr, PolyRespFtr]
