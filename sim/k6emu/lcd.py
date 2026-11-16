"""Reconstruct the K6's SC5260 128x64 LCD from simulator SPI traces."""
from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path


class SC5260:
    """Small stateful SC5260 display RAM model shared by batch and live runs."""

    def __init__(self):
        self.ram = [[0 for _ in range(132)] for _ in range(8)]
        self.page = 0
        self.col = 0
        self.reverse = False
        self.lock = threading.Lock()

    def write(self, dc: int, cs: int, byte: int):
        with self.lock:
            if cs:
                return
            if not dc:
                if byte & 0xF8 == 0xB0:
                    self.page = byte & 7
                elif byte & 0xF0 == 0x10:
                    self.col = (self.col & 0x0F) | ((byte & 0x0F) << 4)
                elif byte & 0xF0 == 0:
                    self.col = (self.col & 0xF0) | (byte & 0x0F)
                elif byte in (0xA0, 0xA1):
                    self.reverse = byte == 0xA1
            elif 0 <= self.page < 8:
                self.ram[self.page][self.col % 132] = byte
                self.col = (self.col + 1) % 132

    def snapshot(self):
        with self.lock:
            return [row[:] for row in self.ram], self.reverse

    def ppm(self):
        """Return a P6 image buffer for the controller RAM in physical display order."""
        ram, reverse = self.snapshot()
        width, height = 128, 64
        buf = bytearray(f"P6\n{width} {height}\n255\n".encode("ascii"))
        background, foreground = bytes((231, 230, 214)), bytes((23, 32, 24))
        for y in range(height):
            page, bit = divmod(y, 8)
            for x in range(width):
                controller_x = 4 + (x if reverse else width - 1 - x)
                lit = ram[page][controller_x] & (1 << bit)
                buf.extend(foreground if lit else background)
        return bytes(buf)

    def tk_pixels(self):
        """Return Tk PhotoImage.put data for a coherent physical-order frame."""
        ram, reverse = self.snapshot()
        rows = []
        for y in range(64):
            page, bit = divmod(y, 8)
            colors = []
            for x in range(128):
                controller_x = 4 + (x if reverse else 127 - x)
                lit = ram[page][controller_x] & (1 << bit)
                colors.append("#172018" if lit else "#e7e6d6")
            rows.append("{" + " ".join(colors) + "}")
        return " ".join(rows)


def decode(path: Path):
    """Return (controller RAM, segment direction) from JSONL emitted by sim.k6emu."""
    screen = SC5260()
    for line in path.read_text().splitlines():
        event = json.loads(line)
        screen.write(event["dc"], event["cs"], event["byte"])
    return screen.snapshot()


def write_svg(trace: Path, output: Path, scale: int = 5):
    ram, reverse = decode(trace)
    width, height = 128, 64
    rects = []
    for x in range(width):
        # SC5260's A1 segment-remap command is already accounted for by the
        # panel wiring; the captured image showed that applying a second flip
        # here mirrored the screen. Map the remapped controller columns back
        # to display order once.
        controller_x = 4 + (x if reverse else width - 1 - x)
        for y in range(height):
            if ram[y // 8][controller_x] & (1 << (y & 7)):
                rects.append(f'<rect x="{x}" y="{y}" width="1" height="1"/>')
    body = "\n  ".join(rects)
    output.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width * scale}" '
        f'height="{height * scale}" viewBox="0 0 {width} {height}">\n'
        f'<rect width="{width}" height="{height}" fill="#e7e6d6"/>\n'
        f'<g fill="#172018">{body}</g>\n</svg>\n'
    )
    return len(rects)


def terminal_preview(trace: Path):
    """Return a compact 64x32 Unicode preview of the captured 128x64 display."""
    ram, reverse = decode(trace)
    rows = []
    shades = (" ", "▀", "▄", "█")
    for y in range(0, 64, 2):
        row = []
        for x in range(0, 128, 2):
            top = bottom = False
            for dx in (0, 1):
                controller_x = 4 + (x + dx if reverse else 127 - (x + dx))
                top |= bool(ram[y // 8][controller_x] & (1 << (y & 7)))
                bottom |= bool(ram[(y + 1) // 8][controller_x] & (1 << ((y + 1) & 7)))
            row.append(shades[(2 if bottom else 0) | (1 if top else 0)])
        rows.append("".join(row).rstrip())
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="LCD JSONL from python -m sim.k6emu --lcd-trace")
    parser.add_argument("-o", "--output", type=Path, default=Path("k6-screen.svg"))
    parser.add_argument("--ascii", action="store_true", help="print a compact Unicode terminal preview")
    args = parser.parse_args()
    pixels = write_svg(args.trace, args.output)
    print(f"Rendered {pixels} lit pixels to {args.output}")
    if args.ascii:
        print(terminal_preview(args.trace))


if __name__ == "__main__":
    main()
