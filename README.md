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

## Where the argument actually rests

For a film the wrapper is noise and the case is closed. For a PDF it is not —
unless the interpreter is *shared*. The kernel is one blob common to every service
that will ever exist. The interpreter is one blob common to every service of its
kind. If each is transferred once and referenced thereafter, the marginal cost of
the five-hundredth PDF capsule is the PDF.

The packer already does its half: a file at or above `MIN_BUFFER_BLOCK_SIZE`
(32 kB) is stored as its own content-addressed block and referenced by hash
(`docs/PACKING.md:1749`). Two things are missing, and neither is free.

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

Design only. Nothing is packaged yet — see [TODO.md](TODO.md). Every number above
is an estimate written down so that building the thing can contradict it.
