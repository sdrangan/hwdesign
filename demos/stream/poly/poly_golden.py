"""The Python golden model and test transactions for the poly demo.

The kernel evaluates a cubic on every input sample,

    y = c[0] + c[1]*x + c[2]*x**2 + c[3]*x**3

and this module does the same in Python.  The model is purely *functional*:
it says what the output messages should contain, not when they appear.

It computes in float32 and in the kernel's order -- Horner's rule, from the
highest coefficient down -- so a correct kernel matches it bit for bit.

This module also writes the test vectors.  Every file is a sequence of
32-bit words, packed by the schemas in ``poly_schema.py``, which is exactly
what the testbench's generated ``read_uint32_file`` expects.  The files
say nothing about the stream's word width: the testbench packs them into
32- or 64-bit stream words itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from waveflow.hw.arrayutils import read_uint32_file, write_uint32_file

from poly_schema import Float32, PolyCmdHdr, PolyError, PolyRespFtr, PolyRespHdr


@dataclass(frozen=True)
class Transaction:
    """One command: a polynomial and the samples to evaluate it on."""

    tx_id: int
    coeffs: tuple[float, float, float, float]
    x: np.ndarray


def test_transactions() -> list[Transaction]:
    """Three commands, so the plot shows three curves and the kernel is
    exercised on back-to-back transactions with different lengths."""
    return [
        Transaction(0x10, (0.0, 1.0, 0.0, -0.5),
                    np.linspace(-2.0, 2.0, 40, dtype=np.float32)),
        Transaction(0x11, (1.0, -2.0, -3.0, 4.0),
                    np.linspace(-1.0, 1.0, 64, dtype=np.float32)),
        Transaction(0x12, (-1.0, 0.0, 2.0, 0.0),
                    np.linspace(-1.5, 1.5, 25, dtype=np.float32)),
    ]


def poly_eval(coeffs, x: np.ndarray) -> np.ndarray:
    """The reference model: Horner's rule in float32, in the kernel's order."""
    c = np.asarray(coeffs, dtype=np.float32)
    x = np.asarray(x, dtype=np.float32)
    y = np.full_like(x, c[3])
    for k in (2, 1, 0):
        y = y * x + c[k]
    return y


# ---------------------------------------------------------------------------
# Files.  Transaction k's messages are txn<k>_<name>.bin.
# ---------------------------------------------------------------------------

def _name(k: int, what: str) -> str:
    return f"txn{k}_{what}.bin"


def write_inputs(in_dir: Path, txns: list[Transaction]) -> Path:
    """What the testbench sends: a command header and the input samples, per transaction."""
    in_dir.mkdir(parents=True, exist_ok=True)
    for k, t in enumerate(txns):
        hdr = PolyCmdHdr()
        hdr.tx_id = t.tx_id
        hdr.coeffs = np.asarray(t.coeffs, dtype=np.float32)
        hdr.nsamp = len(t.x)
        hdr.write_uint32_file(in_dir / _name(k, "cmd_hdr"))
        write_uint32_file(t.x, elem_type=Float32, file_path=in_dir / _name(k, "samp_in"),
                          nwrite=len(t.x))
    # The testbench needs to know how many transactions to send.
    (in_dir / "ntxn.txt").write_text(f"{len(txns)}\n", encoding="utf-8")
    return in_dir


def write_expected(out_dir: Path, txns: list[Transaction]) -> Path:
    """What the testbench should receive back, in the files it writes its own to."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for k, t in enumerate(txns):
        resp_hdr = PolyRespHdr()
        resp_hdr.tx_id = t.tx_id
        resp_hdr.write_uint32_file(out_dir / _name(k, "resp_hdr"))
        y = poly_eval(t.coeffs, t.x)
        write_uint32_file(y, elem_type=Float32, file_path=out_dir / _name(k, "samp_out"),
                          nwrite=len(y))
        ftr = PolyRespFtr()
        ftr.nsamp_read = len(t.x)
        ftr.error = PolyError.NO_ERROR
        ftr.write_uint32_file(out_dir / _name(k, "resp_ftr"))
    return out_dir


@dataclass
class Response:
    """One transaction's response, read back from files."""

    tx_id: int
    y: np.ndarray
    nsamp_read: int
    error: PolyError


def read_transaction(in_dir: Path, k: int) -> tuple[int, np.ndarray, np.ndarray]:
    """Transaction k's command, as ``(tx_id, coeffs, x)``."""
    hdr = PolyCmdHdr().read_uint32_file(in_dir / _name(k, "cmd_hdr"))
    nsamp = int(hdr.nsamp)
    x = _read_floats(in_dir / _name(k, "samp_in"), nsamp)
    return int(hdr.tx_id), np.asarray(hdr.coeffs, dtype=np.float32), x


def read_response(out_dir: Path, k: int, nsamp: int) -> Response:
    """Transaction k's response.  ``nsamp`` is how many samples the command asked for."""
    resp_hdr = PolyRespHdr().read_uint32_file(out_dir / _name(k, "resp_hdr"))
    ftr = PolyRespFtr().read_uint32_file(out_dir / _name(k, "resp_ftr"))
    y = _read_floats(out_dir / _name(k, "samp_out"), nsamp)
    return Response(int(resp_hdr.tx_id), y, int(ftr.nsamp_read), PolyError(int(ftr.error)))


def _read_floats(path: Path, n: int) -> np.ndarray:
    arr = read_uint32_file(path, elem_type=Float32, shape=n)
    return np.asarray(getattr(arr, "val", arr), dtype=np.float32)


def count_transactions(in_dir: Path) -> int:
    return int((in_dir / "ntxn.txt").read_text(encoding="utf-8").strip())


def summary(txns: list[Transaction]) -> str:
    """One line per transaction, for the console."""
    return "\n".join(f"  txn {k}: tx_id=0x{t.tx_id:02x} coeffs={list(t.coeffs)} nsamp={len(t.x)}"
                     for k, t in enumerate(txns))
