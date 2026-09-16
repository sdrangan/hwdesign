---
title: Theory
parent: Conditional Subtraction Division
nav_order: 1
has_children: false
---

# The conditional subtraction algorithm

## What we are computing

We are given two unsigned integers `a` and `b` with `0 <= a < b`, and we want the
quotient `a/b`. In general that quotient needs an arbitrary number of bits, so we
do not compute it exactly. Instead the algorithm produces an integer `z` from
which an `nbits`-bit approximation is read off:

```python
     qhat = z / (2**nbits) ~= a/b
```

So `z` is the *numerator* of the approximation. Since we assumed `a < b`, the true
quotient `a/b < 1`, and `z` therefore ranges over `0, 1, ..., 2**nbits - 1`.

For example with `a=3` and `b=10`, increasing `nbits` gives:

| `nbits` | `z` | `qhat = z/2**nbits` |
| --- | --- | --- |
| 1 | 0 | `0/2` = 0.0 |
| 2 | 1 | `1/4` = 0.25 |
| 4 | 4 | `4/16` = 0.25 |
| 8 | 76 | `76/256` = 0.297 |
| 16 | 19660 | `19660/65536` = 0.29999 |

As we increase the number of bits we get closer to the true fraction `a/b = 0.3`.

## The algorithm

This is the long division you learned in school, in base 2.

At each step you bring down the next bit of the dividend, ask whether the divisor
fits, and if it does, subtract it and write a 1 in the quotient. In binary "does
it fit" has only two answers, so there is no guessing and no multiplication — just
a shift, a comparison, and a conditional subtract. That is the whole circuit, and
it is why this is what small hardware actually does.

One iteration produces one quotient bit, most significant first, and each
iteration does four things in order:

1. shift `z` left, to make room for the bit about to be decided
2. shift `a` left — this is "bring down the next bit"
3. if the shifted `a` is now at least `b`, subtract `b` from it
4. if you subtracted, set the low bit of `z`

`a` is the running **remainder**, so it is the shifted-and-subtracted value that
carries into the next iteration, not the original dividend. Writing it in Python
is [the first stage of the lab](./python.md).

## The error bound

The approximation is **one-sided**:

```python
    qhat  <=  a/b  <  qhat + 2**-nbits
```

This is the part worth understanding, because it is what the lab checks and it is
not the same as "the error is small".

A quotient bit is only ever set *after* the subtraction that pays for it has
succeeded. The algorithm never optimistically rounds up, so `qhat` can never
exceed `a/b` — it only ever falls short, and by less than one unit in the last
place. In other words `z` is exactly `floor(a * 2**nbits / b)`.

Two consequences:

* **The error shrinks geometrically.** Every extra bit halves the worst case. Plot
  the worst error against `nbits` on a logarithmic axis and you get a straight
  line. Confirming that is [the second stage](./evaluate.md).

* **A divider that rounds to nearest is wrong here**, even though its *absolute*
  error would be smaller. The rest of a design is entitled to assume the quotient
  is an under-estimate, and a measurement that discards the sign cannot tell the
  two apart. That is why the lab asks for a signed error.

---

Go to [building a python model](./python.md).
