"""
db_cache.py — 本地 SQLite 缓存模块
持久化缓存：
  1. 歌曲元信息（歌名、歌手、网易云 song_id）
  2. 歌词数据（YRC 逐字歌词、LRC 原文歌词、TLYRIC 翻译歌词）
  3. 专辑封面（BLOB 二进制）
减少重复网络请求与 API 查询延迟。
"""
from __future__ import annotations

import os
import sqlite3
import threading
from typing import Optional

# 数据库存储在 data/lyrikflow_cache.db（位于项目根目录下）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "lyrikflow_cache.db")

_lock = threading.Lock()


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
                    song_id TEXT,
                    yrc TEXT,
                    lrc TEXT,
                    tlyric TEXT,
                    cover_data BLOB,
                    sub_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_song_track_key 
                ON song_cache(track_key);
            """)
            try:
                conn.execute("ALTER TABLE song_cache ADD COLUMN sub_name TEXT;")
            except Exception:
                pass
            conn.commit()
        finally:
            conn.close()


def make_track_key(title: str, artist: str) -> str:
    """归一化歌曲唯一检索键"""
    return f"{title.lower().strip()}|||{artist.lower().strip()}"


def get_song_cache(title: str, artist: str) -> Optional[dict]:
    """
    从 SQLite 查询已缓存的歌曲数据与封面。
    返回 dict: {"yrc": str, "lrc": str, "tlyric": str, "hd_cover": bytes|None, "song_id": str, "sub_name": str}
    """
    key = make_track_key(title, artist)
    with _lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT yrc, lrc, tlyric, cover_data, song_id, sub_name 
                FROM song_cache 
                WHERE track_key = ?
            """, (key,))
            row = cursor.fetchone()
            if row:
                yrc, lrc, tlyric, cover_data, song_id, sub_name = row
                # 更新最后访问时间
                cursor.execute("""
                    UPDATE song_cache 
                    SET last_accessed = CURRENT_TIMESTAMP 
                    WHERE track_key = ?
                """, (key,))
                conn.commit()
                return {
                    "yrc": yrc or "",
                    "lrc": lrc or "",
                    "tlyric": tlyric or "",
                    "hd_cover": bytes(cover_data) if cover_data else None,
                    "song_id": song_id or "",
                    "sub_name": sub_name or "",
                }
        except Exception as e:
            print(f"[db_cache] 查询缓存异常: {e}")
        finally:
            conn.close()
    return None


def save_song_cache(
    title: str,
    artist: str,
    yrc: str = "",
    lrc: str = "",
    tlyric: str = "",
    hd_cover: Optional[bytes] = None,
    song_id: Optional[str] = None,
    sub_name: Optional[str] = None,
) -> None:
    """持久化保存或更新歌曲数据与封面"""
    key = make_track_key(title, artist)
    with _lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            # 若已有记录但新数据缺少某字段，保留已有封面/歌词/副名称
            cursor.execute("""
                SELECT yrc, lrc, tlyric, cover_data, song_id, sub_name 
                FROM song_cache 
                WHERE track_key = ?
            """, (key,))
            existing = cursor.fetchone()

            final_yrc = yrc if yrc else (existing[0] if existing else "")
            final_lrc = lrc if lrc else (existing[1] if existing else "")
            final_tlyric = tlyric if tlyric else (existing[2] if existing else "")
            final_cover = hd_cover if (hd_cover and len(hd_cover) > 500) else (existing[3] if existing else None)
            final_song_id = song_id if song_id else (existing[4] if existing else "")
            final_sub_name = sub_name if sub_name is not None else (existing[5] if (existing and len(existing) > 5 and existing[5]) else "")

            cursor.execute("""
                INSERT INTO song_cache (
                    track_key, title, artist, song_id, yrc, lrc, tlyric, cover_data, sub_name, last_accessed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(track_key) DO UPDATE SET
                    yrc = excluded.yrc,
                    lrc = excluded.lrc,
                    tlyric = excluded.tlyric,
                    cover_data = excluded.cover_data,
                    song_id = excluded.song_id,
                    sub_name = excluded.sub_name,
                    last_accessed = CURRENT_TIMESTAMP;
            """, (
                key, title.strip(), artist.strip(), str(final_song_id),
                final_yrc, final_lrc, final_tlyric, final_cover, str(final_sub_name)
            ))
            conn.commit()
        except Exception as e:
            print(f"[db_cache] 保存缓存异常: {e}")
        finally:
            conn.close()


# 模块载入时自动建表
init_db()
