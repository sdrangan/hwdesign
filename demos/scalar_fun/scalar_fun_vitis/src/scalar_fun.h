#ifndef SCALAR_FUN_H
#define SCALAR_FUN_H

// The kernel: y = max(w*x + b, 0), a single artificial neuron.
//
// The name is `simp_fun` rather than `scalar_fun` because that is the name
// the synthesized IP carries in the pre-built bitstream
// (`scalar_fun_pynqz2/overlay/`), where the PYNQ driver reaches it as
// `overlay.simp_fun_0`.  Renaming the function would mean rebuilding the
// bitstream.
void simp_fun(int x, int w, int b, int& y);

#endif  // SCALAR_FUN_H
