# Local module store prototype

The store is a small local catalog, not a service running on the radio. It reads Git repositories,
shows the project README and its screenshots, and can send a compatible module bundle to the K6
through the existing serial cable loader.

## Start it

```sh
python3 -m pip install -r tools/k6_store_requirements.txt
python3 tools/k6_store.py add https://github.com/OWNER/K6-MODULE --ref main
python3 tools/k6_store.py serve
```

Open <http://127.0.0.1:5055>. The web server binds to localhost by default. The add form also accepts
an existing local Git checkout. A ref can be a branch or tag; refresh checks out its latest commit.
Each source is cached below `~/.cache/blowfang/module-store/repos/`. The catalog list is stored in
`~/.config/blowfang/module-store.json`.

Select **My radio** in the top navigation to inspect library slots over the programming cable.
Enter the serial port and choose **Read radio library**. This runs the existing `k6_install.py
status` command; that command ends the cable session by restarting the radio. Occupied module
slots can link to a matching project in the catalog by module name. Install or update a module from
that project's page. Remove a module by typing `ERASE <slot>` in its confirmation field. The
firmware validates the slot type, erases and verifies the full 16 KB slot, and rejects firmware
pages and help decks. Removal is permanent, and the cable session restarts the radio when it ends.

## Local starter module repositories

Build local Git repositories for the current host's SURF, VFO, and CARD LINK starter modules:

```sh
python3 tools/k6_make_local_catalog.py
```

The generated Git working directories live under `local-modules/` and are discovered by the
catalog by default. They are local build artifacts, not committed releases. The generator refuses
to overwrite an existing directory; move it aside before rebuilding. These are starter packages
for this host, not a certification that every module has been hardware-tested.

Other module repositories can be added as they are developed for the host. The host verifies
module format and signatures, but it does not sandbox native code. A successful build does not
mean a module will fit or run correctly on hardware.

## Slot-independent bundles

Package one source (or a prebuilt binary with an explicit `--level`) with a stable, globally unique
ID. Keep the same ID across versions:

```sh
python3 tools/k6_install.py module-bundle c/k6/mod/morse.c --id org.blowfang.k6.morse -o /path/to/bundle
python3 tools/k6_install.py --port /dev/ttyUSB0 load /path/to/bundle
```

The manifest omits `slot` for automatic placement and supplies `id`. The installer searches slots
0–8 and 16–31, preserving 9–15 for firmware pages and help decks. It checks the flash before
choosing an empty location, signs for that location and verifies the write. A 24-byte identity
marker inside the signed image identifies subsequent versions, so a reinstall updates that slot;
legacy installations without a marker are not automatically adopted or removed. Duplicate IDs,
insufficient space and a full library are refused before library writes. `load --only` filters
by fixed manifest slots and therefore does not select automatic entries; omit it for these bundles.
Fixed-slot format-1 entries continue to work as before and can overwrite their specified slots.

An automatic update is in-place and can be interrupted by power loss. The signature authorizes
native code; it does not sandbox it. Keep a backup and install only trusted modules.

## CLI

```sh
python3 tools/k6_store.py add https://github.com/OWNER/K6-MODULE --ref v1.0
python3 tools/k6_store.py list
python3 tools/k6_store.py show module-id
python3 tools/k6_store.py refresh [module-id]
python3 tools/k6_store.py remove module-id
python3 tools/k6_store.py install module-id --port /dev/ttyUSB0 \
  --key-file ~/.config/blowfang/k6-mod.key --verify
python3 tools/k6_install.py --port /dev/ttyUSB0 remove-slot 30
```

Add prints the catalog ID used by the other commands. `install` calls `tools/k6_install.py load`
with the selected repository's bundle. The browser offers the same explicit action and shows the
installer's output. It never flashes the firmware image; it only loads library entries in the
bundle manifest.

## README content

The title is the first Markdown H1. The short card description is the first ordinary paragraph
after it. Add screenshots with normal Markdown image syntax; relative paths are served from the
cached checkout, and HTTPS image URLs are displayed as-is:

```markdown
# Weather Beacon

Receive and display local APRS weather telemetry.

![Radio screen](docs/radio-screen.png)
```

An installable repository contains a format-1 `manifest.json` at the repository root, in `dist/`,
or one directory below the root, plus every file named in its `sha256` map. It uses the existing
bundle fields: `build_id`, `library` entries (`slot`, `kind`, `file`, `name`, `level`), and `sha256`.
The installer verifies the listed hashes and signs each image locally with the user's configured
module key before sending it. Existing bundles such as the VFO/SURF output can be used directly.

## Current scope

- Catalog sources are manually added Git URLs or local directories; no central server or account is
  needed.
- Catalog display metadata comes from README text and images. Module slot/API details come from the
  bundle manifest.
- GitHub releases are not queried yet. This prototype clones the repo's selected branch or tag and
  installs a checked-in or committed bundle.
- There is no sandbox for native modules. Only add sources you trust; the radio's module signature
  check authorizes images for the local key but does not constrain what module code can do.
