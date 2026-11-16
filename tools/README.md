# Navigation data maintenance

The generated `Nav*_*.lua` files contain zlib-compressed strings. The
original generator writes non-UTF-8 bytes directly into those strings. The
`v0.3.7.2-zh.1` CurseForge package changed those bytes into UTF-8 replacement
characters, so the game could not decompress the navigation data. The exact
packaging step responsible has not been identified.

The checked-in files instead use Lua's three-digit decimal escapes for bytes
at or above 128. Lua 5.1 evaluates those escapes to the same compressed bytes;
the source files also survive UTF-8 replacement processing. This increases
the size of the uncompressed navigation sources (about 39 MB to 93 MB).

Run the checks before releasing or after updating the generated data:

```sh
python -m unittest discover -s tests -v
```

When importing new, undamaged navigation sources, prepare an overlay in a
separate directory, copy it over the corresponding paths in the checkout,
and rerun the checks:

```sh
python tools/escape_nav_sources.py /path/to/clean/source /path/to/new/overlay
python tools/escape_nav_sources.py /path/to/new/overlay --check
```

Use the overlay only if the command succeeds. The converter checks that every
compressed block it processes can be decompressed. It cannot recover bytes
that were already replaced: obtain clean data from the matching source version.
The generated Lua files should be converted again after each upstream rebuild.
