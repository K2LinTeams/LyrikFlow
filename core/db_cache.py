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

try:
    from core import settings
    BASE_DIR = settings.BASE_DIR
    DATA_DIR = settings.DATA_DIR
except Exception:
    import sys
    BASE_DIR = (
        os.path.dirname(os.path.abspath(sys.executable))
        if (getattr(sys, "frozen", False) or "__compiled__" in globals())
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    DATA_DIR = os.path.join(BASE_DIR, "data")

DB_PATH = os.path.join(DATA_DIR, "lyrikflow_cache.db")
MAX_DB_CACHE_ENTRIES = 2000  # 本地 SQLite 歌词缓存最大歌曲数

_lock = threading.Lock()


def _prune_db_cache(cursor: sqlite3.Cursor) -> None:
    """保持 SQLite 歌词缓存条数上限，按最近访问时间 LRU 淘汰最旧数据"""
    try:
        cursor.execute("SELECT COUNT(*) FROM song_cache;")
        row = cursor.fetchone()
        if row and row[0] > MAX_DB_CACHE_ENTRIES:
            excess = row[0] - MAX_DB_CACHE_ENTRIES
            cursor.execute("""
                DELETE FROM song_cache 
                WHERE id IN (
                    SELECT id FROM song_cache 
                    ORDER BY last_accessed ASC 
                    LIMIT ?
                );
            """, (excess,))
    except Exception as e:
        print(f"[db_cache] 自动清理数据库缓存异常: {e}")


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
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_song_last_accessed 
                ON song_cache(last_accessed);
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS song_offsets (
                    track_key TEXT PRIMARY KEY,
                    song_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    offset_ms INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_song_offsets_key 
                ON song_offsets(track_key);
            """)
            conn.commit()
        finally:
            conn.close()


def _normalize_key_str(s: str) -> str:
    return s.replace("’", "'").replace("‘", "'").replace("`", "'").replace("“", '"').replace("”", '"').lower().strip()


def make_track_key(title: str, artist: str) -> str:
    """归一化歌曲唯一检索键（统一弯引号等符号）"""
    return f"{_normalize_key_str(title)}|||{_normalize_key_str(artist)}"


def get_song_cache(title: str, artist: str) -> Optional[dict[str, Any]]:
    """从 SQLite 查询已缓存的结构化歌词与封面"""
    key = make_track_key(title, artist)
    raw_key = f"{title.lower().strip()}|||{artist.lower().strip()}"
    curly_key = raw_key.replace("'", "’")

    with _lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lyrics_json, cover_data, sub_name, provider, song_id 
                FROM song_cache 
                WHERE track_key = ? OR track_key = ? OR track_key = ?
            """, (key, raw_key, curly_key))
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
            _prune_db_cache(cursor)
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


def delete_song_cache(title: str, artist: str = "") -> bool:
    """删除 SQLite 缓存中指定歌曲的记录"""
    if not title:
        return False
    key = make_track_key(title, artist)
    with _lock:
        conn = _get_connection()
        try:
            conn.execute("DELETE FROM song_cache WHERE track_key = ?", (key,))
            conn.commit()
            return True
        except Exception as e:
            print(f"[db_cache] 删除歌曲缓存异常: {e}")
            return False
        finally:
            conn.close()


def get_song_offset(title: str, artist: str = "") -> Optional[int]:
    """从 SQLite 数据库获取指定歌曲的独立偏移量（毫秒），未单独配置时返回 None"""
    if not title:
        return None
    key = make_track_key(title, artist)
    raw_key = f"{title.lower().strip()}|||{artist.lower().strip()}"
    curly_key = raw_key.replace("'", "’")
    std_key = f"{title.strip()} - {artist.strip()}" if artist.strip() else title.strip()

    with _lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT offset_ms FROM song_offsets 
                WHERE track_key = ? OR track_key = ? OR track_key = ? OR song_key = ?
            """, (key, raw_key, curly_key, std_key))
            row = cursor.fetchone()
            if row is not None:
                return int(row[0])

            # 兼容：若 song_offsets 表未命中，尝试从 song_cache 的 ParsedLyrics 中读取
            cursor.execute("""
                SELECT lyrics_json FROM song_cache
                WHERE track_key = ? OR track_key = ? OR track_key = ?
            """, (key, raw_key, curly_key))
            row_c = cursor.fetchone()
            if row_c and row_c[0]:
                lj = _decompress_lyrics(row_c[0])
                if lj:
                    p = ParsedLyrics.from_json(lj)
                    if p and p.offset_ms != 0:
                        return int(p.offset_ms)
        except Exception as e:
            print(f"[db_cache] 查询歌曲偏移异常: {e}")
        finally:
            conn.close()
    return None


def get_all_song_offsets() -> dict[str, int]:
    """从 SQLite 数据库获取所有单独配置的歌曲独立偏移量字典 {song_key: offset_ms}"""
    with _lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT song_key, offset_ms FROM song_offsets ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            return {str(r[0]): int(r[1]) for r in rows if str(r[0]).strip()}
        except Exception as e:
            print(f"[db_cache] 查询所有歌曲偏移异常: {e}")
            return {}
        finally:
            conn.close()


def set_song_offset(title: str, artist: str = "", offset_ms: int = 0) -> None:
    """持久化保存单首歌曲的独立偏移量至 SQLite 数据库"""
    if not title:
        return
    key = make_track_key(title, artist)
    t = title.strip()
    a = artist.strip()
    song_key = f"{t} - {a}" if a else t
    with _lock:
        conn = _get_connection()
        try:
            conn.execute("""
                INSERT INTO song_offsets (track_key, song_key, title, artist, offset_ms, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(track_key) DO UPDATE SET
                    song_key = excluded.song_key,
                    title = excluded.title,
                    artist = excluded.artist,
                    offset_ms = excluded.offset_ms,
                    updated_at = CURRENT_TIMESTAMP;
            """, (key, song_key, t, a, int(offset_ms)))
            conn.commit()
        except Exception as e:
            print(f"[db_cache] 设置歌曲偏移异常: {e}")
        finally:
            conn.close()

    # 同步更新 song_cache 中的 ParsedLyrics 歌词结构
    update_song_offset(title, artist, int(offset_ms))


def remove_song_offset(title: str, artist: str = "") -> None:
    """从 SQLite 数据库移除单首歌曲的独立偏移量配置"""
    if not title:
        return
    key = make_track_key(title, artist)
    raw_key = f"{title.lower().strip()}|||{artist.lower().strip()}"
    curly_key = raw_key.replace("'", "’")
    std_key = f"{title.strip()} - {artist.strip()}" if artist.strip() else title.strip()
    with _lock:
        conn = _get_connection()
        try:
            conn.execute("""
                DELETE FROM song_offsets 
                WHERE track_key = ? OR track_key = ? OR track_key = ? OR song_key = ?
            """, (key, raw_key, curly_key, std_key))
            conn.commit()
        except Exception as e:
            print(f"[db_cache] 移除歌曲偏移异常: {e}")
        finally:
            conn.close()

    # 重置 song_cache 中的 ParsedLyrics 偏移为 0
    update_song_offset(title, artist, 0)


def set_all_song_offsets(offsets: dict[str, int]) -> None:
    """全量更新 SQLite 数据库中的歌曲独立偏移量配置"""
    with _lock:
        conn = _get_connection()
        try:
            conn.execute("DELETE FROM song_offsets")
            for k, v in offsets.items():
                song_key = str(k).strip()
                if not song_key:
                    continue
                try:
                    offset_val = int(v)
                except (ValueError, TypeError):
                    continue
                if "|||" in song_key:
                    parts = song_key.split("|||", 1)
                    title, artist = parts[0].strip(), parts[1].strip()
                elif " - " in song_key:
                    parts = song_key.split(" - ", 1)
                    title, artist = parts[0].strip(), parts[1].strip()
                else:
                    title, artist = song_key, ""
                track_key = make_track_key(title, artist)
                std_key = f"{title} - {artist}" if artist else title
                conn.execute("""
                    INSERT INTO song_offsets (track_key, song_key, title, artist, offset_ms, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(track_key) DO UPDATE SET
                        song_key = excluded.song_key,
                        title = excluded.title,
                        artist = excluded.artist,
                        offset_ms = excluded.offset_ms,
                        updated_at = CURRENT_TIMESTAMP;
                """, (track_key, std_key, title, artist, offset_val))
            conn.commit()
        except Exception as e:
            print(f"[db_cache] 全量更新歌曲偏移异常: {e}")
        finally:
            conn.close()

    # 同步更新已缓存歌词的 offset_ms
    for k, v in offsets.items():
        song_key = str(k).strip()
        if not song_key:
            continue
        try:
            offset_val = int(v)
        except (ValueError, TypeError):
            continue
        if "|||" in song_key:
            parts = song_key.split("|||", 1)
            t, a = parts[0].strip(), parts[1].strip()
        elif " - " in song_key:
            parts = song_key.split(" - ", 1)
            t, a = parts[0].strip(), parts[1].strip()
        else:
            t, a = song_key, ""
        update_song_offset(t, a, offset_val)


init_db()
