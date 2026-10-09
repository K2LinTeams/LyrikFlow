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
                    return self._pick_best_song(songs, title, artist)
        except Exception:
            pass
        return None

    def _pick_best_song(self, songs: list[dict], title: str, artist: str) -> Optional[SearchSongItem]:
        import difflib

        def clean_str(s: str) -> str:
            s = s.lower().strip()
            s = re.sub(r"\(.*?\)|\[.*?\]|（.*?）|【.*?】", "", s)
            s = re.sub(r"[^\w\u4e00-\u9fa5]+", "", s)
            return s

        t_clean = clean_str(title)
        t_raw = title.lower().strip()
        a_clean = clean_str(artist)
        a_raw = artist.lower().strip()

        best_song = None
        best_score = -1.0
        best_t_sim = 0.0
        best_a_sim = 0.0

        for s in songs:
            s_name = s.get("name") or s.get("title") or ""
            c_raw = s_name.lower().strip()
            c_clean = clean_str(s_name)

            # 1. 标题相似度
            sim_raw = difflib.SequenceMatcher(None, t_raw, c_raw).ratio()
            sim_clean = difflib.SequenceMatcher(None, t_clean, c_clean).ratio() if (t_clean and c_clean) else 0.0
            t_sim = max(sim_raw, sim_clean)
            if t_clean and c_clean:
                if t_clean == c_clean:
                    t_sim = 1.0
                elif t_clean in c_clean or c_clean in t_clean:
                    t_sim = max(t_sim, 0.85)

            # 2. 歌手相似度
            singers = [sg.get("name", "") for sg in s.get("singer", []) if sg.get("name")]
            cand_artist_str = "/".join(singers)
            ca_clean = clean_str(cand_artist_str)
            ca_raw = cand_artist_str.lower().strip()

            if not a_clean:
                a_sim = 1.0
            else:
                best_cand_a = max(
                    difflib.SequenceMatcher(None, a_raw, ca_raw).ratio(),
                    difflib.SequenceMatcher(None, a_clean, ca_clean).ratio() if (a_clean and ca_clean) else 0.0,
                )
                if ca_clean and (a_clean in ca_clean or ca_clean in a_clean):
                    best_cand_a = max(best_cand_a, 0.85)

                for sg in singers:
                    sg_c = clean_str(sg)
                    sg_r = sg.lower().strip()
                    if not sg_c:
                        continue
                    cur = max(
                        difflib.SequenceMatcher(None, a_raw, sg_r).ratio(),
                        difflib.SequenceMatcher(None, a_clean, sg_c).ratio(),
                    )
                    if a_clean == sg_c:
                        cur = 1.0
                    elif a_clean in sg_c or sg_c in a_clean:
                        cur = max(cur, 0.85)
                    if cur > best_cand_a:
                        best_cand_a = cur
                a_sim = best_cand_a

            score = t_sim * 0.6 + a_sim * 0.4
            if score > best_score:
                best_score = score
                best_song = s
                best_t_sim = t_sim
                best_a_sim = a_sim

        # 相似度阈值检查：若歌名或歌手与检索目标严重不符，则判定为搜错歌，跳过该结果
        if not best_song or best_t_sim < 0.4 or (a_clean and best_a_sim < 0.3):
            return None

        best = best_song
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
