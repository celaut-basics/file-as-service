# Measurements

The README's cost table was written from documentation and general knowledge, in
order to be contradicted. This is the contradiction. Everything below was run on
one machine on 2026-09-16; nothing is quoted from a spec.

**Audit note (2026-10-05).** These numbers are from nodo `7a743210`. Current nodo
`dev` @ `698e6583` has `read_only_filesystem` (nodo #369 closed). The capsules now
declare that flag. This file is not a new measurement. Nothing was packed or
executed on a node for the audit.

## Method

Host: macOS 26.6 / Apple Silicon. Docker builds in a `colima` VM (aarch64 guest,
`/dev/kvm` present). `nodo` runs **inside that same VM** at `/nodo`, checkout
`7a743210`, `packer.local: true`, so `nodo pack` uses the local BuildKit backend
and `nodo execute` uses Cloud Hypervisor with the arm64 guest kernel.

All three capsules are `linux/arm64`, `FROM debian:trixie-slim` pinned by digest.

Reproduce:

```sh
python3 tools/fixtures.py          # payloads (needs host ffmpeg with libx264)
python3 tools/prepare.py           # stage shared code, write service.json
docker build -f film/.service/Dockerfile -t fas-film film/     # and game, pdf
docker run -d --name fas-film --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  --user 65534:65534 --cap-drop ALL -p 127.0.0.1:18081:8080 fas-film
python3 tests/smoke.py
```

## Smoke test

Against the three containers under the hardened flags above:

```json
{
  "film_frames": 48,
  "pcm_bytes": 1540096,
  "pdf_page_bytes": [10460, 11960],
  "game_input_changes_pixels": true
}
```

48 distinct RGB24 frames and 1.54 MB of f32 PCM from the film slot; two
different-sized PNG pages from the pdf slot; the game's framebuffer changes when
keys are pressed. All three return 404 for the raw payload path and 400 for
malformed input.

## Interpreter binaries

The first column of the README's per-subject table, measured.

| subject | interpreter | estimate | **measured** | verdict |
|---|---|---|---|---|
| film | `ffmpeg`, `--disable-everything` + h264/aac decode, stripped | 10–20 MB | **4.44 MiB** | better than claimed |
| game | `chip8`, static, `-O2 -s` | 10–20 MB | **584 KiB** | far better |
| pdf | `mutool` | 8–15 MB | **515 KiB** binary + **67.7 MiB** `libmupdf.so.25.1` | **much worse** |

The decode-only ffmpeg claim holds and then some: 4.44 MiB against a Debian
`ffmpeg` package that is 70–90 MB, so the lever the README points at is real and
is worth more than 10x.

The `mutool` line is where the estimate breaks. `mutool` itself is half a
megabyte, but Debian's build links `libmupdf.so` dynamically and that object is
67.7 MiB — it carries every font, every filter, every codec MuPDF can parse. The
README estimated 8–15 MB for "render-only". Nothing in this build is render-only;
a render-only MuPDF would have to be compiled the way the ffmpeg here was, and was
not.

## Docker images

| subject | `docker images` | export tar | regular files on disk | files |
|---|---|---|---|---|
| film | 199 MB | 144,992,768 B | **138.4 MiB** | 4,060 |
| game | 192 MB | 140,811,776 B | **134.5 MiB** | 4,061 |
| pdf | 324 MB | 225,280,512 B | **214.9 MiB** | 4,167 |

Against a README estimate of 12–25 MB per image. **Off by 6–10x**, and not because
of the interpreters.

What is actually in a 138 MiB film image:

| | |
|---|---|
| `python3.13` + stdlib | 28.5 MiB + 6.36 MiB binary |
| `libcrypto.so.3` | 6.01 MiB |
| `perl` (×2 paths) | 7.28 MiB |
| `libstdc++`, `libapt-pkg`, `libdb` | 6.34 MiB |
| **the interpreter** | **4.44 MiB** |
| the payload | 117 KiB |
| everything else (Debian base) | ~79 MiB |

The interpreter is **3.2%** of the film capsule. The estimate assumed the image
*was* the interpreter plus a libc. It is the interpreter plus a general-purpose
distribution, because `debian:trixie-slim` and a stdlib HTTP server were the
convenient choices, not the small ones. A static-binary `/init` with no Python and
no shell — the row the README's component table actually describes — is a
different build that this repo did not do.

## Packed services

```
nodo pack <subject>   # positional dir, no flags
```

| subject | service id | `__registry__` bytes | blocks emitted |
|---|---|---|---|
| film | `d7ee25d8bac9c9d4d5f3c4a4be1e63a1e6a6a7de52ae09e608ac434f0fd6c262` | 145,894,422 (flat file) | **0** |
| game | `1e9fd5b0045d62ea683e3f91bf0f0c2f73725ba6d706b33fcba127f6073cb033` | 141,712,242 (flat file) | **0** |
| pdf | `b5aa3b1fde8c2c0a4f7d4e0df224476570ec2d8cc6a0c3754dcee94ffdddb8f4` | 310,173,306 (directory) | **1** |
| pdf, second payload | `46a007b71ccd405e2df53e466ef856a0315741504467d9d4d3bbb6caaf0d1bda` | 310,173,340 (directory) | **1**, the same one |

Film and game emitted **zero blocks**, and that is a configuration accident worth
naming. `packer.MIN_BUFFER_BLOCK_SIZE` is documented at **32,768** in
`config.example.yaml:281` on `7a743210`. This node's `config.yaml` carries it at **10,000,000**
under a `misc:` key. Film's largest file is `python3.13` at 6.36 MiB — under 10 MB
— so nothing in the film or game image is block-eligible and the entire 138 MiB
filesystem is inlined into one protobuf. Only `libmupdf.so` (67.7 MiB) clears the
bar, which is why pdf is the only subject with a block at all.

What the documented 32 KiB threshold would have produced, computed over the same
exported trees:

| subject | blocks at 32 KiB | block bytes | inlined |
|---|---|---|---|
| film | **952** | 125.4 MiB | 13.1 MiB |
| game | **951** | 121.4 MiB | 13.1 MiB |
| pdf | **983** | 201.6 MiB | 13.3 MiB |

At the documented default, 90% of every capsule is content-addressed blocks. At
this node's configured value, 0–31% is.

## Rootfs the node actually builds

`nodo execute` on the pdf capsule produced `bundle.json`:

```json
{
  "arch": "linux/arm64",
  "requested_disk_space_bytes": 1073741824,
  "rootfs_size_bytes": 1073741824,
  "kernel_path": "/nodo/cloud_hypervisor/kernels/linux/arm64/vmlinuz",
  "initramfs_path": "/nodo/cloud_hypervisor/initramfs/linux/arm64/initramfs"
}
```

A **1,073,741,824-byte ext4 image for a 221 MiB tree**. `du` reports 235 MiB
allocated because the file is sparse, but `rootfs_size_bytes` is what the node
records, prices and hands the VMM.

That is our own fault before it is the node's: `service.json` declares
`at_init.disk_space: 1073741824`, and
`limits.initial_rootfs_size_bytes` (`src/virtualizers/microvm/limits.py:368-374`)
takes the **max** of three terms, so a declared figure is a floor, never a cap.

What the floor would be with no declaration at all:

| subject | tree | floor (`max(128 MiB, tree + 64 MiB)`) | slack |
|---|---|---|---|
| film | 144.6 MiB | 208.6 MiB | 64.0 MiB (44.3%) |
| game | 140.6 MiB | 204.6 MiB | 64.0 MiB (45.5%) |
| pdf | 221.3 MiB | 285.3 MiB | 64.0 MiB (28.9%) |

`OVERHEAD_BYTES` is a flat 64 MiB (`limits.py:54`), so it is 44% of a film capsule
and would be 500% of the 12 MB capsule the README imagined. `MIN_ROOTFS_BYTES`
(128 MiB, `limits.py:55`) never binds here because every tree is already above it.

## Kernel and initramfs

TODO item 3 asked whether the kernel figure was wrong by 10x. It is.

| | estimate | **measured** (arm64) |
|---|---|---|
| guest kernel `vmlinuz` | 1.5–4 MB | **19,126,280 B (18.2 MiB)** |
| initramfs (gzip'd newc cpio) | — | **1,190,487 B (1.14 MiB)** |
| busybox inside it, static | ~1 MB | **2,242,336 B (2.14 MiB)** |

The kernel is **5–12x** the estimate. It is a distribution-style build (6.12.103,
`linux,dummy-virt`) with IPVS, CAN, 9pnet, SCTP, bridge netfilter and X.509
verification all compiled in — visible in the boot log. The README's 1.5–4 MB is
what a virtio-only `make tinyconfig` derivative costs, and nobody built one; nodo
ships a general kernel because it has to boot every service, not this one.

Both are shipped once per node, not once per service, so they do not scale with
the number of capsules. That is the honest mitigation — but it means the kernel is
19 MB of the *first* capsule you ever fetch, which is four times the film
interpreter.

## Execution

`nodo execute b5aa3b1f…` **succeeded**, after two node-side fixes:

```
🚀 Service launched successfully!
🌐 Endpoints available:
  • http://192.168.200.161:8080
```

and from inside the VM, against the running guest:

```
/health          -> {"ok": true}
/page?n=1        -> http=200 bytes=10460   89 50 4e 47 …  (PNG)
/page?n=2        -> http=200 bytes=11960   different sha256
/payload.pdf     -> 404
/page?n=0        -> 400
```

**The capsule runs as a microVM and renders pages. The source PDF never leaves the
guest.** That is the claim the repo makes, executed rather than asserted.

It did not work out of the box. Two bugs, each reproduced and fixed
independently before being combined:

1. **`console=ttyS0` on arm64.** `virtualizers.ch.KERNEL_CMDLINE_EXTRA` defaults
   to `console=ttyS0` (`src/virtualizers/ch/execute.py:60`). The arm64 guest
   registers a PL011 at `ttyAMA0` — `9000000.pl011: ttyAMA0 at MMIO 0x9000000` in
   the boot log — and has no `ttyS0`.
2. **No `/dev/console` in the initramfs.** `bash/build_ch_initramfs.sh:83` creates
   an empty `$ROOT/dev`, and `/init` line 2 is `exec >/dev/console 2>&1` before
   anything mounts devtmpfs. The kernel prints `Warning: unable to open an initial
   console.` and `/init` exits 1 on its second line.

Symptom of either, or both:

```
[    1.680230] Warning: unable to open an initial console.
[    1.695887] Run /init as init process
[    1.712626] Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000100
```

Fixing only (1) still panicked; fixing only (2) still panicked. Both, plus a
daemon restart — `ConfigManager` reads `config.yaml` once per process and never
re-reads it (`src/utils/config.py:188-192`), so editing it under a running
`nodo serve` changes nothing — and it boots. Filed as
[celaut-project/nodo#368](https://github.com/celaut-project/nodo/issues/368).

## The four questions TODO said to settle first

### 1. Can a service boot from a read-only rootfs?

**No, on nodo `7a743210` (2026-09-16).** That checkout's
`src/virtualizers/microvm/build.py:1122` called `_mkfs_ext4`, which shelled
out to `mkfs.ext4` (`build.py:902-935`) and had no squashfs or erofs path. The
kernel cmdline was `root=/dev/vda rw` (`execute.py:867`) and `/init` mounted it
`mount -t ext4 -o rw /dev/vda /newroot`.

On that node, `MIN_ROOTFS_BYTES` and `OVERHEAD_BYTES` were the floor. The measured
consequence: 64 MiB of unconditional slack per capsule, and a 12 MB PDF capsule
really would be a 192 MB one. Filed as
[celaut-project/nodo#369](https://github.com/celaut-project/nodo/issues/369)
(now closed). Current nodo `dev` @ `698e6583` accepts `read_only_filesystem`.
This section is history, not a new measurement.

### 2. Do two capsules with the same interpreter share its block?

**Yes at file level — and this is the good news of the report.** Two pdf capsules
were packed whose only difference is `payload.pdf`
(`a5aafe3a…` vs `ac1221d4…`, 889 B and 906 B). Both service records point at the
same block:

```
b5aa3b1f…/_.json  [1, ["bb2331bfdc5916a1a912a73e9299d6282c13fe2b49c203d3b07804aa22183015", […]], 2]
46a007b7…/_.json  [1, ["bb2331bfdc5916a1a912a73e9299d6282c13fe2b49c203d3b07804aa22183015", […]], 2]
```

and `__block__` holds **13 files, not 14** — `bb2331bf…` is the 71,014,688-byte
`libmupdf.so`, stored once. The 67.7 MiB interpreter was transferred and stored
once and referenced twice. The claim the argument rests on is **confirmed**.

Three caveats, all measured:

- It is **file-level, not layer-level**. Nothing in the packer groups an image
  layer into one block. Sharing happens only because two builds produced a
  byte-identical file, which here is guaranteed only by both pulling the same
  pinned digest.
- It is **gated on `MIN_BUFFER_BLOCK_SIZE`**, and this node's value (10 MB)
  excludes every file in the film and game images. Those two capsules share
  nothing with anything, despite being 4,060 and 4,061 nearly-identical files.
- **It saves disk, not bandwidth.** The receiver drains and discards blocks it
  already has (`bee_rpc/client.py:271-277`); the skip never reaches the wire.
  [bee-rpc-over-grpc-py#8](https://github.com/bee-rpc-protocol/bee-rpc-over-grpc-py/issues/8),
  PR [#9](https://github.com/bee-rpc-protocol/bee-rpc-over-grpc-py/pull/9).

The second pdf capsule cost 310 MB of new registry bytes and reused 71 MB of
block. Sharing recovered **18.6%** of the total. That is the real number behind
"the marginal cost of the five-hundredth PDF capsule is the PDF" — today it is
81% of a whole capsule.

### 3. How small is the kernel actually?

**18.2 MiB**, against an estimate of 1.5–4 MB. Wrong by 5–12x, in the direction
TODO guessed it might be. See above.

### 4. Is a decode-only build as small as claimed?

**Yes, and smaller.** 4.44 MiB against a claim of 5–15 MB and a full ffmpeg of
70–90 MB. This is the one estimate that survived, and it is the one the film case
depends on.

## Summary against the README's table

| subject | estimated image | **measured image** | estimated interpreter | **measured interpreter** |
|---|---|---|---|---|
| film | 15–25 MB | **138.4 MiB** (5.5–9x) | 10–20 MB | **4.44 MiB** ✅ |
| game | 15–25 MB | **134.5 MiB** (5.4–9x) | 10–20 MB | **584 KiB** ✅ |
| pdf | 12–20 MB | **214.9 MiB** (11–18x) | 8–15 MB | **68.2 MiB** ❌ |

The README's thesis — *a decode-only interpreter is an order of magnitude smaller
than the general tool, so the wrapper is noise on a large payload* — is correct
about interpreters and wrong about capsules. The capsule is not the interpreter.
It is the interpreter plus Debian plus a 64 MiB ext4 floor plus, once per node, a
19 MB kernel. On a 4 GB film that is still noise. On this repo's 889-byte PDF the
overhead is **25,000,000%**, and no amount of block sharing fixes the part that is
Debian.

What would: a static interpreter as `/init` with no Python and no shell, a
read-only rootfs (#369), and layer-level rather than file-level blocks (#370).
Those are three separate pieces of work, and only the first is ours.
