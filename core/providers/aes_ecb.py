"""
core/providers/aes_ecb.py — AES-128-ECB
"""
from __future__ import annotations

import sys

_bcrypt_available = False
if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes

        _bcrypt = ctypes.windll.bcrypt
        _BCRYPT_ALG_HANDLE = wintypes.HANDLE
        _BCRYPT_KEY_HANDLE = wintypes.HANDLE
        _bcrypt_available = True
    except Exception:
        _bcrypt_available = False


def _encrypt_aes_128_ecb_bcrypt(key: bytes, plaintext: bytes) -> bytes:
    pad_len = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([pad_len] * pad_len)

    alg_handle = _BCRYPT_ALG_HANDLE()
    status = _bcrypt.BCryptOpenAlgorithmProvider(
        ctypes.byref(alg_handle),
        ctypes.c_wchar_p("AES"),
        None,
        0,
    )
    if status != 0:
        raise RuntimeError(f"BCryptOpenAlgorithmProvider failed: {status:#x}")

    try:
        chaining_mode_bytes = "ChainingModeECB".encode("utf-16le") + b"\x00\x00"
        status = _bcrypt.BCryptSetProperty(
            alg_handle,
            ctypes.c_wchar_p("ChainingMode"),
            chaining_mode_bytes,
            len(chaining_mode_bytes),
            0,
        )
        if status != 0:
            raise RuntimeError(f"BCryptSetProperty failed: {status:#x}")

        key_handle = _BCRYPT_KEY_HANDLE()
        status = _bcrypt.BCryptGenerateSymmetricKey(
            alg_handle,
            ctypes.byref(key_handle),
            None,
            0,
            key,
            len(key),
            0,
        )
        if status != 0:
            raise RuntimeError(f"BCryptGenerateSymmetricKey failed: {status:#x}")

        try:
            out_buf = ctypes.create_string_buffer(len(padded))
            cb_result = wintypes.ULONG()
            status = _bcrypt.BCryptEncrypt(
                key_handle,
                padded,
                len(padded),
                None,
                None,
                0,
                out_buf,
                len(padded),
                ctypes.byref(cb_result),
                0,
            )
            if status != 0:
                raise RuntimeError(f"BCryptEncrypt failed: {status:#x}")
            return out_buf.raw[: cb_result.value]
        finally:
            _bcrypt.BCryptDestroyKey(key_handle)
    finally:
        _bcrypt.BCryptCloseAlgorithmProvider(alg_handle, 0)

_S_BOX = (
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
)

_RCON = (
    0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40,
    0x80, 0x1B, 0x36,
)


def _xtimes(a: int) -> int:
    return ((a << 1) ^ 0x1B) & 0xFF if (a & 0x80) else (a << 1)


def _sub_word(w: int) -> int:
    return (
        (_S_BOX[(w >> 24) & 0xFF] << 24)
        | (_S_BOX[(w >> 16) & 0xFF] << 16)
        | (_S_BOX[(w >> 8) & 0xFF] << 8)
        | (_S_BOX[w & 0xFF])
    )


def _rot_word(w: int) -> int:
    return ((w << 8) & 0xFFFFFFFF) | (w >> 24)


def _key_expansion_128(key: bytes) -> list[int]:
    w = [int.from_bytes(key[4 * i : 4 * i + 4], "big") for i in range(4)]
    for i in range(4, 44):
        temp = w[i - 1]
        if i % 4 == 0:
            temp = _sub_word(_rot_word(temp)) ^ (_RCON[i // 4] << 24)
        w.append(w[i - 4] ^ temp)
    return w


def _encrypt_block(block: bytes, w: list[int]) -> bytes:
    s = list(block)

    # Round 0: AddRoundKey
    for c in range(4):
        k = w[c]
        s[4 * c + 0] ^= (k >> 24) & 0xFF
        s[4 * c + 1] ^= (k >> 16) & 0xFF
        s[4 * c + 2] ^= (k >> 8) & 0xFF
        s[4 * c + 3] ^= k & 0xFF

    for rnd in range(1, 10):
        # SubBytes
        for i in range(16):
            s[i] = _S_BOX[s[i]]

        # ShiftRows
        s[1], s[5], s[9], s[13] = s[5], s[9], s[13], s[1]
        s[2], s[6], s[10], s[14] = s[10], s[14], s[2], s[6]
        s[3], s[7], s[11], s[15] = s[15], s[3], s[7], s[11]

        # MixColumns
        for c in range(4):
            i = 4 * c
            a0, a1, a2, a3 = s[i], s[i + 1], s[i + 2], s[i + 3]
            s[i + 0] = _xtimes(a0) ^ _xtimes(a1) ^ a1 ^ a2 ^ a3
            s[i + 1] = a0 ^ _xtimes(a1) ^ _xtimes(a2) ^ a2 ^ a3
            s[i + 2] = a0 ^ a1 ^ _xtimes(a2) ^ _xtimes(a3) ^ a3
            s[i + 3] = _xtimes(a0) ^ a0 ^ a1 ^ a2 ^ _xtimes(a3)

        # AddRoundKey
        for c in range(4):
            k = w[rnd * 4 + c]
            s[4 * c + 0] ^= (k >> 24) & 0xFF
            s[4 * c + 1] ^= (k >> 16) & 0xFF
            s[4 * c + 2] ^= (k >> 8) & 0xFF
            s[4 * c + 3] ^= k & 0xFF

    # Round 10: SubBytes -> ShiftRows -> AddRoundKey (No MixColumns)
    for i in range(16):
        s[i] = _S_BOX[s[i]]
    s[1], s[5], s[9], s[13] = s[5], s[9], s[13], s[1]
    s[2], s[6], s[10], s[14] = s[10], s[14], s[2], s[6]
    s[3], s[7], s[11], s[15] = s[15], s[3], s[7], s[11]
    for c in range(4):
        k = w[40 + c]
        s[4 * c + 0] ^= (k >> 24) & 0xFF
        s[4 * c + 1] ^= (k >> 16) & 0xFF
        s[4 * c + 2] ^= (k >> 8) & 0xFF
        s[4 * c + 3] ^= k & 0xFF

    return bytes(s)


def _encrypt_aes_128_ecb_py(key: bytes, plaintext: bytes) -> bytes:
    pad_len = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([pad_len] * pad_len)
    w = _key_expansion_128(key)
    out = bytearray()
    for offset in range(0, len(padded), 16):
        out.extend(_encrypt_block(padded[offset : offset + 16], w))
    return bytes(out)


def encrypt_aes_128_ecb(key: bytes, plaintext: bytes) -> bytes:
    if _bcrypt_available:
        try:
            return _encrypt_aes_128_ecb_bcrypt(key, plaintext)
        except Exception:
            pass
    return _encrypt_aes_128_ecb_py(key, plaintext)
