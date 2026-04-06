"""
Main Entry Point.

분석 모듈 통합 런처.
"""
import sys
from pathlib import Path

from loguru import logger
from core.settings import load_settings

# ── Settings ──
_settings = load_settings()
_app = _settings.get("app", {})
_display_name = _app.get("display_name", "Integrated Analyzer")
_build_name = _app.get("build_name", "IntegratedAnalyzer")

# ── Logging ──
LOG_DIR = Path.home() / "AppData" / "Local" / _build_name / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger.remove()
if sys.stderr is not None:
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:HH:mm:ss} | {level:<7} | {message}",
    )
logger.add(
    LOG_DIR / "launcher_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG",
    encoding="utf-8",
)


def _resource_path(relative: str) -> str:
    """PyInstaller 번들/개발 환경 모두에서 리소스 경로를 반환."""
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return str(Path(base) / relative)


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from ui.main_window import MainWindow
    from ui.styles import DARK_STYLE

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(_display_name)
    app.setApplicationVersion(_app.get("version", "1.0.0"))
    app.setWindowIcon(QIcon(_resource_path("assets/app.ico")))
    app.setStyleSheet(DARK_STYLE)

    window = MainWindow()
    window.show()

    logger.info(f"{_display_name} 런처 시작")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
