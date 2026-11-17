# Hello Flux

A minimal native K6 module that writes a greeting to the serial diagnostic output and returns immediately. It does not transmit or change radio settings.

## Build and test

You need a Flux source checkout, Python 3 with its installer dependencies (numpy and pyserial), clang, ld.lld, llvm-nm and llvm-objcopy. Use the Flux revision matching your firmware; record that revision when releasing a module.

```sh
python3 build.py --flux /path/to/flux
cc -I/path/to/flux/c/k6 src/hello.c tests/test_hello.c -o /tmp/flux-hello-test
/tmp/flux-hello-test
python3 /path/to/flux/tools/k6_store.py add "$(pwd)"
```

The final command registers the local checkout in the catalog. Open the project page to install explicitly; a matching module-enabled radio and local signing key are required. No key belongs in this repository. Expect `K6 MOD say Hello from Flux!` when the module runs. Hardware behavior has not been verified by the host test.

## Make your own

Copy this directory into a new Git repository. Change the module ID in build.py to a stable globally unique reverse-domain ID you control, change K6_MODULE_NAME (maximum 12 characters), and update the README. Declare the minimum API level needed in the C source. The authoritative API is Flux's `c/k6/k6_mod.h`; read `docs/k6-modules.md` and `docs/k6-ui-conventions.md` for the ABI and interaction rules.

The toolchain builds position-independent Cortex-M0 code; no writable globals/statics in module code, libc, heap or unresolved runtime helpers. Use stack/scratch and the host API. Keep bounded execution, restore hardware state and respect EXIT for interactive modules. Check the arena and API level of target firmware; a 16 KiB library slot does not guarantee enough execution RAM.

## Publish

Commit your source, README, tests, and generated `dist/manifest.json` and `dist/module.bin` together into a release commit or tag. The catalog reads the committed bundle, not GitHub release assets. Put screenshots in the README with relative Markdown image links. Add the GitHub HTTPS URL and optional tag to the catalog. Never publish signing keys, radio backups or signed device-specific images.

The catalog verifies bundle hashes and signs locally at installation; native modules are not sandboxed. Only install trusted code.
