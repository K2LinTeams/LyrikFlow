"""
core/lyrics_parser.py — 结构化歌词解析与序列化
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LyricWord:
    time_ms: int
    duration_ms: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_ms": self.time_ms,
            "duration_ms": self.duration_ms,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LyricWord:
        return cls(
            time_ms=int(d.get("time_ms", 0)),
            duration_ms=int(d.get("duration_ms", 0)),
            text=str(d.get("text", "")),
        )


@dataclass
class LyricLine:
    time_ms: int
    duration_ms: int = 0
    text: str = ""
    words: list[LyricWord] = field(default_factory=list)
    translation: str = ""
    romaji: str = ""
    role: str = ""
    section: str = ""

    @property
    def end_time_ms(self) -> int:
        if self.duration_ms > 0:
            return self.time_ms + self.duration_ms
        if self.words:
            last = self.words[-1]
            return last.time_ms + last.duration_ms
        return self.time_ms + 4000

    def get_secondary_text(
        self,
        show_translation: bool = True,
        show_romaji: bool = False,
        secondary_mode: str = "prefer_trans",
        parse_sections: bool = True,
    ) -> str:
        tr = self.translation.strip() if show_translation else ""
        ro = self.romaji.strip() if show_romaji else ""

        if tr and ro:
            if secondary_mode == "prefer_romaji":
                return ro
            elif secondary_mode == "both":
                return f"{ro}  ·  {tr}"
            return tr
        elif tr:
            return tr
        elif ro:
            return ro

        if parse_sections:
            sec = self.section.strip()
            role = self.role.strip()
            if sec and role:
                return f"{sec} · {role}"
            return role or sec
        return ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "time_ms": self.time_ms,
            "duration_ms": self.duration_ms,
            "text": self.text,
        }
        if self.words:
            d["words"] = [w.to_dict() for w in self.words]
        if self.translation:
            d["translation"] = self.translation
        if self.romaji:
            d["romaji"] = self.romaji
        if self.role:
            d["role"] = self.role
        if self.section:
            d["section"] = self.section
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LyricLine:
        words = [LyricWord.from_dict(w) for w in d.get("words", [])]
        return cls(
            time_ms=int(d.get("time_ms", 0)),
            duration_ms=int(d.get("duration_ms", 0)),
            text=str(d.get("text", "")),
            words=words,
            translation=str(d.get("translation", "")),
            romaji=str(d.get("romaji", "")),
            role=str(d.get("role", "")),
            section=str(d.get("section", "")),
        )


@dataclass
class ParsedLyrics:
    lines: list[LyricLine] = field(default_factory=list)
    has_words: bool = False
    is_instrumental: bool = False
    title: str = ""
    artist: str = ""
    album: str = ""
    by: str = ""
    offset_ms: int = 0
    provider: str = ""
    song_id: str = ""

    def get_line_index(self, time_ms: int) -> int:
        if not self.lines:
            return -1
        lo, hi = 0, len(self.lines) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.lines[mid].time_ms <= time_ms:
                lo = mid + 1
            else:
                hi = mid - 1
        return lo - 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "provider": self.provider,
            "song_id": self.song_id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "by": self.by,
            "offset_ms": self.offset_ms,
            "is_verbatim": self.has_words,
            "is_instrumental": self.is_instrumental,
            "lines": [line.to_dict() for line in self.lines],
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        if indent is not None:
            return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ParsedLyrics:
        lines = [LyricLine.from_dict(line_d) for line_d in d.get("lines", [])]
        return cls(
            lines=lines,
            has_words=bool(d.get("is_verbatim", any(bool(l.words) for l in lines))),
            is_instrumental=bool(d.get("is_instrumental", False)),
            title=str(d.get("title", "")),
            artist=str(d.get("artist", "")),
            album=str(d.get("album", "")),
            by=str(d.get("by", "")),
            offset_ms=int(d.get("offset_ms", 0)),
            provider=str(d.get("provider", "")),
            song_id=str(d.get("song_id", "")),
        )

    @classmethod
    def from_json(cls, json_str: str) -> ParsedLyrics:
        if not json_str or not json_str.strip():
            return cls()
        return cls.from_dict(json.loads(json_str))


_MS_LINE_RE = re.compile(r"^\[(\d+),(\d+)\](.*)$")
_YRC_WORD_RE = re.compile(r"\((\d+),(\d+),\d+\)([^(]+)")
_QRC_WORD_RE = re.compile(r"([^\(\)]+)\((\d+),(\d+)\)")
_LRC_TIME_RE = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
_HEADER_RE = re.compile(r"^\[(ti|ar|al|by|offset):(.*)\]$", re.IGNORECASE)

SECTION_KEYWORD_RE = re.compile(
    r"^(?:Chorus(?:\s*\d+)?|Verse(?:\s*\d+)?|Bridge|Intro|Outro|Hook|Pre-Chorus|副歌|主歌|过渡)$",
    re.IGNORECASE,
)
SECTION_DASH_RE = re.compile(r"^[-—–=~*]{1,4}\s*(.+?)\s*[-—–=~*]{1,4}$")
STANDALONE_BRACKET_RE = re.compile(r"^[【\[(（<]([^】\])）>]{1,32})[】\])）>]\s*[:：]?$")
STANDALONE_COLON_RE = re.compile(r"^([^\s：:【\[\]()]{1,32})\s*[:：]$")
ROLE_INLINE_BRACKET_RE = re.compile(r"^[【\[(（<]([^】\])）>]{1,32})[】\])）>]\s*(.+)$")
SPACER_RE = re.compile(r"^[\.·•●…\-\s\xa0]+$")
NUMERIC_TAG_RE = re.compile(r"^(?:\d+|[IVXLCDMivxlcdm]+)$")

INSTRUMENTAL_KEYWORDS = ("纯音乐", "没有填词", "暂无歌词")


def _lrc_time_to_ms(m_str: str, s_str: str, ms_str: str) -> int:
    ms = int(ms_str[:3].ljust(3, "0")) if ms_str else 0
    return int(m_str) * 60_000 + int(s_str) * 1_000 + ms


def _is_instrumental_text(txt: str) -> bool:
    return any(k in txt for k in INSTRUMENTAL_KEYWORDS)


def _apply_header_tag(parsed: ParsedLyrics, tag: str, val: str) -> None:
    tag = tag.lower()
    val = val.strip()
    if tag == "ti":
        if not parsed.title:
            parsed.title = val
    elif tag == "ar":
        if not parsed.artist:
            parsed.artist = val
    elif tag == "al":
        if not parsed.album:
            parsed.album = val
    elif tag == "by":
        if not parsed.by:
            parsed.by = val
    elif tag == "offset":
        try:
            parsed.offset_ms = int(val)
        except ValueError:
            pass


def _is_title_or_artist(text: str, title: str = "", artist: str = "") -> bool:
    t = text.strip()
    if not t or SPACER_RE.match(t):
        return True

    t_lower = t.lower()
    title_lower = title.strip().lower()
    artist_lower = artist.strip().lower()

    if title_lower:
        if t_lower == title_lower or t_lower.startswith((f"{title_lower} -", f"{title_lower}-")) or t_lower.endswith((f"- {title_lower}", f"-{title_lower}")):
            return True

    if artist_lower:
        if t_lower == artist_lower or t_lower.startswith((f"{artist_lower} -", f"{artist_lower}-")) or t_lower.endswith((f"- {artist_lower}", f"-{artist_lower}")):
            return True

    if title_lower and artist_lower and (title_lower in t_lower and artist_lower in t_lower):
        return True

    if " - " in t:
        if (title_lower and title_lower in t_lower) or (artist_lower and artist_lower in t_lower):
            return True
        if not title_lower and not artist_lower and len(t) < 60:
            return True

    return False


def _find_first_lyric_index(
    lines: list[LyricLine],
    title: str = "",
    artist: str = "",
) -> int:
    if not lines:
        return 0

    n = len(lines)
    for i in range(n):
        cand_text = lines[i].text.strip()
        if ":" in cand_text or "：" in cand_text or _is_title_or_artist(cand_text, title=title, artist=artist):
            continue

        streak_len = min(3, n - i)
        is_streak = True
        for j in range(i + 1, i + streak_len):
            t = lines[j].text.strip()
            if ":" in t or "：" in t or _is_title_or_artist(t, title=title, artist=artist):
                is_streak = False
                break

        if is_streak:
            return i

    return 0


def _filter_opening_preamble(
    lines: list[LyricLine],
    title: str = "",
    artist: str = "",
) -> list[LyricLine]:
    if not lines:
        return lines

    first_idx = _find_first_lyric_index(lines, title=title, artist=artist)
    if first_idx == 0:
        return lines

    filtered_pre: list[LyricLine] = []
    for idx in range(first_idx):
        line = lines[idx]
        t = line.text.strip()
        if _is_title_or_artist(t, title=title, artist=artist):
            continue

        if STANDALONE_COLON_RE.match(t) or SECTION_DASH_RE.match(t) or STANDALONE_BRACKET_RE.match(t):
            filtered_pre.append(line)
            continue

        if ":" in t or "：" in t:
            continue

        filtered_pre.append(line)

    return filtered_pre + lines[first_idx:]


def _parse_verbatim_body(body: str, word_re: re.Pattern, is_qrc: bool = False) -> tuple[str, list[LyricWord]]:
    matches = word_re.findall(body)
    if not matches:
        clean = re.sub(r"\(\d+,\d+(?:,\d+)?\)", "", body).strip()
        return clean, []
    words: list[LyricWord] = []
    chars: list[str] = []
    for item in matches:
        if is_qrc:
            w_char, w_start, w_dur = item
        else:
            w_start, w_dur, w_char = item
        words.append(LyricWord(time_ms=int(w_start), duration_ms=int(w_dur), text=w_char))
        chars.append(w_char)
    return "".join(chars).strip(), words


def _finalize_parsed(
    parsed: ParsedLyrics,
    lines: list[LyricLine],
    is_inst: bool,
    parse_sections: Optional[bool] = None,
) -> ParsedLyrics:
    lines.sort(key=lambda x: x.time_ms)
    parsed.lines = _filter_opening_preamble(lines, title=parsed.title, artist=parsed.artist)
    parsed.has_words = any(bool(l.words) for l in parsed.lines)
    parsed.is_instrumental = is_inst
    return _process_sections_and_roles(parsed, parse_sections=parse_sections)


def parse_raw_bundle(
    yrc_text: str = "",
    lrc_text: str = "",
    tlyric_text: str = "",
    romalrc_text: str = "",
    qrc_text: str = "",
    title: str = "",
    artist: str = "",
    provider: str = "",
    song_id: str = "",
    is_instrumental: bool = False,
    parse_sections: Optional[bool] = None,
) -> ParsedLyrics:
    if is_instrumental:
        return ParsedLyrics(
            is_instrumental=True,
            title=title,
            artist=artist,
            provider=provider,
            song_id=song_id,
        )

    yrc_text = (yrc_text or "").strip()
    qrc_text = (qrc_text or "").strip()
    lrc_text = (lrc_text or "").strip()
    tlyric_text = (tlyric_text or "").strip()
    romalrc_text = (romalrc_text or "").strip()

    if yrc_text:
        parsed = parse_yrc(yrc_text, title=title, artist=artist, parse_sections=parse_sections)
    elif qrc_text:
        parsed = parse_qrc(qrc_text, title=title, artist=artist, parse_sections=parse_sections)
    elif lrc_text:
        parsed = parse_lrc(lrc_text, title=title, artist=artist, parse_sections=parse_sections)
    else:
        parsed = ParsedLyrics(title=title, artist=artist)

    if not parsed.title:
        parsed.title = title
    if not parsed.artist:
        parsed.artist = artist
    parsed.provider = provider
    parsed.song_id = song_id

    if parsed.lines and tlyric_text:
        _attach_translations(parsed.lines, tlyric_text)

    if parsed.lines and romalrc_text:
        _attach_romaji(parsed.lines, romalrc_text)

    return parsed


def parse_qrc(
    qrc_text: str,
    title: str = "",
    artist: str = "",
    parse_sections: Optional[bool] = None,
) -> ParsedLyrics:
    if not qrc_text:
        return ParsedLyrics()

    parsed = ParsedLyrics(title=title, artist=artist)
    lines: list[LyricLine] = []
    is_inst = False

    for raw in qrc_text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("[kana:") or raw.startswith("{"):
            continue

        m_head = _HEADER_RE.match(raw)
        if m_head:
            _apply_header_tag(parsed, m_head.group(1), m_head.group(2))
            continue

        m_ms = _MS_LINE_RE.match(raw)
        if m_ms:
            line_start = int(m_ms.group(1))
            line_dur = int(m_ms.group(2))
            body = m_ms.group(3)
        else:
            m_lrc = _LRC_TIME_RE.match(raw)
            if not m_lrc:
                continue
            line_start = _lrc_time_to_ms(m_lrc.group(1), m_lrc.group(2), m_lrc.group(3))
            line_dur = 0
            body = raw[m_lrc.end():]

        line_text, words = _parse_verbatim_body(body, _QRC_WORD_RE, is_qrc=True)
        if not line_text:
            continue

        if _is_instrumental_text(line_text):
            is_inst = True
            continue

        lines.append(LyricLine(time_ms=line_start, duration_ms=line_dur, text=line_text, words=words))

    return _finalize_parsed(parsed, lines, is_inst, parse_sections)


def parse_yrc(
    yrc_text: str,
    title: str = "",
    artist: str = "",
    parse_sections: Optional[bool] = None,
) -> ParsedLyrics:
    if not yrc_text:
        return ParsedLyrics()

    parsed = ParsedLyrics(title=title, artist=artist)
    lines: list[LyricLine] = []
    is_inst = False

    for raw in yrc_text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("{"):
            continue

        m_head = _HEADER_RE.match(raw)
        if m_head:
            _apply_header_tag(parsed, m_head.group(1), m_head.group(2))
            continue

        m = _MS_LINE_RE.match(raw)
        if not m:
            continue

        line_start = int(m.group(1))
        line_dur = int(m.group(2))
        body = m.group(3)

        line_text, words = _parse_verbatim_body(body, _YRC_WORD_RE, is_qrc=False)
        if not line_text:
            continue

        if _is_instrumental_text(line_text):
            is_inst = True
            continue

        lines.append(LyricLine(time_ms=line_start, duration_ms=line_dur, text=line_text, words=words))

    return _finalize_parsed(parsed, lines, is_inst, parse_sections)


def parse_lrc(
    lrc_text: str,
    title: str = "",
    artist: str = "",
    parse_sections: Optional[bool] = None,
) -> ParsedLyrics:
    if not lrc_text:
        return ParsedLyrics()

    parsed = ParsedLyrics(title=title, artist=artist)
    raw_list: list[tuple[int, str]] = []
    is_inst = False

    for raw in lrc_text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("{"):
            continue

        m_head = _HEADER_RE.match(raw)
        if m_head:
            _apply_header_tag(parsed, m_head.group(1), m_head.group(2))
            continue

        timestamps = _LRC_TIME_RE.findall(raw)
        if not timestamps:
            continue

        text = _LRC_TIME_RE.sub("", raw).strip()
        if not text:
            continue

        if _is_instrumental_text(text):
            is_inst = True
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

    return _finalize_parsed(parsed, lines, is_inst, parse_sections)


def _process_sections_and_roles(parsed: ParsedLyrics, parse_sections: Optional[bool] = None) -> ParsedLyrics:
    if not parsed.lines:
        return parsed

    if parse_sections is None:
        try:
            from core import settings
            parse_sections = settings.get_parse_sections()
        except Exception:
            parse_sections = True

    if not parse_sections:
        return parsed

    current_sec = ""
    current_role = ""
    processed: list[LyricLine] = []

    for line in parsed.lines:
        raw_text = line.text.strip()
        if not raw_text or SPACER_RE.match(raw_text):
            continue

        dash_match = SECTION_DASH_RE.match(raw_text)
        if dash_match:
            sec_name = dash_match.group(1).strip()
            current_sec = "" if NUMERIC_TAG_RE.match(sec_name) else sec_name
            current_role = ""
            continue

        bracket_match = STANDALONE_BRACKET_RE.match(raw_text)
        if bracket_match:
            inner = bracket_match.group(1).strip()
            current_sec = inner if SECTION_KEYWORD_RE.match(inner) else ""
            current_role = ""
            continue

        colon_match = STANDALONE_COLON_RE.match(raw_text)
        if colon_match:
            cand = colon_match.group(1).strip()
            if not NUMERIC_TAG_RE.match(cand):
                if SECTION_KEYWORD_RE.match(cand):
                    current_sec = cand
                    current_role = ""
                else:
                    current_role = cand
            else:
                current_role = ""
            continue

        if NUMERIC_TAG_RE.match(raw_text):
            current_sec = ""
            current_role = ""
            continue

        if SECTION_KEYWORD_RE.match(raw_text):
            current_sec = raw_text
            current_role = ""
            continue

        inline_match = ROLE_INLINE_BRACKET_RE.match(raw_text)
        if inline_match:
            cand = inline_match.group(1).strip()
            lyric_body = inline_match.group(2).strip()

            if not NUMERIC_TAG_RE.match(cand):
                if SECTION_KEYWORD_RE.match(cand):
                    current_sec = cand
                    current_role = ""
                else:
                    current_role = cand

                line.section = current_sec
                line.role = current_role
                line.text = lyric_body

                if line.words:
                    words_text = "".join(w.text for w in line.words)
                    if words_text != lyric_body:
                        prefix_len = len(words_text) - len(lyric_body) if words_text.endswith(lyric_body) else (len(raw_text) - len(lyric_body))
                        accum = 0
                        cut_idx = 0
                        for idx, w in enumerate(line.words):
                            accum += len(w.text)
                            if accum >= prefix_len:
                                cut_idx = idx + 1
                                break
                        trimmed = line.words[cut_idx:]
                        if trimmed:
                            line.words = trimmed
                            line.time_ms = trimmed[0].time_ms
                            if line.duration_ms > 0:
                                last = trimmed[-1]
                                line.duration_ms = max(0, (last.time_ms + last.duration_ms) - line.time_ms)

                processed.append(line)
                continue

        line.section = current_sec
        line.role = current_role
        processed.append(line)

    parsed.lines = processed
    return parsed


def _match_timeline_entries(lines: list[LyricLine], entries: list[tuple[int, str]], attr_name: str) -> None:
    if not lines or not entries:
        return

    entries.sort(key=lambda x: x[0])
    entry_idx = 0
    num_entries = len(entries)

    for line in lines:
        if not line.text.strip():
            continue

        best_idx = -1
        best_diff = float("inf")

        for j in range(entry_idx, num_entries):
            t_ms, _ = entries[j]
            diff = abs(line.time_ms - t_ms)
            if diff < best_diff:
                best_diff = diff
                best_idx = j
            elif t_ms > line.time_ms + 3000:
                break

        if best_idx != -1 and best_diff <= 2500:
            setattr(line, attr_name, entries[best_idx][1])
            entry_idx = best_idx + 1


def _attach_translations(lines: list[LyricLine], tlyric_text: str) -> None:
    if not lines or not tlyric_text:
        return

    entries: list[tuple[int, str]] = []
    for raw in tlyric_text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("{") or _HEADER_RE.match(raw):
            continue

        ts = _LRC_TIME_RE.findall(raw)
        if not ts:
            continue
        text = _LRC_TIME_RE.sub("", raw).strip()
        if not text or _is_instrumental_text(text) or text.startswith("//"):
            continue
        for m_str, s_str, ms_str in ts:
            entries.append((_lrc_time_to_ms(m_str, s_str, ms_str), text))

    _match_timeline_entries(lines, entries, "translation")


def _clean_romaji_line(raw: str) -> str:
    s = re.sub(r"\(\d+,\d+(?:,\d+)?\)", "", raw)
    s = _LRC_TIME_RE.sub("", s)
    s = _MS_LINE_RE.sub(r"\3", s)
    return re.sub(r"[ \t]+", " ", s).strip()


def _attach_romaji(lines: list[LyricLine], romalrc_text: str) -> None:
    if not lines or not romalrc_text:
        return

    entries: list[tuple[int, str]] = []
    for raw in romalrc_text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("{") or _HEADER_RE.match(raw) or raw.lower().startswith("[kana:"):
            continue

        m_ms = _MS_LINE_RE.match(raw)
        if m_ms:
            clean_text = _clean_romaji_line(raw)
            if clean_text and not _is_instrumental_text(clean_text) and not clean_text.startswith("//"):
                entries.append((int(m_ms.group(1)), clean_text))
            continue

        ts = _LRC_TIME_RE.findall(raw)
        if ts:
            clean_text = _clean_romaji_line(raw)
            if not clean_text or _is_instrumental_text(clean_text) or clean_text.startswith("//"):
                continue
            for m_str, s_str, ms_str in ts:
                entries.append((_lrc_time_to_ms(m_str, s_str, ms_str), clean_text))

    _match_timeline_entries(lines, entries, "romaji")
