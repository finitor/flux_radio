"""Tk live view and input controls for the virtual K6."""
from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import ttk


KEYMAP = {
    **{str(n): str(n) for n in range(10)},
    "asterisk": "*", "numbersign": "#",
    "m": "MENU", "Return": "MENU", "Escape": "EXIT",
    "Up": "UP", "Down": "DOWN", "v": "VM", "a": "AB", "b": "BAND",
    "F1": "SIDE1", "F2": "SIDE2",
}


def run_live(board, *, quantum: int, slice_instructions: int):
    """Run the firmware continuously while Tk displays the LCD and sends key events."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise SystemExit(f"Could not open the live K6 window: {exc}") from exc

    root.title("K6 firmware simulator")
    root.resizable(False, False)
    shell = ttk.Frame(root, padding=12)
    shell.grid()
    canvas = tk.Canvas(shell, width=512, height=256, bg="#e7e6d6",
                       highlightthickness=1, highlightbackground="#4b5145")
    canvas.grid(row=0, column=0, columnspan=2)
    screen_item = canvas.create_image(0, 0, anchor="nw")
    status = tk.StringVar(value="Starting firmware…")
    ttk.Label(shell, textvariable=status).grid(row=1, column=0, sticky="w", pady=(8, 0))
    ttk.Label(shell, text=("Digits: keypad · M/Enter: Menu · Esc: Exit · ↑/↓ · "
                           "V: V/M · A: A/B · B: Band · F1/F2: side keys · Space: PTT")).grid(
        row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

    stop = threading.Event()
    worker_error = []

    def execute():
        try:
            while not stop.is_set():
                board.run(slice_instructions, quantum)
                # Let the UI thread run frequently; CPU slices remain independent of wall time.
                time.sleep(0.001)
        except BaseException as exc:  # report worker failure in the UI thread
            worker_error.append(exc)
            stop.set()

    worker = threading.Thread(target=execute, name="k6-firmware", daemon=True)
    worker.start()
    photo_ref = {"image": None}

    def refresh():
        if stop.is_set():
            status.set(f"Firmware stopped: {worker_error[0]}" if worker_error else "Stopped")
            return
        try:
            image = tk.PhotoImage(width=128, height=64)
            image.put(board.screen.tk_pixels())
            image = image.zoom(4, 4)
            canvas.itemconfigure(screen_item, image=image)
            photo_ref["image"] = image
            status.set(f"~{board.cycles / 96_000:.0f} ms virtual  ·  "
                       f"{board.instructions:,} instructions  ·  "
                       f"UART {len(board.uart_tx)} B  ·  SPI {len(board.spi_tx[0x40003800])} B")
        except tk.TclError as exc:
            worker_error.append(exc)
            stop.set()
            return
        root.after(80, refresh)

    def key_down(event):
        key = KEYMAP.get(event.keysym)
        if key:
            try:
                board.press_key(key, True)
            except ValueError:
                pass
            return "break"
        if event.keysym == "space":
            board.set_gpio("A", 10, 0)
            return "break"
        return None

    def key_up(event):
        key = KEYMAP.get(event.keysym)
        if key:
            try:
                board.press_key(key, False)
            except ValueError:
                pass
            return "break"
        if event.keysym == "space":
            board.set_gpio("A", 10, 1)
            return "break"
        return None

    def close():
        stop.set()
        worker.join(timeout=1.0)
        root.destroy()

    root.bind_all("<KeyPress>", key_down)
    root.bind_all("<KeyRelease>", key_up)
    root.protocol("WM_DELETE_WINDOW", close)
    root.after(80, refresh)
    root.mainloop()
