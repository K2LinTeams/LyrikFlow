"""
core/providers/qrc_decoder.py — QRC 歌词解密引擎
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
import zlib
from typing import Optional

from .qrc_tables import (
    E12_TABLES,
    INV_S0,
    INV_S1,
    IP0_TABLES,
    IP1_TABLES,
    QQ_PASS_DATA,
    SP01,
    SP23,
    SP45,
    SP67,
)

QQ_KEY = b"!@#)(*$%123ZXC!@!@#)(NHL"

_IP0_0, _IP0_1, _IP0_2, _IP0_3, _IP0_4, _IP0_5, _IP0_6, _IP0_7 = IP0_TABLES
_IP1_0, _IP1_1, _IP1_2, _IP1_3, _IP1_4, _IP1_5, _IP1_6, _IP1_7 = IP1_TABLES
_INV0_0, _INV0_1, _INV0_2, _INV0_3 = INV_S0
_INV1_0, _INV1_1, _INV1_2, _INV1_3 = INV_S1
_E12_0, _E12_1, _E12_2, _E12_3 = E12_TABLES
_SP01, _SP23, _SP45, _SP67 = SP01, SP23, SP45, SP67
_P0_15, _P0_LAST = QQ_PASS_DATA[0]
_P1_15, _P1_LAST = QQ_PASS_DATA[1]
_P2_15, _P2_LAST = QQ_PASS_DATA[2]


def _fast_qrc_decrypt(cipher_bytes: bytes) -> bytes:
    n = len(cipher_bytes)
    out = bytearray(n)
    for i in range(0, n, 8):
        b0 = cipher_bytes[i]
        b1 = cipher_bytes[i + 1]
        b2 = cipher_bytes[i + 2]
        b3 = cipher_bytes[i + 3]
        b4 = cipher_bytes[i + 4]
        b5 = cipher_bytes[i + 5]
        b6 = cipher_bytes[i + 6]
        b7 = cipher_bytes[i + 7]

        # 初始置换 IP
        s0 = _IP0_0[b0] | _IP0_1[b1] | _IP0_2[b2] | _IP0_3[b3] | _IP0_4[b4] | _IP0_5[b5] | _IP0_6[b6] | _IP0_7[b7]
        s1 = _IP1_0[b0] | _IP1_1[b1] | _IP1_2[b2] | _IP1_3[b3] | _IP1_4[b4] | _IP1_5[b5] | _IP1_6[b6] | _IP1_7[b7]

        # Pass 0
        for k_hi, k_lo in _P0_15:
            e12 = _E12_0[s1 & 0xFF] | _E12_1[(s1 >> 8) & 0xFF] | _E12_2[(s1 >> 16) & 0xFF] | _E12_3[(s1 >> 24) & 0xFF]
            v1, v2 = (e12 >> 24) ^ k_hi, (e12 & 0xFFFFFF) ^ k_lo
            s0, s1 = s1, (_SP01[(v1 >> 12) & 0xFFF] | _SP23[v1 & 0xFFF] | _SP45[(v2 >> 12) & 0xFFF] | _SP67[v2 & 0xFFF]) ^ s0
        e12 = _E12_0[s1 & 0xFF] | _E12_1[(s1 >> 8) & 0xFF] | _E12_2[(s1 >> 16) & 0xFF] | _E12_3[(s1 >> 24) & 0xFF]
        v1, v2 = (e12 >> 24) ^ _P0_LAST[0], (e12 & 0xFFFFFF) ^ _P0_LAST[1]
        s0 = (_SP01[(v1 >> 12) & 0xFFF] | _SP23[v1 & 0xFFF] | _SP45[(v2 >> 12) & 0xFFF] | _SP67[v2 & 0xFFF]) ^ s0

        # Pass 1
        for k_hi, k_lo in _P1_15:
            e12 = _E12_0[s1 & 0xFF] | _E12_1[(s1 >> 8) & 0xFF] | _E12_2[(s1 >> 16) & 0xFF] | _E12_3[(s1 >> 24) & 0xFF]
            v1, v2 = (e12 >> 24) ^ k_hi, (e12 & 0xFFFFFF) ^ k_lo
            s0, s1 = s1, (_SP01[(v1 >> 12) & 0xFFF] | _SP23[v1 & 0xFFF] | _SP45[(v2 >> 12) & 0xFFF] | _SP67[v2 & 0xFFF]) ^ s0
        e12 = _E12_0[s1 & 0xFF] | _E12_1[(s1 >> 8) & 0xFF] | _E12_2[(s1 >> 16) & 0xFF] | _E12_3[(s1 >> 24) & 0xFF]
        v1, v2 = (e12 >> 24) ^ _P1_LAST[0], (e12 & 0xFFFFFF) ^ _P1_LAST[1]
        s0 = (_SP01[(v1 >> 12) & 0xFFF] | _SP23[v1 & 0xFFF] | _SP45[(v2 >> 12) & 0xFFF] | _SP67[v2 & 0xFFF]) ^ s0

        # Pass 2
        for k_hi, k_lo in _P2_15:
            e12 = _E12_0[s1 & 0xFF] | _E12_1[(s1 >> 8) & 0xFF] | _E12_2[(s1 >> 16) & 0xFF] | _E12_3[(s1 >> 24) & 0xFF]
            v1, v2 = (e12 >> 24) ^ k_hi, (e12 & 0xFFFFFF) ^ k_lo
            s0, s1 = s1, (_SP01[(v1 >> 12) & 0xFFF] | _SP23[v1 & 0xFFF] | _SP45[(v2 >> 12) & 0xFFF] | _SP67[v2 & 0xFFF]) ^ s0
        e12 = _E12_0[s1 & 0xFF] | _E12_1[(s1 >> 8) & 0xFF] | _E12_2[(s1 >> 16) & 0xFF] | _E12_3[(s1 >> 24) & 0xFF]
        v1, v2 = (e12 >> 24) ^ _P2_LAST[0], (e12 & 0xFFFFFF) ^ _P2_LAST[1]
        s0 = (_SP01[(v1 >> 12) & 0xFFF] | _SP23[v1 & 0xFFF] | _SP45[(v2 >> 12) & 0xFFF] | _SP67[v2 & 0xFFF]) ^ s0

        # 逆初始置换 INV_IP
        out_val = (
            _INV0_0[s0 & 0xFF] | _INV0_1[(s0 >> 8) & 0xFF] | _INV0_2[(s0 >> 16) & 0xFF] | _INV0_3[(s0 >> 24) & 0xFF] |
            _INV1_0[s1 & 0xFF] | _INV1_1[(s1 >> 8) & 0xFF] | _INV1_2[(s1 >> 16) & 0xFF] | _INV1_3[(s1 >> 24) & 0xFF]
        )
        out[i : i + 8] = out_val.to_bytes(8, "little")
    return bytes(out)


class _QrcDES:
    """向后兼容"""

    def __init__(self, key: bytes = QQ_KEY) -> None:
        self.key = key
        self._is_default = (key == QQ_KEY)
        if not self._is_default:
            from scripts.generate_qrc_tables import _ReferenceDES
            self._fallback_engine = _ReferenceDES(key)
        else:
            self._fallback_engine = None

    def decrypt(self, cipher_bytes: bytes) -> bytes:
        if self._is_default:
            return _fast_qrc_decrypt(cipher_bytes)
        return self._fallback_engine.decrypt(cipher_bytes)


_default_des = _QrcDES(QQ_KEY)


def decrypt_qrc(hex_str: str) -> str:
    """
    解密 QQ 音乐 QRC Hex 密文
    """
    cleaned = hex_str.strip()
    if not cleaned:
        return ""
    cipher_bytes = bytes.fromhex(cleaned)
    decompressed = _fast_qrc_decrypt(cipher_bytes)
    decomp = zlib.decompress(decompressed)
    return decomp.decode("utf-8-sig")


def extract_qrc_payload(text_or_hex: str) -> str:
    """
    从歌词节点内容中安全解密并提取纯净 QRC 歌词文本
    """
    if not text_or_hex:
        return ""

    raw_text = text_or_hex.strip()

    # 解密 Hex
    decrypted: str = ""
    is_hex = False
    if len(raw_text) >= 16 and all(c in "0123456789abcdefABCDEF \r\n\t" for c in raw_text[:64]):
        try:
            decrypted = decrypt_qrc(raw_text)
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
