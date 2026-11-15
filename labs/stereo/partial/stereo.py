"""The stereo lab's golden model: block-matching disparity, in Python.

Two cameras side by side see the same scene from slightly different places.
After the images are *rectified* -- warped so that the two cameras' rows line
up -- a point in the scene appears on the same row in both images, shifted to
the left in the right image by its **disparity** d.  Near things shift more
than far ones: depth is proportional to 1/d.  So the search for a match is
along the row only, the x direction, never in y.

This file is the specification the Vitis kernel has to match bit for bit:

* shift_image()      a right image whose every pixel has the same disparity
* disparity_map()    the disparity of every pixel of the left image
* plot_disparity()   the two images and the disparity map, side by side

The constants below repeat the ones in stereo.h and stereo_build.py.  The
build grades your functions against its own copy, so changing them here
changes nothing but your own results.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

#: The image size, the number of disparities searched, and the window
#: half-width: windows are (2*HALF+1) x (2*HALF+1) = 5 x 5.
H, W = 96, 128
NDISP = 16
HALF = 2


def load_image(path: str | Path) -> np.ndarray:
    """A PNG as an (H, W) array of uint8 gray levels.  Given, not graded."""
    from PIL import Image

    return np.asarray(Image.open(path).convert("L"), dtype=np.uint8)


def shift_image(img: np.ndarray, d: int) -> np.ndarray:
    """The right camera's view of a flat scene at disparity d.

    Each point at column x in the left image appears at column x - d in the
    right one, so the right image's column x is the left image's column x + d:

        R[y][x] = img[y][x + d]

    The last d columns have no x + d in the image: repeat the last column
    there, R[y][x] = img[y][W-1].  Returns a new uint8 array; img is unchanged.
    """
    # TODO:  Build R as above.  Array slicing does it in a line or two; a
    # loop over the columns is fine too.
    return img.copy()


def disparity_map(left: np.ndarray, right: np.ndarray, ndisp: int = NDISP,
                  half: int = HALF) -> np.ndarray:
    """Block-matching disparity, exactly as stereo.h specifies it.

    For each pixel (y, x) of the interior

        half <= y < H - half   and   half + ndisp - 1 <= x < W - half

    the disparity is the d in 0 .. ndisp-1 that minimizes

        SAD(y, x, d) = sum over i, j in -half .. half of
                       | left[y+i][x+j] - right[y+i][x+j-d] |

    and on a tie the smallest such d.  Every other pixel is 0.  Returns an
    (H, W) array of uint8.

    The pixels are uint8: subtract them in a wider type, or the difference
    wraps around instead of going negative.
    """
    h, w = left.shape
    disp = np.zeros((h, w), dtype=np.uint8)
    # TODO:  Fill in disp for the interior.  The plainest version is a loop
    # over y, x and d with the 5x5 window sum inside -- the same loops as the
    # kernel's.  It takes several seconds on a 96 x 128 image, which is fine.
    # (A faster version computes one shifted absolute-difference image per d
    # and sums it over 5x5 windows; both give the same answer.)
    return disp


def plot_disparity(left: np.ndarray, right: np.ndarray, disp: np.ndarray,
                   path: str | Path) -> None:
    """Save a figure of the left image, the right image and the disparity map.

    Three panels side by side, each with a title.  Show the images in gray and
    the disparity map with a colormap and a colorbar, 0 to NDISP-1, so that
    near (large d) and far (small d) are easy to tell apart.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # TODO:  Draw the three panels and save the figure to `path`.
