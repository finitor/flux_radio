"""Transaction-level model for Aura's experimental FD6818B raw-FSK API.

This is deliberately not an RF or demodulator model. It mirrors the current
Aura fd6818b.rs driver contract (8 x 16-bit FIFO words per frame) so the
Blowfang port can test register ordering, FIFO framing, and byte-order choices
without pretending those checks prove reception on a physical radio.
"""
from collections import deque


CHIP_ID = 0x4829

REG_IRQ_CLEAR = 0x02
REG_STATUS = 0x0C
REG_FSK_PREAMBLE = 0x58
REG_FSK_CONTROL = 0x59
REG_FSK_TONE_GAIN = 0x70
REG_FSK_WORDS = 0x5C
REG_FSK_LEN = 0x5D
REG_FSK_FIFO = 0x5F
REG_FSK_BAUD = 0x72
REG_WORK_MODE = 0x3F

FSK_BAUD_1200 = 0x3065
FSK_WORDS_VALUE = 0x5665
FSK_LEN_VALUE = 0x0F00
FSK_CONTROL_BASE = 0x0028
FSK_RX_FIFO_CLEAR = 0x4000
FSK_TX_FIFO_CLEAR = 0x8000
FSK_RX_ENABLE = 0x1000
FSK_TX_ENABLE = 0x0800
FSK_RX_MODE = 0x2000
FSK_TX_MODE = 0x8000
FRAME_WORDS = 8


class FD6818BFSKModel:
    """Small register/FIFO model for the API operations used by Aura's B driver."""

    def __init__(self):
        self.regs = {REG_STATUS: 0}
        self.writes = []
        self.rx_frames = deque()
        self.rx_words = deque()
        self.tx_words = []
        self.tx_frames = []
        self.irq_pending = False

    def write(self, reg, value):
        reg, value = int(reg) & 0xFF, int(value) & 0xFFFF
        self.writes.append((reg, value))
        if reg == REG_FSK_CONTROL:
            if value & FSK_RX_FIFO_CLEAR:
                self.rx_frames.clear()
                self.rx_words.clear()
                self.irq_pending = False
            if value & FSK_TX_FIFO_CLEAR:
                self.tx_words.clear()
            self.regs[reg] = value
            if value & FSK_TX_ENABLE:
                if len(self.tx_words) != FRAME_WORDS:
                    raise AssertionError(f"TX started with {len(self.tx_words)} words")
                self.tx_frames.append(tuple(self.tx_words))
                self.tx_words.clear()
                self.irq_pending = True
            return
        if reg == REG_FSK_FIFO and self.regs.get(REG_FSK_CONTROL, 0) & FSK_TX_ENABLE == 0:
            self.tx_words.append(value)
            return
        if reg == REG_IRQ_CLEAR:
            self.irq_pending = False
        self.regs[reg] = value

    def read(self, reg):
        reg = int(reg) & 0xFF
        if reg == REG_STATUS:
            return (self.regs.get(reg, 0) & ~1) | int(self.irq_pending)
        if reg == REG_WORK_MODE:
            return self.regs.get(reg, 0)
        if reg == REG_FSK_FIFO:
            if not self.rx_words:
                return 0
            value = self.rx_words.popleft()
            if not self.rx_words:
                self.irq_pending = False
            return value
        return self.regs.get(reg, 0)

    @property
    def rx_armed(self):
        return (self.regs.get(REG_WORK_MODE, 0) & FSK_RX_MODE) != 0 and \
            (self.regs.get(REG_FSK_CONTROL, 0) & FSK_RX_ENABLE) != 0

    def inject_rx_frame(self, words):
        words = tuple(int(word) & 0xFFFF for word in words)
        if not self.rx_armed:
            raise RuntimeError("FD6818B FSK receiver is not armed")
        if len(words) != FRAME_WORDS:
            raise ValueError(f"frame must contain exactly {FRAME_WORDS} words")
        self.rx_frames.append(words)
        self.rx_words.extend(words)
        self.irq_pending = True

    def arm_1200_rx(self):
        """Mirror Aura fd6818b.rs::enter_fsk_mode's 1200-baud RX writes."""
        self.write(REG_FSK_PREAMBLE, 0x00C1)
        self.write(REG_FSK_TONE_GAIN, 0x00E0)
        self.write(REG_FSK_BAUD, FSK_BAUD_1200)
        self.write(REG_FSK_WORDS, FSK_WORDS_VALUE)
        self.write(REG_FSK_LEN, FSK_LEN_VALUE)
        self.write(REG_FSK_CONTROL, FSK_CONTROL_BASE | FSK_RX_FIFO_CLEAR)
        self.write(REG_FSK_CONTROL, FSK_CONTROL_BASE | FSK_RX_ENABLE)
        self.write(REG_WORK_MODE, FSK_RX_MODE)

    def read_frame(self):
        """Mirror Aura's fixed-length receive helper and its IRQ acknowledgement."""
        if not self.irq_pending:
            return None
        words = tuple(self.read(REG_FSK_FIFO) for _ in range(FRAME_WORDS))
        self.write(REG_IRQ_CLEAR, 0)
        if self.rx_frames:
            self.rx_frames.popleft()
        return words

    def stop_rx(self):
        """Mirror Aura's FSK shutdown, disabling the receiver before clearing settings."""
        self.write(REG_FSK_CONTROL, FSK_CONTROL_BASE)
        self.write(REG_WORK_MODE, 0)
        self.write(REG_IRQ_CLEAR, 0)
        self.write(REG_FSK_TONE_GAIN, 0)
        self.write(REG_FSK_PREAMBLE, 0)

    def send_frame(self, words):
        """Mirror Aura's fixed-length TX transaction; no modulation is simulated."""
        words = tuple(int(word) & 0xFFFF for word in words)
        if len(words) != FRAME_WORDS:
            raise ValueError(f"frame must contain exactly {FRAME_WORDS} words")
        self.write(REG_WORK_MODE, FSK_TX_MODE)
        self.write(REG_FSK_PREAMBLE, 0x00C1)
        self.write(REG_FSK_TONE_GAIN, 0x00E0)
        self.write(REG_FSK_BAUD, FSK_BAUD_1200)
        self.write(REG_FSK_WORDS, FSK_WORDS_VALUE)
        self.write(REG_FSK_LEN, FSK_LEN_VALUE)
        self.write(REG_FSK_CONTROL, FSK_CONTROL_BASE | FSK_TX_FIFO_CLEAR)
        self.write(REG_FSK_CONTROL, FSK_CONTROL_BASE)
        for word in words:
            self.write(REG_FSK_FIFO, word)
        self.write(REG_FSK_CONTROL, FSK_CONTROL_BASE | FSK_TX_ENABLE)
        complete = bool(self.read(REG_STATUS) & 1)
        self.write(REG_IRQ_CLEAR, 0)
        self.write(REG_WORK_MODE, 0)
        self.write(REG_FSK_CONTROL, FSK_CONTROL_BASE)
        return complete


def words_from_bytes(data, byteorder):
    """Pack bytes into 16-bit test words without choosing an unmeasured wire order."""
    data = bytes(data)
    if len(data) % 2:
        raise ValueError("16-bit FIFO fixtures require an even byte count")
    if byteorder not in ("big", "little"):
        raise ValueError("byteorder must be 'big' or 'little'")
    return tuple(int.from_bytes(data[i:i + 2], byteorder)
                 for i in range(0, len(data), 2))


def bytes_from_words(words, byteorder):
    if byteorder not in ("big", "little"):
        raise ValueError("byteorder must be 'big' or 'little'")
    return b"".join(int(word).to_bytes(2, byteorder) for word in words)
