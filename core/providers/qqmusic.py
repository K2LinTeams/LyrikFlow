"""
core/providers/qqmusic.py — QQ 音乐 API 提供源
"""
from __future__ import annotations

import base64
import json
import re
from typing import Optional

import requests

from .base import BaseLyricProvider, RawLyricResult, SearchSongItem
from .qrc_decoder import extract_qrc_payload

TIMEOUT = 6

QQ_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://c.y.qq.com/",
}


QQ_COMM_CONFIGS = [
    {"ct": "26", "cv": "0", "uin": "0"},
    {"ct": "19", "cv": "18030008", "uin": "0"},
    {"ct": "6", "cv": "0", "uin": "0"},
]


class QQMusicLyricProvider(BaseLyricProvider):
    provider_name = "qqmusic"

    def _generate_query_candidates(self, title: str, artist: str = "") -> list[str]:
        variants: list[str] = []
        t_raw = title.strip()
        a_raw = artist.strip()

        invalid_artists = {
            "unknown", "unknown artist", "未知", "未知歌手", "群星",
            "various artists", "佚名", "null", "none", "va",
        }
        if a_raw.lower() in invalid_artists:
            a_raw = ""

        # 1. 原始组合
        primary = f"{t_raw} {a_raw}".strip()
        if primary:
            variants.append(primary)

        # 2. 剥离文件扩展名
        t_no_ext = re.sub(
            r"\.(mp3|flac|wav|m4a|aac|ogg|ape|dsd|dff)$",
            "",
            t_raw,
            flags=re.IGNORECASE,
        ).strip()

        # 3. 检查 ' - ' 分隔符
        t_split = t_no_ext
        a_extracted = a_raw
        if " - " in t_no_ext:
            parts = t_no_ext.split(" - ", 1)
            if not a_extracted:
                a_extracted = parts[0].strip()
            t_split = parts[1].strip()

        # 4. 清洗常见音质与版本干扰标签
        t_clean = re.sub(
            r"\[(FLAC|APE|WAV|MP3|320K|Hi-Res|无损|1080P|720P)\]",
            "",
            t_split,
            flags=re.IGNORECASE,
        )
        t_clean = re.sub(
            r"\((320k|128k|Hi-Res|无损|mp3|flac)\)",
            "",
            t_clean,
            flags=re.IGNORECASE,
        )
        # 清洗 feat / with 合作歌手信息
        t_clean = re.sub(r"(?:feat\.?|with)\s+.*", "", t_clean, flags=re.IGNORECASE).strip()

        cand2 = f"{t_clean} {a_extracted}".strip()
        if cand2 and cand2 not in variants:
            variants.append(cand2)

        # 5. 剥离所有括号内内容
        t_core = re.sub(r"[\(\[（【].*?[\)\]）】]", "", t_clean).strip()
        cand3 = f"{t_core} {a_extracted}".strip()
        if cand3 and cand3 not in variants:
            variants.append(cand3)

        # 6. 仅纯核心歌名兜底
        if t_core and t_core not in variants:
            variants.append(t_core)

        return variants

    def _execute_search_raw(self, query: str, limit: int = 15) -> list[dict]:
        """按优先级轮询客户端配置执行检索"""
        for comm in QQ_COMM_CONFIGS:
            search_body = {
                "comm": comm,
                "req_1": {
                    "method": "DoSearchForQQMusicDesktop",
                    "module": "music.search.SearchCgiService",
                    "param": {
                        "num_per_page": str(limit),
                        "page_num": "1",
                        "query": query,
                        "search_type": 0,
                    },
                },
            }
            try:
                resp = requests.post(
                    "https://u.y.qq.com/cgi-bin/musicu.fcg",
                    json=search_body,
                    headers=QQ_HEADERS,
                    timeout=TIMEOUT,
                )
                if resp.status_code == 200:
                    rj = resp.json()
                    svc = rj.get("req_1") or rj.get("music.search.SearchCgiService") or {}
                    # 若返回非 0 则尝试下一配置
                    if svc.get("code") != 0:
                        continue
                    body = svc.get("data", {}).get("body", {})
                    songs = body.get("song", {}).get("list", [])
                    if songs:
                        return songs
                    # 若单曲列表为空
                    for zd in body.get("zhida", {}).get("list", []):
                        items = zd.get("track_list", {}).get("items", [])
                        if items:
                            return items
            except Exception:
                continue
        return []

    def search_song(self, title: str, artist: str, extra_artists: Optional[list[str]] = None) -> Optional[SearchSongItem]:
        t_strip = title.strip()
        if t_strip.isdigit() and len(t_strip) >= 4:
            direct_item = SearchSongItem(
                song_id=t_strip,
                song_mid="",
                title=t_strip,
                artist=artist,
                album="",
                duration_ms=0,
                pic_url=None,
                sub_name="",
                provider=self.provider_name,
            )
            lyr = self.get_lyrics(direct_item)
            if lyr:
                return direct_item

        candidates = self._generate_query_candidates(title, artist)
        all_songs: list[dict] = []

        for q in candidates:
            raw_songs = self._execute_search_raw(q, limit=20)
            if raw_songs:
                all_songs = raw_songs
                break

        if not all_songs:
            return None

        ranked = self._rank_candidates(all_songs, title, artist, extra_artists=extra_artists)
        if not ranked:
            return None

        # 优先挑选：按相关度从高到低探测，如果最高候选本身没有歌词，则顺位回退到同曲目的其他候选
        for cand_song in ranked[:3]:
            try:
                item = self._parse_song_item(cand_song)
                lyr = self.get_lyrics(item)
                if lyr and (lyr.qrc or lyr.lrc):
                    return item
            except Exception:
                pass
        # 如果前几个候选都没有歌词，返回第一候选
        try:
            return self._parse_song_item(ranked[0])
        except Exception:
            return None

    def _rank_candidates(
        self,
        songs: list[dict],
        title: str,
        artist: str,
        extra_artists: Optional[list[str]] = None,
    ) -> list[dict]:
        import difflib
        import unicodedata

        # 简繁同义转换表
        char_map = str.maketrans({
            '愛': '爱', '葉': '叶', '乐': '乐', '風': '风', '聲': '声',
            '夢': '梦', '聽': '听', '戀': '恋', '時': '时', '會': '会',
            '過': '过', '語': '语', '話': '话', '傳': '传', '說': '说',
            '傷': '伤', '點': '点', '頭': '头', '單': '单', '雙': '双',
            '發': '发', '開': '开', '關': '关', '電': '电', '車': '车',
            '門': '门', '飛': '飞', '機': '机', '長': '长', '問': '问',
            '間': '间', '見': '见', '現': '现', '變': '变', '實': '实',
            '寫': '写', '讀': '读', '難': '难', '歡': '欢',
            '線': '线', '結': '结', '續': '续', '編': '编', '緣': '缘',
            '專': '专', '輯': '辑', '錄': '录', '畫': '画', '視': '视',
        })

        def normalize_str(s: str, strip_brackets: bool = True) -> str:
            s = unicodedata.normalize('NFKC', s)
            s = s.translate(char_map)
            s = s.lower().strip()
            if strip_brackets:
                s = re.sub(r"\(.*?\)|\[.*?\]|（.*?）|【.*?】", "", s)
                s = re.sub(r"\b(?:feat\.?|ft\.?|with)\b.*", "", s, flags=re.IGNORECASE)
            s = re.sub(r"[^\w\u4e00-\u9fa5]+", "", s)
            return s

        def safe_artist_match(t_art: str, c_art: str) -> bool:
            """安全歌手匹配，避免如 'kz' 子串盲目命中 'kztandingan'"""
            if not t_art or not c_art:
                return False
            if t_art == c_art:
                return True
            # 短缩写（<=3 字符，如 kz, iu, dj, mc, an）必须全等匹配
            if len(t_art) <= 3 or len(c_art) <= 3:
                return t_art == c_art
            # 较长字符串允许包含
            return t_art in c_art or c_art in t_art

        # 1. 构建目标歌手池
        target_artists: set[str] = set()
        if artist.strip():
            for p in re.split(r"[/&,、+，]|feat\.?|with", artist.lower()):
                p_norm = normalize_str(p.strip(), strip_brackets=False)
                if p_norm:
                    target_artists.add(p_norm)

        if extra_artists:
            for extra in extra_artists:
                if extra and extra.strip():
                    for p in re.split(r"[/&,、+，]|feat\.?|with", extra.lower()):
                        p_norm = normalize_str(p.strip(), strip_brackets=False)
                        if p_norm:
                            target_artists.add(p_norm)

        # 提取标题括号中的合作者
        for b in re.findall(r"[\(\[（【](.*?)[\)\]）】]", title):
            for p in re.split(r"[xX/&,、+，]|feat\.?|with", b):
                p_norm = normalize_str(p.strip(), strip_brackets=False)
                if len(p_norm) >= 2:
                    target_artists.add(p_norm)

        # 提取标题裸露后缀中的合作者
        m_feat = re.search(r"\b(?:feat\.?|ft\.?|with)\s+(.+)", title, flags=re.IGNORECASE)
        if m_feat:
            for p in re.split(r"[xX/&,、+，]", m_feat.group(1)):
                p_norm = normalize_str(p.strip(), strip_brackets=False)
                if len(p_norm) >= 2:
                    target_artists.add(p_norm)

        t_clean = normalize_str(title, strip_brackets=True)
        t_raw = title.lower().strip()

        scored: list[tuple[float, dict]] = []

        for s in songs:
            s_name = s.get("name") or s.get("title") or ""
            c_clean = normalize_str(s_name, strip_brackets=True)
            c_raw = s_name.lower().strip()

            # 1. 标题相似度
            is_title_contained = (t_clean in c_clean or c_clean in t_clean) if (t_clean and c_clean) else False
            if not t_clean or not c_clean:
                t_sim = difflib.SequenceMatcher(None, t_raw, c_raw).ratio()
            elif t_clean == c_clean:
                t_sim = 1.0
            elif is_title_contained:
                shorter, longer = (len(t_clean), len(c_clean)) if len(t_clean) <= len(c_clean) else (len(c_clean), len(t_clean))
                len_ratio = shorter / longer if longer > 0 else 0
                t_sim = 0.90 if len_ratio >= 0.5 else 0.75
            else:
                t_sim = max(
                    difflib.SequenceMatcher(None, t_raw, c_raw).ratio(),
                    difflib.SequenceMatcher(None, t_clean, c_clean).ratio(),
                )

            # 【硬性门槛】歌名相似度过低且互不包含，绝不可能是目标歌曲（彻底杜绝 Reply 匹配到 Real Gone）
            if t_sim < 0.60 and not is_title_contained:
                continue

            # 2. 歌手相似度
            singers = [sg.get("name", "") for sg in s.get("singer", []) if sg.get("name")]
            cand_artists = [normalize_str(sg, strip_brackets=False) for sg in singers if sg]

            if not target_artists:
                a_sim = 1.0
            else:
                hit_count = 0
                for ta in target_artists:
                    if not ta:
                        continue
                    if any(safe_artist_match(ta, ca) for ca in cand_artists):
                        hit_count += 1

                if hit_count > 0:
                    a_sim = min(1.0, 0.70 + 0.15 * hit_count)
                    a_main = normalize_str(artist, strip_brackets=False)
                    if a_main and any(safe_artist_match(a_main, ca) for ca in cand_artists):
                        a_sim = 1.0
                else:
                    best_cand_ratio = 0.0
                    for ta in target_artists:
                        for ca in cand_artists:
                            r = difflib.SequenceMatcher(None, ta, ca).ratio()
                            if r > best_cand_ratio:
                                best_cand_ratio = r
                    a_sim = best_cand_ratio * 0.40

            # 歌名权重占 70%，歌手权重占 30%
            score = t_sim * 0.70 + a_sim * 0.30
            # 只有歌名非完全一致且歌手相似度很低时才轻微打折
            if target_artists and a_sim < 0.30 and t_sim < 0.90:
                score *= 0.60

            scored.append((score, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored]

    def _pick_best_song(
        self,
        songs: list[dict],
        title: str,
        artist: str,
        extra_artists: Optional[list[str]] = None,
    ) -> Optional[SearchSongItem]:
        ranked = self._rank_candidates(songs, title, artist, extra_artists=extra_artists)
        return self._parse_song_item(ranked[0]) if ranked else None

    def _parse_song_item(self, best: dict) -> SearchSongItem:
        s_id = str(best.get("id") or "")
        s_mid = str(best.get("mid") or best.get("songmid") or "")
        s_name = best.get("name") or best.get("title") or ""
        singers = [sg.get("name", "") for sg in best.get("singer", []) if sg.get("name")]
        s_artist = "/".join(singers)

        album_obj = best.get("album") or {}
        s_album = album_obj.get("name") or album_obj.get("title") or ""
        album_mid = album_obj.get("mid") or ""

        # QQ 音乐 封面
        pic_url = None
        if album_mid:
            pic_url = f"https://y.gtimg.cn/music/photo_new/T002R500x500M000{album_mid}.jpg"

        # 检查副标题
        sub_name = best.get("subtitle") or ""
        if not sub_name:
            t_full = best.get("title") or ""
            t_name = best.get("name") or ""
            # 提取副标题或括号内的译名作为 sub_name
            if t_full and t_name and t_full != t_name and t_full.startswith(t_name):
                m = re.search(r"\((.*?)\)|（(.*?)）", t_full[len(t_name):])
                if m:
                    sub_name = (m.group(1) or m.group(2) or "").strip()

        return SearchSongItem(
            song_id=s_id or s_mid,
            song_mid=s_mid,
            title=s_name,
            artist=s_artist,
            album=s_album,
            duration_ms=int(best.get("interval") or 0) * 1000,
            pic_url=pic_url,
            sub_name=sub_name,
            provider=self.provider_name,
        )

    def search_songs(self, title: str, artist: str = "", limit: int = 15) -> list[SearchSongItem]:
        candidates = self._generate_query_candidates(title, artist)
        all_songs: list[dict] = []

        for q in candidates:
            raw_songs = self._execute_search_raw(q, limit=limit)
            if raw_songs:
                all_songs = raw_songs
                break

        results: list[SearchSongItem] = []
        for s in all_songs:
            try:
                item = self._parse_song_item(s)
                if item.song_id or item.song_mid:
                    results.append(item)
            except Exception:
                continue

        if not results:
            single = self.search_song(title, artist)
            if single:
                results.append(single)
        return results

    def get_lyrics(self, song_item: SearchSongItem) -> Optional[RawLyricResult]:
        numeric_id = song_item.song_id if song_item.song_id.isdigit() else ""
        song_mid = song_item.song_mid or song_item.song_id
        if not numeric_id and not song_mid:
            return None

        qrc_text = ""
        trans_text = ""
        roma_text = ""
        lrc_text = ""

        # 1. 尝试从 lyric_download.fcg 获取并解密 QRC 逐字歌词与译文、罗马音
        if numeric_id:
            try:
                download_data = {
                    "version": "15",
                    "miniversion": "82",
                    "lrctype": "4",
                    "musicid": numeric_id,
                }
                resp = requests.post(
                    "https://c.y.qq.com/qqmusic/fcgi-bin/lyric_download.fcg",
                    data=download_data,
                    headers=QQ_HEADERS,
                    timeout=TIMEOUT,
                )
                if resp.status_code == 200:
                    resp.encoding = "utf-8"
                    xml_str = resp.text.replace("<!--", "").replace("-->", "")
                    m_orig = re.search(r"<content[^>]*><!\[CDATA\[(.*?)\]\]></content>", xml_str, re.DOTALL)
                    if m_orig:
                        qrc_text = extract_qrc_payload(m_orig.group(1))

                    m_trans = re.search(r"<contentts[^>]*><!\[CDATA\[(.*?)\]\]></contentts>", xml_str, re.DOTALL)
                    if m_trans:
                        trans_text = extract_qrc_payload(m_trans.group(1))

                    m_roma = re.search(r"<contentroma[^>]*><!\[CDATA\[(.*?)\]\]></contentroma>", xml_str, re.DOTALL)
                    if m_roma:
                        roma_text = extract_qrc_payload(m_roma.group(1))
            except Exception:
                pass

        # 2. 尝试从 fcg_query_lyric_new.fcg 获取标准 LRC 兜底与译文
        if song_mid and (not qrc_text or not trans_text):
            try:
                params = {
                    "songmid": song_mid,
                    "format": "json",
                    "inCharset": "utf8",
                    "outCharset": "utf8",
                    "nobase64": 0,
                }
                resp = requests.get(
                    "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg",
                    params=params,
                    headers=QQ_HEADERS,
                    timeout=TIMEOUT,
                )
                if resp.status_code == 200:
                    try:
                        rj = resp.json()
                    except Exception:
                        m = re.search(r"^\w+\s*\((.*)\)\s*$", resp.text.strip(), re.DOTALL)
                        rj = json.loads(m.group(1)) if m else {}
                    b64_lrc = rj.get("lyric", "")
                    b64_trans = rj.get("trans", "")
                    if b64_lrc:
                        try:
                            lrc_text = base64.b64decode(b64_lrc).decode("utf-8", errors="ignore").strip()
                        except Exception:
                            pass
                    if b64_trans and not trans_text:
                        try:
                            trans_text = base64.b64decode(b64_trans).decode("utf-8", errors="ignore").strip()
                        except Exception:
                            pass
            except Exception:
                pass

        if qrc_text or lrc_text:
            return RawLyricResult(
                provider=self.provider_name,
                song_id=song_item.song_id,
                title=song_item.title,
                artist=song_item.artist,
                sub_name=song_item.sub_name,
                qrc=qrc_text,
                lrc=lrc_text,
                tlyric=trans_text,
                romalrc=roma_text,
                pic_url=song_item.pic_url,
                is_instrumental=False,
            )

        return None

    def download_cover(self, pic_url: str) -> Optional[bytes]:
        if not pic_url:
            return None
        try:
            resp = requests.get(pic_url, headers=QQ_HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content
        except Exception:
            pass
        return None
