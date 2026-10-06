---
title: The command-response pattern
parent: Command-Response Mini-Project
nav_order: 1
has_children: false
---

# The command-response pattern

How should a host talk to a streaming accelerator? It has to configure it, send
it data, get results back, and find out when something went wrong. This page
gives the pattern every accelerator in this project follows, and the reasons for
each of its rules.

## The protocol

```
in_stream:   CmdHdr | data   CmdHdr | data   ...   CmdHdr(END)
out_stream:  RespHdr | data  RespHdr | data  ...
```

Every `|` is a TLAST. A command is a header burst, followed by a data burst if
the command carries data. Each command that produces a result gets a response
header and, if it has one, a data burst. The response header echoes the
command's transaction id (`tx_id`), so the host can match each response to its
command.

## The rules

1. **Everything the kernel computes with travels on the stream**: commands,
   configuration (coefficients, thresholds, modes) and data. Configuration is a
   command of its own, for example `CONFIG`.
2. **AXI-Lite carries only control and status.** The host starts the kernel with
   `ap_start`. The kernel processes commands until an `END` command or an error,
   then returns, and the host sees `ap_done`.
3. **On an error, the kernel sets its status registers and returns at once.**
   For example `halted`, `error` (a code) and the offending `tx_id`. It reads
   nothing more from the input stream.
4. **Before it returns, the kernel closes any output burst it started**, by
   setting TLAST on the last word it wrote.
5. **After an error, the input stream's contents are undefined.** Recovery is
   the host's job: it reads the status, resets the stream path, and starts the
   kernel again.
6. **Nothing carries over between activations.** Each activation starts clean
   and must begin with a configuration command. A data command before any
   configuration is an error.

## The host and the kernel, side by side

| When | The host | The kernel |
| --- | --- | --- |
| Start | Writes `ap_start` | Clears its status, waits for a command |
| Each command | Sends `CmdHdr`, then the data burst if any | Reads the header, checks it, processes the data, writes `RespHdr` and the results |
| End | Sends `END`, waits for `ap_done` | Returns |
| Error | Waits for `ap_done`, reads `halted` / `error` / `tx_id`, resets the stream path | Sets the status, closes its output burst, returns |
| Restart | Writes `ap_start` again | Starts clean |

## Why not...

**...write the configuration over AXI-Lite?** The stream and AXI-Lite are two
separate paths with no ordering between them. If the host writes new
coefficients while commands are still queued in the stream, which commands use
the old coefficients and which the new? There is no good answer. A
configuration command on the stream arrives in order with the data, so the
answer is always "every command after it".

**...report errors in a response footer and keep running?** Then the kernel
needs hardware to recover from every error in every state, and has to be tested
for each. And after an error, the host has to resynchronize anyway (see the next
question), so recovering inside the kernel buys little.

**...discard input up to the next TLAST, so the next activation starts on a
clean header?** That only removes the rest of the current burst. The host may
already have queued more commands behind it, and the kernel cannot know how
many. A drain looks like recovery but guarantees nothing. Saying plainly that the
stream is undefined, and that the host resets it, is honest and simpler.

**...keep the configuration from one activation to the next?** Then whether a
command is computed correctly depends on what an earlier activation left behind,
including one that ended in an error. Starting clean every time makes every
activation testable on its own.

## Testing an error in C simulation

In C simulation the kernel is an ordinary function call, and the host's stream
reset is modeled by giving the next activation fresh, empty streams. So an error
test is two activations:

1. an activation that ends in the error: check the status it sets, and that its
   last output burst ends with TLAST;
2. a fresh activation that must work correctly, which shows the host can
   recover.

## The Waveflow example

The [Waveflow streaming polynomial example](https://sdrangan.github.io/waveflow/docs/examples/stream_inband/)
is the reference implementation your agent will follow. Its command header has
three fields: `cmd_type` (`DATA` or `END`), `tx_id` and `nsamp`.

**Where the example and this page differ, follow this page.** At the time of
writing, the example's polynomial coefficients are written over AXI-Lite rather
than sent as a command on the stream. Your design sends its configuration as a
command, as in rule 1.

## Check your understanding

* The host sends `CONFIG`, then three `DATA` commands, and the second `DATA`
  command's sample burst ends early. What does the host see on `out_stream` and
  in the status registers, and what must it do next?
* Why does rule 4 matter to a DMA engine receiving `out_stream`?
* A classmate's kernel keeps its coefficients in a `static` variable that
  survives between activations. Which rule does that break, and what test would
  catch it?

---

Next: [In class: prompt design and C simulation →](./inclass.md)
