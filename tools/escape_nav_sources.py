#!/usr/bin/env python3
"""Make Polestar's raw-zlib Lua strings safe for UTF-8-based packagers.

This operates on a clean checkout or an extracted, known-good addon directory.
It writes a separate overlay, never modifying the input. It cannot recover
bytes already replaced with U+FFFD; obtain the matching clean upstream data.
"""

import argparse
import re
import sys
import zlib
from pathlib import Path


PART_DIRS = ("Polestar_Nav/Nav", "Polestar_Nav_EK", "Polestar_Nav_Kalimdor")
PART_NAME = re.compile(r"Nav\d+_\d+\.lua\Z")
ASSIGNMENT = re.compile(
    rb"^data\.packed\.([A-Za-z]+)\[(\d+)\]\s*=\s*\{([^\r\n]*)\}[ \t]*$",
    re.MULTILINE,
)
ASSIGNMENT_START = re.compile(rb"^data\.packed\.", re.MULTILINE)
LITERAL = re.compile(rb'"([^"\r\n]*)"')
ESCAPE = re.compile(rb"\\([0-9]{3})")
UNKNOWN_ESCAPE = re.compile(rb"\\(?![0-9]{3})")


def parts(root):
    found = []
    for directory in PART_DIRS:
        folder = root / directory
        if folder.is_dir():
            found.extend(p for p in folder.iterdir() if p.is_file() and PART_NAME.fullmatch(p.name))
    if not found:
        raise ValueError("No navigation part files found under the given root")
    return sorted(found)


def lua_bytes(value):
    """Decode the decimal escapes used by the generated map files."""
    if UNKNOWN_ESCAPE.search(value):
        raise ValueError("Unexpected Lua escape in compressed data")

    def decimal(match):
        number = int(match.group(1))
        if number > 255:
            raise ValueError("Lua decimal escape exceeds 255")
        return bytes((number,))

    return ESCAPE.sub(decimal, value)


def transform(data):
    changed_bytes = 0
    block_count = 0
    assignments = 0

    def assignment(match):
        nonlocal changed_bytes, block_count, assignments
        assignments += 1
        body = match.group(3)
        if LITERAL.sub(b"", body).strip(b" ,\t"):
            raise ValueError("Unexpected expression in a packed-data assignment")

        def literal(item):
            nonlocal changed_bytes, block_count
            original = item.group(1)
            compressed = lua_bytes(original)
            # Refuse corrupt inputs rather than publishing an apparently fixed file.
            zlib.decompress(compressed)
            safe = bytearray()
            for byte in original:
                if byte >= 128:
                    safe.extend(f"\\{byte:03d}".encode("ascii"))
                    changed_bytes += 1
                else:
                    safe.append(byte)
            encoded = bytes(safe)
            if lua_bytes(encoded) != compressed:
                raise ValueError("Lua string changed after escaping")
            block_count += 1
            return b'"' + encoded + b'"'

        converted = LITERAL.sub(literal, body)
        return match.group(0)[: match.start(3) - match.start()] + converted + match.group(0)[match.end(3) - match.start() :]

    result = ASSIGNMENT.sub(assignment, data)
    if assignments != len(ASSIGNMENT_START.findall(data)) or not block_count:
        raise ValueError("Unrecognized packed-data assignment")
    result.decode("utf-8")
    if result.decode("utf-8", "replace").encode("utf-8") != result:
        raise ValueError("Output is not stable under UTF-8 processing")
    return result, block_count, changed_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="clean repository or extracted addon root")
    parser.add_argument("output", type=Path, nargs="?", help="separate output root for the converted overlay")
    parser.add_argument("--check", action="store_true", help="verify an already-converted overlay, without writing")
    args = parser.parse_args()
    if args.check == bool(args.output):
        parser.error("specify an output root, or --check, but not both")

    source = args.source.resolve()
    output = args.output.resolve() if args.output else None
    if output and (output == source or source in output.parents or output in source.parents):
        parser.error("source and output must be separate directories")
    if output and output.exists() and any(output.iterdir()):
        parser.error("output must be an empty directory")
    files = parts(source)
    blocks = escaped = 0
    # Process each file independently and write only to the separate output tree.
    for file in files:
        try:
            result, count, changes = transform(file.read_bytes())
        except (ValueError, zlib.error) as exc:
            raise ValueError(f"{file}: {exc}") from exc
        if args.check and changes:
            raise ValueError(f"File still has raw non-ASCII data bytes: {file}")
        if output:
            dest = output / file.relative_to(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(result)
        blocks += count
        escaped += changes
    print(f"files={len(files)} zlib_blocks_verified={blocks} escaped_bytes={escaped}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, zlib.error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
