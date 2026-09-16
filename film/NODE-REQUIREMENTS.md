# film — what it asks of the node

Nothing that is not already in the specification. This file exists so that claim
can be checked rather than repeated.

## From the node

| | |
|---|---|
| slot | one TCP port, `8080`, speaking HTTP (`service.json → api[0]`) |
| network | none. `network: []` — the capsule opens no outbound connection |
| RAM | 256 MiB at init, 512 MiB at most. Measured working set is far below that; see below |
| CPU | 2 vCPU-equivalents at init (`cpu_quota 200000 / cpu_period 100000`) |
| disk | the rootfs the packer built. `at_init.disk_space` asks for 1 GiB and the node takes that literally — see *What it actually costs* |
| GPU | none. There is no X server, no compositor, no DRM device, no `/dev/dri` |
| audio device | none. Audio leaves as PCM bytes over the same HTTP response |
| input device | none |
| dependencies | none. No `__services__`, no child services |

## From your host

One browser, and a way to reach the slot:

```
nodo tunnel <instance> 8080
```

then open the tunnelled port. The slot's `/` is an `index.html` that draws frames
into a `<canvas>` and schedules PCM through a `WebAudio` context. Nothing is
installed on your machine; the decoder never runs there.

## What it actually costs

Measured on this node (arm64, `nodo pack` local backend). Full method and the rest
of the numbers in [`../reports/measurements.md`](../reports/measurements.md).

| | |
|---|---|
| ffmpeg, decode-only h264/aac, stripped | **4.44 MiB** |
| docker image | 199 MB (`docker images`), 138.4 MiB of regular files |
| packed service in `__registry__` | 139.1 MiB |
| rootfs.ext4 nodo builds | see the disk note below |

The README's estimate for the interpreter was 10–20 MB. The decode-only build came
in at 4.44 MiB — better than the estimate, and 15–20x smaller than a distribution
ffmpeg. That part of the argument survives contact.

What does not survive is the rest of the image. The interpreter is 3% of it. The
other 97% is Debian: `python3` and its stdlib (28.5 MiB), `libcrypto` (6 MiB),
`perl` (3.6 MiB twice), apt. A capsule whose interpreter is 4.44 MiB ships 138 MiB
because the base image was chosen for being easy rather than for being small.

**Disk.** `at_init.disk_space: 1073741824` is not a ceiling the node clamps to what
it needs — `limits.initial_rootfs_size_bytes` takes the **max** of `MIN_ROOTFS_BYTES`
(128 MiB), the populated tree plus `OVERHEAD_BYTES` (64 MiB), and the declared
figure. Declaring 1 GiB means `mkfs.ext4` formats a 1 GiB image for a 138 MiB tree.
The floor is real and the declaration is a second, larger floor on top of it.

## What this is not

The film case works, but call it what it is: the capsule **re-encodes to raw
RGB24** before the bytes leave the slot. 320×180 at 12 fps is 20.7 MB/s on the
wire for a source that was 120 kB for four seconds. That is a preview transport —
it demonstrates that the decoder ran inside the guest and that the source file
never left it. It is not a player, and it does not scale to a real film at real
resolution.

The honest shape for that is the one `remote-browser/stream/` measured: encode the
decoded frames to H.264 again on the way out. This capsule deliberately does not,
because an encoder in the image would have made the "decode-only build is small"
measurement meaningless.
