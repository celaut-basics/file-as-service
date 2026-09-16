# file-as-service

Any file is a service: the bytes, plus the minimal program that interprets them,
sealed in one content-addressed [Celaut](https://github.com/celaut-project/nodo)
service. A film is a service that contains a film and a decoder. A game is a
service that contains a game and the machine it runs on. A PDF is a service that
contains a PDF and something that draws pages.

**Nothing here asks anything of the node.** That is the whole point.

## Why not a file-transfer RPC

A node already moves one kind of artifact between peers. `GetService` takes a
content hash and streams back a spec and its filesystem, chunked, over the same
generic `buffer.Buffer` transport every other call rides on. Structurally that is
already *give me this blob by hash* — it is only spelled `Service`.

So the cheap way to exchange arbitrary files is not to add a second RPC that does
the same thing with a different name. It is to stop treating "file" as a separate
kind of thing. Everything the node has built around services then applies without
a line of new code in it:

| | comes from |
|---|---|
| transfer | `GetService`, content-addressed and chunked |
| trust | per-peer reputation, local and on-chain |
| payment | MU pricing over the existing ledgers |
| reach | `ResolveNetwork`, the `Peer`/`Instance` addressing |
| policy | the operator's network blacklist/whitelist |
| **isolation** | the interpreter runs in a microVM, not on your machine |

The last row is not a consolation prize. A PDF parser and a video demuxer are two
of the most reliably exploitable programs most people run, and the normal way to
open an untrusted one is to point your own at it. Here the thing that opens it is
fixed by a content hash, declared by a specification you can read, and confined to
a guest.

## What it costs

There is no inherent floor. `nodo`'s `MIN_ROOTFS_BYTES = 128 MiB` and
`OVERHEAD_BYTES = 64 MiB` (`src/virtualizers/microvm/limits.py:54-55`) follow from
building a **writable, pre-sized ext4 rootfs**; `MIN_MEM_MIB` is a configurable
default whose real floor in code is 16 MiB. A read-only squashfs or erofs image —
the natural shape for something immutable and content-addressed — has almost no
slack, and those constants stop applying.

Component minimums, as orders of magnitude to be measured rather than trusted:

| component | size |
|---|---|
| kernel, bzImage, virtio-only config | 1.5–4 MB |
| busybox static (shell + ~300 utilities) | ~1 MB |
| Alpine minirootfs | ~3.3 MB packed, ~8 MB extracted |
| one static binary as `/init`, no shell | 0.1–2 MB |
| guest RAM, shell only | 16–32 MB |
| guest RAM, with a decoder running | 48–96 MB |

And per subject, assuming a read-only image:

| subject | interpreter | image | payload | overhead |
|---|---|---|---|---|
| **film** | decode-only h264/aac, 10–20 MB | 15–25 MB | 1–8 GB | **<1%** |
| **retro game** | static emulator, 10–20 MB | 15–25 MB | 5–100 MB | 20–300% |
| **PDF** | `mutool` render-only, 8–15 MB | 12–20 MB | 0.1–10 MB | 100–10000% |
| **text, image** | anything at all | ~10 MB | KB | absurd |

Note the lever hiding in the first column: a full ffmpeg is 70–90 MB, a build that
decodes exactly one codec is 5–15 MB. Shipping the general tool instead of the
required decoder costs an order of magnitude, every copy.

## Measured

The table above is an estimate. Three capsules now exist, and they were packed and
run rather than reasoned about. Full method and workings in
[reports/measurements.md](reports/measurements.md).

| subject | interpreter, estimated | **measured** | image, estimated | **measured** |
|---|---|---|---|---|
| **film** | 10–20 MB | **4.44 MiB** | 15–25 MB | **138.4 MiB** |
| **retro game** | 10–20 MB | **584 KiB** | 15–25 MB | **134.5 MiB** |
| **PDF** | 8–15 MB | **68.2 MiB** | 12–20 MB | **214.9 MiB** |

The lever is real. A decode-only ffmpeg is **4.44 MiB** against 70–90 MB for the
general tool — better than the estimate, and worth more than the order of
magnitude claimed. A static CHIP-8 interpreter is 584 KiB. That column holds.

The next column does not, by 5–18x, and not because of the interpreters. The film
capsule's decoder is **3.2%** of it; the game's emulator is **0.4%**. The rest is
Debian: `python3` and its stdlib at 34.9 MiB, `libcrypto`, `perl` twice, apt. The
estimate assumed the image *was* the interpreter plus a libc. What got built was
the interpreter plus a general-purpose distribution, because `FROM
debian:trixie-slim` and a stdlib HTTP server were the convenient choices rather
than the small ones. The row the component table actually describes — one static
binary as `/init`, no shell — is a build this repo did not do.

The PDF row is worse than that, and it is the estimate's own error. `mutool` is
515 KiB, but Debian links it against a **67.7 MiB** `libmupdf.so` carrying every
font and filter MuPDF can parse. "`mutool` render-only, 8–15 MB" describes
something nobody compiled.

Two more numbers the table never had. The guest kernel is **18.2 MiB**, not
1.5–4 MB — nodo ships a distribution-style build because it has to boot every
service, not this one. And there is no read-only rootfs path: `nodo pack` builds
a writable ext4, so `OVERHEAD_BYTES` is a flat **64 MiB per capsule**, 44% of the
film image and 500% of the 12 MB capsule imagined above.

## Where the argument actually rests

For a film the wrapper is noise and the case is closed. For a PDF it is not —
unless the interpreter is *shared*. The kernel is one blob common to every service
that will ever exist. The interpreter is one blob common to every service of its
kind. If each is transferred once and referenced thereafter, the marginal cost of
the five-hundredth PDF capsule is the PDF.

The packer already does its half: a file at or above `MIN_BUFFER_BLOCK_SIZE`
(32 kB) is stored as its own content-addressed block and referenced by hash
(`docs/PACKING.md:1749`). **This part is now confirmed by measurement.** Two PDF
capsules were packed differing only in `payload.pdf`; both service records point at
the same block `bb2331bf…` — the 67.7 MiB `libmupdf.so` — and `__block__` holds one
copy of it, not two. The interpreter is genuinely shared.

The saving it produced was **18.6%** of the second capsule, not 99%, and the three
reasons why are the shape of the remaining work: sharing is *file*-level rather
than *layer*-level and happens only when two builds emit byte-identical files; the
threshold that decides eligibility was 10 MB on the node that ran this, excluding
every file in the film and game images (which shared **nothing**, despite being
4,060 nearly-identical files each); and the 64 MiB ext4 floor is per-capsule and
shares with nothing at all.

Two things are missing, and neither is free.

**1. The skip has to reach the wire.** Today's deduplication is a storage
property, not a bandwidth one. When the receiver already holds a block it drains
the incoming buffers and throws them away (`bee_rpc/client.py:271-277`) — the
bytes cross the network regardless, because the function that would tell the
sender to stop is an empty body (`client.py:162-164`). Tracked upstream as
[bee-rpc-over-grpc-py#8](https://github.com/bee-rpc-protocol/bee-rpc-over-grpc-py/issues/8).

**2. Interpreter images have to be reproducible.** If every packager builds their
own viewer with a different toolchain or a different timestamp, the hashes diverge
and nothing is ever shared. What this wants is a small set of canonical, pinned,
published interpreter images that packagers reference by hash — which is a
curation problem at least as much as a technical one.

Until both hold, this is a design that already pays for itself on large payloads
and is an argument about small ones.

## Getting the pixels to a person

Once the content is a service there are two ways someone actually watches it:
fetch it and run it on your own node, or have a peer run it and send you the
pixels. The second is
[remote-browser](https://github.com/celaut-basics/remote-browser)'s subject, and
the three answers it measured — VNC, waypipe, H.264 stream — apply here unchanged.
This repo is about the first: what goes in the capsule, how small it can be, and
what makes two capsules share their blocks.

## Status

Three capsules build, pass their tests, and pack to validated service ids:

| subject | service id |
|---|---|
| film | `d7ee25d8bac9c9d4d5f3c4a4be1e63a1e6a6a7de52ae09e608ac434f0fd6c262` |
| game | `1e9fd5b0045d62ea683e3f91bf0f0c2f73725ba6d706b33fcba127f6073cb033` |
| pdf | `b5aa3b1fde8c2c0a4f7d4e0df224476570ec2d8cc6a0c3754dcee94ffdddb8f4` |

`nodo execute` was run against the pdf capsule and it launched, served rendered
PNG pages over its slot, and returned 404 for the source document. It needed two
node-side fixes to boot at all
([nodo#368](https://github.com/celaut-project/nodo/issues/368)).

Every number in the estimate tables above was written down so that building the
thing could contradict it. It did — see [reports/measurements.md](reports/measurements.md)
and the per-subject `NODE-REQUIREMENTS.md`. What remains is in [TODO.md](TODO.md).
