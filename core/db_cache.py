"""
core/db_cache.py — 本地 SQLite 结构化缓存模块
"""
from __future__ import annotations

import os
import sqlite3
import threading
import zlib
from typing import Any, Optional

try:
    from core.lyrics_parser import ParsedLyrics
except ImportError:
    from lyrics_parser import ParsedLyrics

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "lyrikflow_cache.db")

_lock = threading.Lock()


def _compress_lyrics(json_str: str) -> bytes:
    """使用 zlib 极速压缩 JSON 歌词字符串 (级别 6)"""
    if not json_str:
        return b""
    return zlib.compress(json_str.encode("utf-8"), level=6)


def _decompress_lyrics(raw_data: Any) -> str:
    """使用 zlib 解压二进制歌词"""
    if not raw_data:
        return ""
    if isinstance(raw_data, bytes):
        try:
            return zlib.decompress(raw_data).decode("utf-8")
        except Exception:
            return ""
    return str(raw_data)


def _get_connection() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db() -> None:
    """初始化数据库表与索引"""
    with _lock:
        conn = _get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS song_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_key TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    provider TEXT DEFAULT '',
                    song_id TEXT DEFAULT '',
                    lyrics_json BLOB DEFAULT '',
                    cover_data BLOB,
                    sub_name TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_song_track_key 
                ON song_cache(track_key);
            """)
            conn.commit()
        finally:
            conn.close()


def make_track_key(title: str, artist: str) -> str:
    """归一化歌曲唯一检索键"""
    return f"{title.lower().strip()}|||{artist.lower().strip()}"


def get_song_cache(title: str, artist: str) -> Optional[dict[str, Any]]:
    """从 SQLite 查询已缓存的结构化歌词与封面"""
    key = make_track_key(title, artist)
    with _lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lyrics_json, cover_data, sub_name, provider, song_id 
                FROM song_cache 
                WHERE track_key = ?
            """, (key,))
            row = cursor.fetchone()
            if not row:
                return None

            raw_lyrics, cover_data, sub_name, provider, song_id = row
            if not raw_lyrics:
                return None

            lyrics_json = _decompress_lyrics(raw_lyrics)
            if not lyrics_json:
                return None

            parsed = ParsedLyrics.from_json(lyrics_json)
            if not parsed or (not parsed.lines and not parsed.is_instrumental):
                return None

            cursor.execute("""
                UPDATE song_cache 
                SET last_accessed = CURRENT_TIMESTAMP 
                WHERE track_key = ?
            """, (key,))
            conn.commit()

            return {
                "parsed": parsed,
                "lyrics_json": lyrics_json,
                "hd_cover": bytes(cover_data) if cover_data else None,
                "sub_name": sub_name or "",
                "provider": provider or parsed.provider,
                "song_id": song_id or parsed.song_id,
            }
        except Exception as e:
            print(f"[db_cache] 查询缓存异常: {e}")
        finally:
            conn.close()
    return None


def save_song_cache(
    title: str,
    artist: str,
    parsed: ParsedLyrics,
    hd_cover: Optional[bytes] = None,
    sub_name: Optional[str] = None,
    provider: Optional[str] = None,
    song_id: Optional[str] = None,
) -> None:
    """持久化保存结构化 JSON 歌词数据（zlib 压缩）与专辑封面"""
    if parsed is None or (not parsed.lines and not parsed.is_instrumental):
        return

    key = make_track_key(title, artist)
    compressed_bytes = _compress_lyrics(parsed.to_json())
    provider_str = provider or parsed.provider or ""
    song_id_str = str(song_id or parsed.song_id or "")
    sub_name_str = str(sub_name or "")
    cover_bytes = hd_cover

    with _lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT cover_data, sub_name, song_id, provider FROM song_cache WHERE track_key = ?", (key,))
            existing = cursor.fetchone()

            final_cover = cover_bytes if (cover_bytes and len(cover_bytes) > 500) else (existing[0] if existing else None)
            final_sub_name = sub_name_str if sub_name_str else (existing[1] if (existing and existing[1]) else "")
            final_song_id = song_id_str if song_id_str else (existing[2] if (existing and existing[2]) else "")
            final_provider = provider_str if provider_str else (existing[3] if (existing and existing[3]) else "")

            cursor.execute("""
                INSERT INTO song_cache (
                    track_key, title, artist, provider, song_id, lyrics_json, cover_data, sub_name, last_accessed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(track_key) DO UPDATE SET
                    provider = excluded.provider,
                    song_id = excluded.song_id,
                    lyrics_json = excluded.lyrics_json,
                    cover_data = excluded.cover_data,
                    sub_name = excluded.sub_name,
                    last_accessed = CURRENT_TIMESTAMP;
            """, (
                key, title.strip(), artist.strip(), final_provider, final_song_id,
                compressed_bytes, final_cover, final_sub_name
            ))
            conn.commit()
        except Exception as e:
            print(f"[db_cache] 保存缓存异常: {e}")
        finally:
            conn.close()


def update_song_offset(title: str, artist: str = "", offset_ms: int = 0) -> bool:
    """更新 SQLite 缓存中指定歌曲的歌词偏移量"""
    if not title:
        return False
    key = make_track_key(title, artist)
    with _lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT lyrics_json FROM song_cache WHERE track_key = ?", (key,))
            row = cursor.fetchone()
            if not row or not row[0]:
                return False
            lyrics_json = _decompress_lyrics(row[0])
            if not lyrics_json:
                return False
            parsed = ParsedLyrics.from_json(lyrics_json)
            if not parsed:
                return False
            parsed.offset_ms = int(offset_ms)
            compressed_bytes = _compress_lyrics(parsed.to_json())
            cursor.execute(
                "UPDATE song_cache SET lyrics_json = ?, last_accessed = CURRENT_TIMESTAMP WHERE track_key = ?",
                (compressed_bytes, key),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[db_cache] 更新歌曲偏移量异常: {e}")
            return False
        finally:
            conn.close()


init_db()
