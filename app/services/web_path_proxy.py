from pathlib import Path

class DynamicPath:
    def __init__(self, key: str):
        self.key = key
    def _resolve(self) -> Path:
        import web_helpers
        return getattr(web_helpers, self.key)
    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)
    def __truediv__(self, other) -> Path:
        return self._resolve() / other
    def __rtruediv__(self, other) -> Path:
        return other / self._resolve()
    def __str__(self) -> str:
        return str(self._resolve())
    def __fspath__(self) -> str:
        return str(self._resolve())

ROOT = DynamicPath("ROOT")
OUTPUT = DynamicPath("OUTPUT")
INPUT = DynamicPath("INPUT")
UPLOADS = DynamicPath("UPLOADS")
