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
    time_ms: int       # 该字开始时间（毫秒）
    duration_ms: int   # 该字持续时长（毫秒）
    text: str          # 字文本

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
    time_ms: int                            # 行开始时间
    duration_ms: int = 0                    # 行持续时长
    text: str = ""                          # 歌词正文文本
    words: list[LyricWord] = field(default_factory=list) # 逐字列表
    translation: str = ""                   # 对应译文 (严格为真实译文)
    romaji: str = ""                        # 对应罗马音 (规范化纯净罗马音)
    role: str = ""                          # 演唱者/角色名
    section: str = ""                       # 章节/段落名 (如 副歌, 间奏, Verse, Bridge)

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
        """获取副行渲染文本：支持真实译文与罗马音按开关及偏好模式返回；无副文本且开启段落解析时返回 章节 · 角色"""
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
    has_words: bool = False                 # 是否为逐字歌词
    is_instrumental: bool = False           # 是否为纯音乐
    title: str = ""                         # 歌曲标题
    artist: str = ""                        # 歌手
    album: str = ""                         # 专辑名
    by: str = ""                            # 歌词制作者
    offset_ms: int = 0                      # 时间偏移 (ms)
    provider: str = ""                      # 提供源 (netease, qqmusic, lrclib)
    song_id: str = ""                       # 平台歌曲 ID

    def get_line_index(self, time_ms: int) -> int:
        """二分查找当前时间对应的歌词行索引 (-1 为未开始)"""
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
        """序列化为统一 JSON 字典"""
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
        """导出紧凑结构化 JSON 字符串（默认去除一切无用空白字符）"""
        if indent is not None:
            return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ParsedLyrics:
        """从结构化 JSON 字典恢复 ParsedLyrics"""
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
        """从 JSON 字符串直接极速反序列化 (0ms 零损耗)"""
        if not json_str or not json_str.strip():
            return cls()
        return cls.from_dict(json.loads(json_str))



# ── 正则表达式 ─────────────────────────────────────────────────────────────
_YRC_LINE_RE = re.compile(r"^\[(\d+),(\d+)\](.*)$")
_YRC_WORD_RE = re.compile(r"\((\d+),(\d+),\d+\)([^(]+)")
_QRC_MS_LINE_RE = re.compile(r"^\[(\d+),(\d+)\](.*)$")
_QRC_WORD_RE = re.compile(r"([^\(\)]+)\((\d+),(\d+)\)")
_LRC_TIME_RE = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
_HEADER_RE   = re.compile(r"^\[(ti|ar|al|by|offset):(.*)\]$", re.IGNORECASE)

# 规范章节与角色识别
SECTION_KEYWORD_RE = re.compile(
    r"^(?:Chorus(?:\s*\d+)?|Verse(?:\s*\d+)?|Bridge|Intro|Outro|Hook|Pre-Chorus|副歌|主歌|过渡)$",
    re.IGNORECASE,
)
SECTION_DASH_RE = re.compile(r"^[-—–=~*]{1,4}\s*(.+?)\s*[-—–=~*]{1,4}$")
STANDALONE_BRACKET_RE = re.compile(r"^[【\[(（<]([^】\])）>]{1,32})[】\])）>]\s*[:：]?$")
STANDALONE_COLON_RE = re.compile(r"^([^\s：:【\[\]()]{1,32})\s*[:：]$")
ROLE_INLINE_BRACKET_RE = re.compile(r"^[【\[(（<]([^】\])）>]{1,32})[】\])）>]\s*(.+)$")
SPACER_RE          = re.compile(r"^[\.·•●…\-\s\xa0]+$")
NUM_RE             = re.compile(r"^\d+$")
NUMERIC_TAG_RE     = re.compile(r"^(?:\d+|[IVXLCDMivxlcdm]+)$")


INSTRUMENTAL_KEYWORDS = (
    "纯音乐，请欣赏",
    "纯音乐,请欣赏",
    "纯音乐 请欣赏",
    "请欣赏纯音乐",
    "没有填词的纯音乐",
    "此歌曲为纯音乐",
    "暂无歌词，请欣赏纯音乐",
    "纯音乐",
)


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


def _is_instrumental_text(txt: str) -> bool:
    t = txt.strip()
    return any(k in t for k in INSTRUMENTAL_KEYWORDS)


def _apply_header_tag(parsed: ParsedLyrics, tag: str, val: str) -> None:
    """提取标准头并记入元数据"""
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
    """判断单行是否为歌曲名或歌手名前导行"""
    t = text.strip()
    if not t or SPACER_RE.match(t):
        return True

    t_lower = t.lower()
    title_lower = title.strip().lower()
    artist_lower = artist.strip().lower()

    if title_lower:
        if (
            t_lower == title_lower
            or t_lower.startswith(f"{title_lower} -")
            or t_lower.startswith(f"{title_lower}-")
            or t_lower.endswith(f"- {title_lower}")
            or t_lower.endswith(f"-{title_lower}")
        ):
            return True

    if artist_lower:
        if (
            t_lower == artist_lower
            or t_lower.startswith(f"{artist_lower} -")
            or t_lower.startswith(f"{artist_lower}-")
            or t_lower.endswith(f"- {artist_lower}")
            or t_lower.endswith(f"-{artist_lower}")
        ):
            return True

    if title_lower and artist_lower:
        if title_lower in t_lower and artist_lower in t_lower:
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
    """
    寻找第一句正式歌词的索引：
    定义为：从该句开始，往下连续三句都是没有冒号的句子（且不是纯歌名/歌手信息行或空行）。
    如果歌词总行数不足 3 行，则只要往下所有行均无冒号即可。
    """
    if not lines:
        return 0

    n = len(lines)
    for i in range(n):
        cand_text = lines[i].text.strip()
        if not cand_text or SPACER_RE.match(cand_text):
            continue
        if ":" in cand_text or "：" in cand_text:
            continue
        if _is_title_or_artist(cand_text, title=title, artist=artist):
            continue

        streak_len = min(3, n - i)
        is_streak = True
        for j in range(i, i + streak_len):
            t = lines[j].text.strip()
            if not t or SPACER_RE.match(t):
                is_streak = False
                break
            if ":" in t or "：" in t:
                is_streak = False
                break
            if _is_title_or_artist(t, title=title, artist=artist):
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
    """
    过滤开头的演职名单行：
    冒号丢弃处理只能到第一句歌词（往下连续三句都是没有冒号的句子）。
    第一句歌词之后不再做冒号丢弃处理。
    """
    if not lines:
        return lines

    first_idx = _find_first_lyric_index(lines, title=title, artist=artist)
    if first_idx == 0:
        return lines

    filtered_pre: list[LyricLine] = []
    for idx in range(first_idx):
        line = lines[idx]
        t = line.text.strip()
        if not t or SPACER_RE.match(t):
            continue

        # 歌名/歌手信息行直接丢弃
        if _is_title_or_artist(t, title=title, artist=artist):
            continue

        # 只有单行 "人名：" (末尾为冒号且冒号后无字) 才能作为歌手标签保留
        if STANDALONE_COLON_RE.match(t):
            filtered_pre.append(line)
            continue

        # 段落标记行（如 - 间奏 -，【间奏】）保留
        if SECTION_DASH_RE.match(t) or STANDALONE_BRACKET_RE.match(t):
            filtered_pre.append(line)
            continue

        # 在第一句歌词之前，单行冒号后面有字（如 词：、Piano：、Guitar： 等名单行），全部丢弃
        if ":" in t or "：" in t:
            continue

        filtered_pre.append(line)

    return filtered_pre + lines[first_idx:]



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
    """统一解析原始素材并输出干净结构化的 ParsedLyrics 对象"""
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

    parsed = ParsedLyrics(
        title=title,
        artist=artist,
        provider=provider,
        song_id=song_id,
    )

    if yrc_text:
        parsed = parse_yrc(yrc_text, title=title, artist=artist, parse_sections=parse_sections)
    elif qrc_text:
        parsed = parse_qrc(qrc_text, title=title, artist=artist, parse_sections=parse_sections)
    elif lrc_text:
        parsed = parse_lrc(lrc_text, title=title, artist=artist, parse_sections=parse_sections)

    if title and not parsed.title:
        parsed.title = title
    if artist and not parsed.artist:
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
    """解析 QQ 音乐 QRC 逐字歌词，提取标准头元数据，过滤开头的演职名单行，提取纯净逐字歌词行"""
    if not qrc_text:
        return ParsedLyrics()

    parsed = ParsedLyrics(title=title, artist=artist)
    lines: list[LyricLine] = []
    is_inst = False

    for raw in qrc_text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("[kana:") or raw.startswith("{"):
            continue

        # 提取标准头：正则匹配 ^[(ti|ar|al|by|offset):(.*)]$，直接记入元数据并跳过
        m_head = _HEADER_RE.match(raw)
        if m_head:
            _apply_header_tag(parsed, m_head.group(1), m_head.group(2))
            continue

        m_ms = _QRC_MS_LINE_RE.match(raw)
        if m_ms:
            line_start = int(m_ms.group(1))
            line_dur = int(m_ms.group(2))
            body = m_ms.group(3)
        else:
            # 兼容时间戳行格式 [mm:ss.xx]
            m_lrc = _LRC_TIME_RE.match(raw)
            if not m_lrc:
                continue
            line_start = _lrc_time_to_ms(m_lrc.group(1), m_lrc.group(2), m_lrc.group(3))
            line_dur = 0
            body = raw[m_lrc.end():]

        words_matches = _QRC_WORD_RE.findall(body)
        if not words_matches:
            clean_text = re.sub(r"\(\d+,\d+\)", "", body).strip()
            if clean_text:
                if _is_instrumental_text(clean_text):
                    is_inst = True
                    continue
                lines.append(LyricLine(time_ms=line_start, duration_ms=line_dur, text=clean_text))
            continue

        words: list[LyricWord] = []
        full_chars: list[str] = []
        for w_char, w_start, w_dur in words_matches:
            words.append(LyricWord(time_ms=int(w_start), duration_ms=int(w_dur), text=w_char))
            full_chars.append(w_char)

        line_text = "".join(full_chars).strip()
        if not line_text:
            continue

        if _is_instrumental_text(line_text):
            is_inst = True
            continue

        lines.append(LyricLine(
            time_ms=line_start,
            duration_ms=line_dur,
            text=line_text,
            words=words,
        ))

    lines.sort(key=lambda x: x.time_ms)

    # 头部前导演职员行切片过滤
    lines = _filter_opening_preamble(lines, title=parsed.title or title, artist=parsed.artist or artist)

    parsed.lines = lines
    parsed.has_words = any(bool(l.words) for l in lines)
    parsed.is_instrumental = is_inst
    return _process_sections_and_roles(parsed, parse_sections=parse_sections)


def parse_yrc(
    yrc_text: str,
    title: str = "",
    artist: str = "",
    parse_sections: Optional[bool] = None,
) -> ParsedLyrics:
    """解析网易云 YRC 逐字歌词，提取标准头元数据，过滤开头的演职名单行，提取纯净歌词行"""
    if not yrc_text:
        return ParsedLyrics()

    parsed = ParsedLyrics(title=title, artist=artist)
    lines: list[LyricLine] = []
    is_inst = False

    for raw in yrc_text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("{"):
            continue

        # 提取标准头：正则匹配 ^[(ti|ar|al|by|offset):(.*)]$，直接记入元数据并跳过
        m_head = _HEADER_RE.match(raw)
        if m_head:
            _apply_header_tag(parsed, m_head.group(1), m_head.group(2))
            continue

        m = _YRC_LINE_RE.match(raw)
        if not m:
            continue

        line_start = int(m.group(1))
        line_dur = int(m.group(2))
        body = m.group(3)

        words_matches = _YRC_WORD_RE.findall(body)
        if not words_matches:
            clean_text = re.sub(r"\(\d+,\d+,\d+\)", "", body).strip()
            if clean_text:
                if _is_instrumental_text(clean_text):
                    is_inst = True
                    continue
                lines.append(LyricLine(time_ms=line_start, duration_ms=line_dur, text=clean_text))
            continue

        words: list[LyricWord] = []
        full_chars: list[str] = []
        for w_start, w_dur, w_char in words_matches:
            words.append(LyricWord(time_ms=int(w_start), duration_ms=int(w_dur), text=w_char))
            full_chars.append(w_char)

        line_text = "".join(full_chars).strip()
        if not line_text:
            continue

        if _is_instrumental_text(line_text):
            is_inst = True
            continue

        lines.append(LyricLine(
            time_ms=line_start,
            duration_ms=line_dur,
            text=line_text,
            words=words,
        ))

    lines.sort(key=lambda x: x.time_ms)

    # 头部前导演职员行切片过滤
    lines = _filter_opening_preamble(lines, title=parsed.title or title, artist=parsed.artist or artist)

    parsed.lines = lines
    parsed.has_words = True
    parsed.is_instrumental = is_inst
    return _process_sections_and_roles(parsed, parse_sections=parse_sections)


def parse_lrc(
    lrc_text: str,
    title: str = "",
    artist: str = "",
    parse_sections: Optional[bool] = None,
) -> ParsedLyrics:
    """解析标准 LRC 歌词，提取标准头元数据，过滤开头的演职名单行，提取纯净歌词行"""
    if not lrc_text:
        return ParsedLyrics()

    parsed = ParsedLyrics(title=title, artist=artist)
    raw_list: list[tuple[int, str]] = []
    is_inst = False

    for raw in lrc_text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("{"):
            continue

        # 提取标准头：正则匹配 ^[(ti|ar|al|by|offset):(.*)]$，直接记入元数据并跳过
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

    # 头部前导演职员行切片过滤
    lines = _filter_opening_preamble(lines, title=parsed.title or title, artist=parsed.artist or artist)

    parsed.lines = lines
    parsed.has_words = False
    parsed.is_instrumental = is_inst
    return _process_sections_and_roles(parsed, parse_sections=parse_sections)


def _process_sections_and_roles(parsed: ParsedLyrics, parse_sections: Optional[bool] = None) -> ParsedLyrics:
    """提取规范章节段落与角色名，并保持歌词行与译文行绝对纯净"""
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


        # 2. 独立破折号/装饰线段落标记行 (如 "- 间奏 -", "- 莱塔尼亚 -", "— Verse 1 —")
        dash_match = SECTION_DASH_RE.match(raw_text)
        if dash_match:
            sec_name = dash_match.group(1).strip()
            # 特例：横杠中间纯数字（如 "- 1 -", "— 10 —", "- 01 -", "- IV -"）不解析为段落名，仅清空上一段落
            if NUMERIC_TAG_RE.match(sec_name):
                current_sec = ""
            else:
                current_sec = sec_name
            current_role = ""
            continue

        # 3. 独立括号标记行 (如 "【间奏】", "[Chorus]", "【吉他独奏】" 等)
        # 单独一个括号直接忽略删除，绝不保留为歌词行，也绝不作为歌手角色名（因不会拿方括号单独写名字）
        bracket_match = STANDALONE_BRACKET_RE.match(raw_text)
        if bracket_match:
            inner = bracket_match.group(1).strip()
            if SECTION_KEYWORD_RE.match(inner):
                current_sec = inner
            else:
                # 【间奏】、纯数字、独奏等括号标记不作后续歌词章节，直接清空章节标记
                current_sec = ""
            current_role = ""
            continue

        # 3. 独立冒号角色单行 (如 "茶理理:", "史尔特尔/尹昔眠：")
        # 只有单行 "人名：" 才能作为歌手标签
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

        # 5. 独立纯数字序号或独立章节名 (如单独一行 "10", "间奏", "Chorus")
        if NUMERIC_TAG_RE.match(raw_text):
            current_sec = ""
            current_role = ""
            continue

        if SECTION_KEYWORD_RE.match(raw_text):
            current_sec = raw_text
            current_role = ""
            continue

        # 5. 行内括号角色前缀 (如 "【史尔特尔/尹昔眠】燃烧吧 黄昏余烬的光")
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

                # 同步安全裁切逐字歌词 (words)
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

        # 7. 普通歌词行：继承当前段落与角色名
        line.section = current_sec
        line.role = current_role
        processed.append(line)

    parsed.lines = processed
    return parsed


def _attach_translations(lines: list[LyricLine], tlyric_text: str) -> None:
    """按时间对齐将真实译文合并至对应歌词行 (绝不覆盖或拼接角色名)"""
    if not lines or not tlyric_text:
        return

    trans_entries: list[tuple[int, str]] = []
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
            ms = _lrc_time_to_ms(m_str, s_str, ms_str)
            trans_entries.append((ms, text))

    trans_entries.sort(key=lambda x: x[0])
    if not trans_entries:
        return

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
            trans_text = trans_entries[best_idx][1]
            line.translation = trans_text
            trans_idx = best_idx + 1


def _clean_romaji_line(raw: str) -> str:
    """
    统一规范化罗马音单行文本：
    1. 剥离 QQ 音乐 QRC 动态逐字时间戳: (1547,223)
    2. 剥离网易云 YRC 动态逐字时间戳: (1547,223,0)
    3. 剥离标准分秒时间戳: [mm:ss.xxx] 与毫秒时间戳: [start,dur]
    4. 规范化连字符、单引号及多余空白字符
    """
    s = re.sub(r"\(\d+,\d+(?:,\d+)?\)", "", raw)
    s = _LRC_TIME_RE.sub("", s)
    s = _QRC_MS_LINE_RE.sub(r"\3", s)
    s = re.sub(r"^\[\d+,\d+\]", "", s)
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def _attach_romaji(lines: list[LyricLine], romalrc_text: str) -> None:
    """按时间对齐将规范化后的罗马音合并至对应歌词行 (支持网易云 LRC 与 QQ 音乐 QRC/LRC 格式)"""
    if not lines or not romalrc_text:
        return

    roma_entries: list[tuple[int, str]] = []
    for raw in romalrc_text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("{") or _HEADER_RE.match(raw):
            continue
        if raw.lower().startswith("[kana:") or raw.lower().startswith("[by:"):
            continue

        # 1. 尝试匹配 QRC 格式: [start_ms, dur_ms]body
        m_qrc = _QRC_MS_LINE_RE.match(raw)
        if m_qrc:
            start_ms = int(m_qrc.group(1))
            clean_text = _clean_romaji_line(raw)
            if clean_text and not _is_instrumental_text(clean_text) and not clean_text.startswith("//"):
                roma_entries.append((start_ms, clean_text))
            continue

        # 2. 尝试匹配标准 LRC 格式: [mm:ss.xxx]
        ts = _LRC_TIME_RE.findall(raw)
        if ts:
            clean_text = _clean_romaji_line(raw)
            if not clean_text or _is_instrumental_text(clean_text) or clean_text.startswith("//"):
                continue
            for m_str, s_str, ms_str in ts:
                ms = _lrc_time_to_ms(m_str, s_str, ms_str)
                roma_entries.append((ms, clean_text))

    roma_entries.sort(key=lambda x: x[0])
    if not roma_entries:
        return

    roma_idx = 0
    num_roma = len(roma_entries)

    for line in lines:
        if not line.text.strip():
            continue

        best_idx = -1
        best_diff = float("inf")

        for j in range(roma_idx, num_roma):
            t_ms, t_txt = roma_entries[j]
            diff = abs(line.time_ms - t_ms)
            if diff < best_diff:
                best_diff = diff
                best_idx = j
            elif t_ms > line.time_ms + 3000:
                break

        if best_idx != -1 and best_diff <= 2500:
            line.romaji = roma_entries[best_idx][1]
            roma_idx = best_idx + 1

