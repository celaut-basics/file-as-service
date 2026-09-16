# pdf — what it asks of the node

The unfavourable case, kept because it is the honest test of whether "any file is
a service" means anything outside the cases that were easy.

## From the node

| | |
|---|---|
| slot | one TCP port, `8080`, speaking HTTP (`service.json → api[0]`) |
| network | none. `network: []` |
| RAM | 256 MiB at init, 512 MiB at most |
| CPU | 2 vCPU-equivalents at init |
| disk | see below — this is the whole problem |
| GPU | none |
| audio / input devices | none |
| dependencies | none |

## From your host

```
nodo tunnel <instance> 8080
```

then a browser. The slot's `/` is a page with next/previous buttons that fetch
`/page?n=N` and set it as an `<img>` src. Each response is a PNG rendered by
`mutool` inside the guest. The PDF itself has no route; there is no endpoint that
returns it.

## What it actually costs

Measured — full method in [`../reports/measurements.md`](../reports/measurements.md).

| | |
|---|---|
| payload | **889 bytes** |
| `mutool` binary | 515 KiB |
| `libmupdf.so.25.1` | **67.7 MiB** |
| docker image | 324 MB (`docker images`), 214.9 MiB of regular files |
| packed service | 310,173,306 B in `__registry__`, 1 block |
| rootfs.ext4 nodo built | **1,073,741,824 B** |

The README estimated 12–20 MB for this image and 100–10000% overhead. The image is
**214.9 MiB** and the overhead on an 889-byte payload is **25,000,000%**.

Two things went wrong, and only one of them was predicted.

**Predicted:** small payloads make the wrapper dominate. Yes.

**Not predicted:** the interpreter is not small. `mutool` is 515 KiB, but Debian
links it against a 67.7 MiB `libmupdf.so` that carries every font and filter MuPDF
can parse. The README wrote "`mutool` render-only, 8–15 MB". Nothing about this
build is render-only. A render-only MuPDF would need compiling the way `film/`
compiles ffmpeg, and this capsule does not do that.

**Also not predicted:** `at_init.disk_space: 1073741824` is not a ceiling.
`limits.initial_rootfs_size_bytes` takes the max of `MIN_ROOTFS_BYTES` (128 MiB),
the tree plus `OVERHEAD_BYTES` (64 MiB), and the declared figure — so declaring
1 GiB formats a 1 GiB ext4 image for a 221 MiB tree. Without the declaration the
floor would still be 285.3 MiB. There is no read-only rootfs path
([nodo#369](https://github.com/celaut-project/nodo/issues/369)).

## The one thing that worked

This capsule is the proof for the repo's central claim, and it holds.

Two pdf capsules were packed that differ only in `payload.pdf`. Both service
records reference the same block `bb2331bf…` — the 67.7 MiB `libmupdf.so` — and
`__block__` holds one copy of it, not two. The interpreter **is** shared.

It saves disk and not bandwidth: the receiver still drains the bytes and discards
them ([bee-rpc#8](https://github.com/bee-rpc-protocol/bee-rpc-over-grpc-py/issues/8)),
and sharing happened at *file* level only because two builds pulled the same
pinned digest — nothing groups a layer into a block
([nodo#370](https://github.com/celaut-project/nodo/issues/370)). Measured, the
second capsule recovered 18.6% of its size. The marginal PDF is not yet the PDF.

## Verified running as a microVM

This is the capsule `nodo execute` was run against. From inside the VM, against
the guest at `192.168.200.161:8080`:

```
/health      -> {"ok": true}
/page?n=1    -> 200, 10460 bytes, PNG
/page?n=2    -> 200, 11960 bytes, different sha256
/payload.pdf -> 404
/page?n=0    -> 400
```

Getting there needed two node-side fixes (arm64 console name, missing
`/dev/console` in the initramfs) — see
[nodo#368](https://github.com/celaut-project/nodo/issues/368).
