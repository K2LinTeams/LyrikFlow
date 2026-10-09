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


class QQMusicLyricProvider(BaseLyricProvider):
    provider_name = "qqmusic"

    def search_song(self, title: str, artist: str) -> Optional[SearchSongItem]:
        keyword = f"{title} {artist}".strip()
        search_body = {
            "comm": {
                "ct": "19",
                "cv": "1859",
                "uin": "0",
            },
            "req_1": {
                "method": "DoSearchForQQMusicDesktop",
                "module": "music.search.SearchCgiService",
                "param": {
                    "num_per_page": "20",
                    "page_num": "1",
                    "query": keyword,
                    "search_type": 0,
                },
            }
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
                songs = svc.get("data", {}).get("body", {}).get("song", {}).get("list", [])
                if songs:
                    ranked = self._rank_candidates(songs, title, artist)
                    # 优先挑选：按相关度从高到低探测，如果最高候选本身没有歌词，则顺位回退到同曲目的其他候选
                    for cand_song in ranked[:3]:
                        item = self._parse_song_item(cand_song)
                        lyr = self.get_lyrics(item)
                        if lyr and (lyr.qrc or lyr.lrc):
                            return item
                    # 如果前几个候选都没有歌词，返回第一候选
                    return self._parse_song_item(ranked[0])
        except Exception:
            pass
        return None

    def _rank_candidates(self, songs: list[dict], title: str, artist: str) -> list[dict]:
        import difflib
        import unicodedata

        # 常用中日/简繁同义转换表（音乐标题高频字归一化）
        char_map = str.maketrans({
            '愛': '爱', '葉': '叶', '樂': '乐', '風': '风', '聲': '声',
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
            s = re.sub(r"[^\w\u4e00-\u9fa5]+", "", s)
            return s

        # 1. 构建目标歌手池（主歌手 + 标题括号内合作歌手）
        target_artists: set[str] = set()
        if artist.strip():
            for p in re.split(r"[/&,、+，]|feat\.?|with", artist.lower()):
                p_norm = normalize_str(p.strip(), strip_brackets=False)
                if p_norm:
                    target_artists.add(p_norm)

        # 提取标题括号中的合作者（如 (鹿乃xLONxHanser)）
        for b in re.findall(r"[\(\[（【](.*?)[\)\]）】]", title):
            for p in re.split(r"[xX/&,、+，]|feat\.?|with", b):
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
            if not t_clean or not c_clean:
                t_sim = difflib.SequenceMatcher(None, t_raw, c_raw).ratio()
            elif t_clean == c_clean:
                t_sim = 1.0
            elif t_clean in c_clean or c_clean in t_clean:
                t_sim = 0.88
            else:
                t_sim = max(
                    difflib.SequenceMatcher(None, t_raw, c_raw).ratio(),
                    difflib.SequenceMatcher(None, t_clean, c_clean).ratio(),
                )

            # 2. 歌手相似度
            singers = [sg.get("name", "") for sg in s.get("singer", []) if sg.get("name")]
            cand_artists = [normalize_str(sg, strip_brackets=False) for sg in singers if sg]
            cand_full = "/".join(cand_artists)

            if not target_artists:
                a_sim = 1.0
            else:
                hit_count = 0
                for ta in target_artists:
                    if not ta:
                        continue
                    if any(ta == ca or ta in ca or ca in ta for ca in cand_artists) or ta in cand_full:
                        hit_count += 1

                if hit_count > 0:
                    a_sim = min(1.0, 0.70 + 0.15 * hit_count)
                    # 主歌手精准命中直接拉满
                    a_main = normalize_str(artist, strip_brackets=False)
                    if a_main and any(a_main == ca for ca in cand_artists):
                        a_sim = 1.0
                else:
                    # 歌手未直接命中，计算模糊比例并给予大幅折扣
                    best_cand_ratio = 0.0
                    for ta in target_artists:
                        for ca in cand_artists:
                            r = difflib.SequenceMatcher(None, ta, ca).ratio()
                            if r > best_cand_ratio:
                                best_cand_ratio = r
                    a_sim = best_cand_ratio * 0.45

            score = t_sim * 0.55 + a_sim * 0.45
            if target_artists and a_sim < 0.35:
                score *= 0.45

            scored.append((score, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored]

    def _pick_best_song(self, songs: list[dict], title: str, artist: str) -> Optional[SearchSongItem]:
        ranked = self._rank_candidates(songs, title, artist)
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

        # QQ 音乐 500x500 高清封面 URL 结构
        pic_url = None
        if album_mid:
            pic_url = f"https://y.gtimg.cn/music/photo_new/T002R500x500M000{album_mid}.jpg"

        # 检查副标题（包括原版 subtitle，以及在 name/title 携带的中文译名）
        sub_name = best.get("subtitle") or ""
        if not sub_name:
            t_full = best.get("title") or ""
            t_name = best.get("name") or ""
            # 如果 title 形如 "アイドル (偶像)" 而 name 是 "アイドル"，提取括号内的译名作为 sub_name
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
            duration_ms=int(best.get("interval", 0)) * 1000,
            pic_url=pic_url,
            sub_name=sub_name,
            provider=self.provider_name,
        )

    def search_songs(self, title: str, artist: str = "", limit: int = 15) -> list[SearchSongItem]:
        keyword = f"{title} {artist}".strip()
        search_body = {
            "comm": {
                "ct": "19",
                "cv": "1859",
                "uin": "0",
            },
            "req_1": {
                "method": "DoSearchForQQMusicDesktop",
                "module": "music.search.SearchCgiService",
                "param": {
                    "num_per_page": str(limit),
                    "page_num": "1",
                    "query": keyword,
                    "search_type": 0,
                },
            }
        }
        results: list[SearchSongItem] = []
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
                songs = svc.get("data", {}).get("body", {}).get("song", {}).get("list", [])
                for s in songs:
                    item = self._parse_song_item(s)
                    if item.song_id or item.song_mid:
                        results.append(item)
        except Exception:
            pass

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
        if song_mid:
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
                    rj = resp.json()
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
