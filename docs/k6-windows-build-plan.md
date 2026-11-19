# Native Windows firmware builder

Goal: the same Flux Catalog and CLI can customize, compile and install firmware
on native Windows without WSL. Develop on the windows branch; do not merge until
Linux regression and Windows CI builds pass.

## Milestones

1. Preserve existing Linux build behavior and add a portable orchestration
   backend. Keep pinned Aura revision, patch order, service gates, flash limit,
   About metadata relinks, build identity and artifact receipts unchanged.
2. Port the C library build: use argument arrays, explicit tool paths, native
   host codebook generator (Clang with a Windows SDK/MSVC environment, or an
   equivalent validated host compiler), LLVM ARM cross compiler and archiver.
   Keep legacy codec/benchmark shell entry points until their parity is tested.
3. Port Aura orchestration: Git checkout/patch operations, Python patch scripts,
   Cargo target and encoded Rust flags, llvm-size and objcopy. Handle Windows
   path separators, spaces, executable suffixes and line endings. Preserve
   POSIX-compatible manifest paths.
4. Add a toolchain doctor and guided setup for Git, Python, Rust
   thumbv6m-none-eabi, Clang/LLD/LLVM and the native host C compiler.
   Expose actionable errors in the Catalog; enable Build only when supported.
5. CI: Linux and Windows build Base, Scan and Designer+Scan in both TX profiles.
   Check image bounds, capability receipts, module ABI/size and extracted pack
   verification; compare equivalent builds with pinned compiler versions.
   Bit-for-bit identity is a goal, not a substitute for compatibility tests.
6. Validate on a Windows PC and compatible radio before removing experimental
   status. No live radio writes in CI.

## First slice

Portable build lock and platform-neutral staged pack paths. These are shared
infrastructure independent of the actual compilation backend. Native Windows
build remains gated until the backend and tools are verified.
