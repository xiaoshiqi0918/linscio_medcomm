"""
零宽字符隐写水印 — 在生成内容中嵌入用户标识

每段开头嵌入 user_id 的零宽编码，用于追踪内容来源。
注意：零宽字符隐写只能防懒惰搬运者，Word "清除格式"、
微信编辑器粘贴过滤都可能清洗。不应作为维权依据。
"""
from __future__ import annotations

from typing import Optional

ZW_MAP = {
    '0': '\u200B',  # ZWSP (Zero Width Space)
    '1': '\u200C',  # ZWNJ (Zero Width Non-Joiner)
    '2': '\u200D',  # ZWJ  (Zero Width Joiner)
    '3': '\u2060',  # WJ   (Word Joiner)
}

ZW_REVERSE = {v: k for k, v in ZW_MAP.items()}

ZW_CHARS = set(ZW_MAP.values())

_MARKER_START = '\uFEFF'  # BOM 作为水印起始标记
_MARKER_END = '\u2061'    # FUNCTION APPLICATION 作为结束标记


def _encode_id(user_id: int) -> str:
    """将 user_id 编码为零宽字符序列（4位十六进制，支持 0~65535）"""
    hex_str = format(user_id % 0x10000, '04x')
    chars = []
    for c in hex_str:
        if c in ZW_MAP:
            chars.append(ZW_MAP[c])
        else:
            nibble = int(c, 16)
            hi = str(nibble >> 2)
            lo = str(nibble & 0x3)
            chars.append(ZW_MAP.get(hi, '\u200B'))
            chars.append(ZW_MAP.get(lo, '\u200B'))
    return _MARKER_START + ''.join(chars) + _MARKER_END


def _decode_id(zw_seq: str) -> Optional[int]:
    """从零宽字符序列反解 user_id"""
    start = zw_seq.find(_MARKER_START)
    end = zw_seq.find(_MARKER_END, start + 1)
    if start == -1 or end == -1:
        return None

    payload = zw_seq[start + 1:end]
    hex_chars = []
    for ch in payload:
        if ch in ZW_REVERSE:
            hex_chars.append(ZW_REVERSE[ch])

    if len(hex_chars) < 4:
        return None

    try:
        return int(''.join(hex_chars[:4]), 16)
    except ValueError:
        return None


def embed_watermark(content: str, user_id: int) -> str:
    """在每段开头嵌入 user_id 的零宽编码"""
    if not content:
        return content
    watermark = _encode_id(user_id)
    paragraphs = content.split('\n\n')
    return '\n\n'.join(watermark + p for p in paragraphs)


def extract_watermark(content: str) -> Optional[int]:
    """从内容中反解 user_id（取第一个命中）"""
    if not content:
        return None
    return _decode_id(content)


def strip_watermark(content: str) -> str:
    """移除所有零宽水印字符"""
    if not content:
        return content
    result = []
    for ch in content:
        if ch not in ZW_CHARS and ch != _MARKER_START and ch != _MARKER_END:
            result.append(ch)
    return ''.join(result)
