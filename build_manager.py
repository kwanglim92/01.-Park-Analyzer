"""
Build Manager — 개발자 전용 모듈 관리 도구.

모듈 추가/편집/삭제 및 빌드 설정을 GUI로 관리한다.
메인 런처(main.py)와 완전히 분리된 독립 진입점.
"""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from core.settings import load_settings
from ui.styles import DARK_STYLE


def _resource_path(relative: str) -> str:
    """리소스 경로 반환."""
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return str(Path(base) / relative)


def main():
    settings = load_settings()
    app_info = settings.get("app", {})
    display_name = app_info.get("display_name", "Integrated Analyzer")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(f"{display_name} — Build Manager")
    app.setStyleSheet(DARK_STYLE)

    icon_path = _resource_path("assets/app.ico")
    if Path(icon_path).exists():
        app.setWindowIcon(QIcon(icon_path))

    from ui.build_manager_window import BuildManagerWindow

    window = BuildManagerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
