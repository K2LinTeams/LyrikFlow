"""
gui/settings/workers.py — 歌词版本搜索与应用的异步工作线程
"""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from core import lyrics_fetcher
from core.providers.base import SearchSongItem


class SearchVersionWorker(QThread):
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, keyword: str, provider_filter: str = "all", parent=None):
        super().__init__(parent)
        self.keyword = keyword
        self.provider_filter = provider_filter

    def run(self):
        try:
            results = lyrics_fetcher.search_all_sources(self.keyword, "", provider_filter=self.provider_filter, limit=12)
            self.results_ready.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ApplyVersionWorker(QThread):
    apply_finished = pyqtSignal(bool, str, object)

    def __init__(self, title: str, artist: str, item: SearchSongItem, parent=None):
        super().__init__(parent)
        self.title = title
        self.artist = artist
        self.item = item

    def run(self):
        try:
            parsed, cover, sub_name = lyrics_fetcher.fetch_and_apply_override(self.title, self.artist, self.item)
            if parsed:
                self.apply_finished.emit(True, "应用成功", parsed)
            else:
                self.apply_finished.emit(False, "未能获取到该版本的歌词", None)
        except Exception as e:
            self.apply_finished.emit(False, str(e), None)
