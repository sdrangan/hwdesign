---
title: The golden model
parent: Stereo Depth
nav_order: 1
has_children: false
---

# Stage 1: The golden model

Before writing any C++, you build block matching in Python, where it is easy to
look at what you have. This model is the **golden model**: it produces the
disparity map that both kernels are checked against, bit for bit, so it has to
be right first.

You write three functions in `stereo.py`. `load_image()` is given.

## `shift_image(img, d)`

The simplest scene is a flat one: a picture on a wall, parallel to the cameras,
at disparity `d` everywhere. Every point at column `x` of the left image is at
column `x - d` in the right one, so the right image's column `x` is the left
image's column `x + d`:

```
R[y][x] = img[y][x + d]
```

The last `d` columns have no `x + d`: repeat the last column there. Use it to
check your `disparity_map()`: on `shift_image(L, 6)` it should find 6 at every
interior pixel. The build checks exactly that.

## `disparity_map(left, right)`

The specification is in `stereo.h` and on [the lab's first page](./index.md#the-algorithm).
Three details matter, because the kernels have to reproduce them exactly:

* **Arithmetic.** The pixels are `uint8`. In numpy, `uint8 - uint8` wraps around
  instead of going negative, so convert to a wider integer type before you
  subtract.
* **Ties.** When two disparities have the same SAD, the smaller wins. Visit `d`
  in increasing order and replace the best only on a strictly smaller SAD.
* **Borders.** Outside the interior, `2 <= y < 94` and `17 <= x < 126`, the
  disparity is 0. Why 17? For `d = 15`, the right window around `x - 15` has to
  start at column 0 or later.

The plainest version is the kernel's own loops, over `y`, `x`, `d` and the 5x5
window. In Python that takes a few seconds for the 96 x 128 image, which is
fine. A faster one computes, for each `d`, an image of absolute differences
and sums it over 5x5 windows. Either gives the same answer.

## `plot_disparity(left, right, disp, path)`

Three panels: the two images in gray, and the disparity map in color with a
colorbar from 0 to 15. Near things have large disparity, so the scene's three
layers should stand out as three flat regions.

Look at the edges of the rectangle and the disc in your figure. Next to each
object's left edge there is a strip where the map is noisy: there the left
camera sees background that the object hides from the right camera, so no
disparity matches well. That is **occlusion**, and it is a real property of
stereo, not a bug in your code.

## Running the stage

```bash
python stereo_build.py --through pysim
```

It grades your functions on test images of its own:

* `shift_image()`, on a random image
* the shape, type and border of `disparity_map()`'s answer
* a flat scene, made with the build's own shift, which must give 6 everywhere
  inside
* a three-layer scene of random pixels, at disparities the build knows, which
  must be right wherever a window sees just one layer
* a blank scene, where every disparity ties, which must give 0

Then it runs your model on the lab's scene, `scene_left.png` and
`scene_right.png`, and writes the images and your disparity map to `vectors/`,
for the kernels. It also draws your figure, `results/disparity.png`.

The kernels are checked against **your** model. So until your model passes
every check here, the kernel stages report "fix stereo.py first" instead of
comparing: a kernel that agrees with a wrong model proves nothing.

----

Go to [the baseline kernel](./base.md).
