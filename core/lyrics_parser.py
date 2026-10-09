"""
lyrics_parser.py — 歌词解析器
支持：
  1. YRC 逐字歌词（包含每个字的开始时间与时长，支持卡拉OK逐字渲染）
  2. LRC 标准歌词（回退模式）
  3. 翻译歌词匹配
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LyricWord:
    time_ms: int       # 该字开始时间（毫秒）
    duration_ms: int   # 该字持续时长（毫秒）
    text: str          # 字或词


@dataclass
class LyricLine:
    time_ms: int                            # 行开始时间
    duration_ms: int = 0                    # 行持续时长（YRC 提供，LRC 默认为下一行时间差）
    text: str = ""                          # 完整文本
    words: list[LyricWord] = field(default_factory=list) # 逐字列表（若有则为逐字歌词）
    translation: str = ""                   # 对应译文

    @property
    def end_time_ms(self) -> int:
        if self.duration_ms > 0:
            return self.time_ms + self.duration_ms
        if self.words:
            last = self.words[-1]
            return last.time_ms + last.duration_ms
        return self.time_ms + 4000  # 默认4秒


@dataclass
class ParsedLyrics:
    lines: list[LyricLine] = field(default_factory=list)
    has_words: bool = False                 # 是否为逐字歌词
    is_instrumental: bool = False           # 是否为纯音乐

    def get_line_index(self, time_ms: int) -> int:
        """二分查找当前时间对应的歌词行索引（-1 为未开始）"""
        if not self.lines:
            return -1
        lo, hi = 0, len(self.lines) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.lines[mid].time_ms <= time_ms:
                lo = mid + 1
            else:
                hi = mid - 1
        idx = lo - 1
        return idx


_YRC_LINE_RE = re.compile(r'^\[(\d+),(\d+)\](.*)$')
_YRC_WORD_RE = re.compile(r'\((\d+),(\d+),\d+\)([^(]+)')
# 支持标准与各类变体 LRC 时间戳：[mm:ss.xxx], [mm:ss:xxx], [mm:ss]
_LRC_TIME_RE = re.compile(r'\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]')


def _lrc_time_to_ms(m_str: str, s_str: str, ms_str: str) -> int:
    m = int(m_str)
    s = int(s_str)
    if ms_str:
        if len(ms_str) == 1:
            ms = int(ms_str) * 100
        elif len(ms_str) == 2:
            ms = int(ms_str) * 10
        elif len(ms_str) == 3:
            ms = int(ms_str)
        else:
            ms = int(ms_str[:3])
    else:
        ms = 0
    return m * 60_000 + s * 1_000 + ms

# 章节与角色名特殊解析正则表达式
ROLE_PREFIX_RE  = re.compile(r'^[【\[(（<]([^】\])）>]+)[】\])）>]\s*(.+)$')
ROLE_COLON_RE   = re.compile(r'^([^\s：:]{1,12})[：:]\s*(.+)$')
SECTION_DASH_RE = re.compile(r'^[-—–=~*]{1,4}\s*([^-—–=~*\s].*?[^-—–=~*\s]|[^-—–=~*\s])\s*[-—–=~*]{1,4}$')
SPACER_RE       = re.compile(r'^[\.·…\-\s]+$')

INSTRUMENTAL_PATTERNS = (
    "纯音乐，请欣赏",
    "纯音乐,请欣赏",
    "纯音乐 请欣赏",
    "请欣赏纯音乐",
    "没有填词的纯音乐",
    "此歌曲为纯音乐",
    "暂无歌词，请欣赏纯音乐",
    "纯音乐",
)

CREDIT_PREFIX_RE = re.compile(
    r'^(?:作词|作曲|编曲|制作人?|演唱|主唱|录音师?|录音|混音师?|混音|母带(?:工程师)?|工程师|吉他|贝斯|鼓手?|键盘|弦乐|企划|监制|出品人?|出品|发行|合唱|配唱|和声|乐手|音频|统筹|音乐设计|编程|词|曲|by|ti|ar|al)\s*[:：/]'
    r'|^(?:Written by|Composed by|Arranged by|Produced by|Vocals? by|Mixed by|Mastered by|Mixing|Mastering|Sound Design|Audio|Lyricist|Composer)\b',
    re.IGNORECASE
)


def _is_credit_text(txt: str) -> bool:
    t = txt.strip()
    return bool(CREDIT_PREFIX_RE.match(t))


def _is_instrumental_text(txt: str) -> bool:
    t = txt.strip()
    return any(k in t for k in INSTRUMENTAL_PATTERNS)


def _finalize_lyrics(parsed: ParsedLyrics) -> ParsedLyrics:
    """后处理歌词：纯音乐判断、忽略开头制作名单、解析段落/角色名并拼合到翻译行"""
    if not parsed.lines:
        return parsed

    # 1. 检测纯音乐歌曲：
    # 只要存在“纯音乐”标记，且除去制作名单与占位符后没有其它实际歌词；或者所有非空行均为纯音乐占位
    non_credit_and_non_spacer = [
        l for l in parsed.lines
        if l.text.strip() and not SPACER_RE.match(l.text.strip()) and not _is_credit_text(l.text)
    ]
    has_inst_marker = any(_is_instrumental_text(l.text) for l in parsed.lines)

    if has_inst_marker:
        # 如果包含纯音乐标记，且没有实际唱歌歌词（或剩下的都是纯音乐行）
        if (not non_credit_and_non_spacer) or all(_is_instrumental_text(l.text) for l in non_credit_and_non_spacer):
            parsed.is_instrumental = True
            parsed.lines = []
            return parsed
    elif not non_credit_and_non_spacer:
        # 整首歌曲完全由制作名单构成，没有任何歌词正文，判定为纯音乐
        parsed.is_instrumental = True
        parsed.lines = []
        return parsed

    # 2. 正常歌曲：仅忽略开头前几行的制作名单/元信息行（防误杀：正文中的歌词绝不误杀）
    preamble_count = 0
    for l in parsed.lines:
        txt = l.text.strip()
        if not txt or SPACER_RE.match(txt):
            preamble_count += 1
            continue
        if _is_credit_text(txt) or _is_instrumental_text(txt):
            preamble_count += 1
        else:
            break

    body_lines = parsed.lines[preamble_count:]

    # 3. 正常歌曲中剔除正文开头混入的“纯音乐，请欣赏”行
    parsed.lines = [l for l in body_lines if not _is_instrumental_text(l.text)]

    # 3. 解析段落/章节横线标记与角色名括号标记
    current_sec = ""
    processed: list[LyricLine] = []

    for line in parsed.lines:
        raw_text = line.text.strip()
        if not raw_text or SPACER_RE.match(raw_text):
            continue

        # 检查是否为段落横线标记（例如 "- 哥伦比亚/莱茵生命 -"）
        sm = SECTION_DASH_RE.match(raw_text)
        if sm:
            current_sec = sm.group(1).strip()
            line.text = f"- {current_sec} -"
            processed.append(line)
            continue

        # 检查是否为角色名标记（例如 "【伊芙利特】地面灼烫 沸腾填装"）
        rm = ROLE_PREFIX_RE.match(raw_text) or ROLE_COLON_RE.match(raw_text)
        if rm:
            role = rm.group(1).strip()
            lyric_body = rm.group(2).strip()

            # 排除制作名单信息 (作词/作曲/编曲等)，避免将制作者误认为角色台词
            if _is_credit_text(role) or _is_credit_text(raw_text):
                processed.append(line)
                continue

            combo = f"{current_sec} · {role}" if current_sec else role

            # 若该歌曲/该行没有翻译，将段落+角色名拼合显示在翻译行
            if not line.translation:
                line.translation = combo

            line.text = lyric_body

            # 同步裁切逐字歌词词列表前缀
            if line.words:
                prefix_len = len(raw_text) - len(lyric_body)
                accum = 0
                cut_idx = 0
                for idx, w in enumerate(line.words):
                    accum += len(w.text)
                    if accum >= prefix_len:
                        cut_idx = idx + 1
                        break
                line.words = line.words[cut_idx:]
                if line.words:
                    line.time_ms = line.words[0].time_ms

            processed.append(line)
        else:
            processed.append(line)

    parsed.lines = processed
    return parsed


def parse_bundle(bundle: dict) -> ParsedLyrics:
    """根据歌词包优先解析 YRC，若无则解析 LRC"""
    yrc_text = (bundle.get("yrc") or "").strip()
    lrc_text = (bundle.get("lrc") or "").strip()
    tlyric_text = (bundle.get("tlyric") or "").strip()

    if yrc_text:
        parsed = parse_yrc(yrc_text)
        if parsed.lines:
            parsed = _finalize_lyrics(parsed)
            if parsed.lines and tlyric_text:
                _attach_translations(parsed.lines, tlyric_text)
            return parsed

    if lrc_text:
        parsed = parse_lrc(lrc_text)
        if parsed.lines:
            parsed = _finalize_lyrics(parsed)
            if parsed.lines and tlyric_text:
                _attach_translations(parsed.lines, tlyric_text)
            return parsed

    return ParsedLyrics()


def parse(text: str) -> ParsedLyrics:
    """自动判断格式进行解析"""
    if not text:
        return ParsedLyrics()
    text = text.strip()
    if text.startswith("[") and re.search(r'\[\d+,\d+\]', text):
        return _finalize_lyrics(parse_yrc(text))
    return _finalize_lyrics(parse_lrc(text))


def parse_yrc(yrc_text: str) -> ParsedLyrics:
    """解析网易云官方 YRC 逐字歌词"""
    lines: list[LyricLine] = []

    for raw in yrc_text.splitlines():
        raw = raw.strip()
        if not raw:
            continue

        # 跳过开头的 JSON 元数据行
        if raw.startswith("{") and raw.endswith("}"):
            continue

        m = _YRC_LINE_RE.match(raw)
        if not m:
            continue

        line_start = int(m.group(1))
        line_dur = int(m.group(2))
        body = m.group(3)

        words_matches = _YRC_WORD_RE.findall(body)
        if not words_matches:
            # 可能是没有拆词的特殊行
            clean_text = re.sub(r'\(\d+,\d+,\d+\)', '', body).strip()
            if clean_text:
                lines.append(LyricLine(time_ms=line_start, duration_ms=line_dur, text=clean_text))
            continue

        words: list[LyricWord] = []
        full_chars: list[str] = []
        for w_start, w_dur, w_char in words_matches:
            w_start_ms = int(w_start)
            w_dur_ms = int(w_dur)
            words.append(LyricWord(time_ms=w_start_ms, duration_ms=w_dur_ms, text=w_char))
            full_chars.append(w_char)

        line_text = "".join(full_chars).strip()
        # 过滤完全空白的行（避免界面上出现孤立的空白或特殊符号）
        if not line_text:
            continue

        lines.append(LyricLine(
            time_ms=line_start,
            duration_ms=line_dur,
            text=line_text,
            words=words,
        ))

    lines.sort(key=lambda x: x.time_ms)
    return ParsedLyrics(lines=lines, has_words=True)


def parse_lrc(lrc_text: str) -> ParsedLyrics:
    """解析标准 LRC 歌词（兼容 [mm:ss.xx] 与 [mm:ss:xx] 变体时间戳）"""
    raw_list: list[tuple[int, str]] = []

    for raw in lrc_text.splitlines():
        raw = raw.strip()
        # 跳过空行及网易云演职人员元信息结构
        if not raw or raw.startswith("{"):
            continue

        timestamps = _LRC_TIME_RE.findall(raw)
        if not timestamps:
            continue

        text = _LRC_TIME_RE.sub("", raw).strip()
        # 绝不保留纯空行，防止在界面正中间显示出单独的空白或音符
        if not text:
            continue

        for m_str, s_str, ms_str in timestamps:
            ms = _lrc_time_to_ms(m_str, s_str, ms_str)
            raw_list.append((ms, text))

    raw_list.sort(key=lambda x: x[0])

    lines: list[LyricLine] = []
    for i, (ms, txt) in enumerate(raw_list):
        dur = 3000
        if i + 1 < len(raw_list):
            dur = max(1000, raw_list[i + 1][0] - ms)
        lines.append(LyricLine(time_ms=ms, duration_ms=dur, text=txt))

    return ParsedLyrics(lines=lines, has_words=False)


def _attach_translations(lines: list[LyricLine], tlyric_text: str) -> None:
    """智能单调时间对齐将译文附加到歌词行"""
    if not lines or not tlyric_text:
        return

    trans_entries: list[tuple[int, str]] = []
    for raw in tlyric_text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("{"):
            continue

        ts = _LRC_TIME_RE.findall(raw)
        if not ts:
            continue
        text = _LRC_TIME_RE.sub("", raw).strip()
        # 过滤元数据及纯无意义字符
        if not text or any(text.startswith(k) for k in ["作词", "作曲", "编曲", "制作", "纯音乐", "//"]):
            continue
        for m_str, s_str, ms_str in ts:
            ms = _lrc_time_to_ms(m_str, s_str, ms_str)
            trans_entries.append((ms, text))

    trans_entries.sort(key=lambda x: x[0])
    if not trans_entries:
        return

    # 单调有序对齐 (允许前后 2.5 秒容差)
    trans_idx = 0
    num_trans = len(trans_entries)

    for line in lines:
        if not line.text.strip():
            continue

        best_idx = -1
        best_diff = float("inf")

        for j in range(trans_idx, num_trans):
            t_ms, t_txt = trans_entries[j]
            diff = abs(line.time_ms - t_ms)
            if diff < best_diff:
                best_diff = diff
                best_idx = j
            elif t_ms > line.time_ms + 3000:
                break

        if best_idx != -1 and best_diff <= 2500:
            line.translation = trans_entries[best_idx][1]
            trans_idx = best_idx + 1
