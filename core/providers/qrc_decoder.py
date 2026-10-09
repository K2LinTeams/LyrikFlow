"""
core/providers/qrc_decoder.py — QRC 解密引擎
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
import zlib
from typing import Optional

QQ_KEY = b"!@#)(*$%123ZXC!@!@#)(NHL"


class _QrcDES:

    _SBOX1 = (
        14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7,
        0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8,
        4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0,
        15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13,
    )
    _SBOX2 = (
        15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10,
        3, 13, 4, 7, 15, 2, 8, 15, 12, 0, 1, 10, 6, 9, 11, 5,
        0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15,
        13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9,
    )
    _SBOX3 = (
        10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8,
        13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1,
        13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7,
        1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12,
    )
    _SBOX4 = (
        7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15,
        13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9,
        10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4,
        3, 15, 0, 6, 10, 10, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14,
    )
    _SBOX5 = (
        2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9,
        14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6,
        4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14,
        11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3,
    )
    _SBOX6 = (
        12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11,
        10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8,
        9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6,
        4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13,
    )
    _SBOX7 = (
        4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1,
        13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6,
        1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2,
        6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12,
    )
    _SBOX8 = (
        13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7,
        1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2,
        7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8,
        2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11,
    )

    _KEY_RND_SHIFT = (1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1)
    _KEY_PERM_C = (
        56, 48, 40, 32, 24, 16, 8, 0, 57, 49, 41, 33, 25, 17,
        9, 1, 58, 50, 42, 34, 26, 18, 10, 2, 59, 51, 43, 35,
    )
    _KEY_PERM_D = (
        62, 54, 46, 38, 30, 22, 14, 6, 61, 53, 45, 37, 29, 21,
        13, 5, 60, 52, 44, 36, 28, 20, 12, 4, 27, 19, 11, 3,
    )
    _KEY_COMPRESSION = (
        13, 16, 10, 23, 0, 4, 2, 27, 14, 5, 20, 9,
        22, 18, 11, 3, 25, 7, 15, 6, 26, 19, 12, 1,
        40, 51, 30, 36, 46, 54, 29, 39, 50, 44, 32, 47,
        43, 48, 38, 55, 33, 52, 45, 41, 49, 35, 28, 31,
    )

    def __init__(self, key: bytes = QQ_KEY) -> None:
        self.sched = [[bytearray(6) for _ in range(16)] for _ in range(3)]
        self._key_schedule(key[0:8], self.sched[2], 0)
        self._key_schedule(key[8:16], self.sched[1], 1)
        self._key_schedule(key[16:24], self.sched[0], 0)

    @staticmethod
    def _bitnum(a: bytes, b: int, c: int) -> int:
        idx = (b // 32) * 4 + 3 - (b % 32) // 8
        bit = (a[idx] >> (7 - (b % 8))) & 1
        return bit << c

    @staticmethod
    def _bitnum_intr(a: int, b: int, c: int) -> int:
        return (((a >> (31 - b)) & 1) << c) & 0xFF

    @staticmethod
    def _bitnum_intl(a: int, b: int, c: int) -> int:
        return (((a << b) & 0x80000000) >> c) & 0xFFFFFFFF

    @staticmethod
    def _sboxbit(a: int) -> int:
        return (a & 0x20) | ((a & 0x1F) >> 1) | ((a & 1) << 4)

    def _key_schedule(self, key: bytes, sched: list[bytearray], mode: int) -> None:
        c, d = 0, 0
        for i in range(28):
            c |= self._bitnum(key, self._KEY_PERM_C[i], 31 - i)
            d |= self._bitnum(key, self._KEY_PERM_D[i], 31 - i)

        for i in range(16):
            c = (((c << self._KEY_RND_SHIFT[i]) | (c >> (28 - self._KEY_RND_SHIFT[i])))) & 0xFFFFFFF0
            d = (((d << self._KEY_RND_SHIFT[i]) | (d >> (28 - self._KEY_RND_SHIFT[i])))) & 0xFFFFFFF0

            to_gen = (15 - i) if mode == 0 else i
            for j in range(6):
                sched[to_gen][j] = 0

            for j in range(24):
                sched[to_gen][j // 8] |= self._bitnum_intr(c, self._KEY_COMPRESSION[j], 7 - (j % 8))
            for j in range(24, 48):
                sched[to_gen][j // 8] |= self._bitnum_intr(d, self._KEY_COMPRESSION[j] - 27, 7 - (j % 8))

    def _ip(self, state: list[int], inp: bytes) -> None:
        state[0] = (
            self._bitnum(inp, 57, 31) | self._bitnum(inp, 49, 30) | self._bitnum(inp, 41, 29) | self._bitnum(inp, 33, 28) |
            self._bitnum(inp, 25, 27) | self._bitnum(inp, 17, 26) | self._bitnum(inp, 9, 25) | self._bitnum(inp, 1, 24) |
            self._bitnum(inp, 59, 23) | self._bitnum(inp, 51, 22) | self._bitnum(inp, 43, 21) | self._bitnum(inp, 35, 20) |
            self._bitnum(inp, 27, 19) | self._bitnum(inp, 19, 18) | self._bitnum(inp, 11, 17) | self._bitnum(inp, 3, 16) |
            self._bitnum(inp, 61, 15) | self._bitnum(inp, 53, 14) | self._bitnum(inp, 45, 13) | self._bitnum(inp, 37, 12) |
            self._bitnum(inp, 29, 11) | self._bitnum(inp, 21, 10) | self._bitnum(inp, 13, 9) | self._bitnum(inp, 5, 8) |
            self._bitnum(inp, 63, 7) | self._bitnum(inp, 55, 6) | self._bitnum(inp, 47, 5) | self._bitnum(inp, 39, 4) |
            self._bitnum(inp, 31, 3) | self._bitnum(inp, 23, 2) | self._bitnum(inp, 15, 1) | self._bitnum(inp, 7, 0)
        ) & 0xFFFFFFFF
        state[1] = (
            self._bitnum(inp, 56, 31) | self._bitnum(inp, 48, 30) | self._bitnum(inp, 40, 29) | self._bitnum(inp, 32, 28) |
            self._bitnum(inp, 24, 27) | self._bitnum(inp, 16, 26) | self._bitnum(inp, 8, 25) | self._bitnum(inp, 0, 24) |
            self._bitnum(inp, 58, 23) | self._bitnum(inp, 50, 22) | self._bitnum(inp, 42, 21) | self._bitnum(inp, 34, 20) |
            self._bitnum(inp, 26, 19) | self._bitnum(inp, 18, 18) | self._bitnum(inp, 10, 17) | self._bitnum(inp, 2, 16) |
            self._bitnum(inp, 60, 15) | self._bitnum(inp, 52, 14) | self._bitnum(inp, 44, 13) | self._bitnum(inp, 36, 12) |
            self._bitnum(inp, 28, 11) | self._bitnum(inp, 20, 10) | self._bitnum(inp, 12, 9) | self._bitnum(inp, 4, 8) |
            self._bitnum(inp, 62, 7) | self._bitnum(inp, 54, 6) | self._bitnum(inp, 46, 5) | self._bitnum(inp, 38, 4) |
            self._bitnum(inp, 30, 3) | self._bitnum(inp, 22, 2) | self._bitnum(inp, 14, 1) | self._bitnum(inp, 6, 0)
        ) & 0xFFFFFFFF

    def _inv_ip(self, state: list[int], out: bytearray) -> None:
        out[3] = self._bitnum_intr(state[1], 7, 7) | self._bitnum_intr(state[0], 7, 6) | self._bitnum_intr(state[1], 15, 5) | self._bitnum_intr(state[0], 15, 4) | self._bitnum_intr(state[1], 23, 3) | self._bitnum_intr(state[0], 23, 2) | self._bitnum_intr(state[1], 31, 1) | self._bitnum_intr(state[0], 31, 0)
        out[2] = self._bitnum_intr(state[1], 6, 7) | self._bitnum_intr(state[0], 6, 6) | self._bitnum_intr(state[1], 14, 5) | self._bitnum_intr(state[0], 14, 4) | self._bitnum_intr(state[1], 22, 3) | self._bitnum_intr(state[0], 22, 2) | self._bitnum_intr(state[1], 30, 1) | self._bitnum_intr(state[0], 30, 0)
        out[1] = self._bitnum_intr(state[1], 5, 7) | self._bitnum_intr(state[0], 5, 6) | self._bitnum_intr(state[1], 13, 5) | self._bitnum_intr(state[0], 13, 4) | self._bitnum_intr(state[1], 21, 3) | self._bitnum_intr(state[0], 21, 2) | self._bitnum_intr(state[1], 29, 1) | self._bitnum_intr(state[0], 29, 0)
        out[0] = self._bitnum_intr(state[1], 4, 7) | self._bitnum_intr(state[0], 4, 6) | self._bitnum_intr(state[1], 12, 5) | self._bitnum_intr(state[0], 12, 4) | self._bitnum_intr(state[1], 20, 3) | self._bitnum_intr(state[0], 20, 2) | self._bitnum_intr(state[1], 28, 1) | self._bitnum_intr(state[0], 28, 0)
        out[7] = self._bitnum_intr(state[1], 3, 7) | self._bitnum_intr(state[0], 3, 6) | self._bitnum_intr(state[1], 11, 5) | self._bitnum_intr(state[0], 11, 4) | self._bitnum_intr(state[1], 19, 3) | self._bitnum_intr(state[0], 19, 2) | self._bitnum_intr(state[1], 27, 1) | self._bitnum_intr(state[0], 27, 0)
        out[6] = self._bitnum_intr(state[1], 2, 7) | self._bitnum_intr(state[0], 2, 6) | self._bitnum_intr(state[1], 10, 5) | self._bitnum_intr(state[0], 10, 4) | self._bitnum_intr(state[1], 18, 3) | self._bitnum_intr(state[0], 18, 2) | self._bitnum_intr(state[1], 26, 1) | self._bitnum_intr(state[0], 26, 0)
        out[5] = self._bitnum_intr(state[1], 1, 7) | self._bitnum_intr(state[0], 1, 6) | self._bitnum_intr(state[1], 9, 5) | self._bitnum_intr(state[0], 9, 4) | self._bitnum_intr(state[1], 17, 3) | self._bitnum_intr(state[0], 17, 2) | self._bitnum_intr(state[1], 25, 1) | self._bitnum_intr(state[0], 25, 0)
        out[4] = self._bitnum_intr(state[1], 0, 7) | self._bitnum_intr(state[0], 0, 6) | self._bitnum_intr(state[1], 8, 5) | self._bitnum_intr(state[0], 8, 4) | self._bitnum_intr(state[1], 16, 3) | self._bitnum_intr(state[0], 16, 2) | self._bitnum_intr(state[1], 24, 1) | self._bitnum_intr(state[0], 24, 0)

    def _f(self, state: int, key: bytearray) -> int:
        t1 = (
            self._bitnum_intl(state, 31, 0) | ((state & 0xF0000000) >> 1) | self._bitnum_intl(state, 4, 5) |
            self._bitnum_intl(state, 3, 6) | ((state & 0x0F000000) >> 3) | self._bitnum_intl(state, 8, 11) |
            self._bitnum_intl(state, 7, 12) | ((state & 0x00F00000) >> 5) | self._bitnum_intl(state, 12, 17) |
            self._bitnum_intl(state, 11, 18) | ((state & 0x000F0000) >> 7) | self._bitnum_intl(state, 16, 23)
        ) & 0xFFFFFFFF
        t2 = (
            self._bitnum_intl(state, 15, 0) | ((state & 0x0000F000) << 15) | self._bitnum_intl(state, 20, 5) |
            self._bitnum_intl(state, 19, 6) | ((state & 0x00000F00) << 13) | self._bitnum_intl(state, 24, 11) |
            self._bitnum_intl(state, 23, 12) | ((state & 0x000000F0) << 11) | self._bitnum_intl(state, 28, 17) |
            self._bitnum_intl(state, 27, 18) | ((state & 0x0000000F) << 9) | self._bitnum_intl(state, 0, 23)
        ) & 0xFFFFFFFF
        s0 = ((t1 >> 24) & 0xFF) ^ key[0]
        s1 = ((t1 >> 16) & 0xFF) ^ key[1]
        s2 = ((t1 >> 8) & 0xFF) ^ key[2]
        s3 = ((t2 >> 24) & 0xFF) ^ key[3]
        s4 = ((t2 >> 16) & 0xFF) ^ key[4]
        s5 = ((t2 >> 8) & 0xFF) ^ key[5]

        st = (
            (self._SBOX1[self._sboxbit(s0 >> 2)] << 28) |
            (self._SBOX2[self._sboxbit(((s0 & 3) << 4) | (s1 >> 4))] << 24) |
            (self._SBOX3[self._sboxbit(((s1 & 0xF) << 2) | (s2 >> 6))] << 20) |
            (self._SBOX4[self._sboxbit(s2 & 0x3F)] << 16) |
            (self._SBOX5[self._sboxbit(s3 >> 2)] << 12) |
            (self._SBOX6[self._sboxbit(((s3 & 3) << 4) | (s4 >> 4))] << 8) |
            (self._SBOX7[self._sboxbit(((s4 & 0xF) << 2) | (s5 >> 6))] << 4) |
            self._SBOX8[self._sboxbit(s5 & 0x3F)]
        ) & 0xFFFFFFFF
        return (
            self._bitnum_intl(st, 15, 0) | self._bitnum_intl(st, 6, 1) | self._bitnum_intl(st, 19, 2) |
            self._bitnum_intl(st, 20, 3) | self._bitnum_intl(st, 28, 4) | self._bitnum_intl(st, 11, 5) |
            self._bitnum_intl(st, 27, 6) | self._bitnum_intl(st, 16, 7) | self._bitnum_intl(st, 0, 8) |
            self._bitnum_intl(st, 14, 9) | self._bitnum_intl(st, 22, 10) | self._bitnum_intl(st, 25, 11) |
            self._bitnum_intl(st, 4, 12) | self._bitnum_intl(st, 17, 13) | self._bitnum_intl(st, 30, 14) |
            self._bitnum_intl(st, 9, 15) | self._bitnum_intl(st, 1, 16) | self._bitnum_intl(st, 7, 17) |
            self._bitnum_intl(st, 23, 18) | self._bitnum_intl(st, 13, 19) | self._bitnum_intl(st, 31, 20) |
            self._bitnum_intl(st, 26, 21) | self._bitnum_intl(st, 2, 22) | self._bitnum_intl(st, 8, 23) |
            self._bitnum_intl(st, 18, 24) | self._bitnum_intl(st, 12, 25) | self._bitnum_intl(st, 29, 26) |
            self._bitnum_intl(st, 5, 27) | self._bitnum_intl(st, 21, 28) | self._bitnum_intl(st, 10, 29) |
            self._bitnum_intl(st, 3, 30) | self._bitnum_intl(st, 24, 31)
        ) & 0xFFFFFFFF

    def _crypt(self, inp: bytes, out: bytearray, key_sched: list[bytearray]) -> None:
        state = [0, 0]
        self._ip(state, inp)
        for idx in range(15):
            t = state[1]
            state[1] = (self._f(state[1], key_sched[idx]) ^ state[0]) & 0xFFFFFFFF
            state[0] = t
        state[0] = (self._f(state[1], key_sched[15]) ^ state[0]) & 0xFFFFFFFF
        self._inv_ip(state, out)

    def decrypt(self, cipher_bytes: bytes) -> bytes:
        out = bytearray(len(cipher_bytes))
        tmp = bytearray(8)
        for i in range(0, len(cipher_bytes), 8):
            block = cipher_bytes[i : i + 8]
            self._crypt(block, tmp, self.sched[0])
            self._crypt(tmp, tmp, self.sched[1])
            self._crypt(tmp, tmp, self.sched[2])
            out[i : i + 8] = tmp
        return bytes(out)


_default_des = _QrcDES(QQ_KEY)


def decrypt_qrc(hex_str: str) -> str:
    """
    解密 QQ 音乐 QRC Hex 密文：
    1. Hex 还原为密文字节
    2. 3DES 特化 ECB 解密
    3. Zlib 解压缩
    4. 移除 UTF-8 BOM 并转字符串
    """
    cleaned = hex_str.strip()
    if not cleaned:
        return ""
    cipher_bytes = bytes.fromhex(cleaned)
    decompressed = _default_des.decrypt(cipher_bytes)
    decomp = zlib.decompress(decompressed)
    return decomp.decode("utf-8-sig")


def extract_qrc_payload(text_or_hex: str) -> str:
    """
    从歌词节点内容中安全解密并提取纯净 QRC 歌词文本。
    支持自动识别 Hex 密文与明文，若内嵌 XML <Lyric_1 LyricContent="..."/> 则自动提取 LyricContent。
    """
    if not text_or_hex:
        return ""

    raw_text = text_or_hex.strip()

    # 尝试解密 Hex
    decrypted: str = ""
    is_hex = False
    if len(raw_text) >= 16 and all(c in "0123456789abcdefABCDEF \r\n" for c in raw_text[:64]):
        try:
            decrypted = decrypt_qrc(re.sub(r"\s+", "", raw_text))
            is_hex = True
        except Exception:
            decrypted = ""

    if not is_hex or not decrypted:
        decrypted = raw_text

    # 若解密结果包含 XML 包装器，提取 LyricContent
    if "<Lyric_1" in decrypted or "LyricContent=" in decrypted:
        m = re.search(r'LyricContent="([^"]*)"', decrypted, re.DOTALL)
        if m:
            return html.unescape(m.group(1))
        # 兼容 XML 树解析兜底
        try:
            tree = ET.fromstring(decrypted)
            for elem in tree.iter():
                if "LyricContent" in elem.attrib:
                    return html.unescape(elem.attrib["LyricContent"])
        except Exception:
            pass

    return decrypted
