# TODO

Nothing is packed. The README states a cost model built from documentation and
component sizes rather than from a running system, so the list below is in three
halves: what has to be **settled** before any of it is worth building, what is
left to **build**, and what this repo does not control.

## Settle first, in this order

Each of these can invalidate the README rather than refine it.

1. **Can a service boot from a read-only rootfs?** The whole cost model assumes
   squashfs or erofs. If `nodo`'s packer and virtualizers have a writable ext4
   wired in, then `MIN_ROOTFS_BYTES` (128 MiB) and `OVERHEAD_BYTES` (64 MiB) are
   not policy constants that can be set aside — they are the floor, and a 12 MB
   PDF capsule is really a 192 MB one. Read `src/virtualizers/microvm/build.py`
   and the `ch`/`qemu` boot paths before anything else.

2. **Do two capsules with the same interpreter actually share its block?** The
   packer stores a file at or above 32 kB as its own content-addressed block, so
   in principle yes. Confirm it for real: pack the same interpreter into two
   services that differ only in payload, and check that `BLOCKDIR` holds one copy
   of the interpreter and not two. This is the claim the argument for small files
   rests on; if it fails, only films and games survive.

3. **How small is the kernel actually.** Every number in the README's component
   table is an order of magnitude from general knowledge, not a measurement. The
   kernel is the one most likely to be wrong by 10x, because it depends on
   whether the VMM takes a compressed bzImage or an uncompressed ELF.

4. **Whether a decode-only build is as small as claimed.** 5–15 MB for one codec
   versus 70–90 MB for a full ffmpeg is the difference between the film case
   being noise and being merely fine. It is also the piece of work most likely to
   be tedious.

## Build

One directory per subject, following `remote-browser`'s layout: `.service/`
(Dockerfile, `pack_config.json`, `service.json`), `service/entrypoint.sh`, and a
`NODE-REQUIREMENTS.md` saying what it wants from the node and from your host.

- **`film/`** — the case that closes itself. Decode-only h264/aac, no X server,
  no compositor, frames to wherever the pixels leave. Build this one first:
  at <1% overhead it does not depend on block sharing working.
- **`game/`** — a static emulator plus a ROM. Needs input, which is the thing
  `remote-browser/stream/` could not get on an unmodified node; find out whether
  that constraint is inherited here.
- **`pdf/`** — `mutool` render-only. The case that exists to be the unfavourable
  one, and the honest test of whether "any file is a service" means anything
  outside the cases that were easy.

Each one should report its **measured** image size against the README's estimate.
The table is written down in order to be contradicted.

## Not ours to fix

- [bee-rpc-over-grpc-py#8](https://github.com/bee-rpc-protocol/bee-rpc-over-grpc-py/issues/8) —
  until the block-skip signal reaches the wire, sharing an interpreter saves disk
  on the receiving node and nothing on the network. The film case does not care.
  The PDF case is entirely this.
- Canonical, reproducibly-built interpreter images that packagers reference by
  hash. Without them the hashes diverge per packager and nothing is shared, no
  matter what the transport does. This probably belongs somewhere else, and
  probably needs deciding by more than one person.
