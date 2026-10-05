# game — what it asks of the node

TODO asked whether the input constraint that `remote-browser/stream/` hit on an
unmodified node is inherited here. **It is not**, and the reason is worth stating
precisely.

## From the node

| | |
|---|---|
| slot | one TCP port, `8080`, speaking HTTP (`service.json → api[0]`) |
| network | none. `network: []` |
| RAM | 256 MiB at init, 512 MiB at most. The emulator's own state is 4 KiB of guest RAM plus a 2 KiB framebuffer |
| CPU | 2 vCPU-equivalents at init. The interpreter loop is ~600 instructions/frame at 60 Hz |
| disk | read-only rootfs. `read_only_filesystem: true`. `at_init.disk_space` is 512 MiB and is a **ceiling** on current nodo |
| GPU | **none** |
| audio device | **none** |
| input device | **none** |
| dependencies | none |

## On input

`remote-browser/stream/` could not get input on an unmodified node because it was
streaming an *encoded video frame* out and needed a separate back-channel — a
device, or a protocol the node does not have — to get key events in.

This capsule does not have that problem, because it never had a video stream. Both
directions ride the one HTTP slot the specification already declares:

```
GET /frame?keys=<16-bit mask>   ->  2048 bytes framebuffer + 1 byte sound flag
```

The key mask goes **up** in the query string and the framebuffer comes **down** in
the response body. One request per frame, ~30 Hz from the browser. There is no
second channel, no `/dev/input`, no evdev, no uinput, nothing for the node to
provide. Held keys expire after 1 s without a new request
(`service/app.py`, `LAST_INPUT`), so a disconnected viewer releases the keys
rather than leaving them stuck down.

Sound is one bit: the CHIP-8 sound timer is non-zero or it is not. The browser
owns an oscillator and gates its gain. No audio device is asked for.

**This is not a general answer.** It works because a CHIP-8 frame is 2 KiB and the
subject tolerates 30 Hz request/response latency. A capsule that needed 60 Hz at
any real resolution would be back in `remote-browser`'s problem, and the input
half would still be fine — it is the *output* half that forced the question there.

## From your host

```
nodo tunnel <instance> 8080
```

then a browser. Keyboard `1234/QWER/ASDF/ZXCV` maps to the CHIP-8 keypad, and
there are on-screen buttons for pointer input. The included demo ROM responds to
keys 4 and 6 (`Q` / `E`).

## What it actually costs

Measured — full method in [`../reports/measurements.md`](../reports/measurements.md).

| | |
|---|---|
| payload (`payload.ch8`) | **45 bytes** |
| `chip8`, static, stripped | **584 KiB** |
| docker image | 192 MB (`docker images`), 134.5 MiB of regular files |
| packed service | 141,712,242 B in `__registry__` |
| blocks emitted | **0** |

The README estimated 10–20 MB for a static emulator and 15–25 MB for the image.
The emulator came in at 584 KiB — better than estimated by 20x. The image came in
at 134.5 MiB — worse by 5–9x.

The emulator is **0.4%** of this capsule. The rest is `python3` and its stdlib
(34.9 MiB), `perl`, `libcrypto`, apt, and the Debian base. A 584 KiB interpreter
and a 45-byte ROM shipped inside 134 MiB is the clearest statement in this repo of
what is actually wrong: nothing here needed a distribution, and it got one anyway
because `FROM debian:trixie-slim` and `python3 app.py` were the fast way to build
it. A static `/init` with no Python and no shell is the build this subject
deserves and did not get.

The capsule now sets `read_only_filesystem: true`. That removes the 128+64 MiB
ext4 floor on current nodo. It does not remove Debian. Do not add
`shared_filesystems`.

## Zero blocks

This capsule emitted **no** content-addressed blocks at all. Its largest file is
`python3.13` at 6.36 MiB, and this node runs `MIN_BUFFER_BLOCK_SIZE` at 10,000,000
— so nothing clears the bar and all 134.5 MiB is inlined into one protobuf.

At the documented default of 32,768 (`config.example.yaml:322`) the same tree
would have produced **951 blocks / 121.4 MiB**, nearly all of it Debian shared
with any other Debian capsule. The threshold, not the design, is what decides
whether this capsule shares anything.
