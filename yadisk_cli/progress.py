import asyncio
import os
import time


SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"]


def fmt_size(size: float) -> str:
    for unit in SIZE_UNITS:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def fmt_time(seconds: float) -> str:
    if seconds < 0:
        return "--"
    if seconds < 60:
        return f"{int(seconds)}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s}s"


def render_progress_bar(fraction: float, width: int = 20) -> str:
    filled = int(fraction * width)
    return "█" * filled + "░" * (width - filled)


class TransferTracker:
    def __init__(self):
        self.total_bytes = 0
        self.downloaded_bytes = 0
        self.current_file = ""
        self.file_index = 0
        self.total_files = 0
        self.speed = 0.0
        self.eta = 0.0
        self.active = False
        self.cancelled = False
        self._start_time = 0.0
        self._last_check = 0.0
        self._last_bytes = 0
        self._samples: list[float] = []

    def start(self, total_bytes: int = 0, total_files: int = 1):
        self.total_bytes = total_bytes
        self.downloaded_bytes = 0
        self.total_files = total_files
        self.file_index = 0
        self.current_file = ""
        self.speed = 0.0
        self.eta = 0.0
        self.active = True
        self.cancelled = False
        self._start_time = time.monotonic()
        self._last_check = self._start_time
        self._last_bytes = 0
        self._samples.clear()

    def cancel(self):
        self.cancelled = True

    def start_file(self, name: str):
        self.current_file = name
        self.file_index += 1
        self._file_start = time.monotonic()
        self._file_bytes = 0

    def update(self, bytes_downloaded: int):
        self.downloaded_bytes = bytes_downloaded
        now = time.monotonic()
        if now - self._last_check >= 0.4:
            bytes_diff = self.downloaded_bytes - self._last_bytes
            elapsed = now - self._last_check
            speed = bytes_diff / elapsed if elapsed > 0 else 0
            self._samples.append(speed)
            if len(self._samples) > 8:
                self._samples.pop(0)
            self.speed = sum(self._samples) / len(self._samples)
            self._last_check = now
            self._last_bytes = self.downloaded_bytes
            remaining = self.total_bytes - self.downloaded_bytes
            self.eta = remaining / self.speed if self.speed > 0 else 0.0

    def finish(self):
        self.active = False
        self.speed = 0.0
        self.eta = 0.0

    def status_lines(self) -> list[str]:
        lines = []
        if self.total_files > 1:
            lines.append(f"Файл {self.file_index}/{self.total_files}: {self.current_file}")
        else:
            lines.append(f"Файл: {self.current_file}")
        if self.total_bytes > 0:
            pct = self.downloaded_bytes / self.total_bytes * 100 if self.total_bytes else 0
            lines.append(render_progress_bar(self.downloaded_bytes / self.total_bytes))
            lines.append(f"{pct:.0f}%  {fmt_size(self.downloaded_bytes)} / {fmt_size(self.total_bytes)}")
        else:
            lines.append(f"Загружено: {fmt_size(self.downloaded_bytes)}")
        lines.append(f"Скорость: {fmt_size(self.speed)}/s  ETA: {fmt_time(self.eta)}")
        return lines


class DownloadCancelled(asyncio.CancelledError):
    pass


class CountingFile:
    def __init__(self, path: str, tracker: TransferTracker):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        self._file = open(path, "wb")
        self._tracker = tracker
        self._written = 0

    def write(self, data: bytes):
        if self._tracker.cancelled:
            raise DownloadCancelled()
        self._file.write(data)
        self._written += len(data)
        self._tracker.update(self._written)

    def tell(self) -> int:
        return self._written

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._file.seek(offset, whence)

    def close(self):
        self._file.close()
