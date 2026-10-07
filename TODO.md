# TODO

The README stated a cost model built from documentation and component sizes rather
than from a running system. Three capsules now exist and have been packed, run and
measured, so the "settle first" list below is answered rather than open — with the
numbers in [reports/measurements.md](reports/measurements.md). What is left is
smaller and sharper than what was there before.

## Settled

Each of these could have invalidated the README. Two did.

1. **Can a service boot from a read-only rootfs?** — **Not on 2026-09-16.
   Yes on current nodo `dev`.**
   On `7a743210` the packer always built writable ext4, so `MIN_ROOTFS_BYTES`
   (128 MiB) and `OVERHEAD_BYTES` (64 MiB) were the floor. Measured: 64 MiB of
   slack per capsule. Filed as
   [nodo#369](https://github.com/celaut-project/nodo/issues/369) (now closed).
   Current nodo (`698e6583`) reads `read_only_filesystem` as a JSON boolean
   (`src/packers/zip_with_dockerfile.py:453-481`) and builds squashfs/erofs.
   For that mode, `disk_space` is a ceiling (`limits.py:416-441`, `444-460`). The capsules
   now set `read_only_filesystem: true`. A real pack on a node is still required.

2. **Do two capsules with the same interpreter share its block?** — **Yes.**
   Two PDF capsules differing only in `payload.pdf` both reference block
   `bb2331bf…` (the 67.7 MiB `libmupdf.so`), and `__block__` holds one copy.
   The claim the argument for small files rests on is confirmed. It bought 18.6%,
   not 99%: sharing is file-level not layer-level, is gated on a threshold that
   was 10 MB on the node tested (excluding *everything* in the film and game
   images), and saves disk rather than bandwidth. Filed as
   [nodo#370](https://github.com/celaut-project/nodo/issues/370) and
   [nodo#371](https://github.com/celaut-project/nodo/issues/371).

3. **How small is the kernel actually?** — **18.2 MiB**, against an estimate of
   1.5–4 MB. Wrong by 5–12x, in the direction suspected. It is a
   distribution-style 6.12.103 with IPVS, CAN, 9pnet and SCTP compiled in. Shipped
   once per node rather than once per service, which is the mitigation, but it is
   still 19 MB of the first capsule anyone fetches — four times the film
   interpreter.

4. **Whether a decode-only build is as small as claimed.** — **Yes, and smaller.**
   4.44 MiB against a claim of 5–15 MB and a full ffmpeg of 70–90 MB. The one
   estimate that survived, and the one the film case depends on. It was as tedious
   as predicted: `--enable-muxer=f32le` is not the muxer's configure name and fails
   only at runtime.

## Build

One directory per subject, with one pack root per architecture (`amd64/`,
`arm64/`, each with `.service/`: Dockerfile, `pack_config.json`, `service.json`),
`service/entrypoint.sh`, and a
`NODE-REQUIREMENTS.md` saying what it wants from the node and from your host.

- [x] **`film/`** — decode-only h264/aac, no X server, no compositor. Packs,
      serves 48 distinct RGB24 frames and 1.54 MB of PCM over one HTTP stream.
      Interpreter 4.44 MiB. **Caveat the README should carry:** it re-encodes to
      raw RGB, which is 20.7 MB/s at 320×180. That is a preview transport, not a
      player.
- [x] **`game/`** — static CHIP-8 interpreter (584 KiB) plus a 45-byte ROM. Input
      was the open question and it is not a problem here: the key mask goes up in
      the query string and the framebuffer comes down in the response, on the one
      slot the specification already declares. No device, no back-channel. That
      answer does not generalise — it works because a frame is 2 KiB.
- [x] **`pdf/`** — `mutool` render-only. The unfavourable case, and it was more
      unfavourable than written: 68.2 MiB of interpreter for an 889-byte payload.
      Also the case that proved block sharing works.

Each one reports its measured image size against the estimate in
`NODE-REQUIREMENTS.md`. The table was written down in order to be contradicted,
and it was: images are 5–18x the estimate.

## Now the real work

The measurements moved the problem. It is no longer "is the wrapper noise" — it is
that **the interpreter is 0.4–3.2% of the capsule and Debian is the rest**.

- [x] **Declare `read_only_filesystem: true`.** Current nodo supports it. The
      capsules do not write the rootfs. `disk_space` is now 512 MiB and is a
      ceiling. Do not add `shared_filesystems`: a share is not the file-as-service
      model, and a `shared` export is refused with a read-only rootfs
      (`zip_with_dockerfile.py:495-521`).
- [ ] **Build one subject as a static `/init` with no Python and no shell.** This
      is the row the README's component table describes and the one nothing here
      implements. `game/` is the right subject: a 584 KiB emulator that currently
      ships inside 134.5 MiB. Until this exists, every image number in this repo
      measures Debian rather than the design.
- [ ] **Compile MuPDF render-only**, the way `film/` compiles ffmpeg. 67.7 MiB of
      `libmupdf.so` is the single largest object in the repo and the README's
      8–15 MB estimate assumed someone had done this.
- [ ] **Decide what the film case's output actually is.** Raw RGB proves the
      decode happened in the guest and does not scale. Re-encoding on the way out
      is `remote-browser/stream/`'s answer; adopting it means an encoder in the
      image, which would have made the decode-only measurement meaningless. Pick
      one deliberately.
- [ ] **Pack and execute on a real node** with current `dev`. Confirm the
      read-only image, the 512 MiB ceiling, and the pdf `/page` route.

## Not ours to fix

Closed on nodo after the 2026-09-16 run (do not re-file):

- [nodo#368](https://github.com/celaut-project/nodo/issues/368) — arm64 console
  (closed).
- [nodo#369](https://github.com/celaut-project/nodo/issues/369) — read-only rootfs
  (closed). Capsules now declare it.
- [nodo#371](https://github.com/celaut-project/nodo/issues/371) — wire-level skip
  follow-up (closed). This audit did not verify skip on the wire.
- [nodo#372](https://github.com/celaut-project/nodo/issues/372) — local packer
  `unzip` (closed).
- [nodo#373](https://github.com/celaut-project/nodo/issues/373) —
  `MIN_BUFFER_BLOCK_SIZE` key (closed). Current example sets
  `packer.MIN_BUFFER_BLOCK_SIZE: 32768` (`config.example.yaml:322`).

Still open:

- [nodo#370](https://github.com/celaut-project/nodo/issues/370) — layer-level
  blocks. File-level sharing works but only deduplicates byte-identical files.
- [bee-rpc-over-grpc-py#8](https://github.com/bee-rpc-protocol/bee-rpc-over-grpc-py/issues/8) —
  until the block-skip signal reaches the wire, sharing an interpreter saves disk
  on the receiving node and nothing on the network. The film case does not care.
  The PDF case is entirely this.
- Canonical, reproducibly-built interpreter images that packagers reference by
  hash. The measurement above only shared a block because both builds pulled the
  same pinned digest; nothing enforces that. Without such images the hashes
  diverge per packager and nothing is shared, no matter what the transport does.
  This probably belongs somewhere else, and probably needs deciding by more than
  one person.
