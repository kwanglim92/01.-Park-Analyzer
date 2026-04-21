"""
Build Manager Window.

개발자 전용 모듈 관리 + 빌드 실행 GUI.
modules/ 폴더의 module.json을 CRUD하고, 빌드를 실행한다.
"""
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QTextEdit, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QSizePolicy,
    QDialog, QCheckBox, QScrollArea, QDialogButtonBox,
    QProgressBar,
)
from PySide6.QtCore import Qt, QProcess, QThread, Signal
from PySide6.QtGui import QFont, QColor

from core.module_manager import ModuleManager, ModuleInfo, MODULES_DIR
from core.settings import load_settings, save_settings
from ui.module_edit_dialog import ModuleEditDialog
from ui.styles import BG, BG2, BG3, FG, FG2, ACCENT, GREEN, RED, ORANGE, TEAL, PURPLE


# ── Build method display ──
_METHOD_LABELS = {
    "pyinstaller": "PI",
    "copy": "CP",
    "copy_dir": "CD",
    "none": "--",
}


# ── File size utilities ──
def _format_file_size(size_bytes: int) -> str:
    """바이트 크기를 사람이 읽기 좋은 형식으로 변환."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def _get_dir_size(path: Path) -> int:
    """디렉토리의 총 크기를 재귀적으로 계산."""
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            total += entry.stat().st_size
    return total


# ═══════════════════════════════════════════════════
#  Copy Dir Worker (background thread)
# ═══════════════════════════════════════════════════
class _CopyDirWorker(QThread):
    """폴더째 복사를 백그라운드 스레드에서 실행."""
    finished = Signal(bool, str)  # (success, message)

    def __init__(self, src: Path, target: Path, mod_json: dict, parent=None):
        super().__init__(parent)
        self._src = src
        self._target = target
        self._mod_json = mod_json

    def run(self):
        try:
            if self._target.exists():
                shutil.rmtree(str(self._target), ignore_errors=True)
            self._target.mkdir(parents=True, exist_ok=True)

            for item in self._src.iterdir():
                dst = self._target / item.name
                if item.is_dir():
                    shutil.copytree(str(item), str(dst))
                else:
                    shutil.copy2(str(item), str(dst))

            # module.json 보존
            json_path = self._target / "module.json"
            if not json_path.exists():
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(self._mod_json, f, indent=4, ensure_ascii=False)

            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


# ═══════════════════════════════════════════════════
#  Build Select Dialog
# ═══════════════════════════════════════════════════
class BuildSelectDialog(QDialog):
    """빌드할 모듈을 선택하는 다이얼로그."""

    def __init__(self, modules: list[ModuleInfo], parent=None):
        super().__init__(parent)
        self._modules = modules
        self._checkboxes: list[QCheckBox] = []
        self._selected: list[ModuleInfo] = []

        self.setWindowTitle("빌드 대상 선택")
        self.setMinimumSize(500, 400)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG}; color: {FG}; }}
            QLabel {{ background: transparent; }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("빌드할 모듈을 선택하세요")
        title.setStyleSheet(f"color: {FG}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel("체크된 모듈만 빌드에 포함됩니다.")
        desc.setStyleSheet(f"color: {FG2}; font-size: 13px;")
        layout.addWidget(desc)

        # Select All / Deselect All
        sel_row = QHBoxLayout()
        sel_row.setSpacing(10)

        select_all_btn = QPushButton("전체 선택")
        select_all_btn.setFixedHeight(34)
        select_all_btn.setCursor(Qt.PointingHandCursor)
        select_all_btn.setStyleSheet(
            f"QPushButton {{ background: {BG2}; color: {FG}; border: 1px solid {BG3}; "
            f"border-radius: 6px; padding: 4px 16px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {BG3}; border-color: {ACCENT}; }}"
        )
        select_all_btn.clicked.connect(lambda: self._set_all(True))
        sel_row.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("전체 해제")
        deselect_all_btn.setFixedHeight(34)
        deselect_all_btn.setCursor(Qt.PointingHandCursor)
        deselect_all_btn.setStyleSheet(
            f"QPushButton {{ background: {BG2}; color: {FG}; border: 1px solid {BG3}; "
            f"border-radius: 6px; padding: 4px 16px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {BG3}; border-color: {ACCENT}; }}"
        )
        deselect_all_btn.clicked.connect(lambda: self._set_all(False))
        sel_row.addWidget(deselect_all_btn)

        self._count_lbl = QLabel()
        self._count_lbl.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        sel_row.addWidget(self._count_lbl)

        sel_row.addStretch()
        layout.addLayout(sel_row)

        # Scrollable checkbox list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ background: {BG}; border: none; }}")

        content = QWidget()
        content.setStyleSheet(f"background: {BG};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        for mod in self._modules:
            build = mod.build_config or {}
            method = build.get("method", "none")
            method_lbl = _METHOD_LABELS.get(method, "??")
            dev_exists = Path(mod.dev_path).exists() if mod.dev_path else False
            status = "Ready" if dev_exists else "N/A"
            status_color = GREEN if dev_exists else ORANGE

            cb = QCheckBox(f"  {mod.name}   [{mod.category}]   [{method_lbl}]   {status}")
            cb.setChecked(True)
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {FG}; font-size: 13px; padding: 8px 6px;
                    background: {BG2}; border: 1px solid {BG3}; border-radius: 6px;
                }}
                QCheckBox:hover {{
                    border-color: {ACCENT}; background: {BG3};
                }}
                QCheckBox::indicator {{
                    width: 18px; height: 18px;
                }}
            """)
            cb.toggled.connect(self._update_count)
            content_layout.addWidget(cb)
            self._checkboxes.append(cb)

        self._update_count()
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {BG2}; color: {FG}; border: 1px solid {BG3}; "
            f"border-radius: 6px; padding: 6px 24px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {BG3}; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        build_btn = QPushButton("빌드 시작")
        build_btn.setFixedHeight(34)
        build_btn.setCursor(Qt.PointingHandCursor)
        build_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: {BG}; border: none; "
            f"border-radius: 6px; padding: 6px 24px; font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #7ba8e8; }}"
        )
        build_btn.clicked.connect(self._on_build)
        btn_row.addWidget(build_btn)

        layout.addLayout(btn_row)

    def _set_all(self, checked: bool):
        for cb in self._checkboxes:
            cb.setChecked(checked)
        self._update_count()

    def _update_count(self):
        checked = sum(1 for cb in self._checkboxes if cb.isChecked())
        total = len(self._checkboxes)
        total_size = 0
        for i, cb in enumerate(self._checkboxes):
            if cb.isChecked():
                mod = self._modules[i]
                prod_path = MODULES_DIR / mod.id / mod.entry_prod
                if prod_path.exists():
                    if prod_path.is_dir():
                        total_size += _get_dir_size(prod_path)
                    else:
                        total_size += prod_path.stat().st_size
        size_text = _format_file_size(total_size) if total_size > 0 else "—"
        self._count_lbl.setText(f"  {checked} / {total}    (모듈 합계: {size_text})")

    def _on_build(self):
        self._selected = []
        for i, cb in enumerate(self._checkboxes):
            if cb.isChecked():
                self._selected.append(self._modules[i])

        if not self._selected:
            QMessageBox.information(self, "선택 없음", "빌드할 모듈을 최소 1개 선택하세요.")
            return

        self.accept()

    def get_selected(self) -> list[ModuleInfo]:
        return self._selected


# ═══════════════════════════════════════════════════
#  Settings Dialog
# ═══════════════════════════════════════════════════
class SettingsDialog(QDialog):
    """프로그램 설정 다이얼로그 (display_name, build_name, version)."""

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._saved = False

        self.setWindowTitle("프로그램 설정")
        self.setFixedSize(460, 340)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG}; color: {FG}; }}
            QLabel {{ background: transparent; border: none; }}
            QLineEdit {{
                background: {BG2}; color: {FG};
                border: 1px solid {BG3}; border-radius: 5px;
                padding: 5px 8px; font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("프로그램 설정")
        title.setStyleSheet(f"color: {FG}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # ── 프로그램 이름 섹션 ──
        name_frame = QFrame()
        name_frame.setStyleSheet(
            f"QFrame {{ background: {BG2}; border: 1px solid {BG3}; border-radius: 8px; }}"
        )
        nf_layout = QVBoxLayout(name_frame)
        nf_layout.setContentsMargins(16, 12, 16, 14)
        nf_layout.setSpacing(8)

        nf_title = QLabel("프로그램 이름")
        nf_title.setStyleSheet(f"color: {ACCENT}; font-size: 13px; font-weight: bold;")
        nf_layout.addWidget(nf_title)

        app = self._settings.get("app", {})

        r1 = QHBoxLayout()
        r1.setSpacing(10)
        lbl1 = QLabel("표시 이름:")
        lbl1.setFixedWidth(80)
        lbl1.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        r1.addWidget(lbl1)
        self._display_name_edit = QLineEdit(app.get("display_name", ""))
        r1.addWidget(self._display_name_edit)
        nf_layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.setSpacing(10)
        lbl2 = QLabel("빌드 이름:")
        lbl2.setFixedWidth(80)
        lbl2.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        r2.addWidget(lbl2)
        self._build_name_edit = QLineEdit(app.get("build_name", ""))
        self._build_name_edit.setPlaceholderText("ASCII만 (예: IntegratedAnalyzer)")
        r2.addWidget(self._build_name_edit)
        nf_layout.addLayout(r2)

        hint = QLabel("빌드 이름은 ASCII만 사용. 빌드 출력 폴더명에 사용됩니다.")
        hint.setStyleSheet(f"color: {FG2}; font-size: 11px;")
        nf_layout.addWidget(hint)

        layout.addWidget(name_frame)

        # ── 버전 섹션 ──
        ver_frame = QFrame()
        ver_frame.setStyleSheet(
            f"QFrame {{ background: {BG2}; border: 1px solid {BG3}; border-radius: 8px; }}"
        )
        vf_layout = QVBoxLayout(ver_frame)
        vf_layout.setContentsMargins(16, 12, 16, 14)
        vf_layout.setSpacing(8)

        vf_title = QLabel("버전")
        vf_title.setStyleSheet(f"color: {ACCENT}; font-size: 13px; font-weight: bold;")
        vf_layout.addWidget(vf_title)

        r3 = QHBoxLayout()
        r3.setSpacing(10)
        lbl3 = QLabel("버전:")
        lbl3.setFixedWidth(80)
        lbl3.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        r3.addWidget(lbl3)
        self._version_edit = QLineEdit(app.get("version", "1.0.0"))
        self._version_edit.setFixedWidth(120)
        r3.addWidget(self._version_edit)
        r3.addStretch()
        vf_layout.addLayout(r3)

        layout.addWidget(ver_frame)

        note = QLabel("변경 시 런처 타이틀, 빌드 출력명, 인스톨러에 모두 자동 적용됩니다.")
        note.setStyleSheet(f"color: {FG2}; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()

        # ── 버튼 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.setFixedSize(90, 34)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {BG2}; color: {FG}; border: 1px solid {BG3}; "
            f"border-radius: 6px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {BG3}; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("저장")
        save_btn.setFixedSize(90, 34)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: {BG}; border: none; "
            f"border-radius: 6px; font-size: 13px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #7ba8e8; }}"
        )
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _on_save(self):
        dn = self._display_name_edit.text().strip()
        bn = self._build_name_edit.text().strip()
        ver = self._version_edit.text().strip()

        if not dn:
            QMessageBox.warning(self, "입력 오류", "표시 이름을 입력하세요.")
            return
        if not bn:
            QMessageBox.warning(self, "입력 오류", "빌드 이름을 입력하세요.")
            return

        self._settings.setdefault("app", {})
        self._settings["app"]["display_name"] = dn
        self._settings["app"]["build_name"] = bn
        self._settings["app"]["version"] = ver or "1.0.0"

        save_settings(self._settings)
        self._saved = True
        self.accept()

    @property
    def was_saved(self) -> bool:
        return self._saved


# ═══════════════════════════════════════════════════
#  Build Manager Window
# ═══════════════════════════════════════════════════
class BuildManagerWindow(QMainWindow):
    """개발자 전용 빌드 매니저 윈도우."""

    def __init__(self):
        super().__init__()
        self._settings = load_settings()
        self._display_name = self._settings.get("app", {}).get(
            "display_name", "Integrated Analyzer"
        )
        version = self._settings.get("app", {}).get("version", "1.0.0")
        self.setWindowTitle(f"Build Manager — {self._display_name} v{version}")
        self.setMinimumSize(880, 700)
        self.resize(980, 780)

        self._manager = ModuleManager()
        self._selected_module: ModuleInfo | None = None

        # Build state
        self._is_building = False
        self._build_process: QProcess | None = None
        self._build_queue: list[ModuleInfo] = []
        self._current_build_module: ModuleInfo | None = None
        self._build_launcher_after: bool = False
        self._build_total: int = 0
        self._build_done: int = 0

        self._build_ui()
        self._refresh_modules()

    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet(f"background: {BG}; color: {FG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)

        # ── Header ──
        hdr = QHBoxLayout()
        title = QLabel(f"Build Manager")
        title.setStyleSheet(f"color: {FG}; font-size: 24px; font-weight: bold;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._subtitle = QLabel(f"{self._display_name}")
        self._subtitle.setStyleSheet(f"color: {FG2}; font-size: 14px;")
        hdr.addWidget(self._subtitle)

        settings_btn = QPushButton("설정")
        settings_btn.setFixedHeight(30)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setStyleSheet(
            f"QPushButton {{ background: {BG2}; color: {FG}; border: 1px solid {BG3}; "
            f"border-radius: 6px; padding: 2px 14px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {BG3}; border-color: {ACCENT}; }}"
        )
        settings_btn.clicked.connect(self._on_settings)
        hdr.addWidget(settings_btn)
        root.addLayout(hdr)

        # ══════════════════════════════════════
        #  BODY — Left (table+buttons) + Right (detail)
        # ══════════════════════════════════════
        body = QHBoxLayout()
        body.setSpacing(16)

        # ── Left Panel: Table + Buttons ──
        left = QWidget()
        left.setStyleSheet(f"background: {BG};")
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(10)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["상태", "이름", "카테고리", "버전", "빌드", "문서"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.StrongFocus)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self._table.setColumnWidth(0, 50)
        self._table.setColumnWidth(4, 50)
        self._table.setColumnWidth(5, 60)

        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {BG2}; color: {FG}; border: 1px solid {BG3};
                border-radius: 6px; font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 6px 8px; border: none;
            }}
            QTableWidget::item:selected {{
                background: {BG3}; color: {FG};
            }}
            QHeaderView::section {{
                background: {BG3}; color: {FG2}; border: none;
                padding: 6px 8px; font-size: 12px; font-weight: bold;
            }}
        """)
        self._table.currentItemChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self._on_edit)
        left_vbox.addWidget(self._table, 1)

        # Button rows (2줄로 분리)
        _btn_style = (
            f"QPushButton {{ background: {BG2}; color: {FG}; border: 1px solid {BG3}; "
            f"border-radius: 6px; padding: 4px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {BG3}; border-color: {ACCENT}; }}"
            f"QPushButton:disabled {{ background: {BG2}; color: {BG3}; border-color: {BG2}; }}"
        )
        _folder_btn_style = (
            f"QPushButton {{ background: {BG2}; color: {TEAL}; border: 1px solid {BG3}; "
            f"border-radius: 6px; padding: 4px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {BG3}; border-color: {TEAL}; }}"
        )
        _build_btn_style = (
            f"QPushButton {{ background: {ACCENT}; color: {BG}; border: none; "
            f"border-radius: 6px; padding: 4px 14px; font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #7ba8e8; }}"
            f"QPushButton:disabled {{ background: {BG3}; color: {FG2}; }}"
        )

        # Row 1: CRUD + Order
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        for text, handler in [
            ("+ 추가", self._on_add),
            ("편집", self._on_edit),
            ("삭제", self._on_delete),
            ("소스 열기", self._on_open_source),
            ("새로고침", self._refresh_modules),
        ]:
            btn = QPushButton(text)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(_btn_style)
            btn.clicked.connect(handler)
            row1.addWidget(btn)

        row1.addStretch()

        _order_btn_style = (
            f"QPushButton {{ background: {BG2}; color: {PURPLE}; border: 1px solid {BG3}; "
            f"border-radius: 6px; padding: 4px 8px; font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {BG3}; border-color: {PURPLE}; }}"
            f"QPushButton:disabled {{ background: {BG2}; color: {BG3}; border-color: {BG2}; }}"
        )

        self._move_up_btn = QPushButton("▲")
        self._move_up_btn.setFixedSize(30, 30)
        self._move_up_btn.setCursor(Qt.PointingHandCursor)
        self._move_up_btn.setToolTip("위로 이동")
        self._move_up_btn.setStyleSheet(_order_btn_style)
        self._move_up_btn.clicked.connect(self._on_move_up)
        row1.addWidget(self._move_up_btn)

        self._move_down_btn = QPushButton("▼")
        self._move_down_btn.setFixedSize(30, 30)
        self._move_down_btn.setCursor(Qt.PointingHandCursor)
        self._move_down_btn.setToolTip("아래로 이동")
        self._move_down_btn.setStyleSheet(_order_btn_style)
        self._move_down_btn.clicked.connect(self._on_move_down)
        row1.addWidget(self._move_down_btn)

        left_vbox.addLayout(row1)

        # Row 2: Folders + Build
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        dist_btn = QPushButton("dist 폴더")
        dist_btn.setFixedHeight(30)
        dist_btn.setCursor(Qt.PointingHandCursor)
        dist_btn.setStyleSheet(_folder_btn_style)
        dist_btn.clicked.connect(self._on_open_dist)
        row2.addWidget(dist_btn)

        installer_btn = QPushButton("installer 폴더")
        installer_btn.setFixedHeight(30)
        installer_btn.setCursor(Qt.PointingHandCursor)
        installer_btn.setStyleSheet(_folder_btn_style)
        installer_btn.clicked.connect(self._on_open_installer)
        row2.addWidget(installer_btn)

        row2.addStretch()

        self._build_one_btn = QPushButton("선택 빌드")
        self._build_one_btn.setFixedHeight(30)
        self._build_one_btn.setCursor(Qt.PointingHandCursor)
        self._build_one_btn.setStyleSheet(_build_btn_style)
        self._build_one_btn.clicked.connect(self._on_build_selected)
        row2.addWidget(self._build_one_btn)

        self._build_all_btn = QPushButton("전체 빌드")
        self._build_all_btn.setFixedHeight(30)
        self._build_all_btn.setCursor(Qt.PointingHandCursor)
        self._build_all_btn.setStyleSheet(_build_btn_style)
        self._build_all_btn.clicked.connect(self._on_build_all)
        row2.addWidget(self._build_all_btn)

        left_vbox.addLayout(row2)

        body.addWidget(left, 3)  # 좌측 60%

        # ── Right Panel: Detail ──
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        detail_scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG2}; border: 1px solid {BG3}; border-radius: 8px; }}
        """)

        detail_widget = QWidget()
        detail_widget.setStyleSheet(f"background: {BG2};")
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(16, 12, 16, 12)
        detail_layout.setSpacing(3)

        self._detail_labels: dict[str, QLabel] = {}
        sections = {
            "기본 정보": [
                ("ID", "id"), ("이름", "name"), ("카테고리", "category"),
                ("버전", "version"), ("설명", "description"),
                ("파일 크기", "file_size"),
            ],
            "경로 정보": [
                ("개발 경로", "dev_path"), ("개발 진입점", "entry_dev"),
                ("배포 진입점", "entry_prod"), ("상태", "status"),
            ],
            "빌드 설정": [
                ("빌드 방식", "build_method"), ("빌드 진입점", "build_entry"),
                ("빌드 이름", "build_name"), ("Hidden Imports", "hidden_imports"),
                ("Add Data", "add_data"),
            ],
            "문서 관리": [
                ("MC-Wiki", "manual_wiki"),
                ("SharePoint", "manual_sharepoint"),
                ("변경사항", "changelog"),
            ],
        }

        for section_name, fields in sections.items():
            sec_lbl = QLabel(section_name)
            sec_lbl.setStyleSheet(
                f"color: {ACCENT}; font-size: 12px; font-weight: bold; "
                f"padding: 6px 0 2px 0; background: transparent; border: none;"
            )
            detail_layout.addWidget(sec_lbl)

            for display_name, key in fields:
                row = QHBoxLayout()
                row.setSpacing(8)

                name_lbl = QLabel(f"{display_name}:")
                name_lbl.setFixedWidth(110)
                name_lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
                name_lbl.setStyleSheet(f"color: {FG2}; font-size: 11px; background: transparent; border: none;")
                row.addWidget(name_lbl)

                val_lbl = QLabel("—")
                val_lbl.setStyleSheet(f"color: {FG}; font-size: 11px; background: transparent; border: none;")
                val_lbl.setWordWrap(True)
                row.addWidget(val_lbl, 1)

                self._detail_labels[key] = val_lbl
                detail_layout.addLayout(row)

        detail_layout.addStretch()
        detail_scroll.setWidget(detail_widget)

        body.addWidget(detail_scroll, 2)  # 우측 40%

        root.addLayout(body, 1)

        # ── Progress Bar ──
        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(
            f"color: {ACCENT}; font-size: 12px; font-weight: bold; background: transparent;"
        )
        self._progress_label.setFixedWidth(280)
        progress_row.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(18)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {BG2}; border: 1px solid {BG3}; border-radius: 4px;
                text-align: center; color: {FG}; font-size: 11px;
            }}
            QProgressBar::chunk {{
                background: {ACCENT}; border-radius: 3px;
            }}
        """)
        progress_row.addWidget(self._progress_bar, 1)

        self._progress_widget = QWidget()
        self._progress_widget.setLayout(progress_row)
        self._progress_widget.setVisible(False)
        root.addWidget(self._progress_widget)

        # ── Log Panel ──
        self._log_panel = QTextEdit()
        self._log_panel.setReadOnly(True)
        self._log_panel.setFixedHeight(200)
        self._log_panel.setStyleSheet(f"""
            QTextEdit {{
                background: {BG2}; color: {FG2}; border: 1px solid {BG3};
                border-radius: 6px; padding: 10px;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px;
            }}
        """)
        root.addWidget(self._log_panel)

    # ──────────────────────────────────────────
    #  Module Discovery & Table
    # ──────────────────────────────────────────
    def _refresh_modules(self):
        modules = self._manager.discover()
        self._table.setRowCount(len(modules))

        for row, mod in enumerate(modules):
            # Status
            dev_exists = Path(mod.dev_path).exists() if mod.dev_path else False
            status_text = "Ready" if dev_exists else "N/A"
            status_color = GREEN if dev_exists else ORANGE

            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            status_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 0, status_item)

            # Name
            self._table.setItem(row, 1, QTableWidgetItem(mod.name))

            # Category
            self._table.setItem(row, 2, QTableWidgetItem(mod.category))

            # Version
            ver_item = QTableWidgetItem(mod.version)
            ver_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 3, ver_item)

            # Build method
            method = mod.build_config.get("method", "none") if mod.build_config else "none"
            method_item = QTableWidgetItem(_METHOD_LABELS.get(method, "??"))
            method_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 4, method_item)

            # 문서 상태
            w = "O" if mod.manual_wiki else "X"
            s = "O" if mod.manual_sharepoint else "X"
            doc_text = f"{w}/{s}"
            if mod.manual_wiki and mod.manual_sharepoint:
                doc_color = GREEN
            elif mod.manual_wiki or mod.manual_sharepoint:
                doc_color = ORANGE
            else:
                doc_color = RED
            doc_item = QTableWidgetItem(doc_text)
            doc_item.setForeground(QColor(doc_color))
            doc_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 5, doc_item)

        self._selected_module = None
        self._clear_detail()
        self._log_msg(f"{len(modules)}개 모듈 탐색 완료")

    def _on_selection_changed(self, current, previous):
        if current is None:
            self._selected_module = None
            self._clear_detail()
            return

        row = current.row()
        modules = self._manager.modules
        if 0 <= row < len(modules):
            self._selected_module = modules[row]
            self._update_detail(self._selected_module)

    def _clear_detail(self):
        for lbl in self._detail_labels.values():
            lbl.setText("—")

    def _update_detail(self, mod: ModuleInfo):
        self._detail_labels["id"].setText(mod.id)
        self._detail_labels["name"].setText(mod.name)
        self._detail_labels["category"].setText(mod.category)
        self._detail_labels["version"].setText(mod.version)
        self._detail_labels["description"].setText(mod.description or "—")

        prod_path = MODULES_DIR / mod.id / mod.entry_prod
        if prod_path.exists():
            if prod_path.is_dir():
                size = _get_dir_size(prod_path)
            else:
                size = prod_path.stat().st_size
            self._detail_labels["file_size"].setText(_format_file_size(size))
        else:
            self._detail_labels["file_size"].setText("빌드 안됨")

        self._detail_labels["dev_path"].setText(mod.dev_path or "—")
        self._detail_labels["entry_dev"].setText(mod.entry_dev)
        self._detail_labels["entry_prod"].setText(mod.entry_prod)

        dev_exists = Path(mod.dev_path).exists() if mod.dev_path else False
        status_text = "Ready (dev_path 존재)" if dev_exists else "경로 없음"
        status_color = GREEN if dev_exists else ORANGE
        self._detail_labels["status"].setText(status_text)
        self._detail_labels["status"].setStyleSheet(f"color: {status_color}; font-size: 11px; background: transparent; border: none;")

        build = mod.build_config or {}
        method = build.get("method", "none")
        self._detail_labels["build_method"].setText(method)
        self._detail_labels["build_entry"].setText(build.get("entry", build.get("copy_from", "—")))
        self._detail_labels["build_name"].setText(build.get("build_name", "—"))

        hidden = build.get("hidden_imports", [])
        self._detail_labels["hidden_imports"].setText(", ".join(hidden) if hidden else "—")

        add_data = build.get("add_data", [])
        self._detail_labels["add_data"].setText(", ".join(add_data) if add_data else "—")

        self._detail_labels["manual_wiki"].setText(mod.manual_wiki or "—")
        self._detail_labels["manual_sharepoint"].setText(mod.manual_sharepoint or "—")
        cl = mod.changelog
        self._detail_labels["changelog"].setText(
            ", ".join(e.get("version", "") for e in cl if e.get("version")) if cl else "—"
        )

    # ──────────────────────────────────────────
    #  CRUD Operations
    # ──────────────────────────────────────────
    def _get_categories(self) -> list[str]:
        cats = set()
        for mod in self._manager.modules:
            cats.add(mod.category)
        return sorted(cats)

    def _on_add(self):
        template_path = MODULES_DIR.parent / "_template" / "module.json"
        if template_path.exists():
            with open(template_path, "r", encoding="utf-8") as f:
                template_data = json.load(f)
        else:
            template_data = {}

        dlg = ModuleEditDialog(
            data=template_data,
            categories=self._get_categories(),
            is_new=True,
            parent=self,
        )
        if dlg.exec() != ModuleEditDialog.Accepted:
            return

        data = dlg.get_data()
        if not data:
            return

        module_id = data["id"]
        module_dir = MODULES_DIR / module_id

        if module_dir.exists():
            QMessageBox.warning(
                self, "중복", f"modules/{module_id}/ 폴더가 이미 존재합니다."
            )
            return

        module_dir.mkdir(parents=True, exist_ok=True)
        json_path = module_dir / "module.json"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        self._log_msg(f"모듈 추가: {data['name']} ({module_id})")
        self._refresh_modules()

    def _on_edit(self):
        if self._selected_module is None:
            QMessageBox.information(self, "선택 필요", "편집할 모듈을 선택하세요.")
            return

        mod = self._selected_module
        data = mod.to_json()

        dlg = ModuleEditDialog(
            data=data,
            categories=self._get_categories(),
            is_new=False,
            parent=self,
        )
        if dlg.exec() != ModuleEditDialog.Accepted:
            return

        new_data = dlg.get_data()
        if not new_data:
            return

        json_path = MODULES_DIR / mod.id / "module.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4, ensure_ascii=False)

        self._log_msg(f"모듈 편집 저장: {new_data['name']}")
        self._refresh_modules()

    def _on_delete(self):
        if self._selected_module is None:
            QMessageBox.information(self, "선택 필요", "삭제할 모듈을 선택하세요.")
            return

        mod = self._selected_module
        reply = QMessageBox.question(
            self, "모듈 삭제",
            f"'{mod.name}' 모듈을 삭제하시겠습니까?\n\n"
            f"modules/{mod.id}/ 폴더가 삭제됩니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        module_dir = MODULES_DIR / mod.id
        if module_dir.exists():
            shutil.rmtree(module_dir)

        self._log_msg(f"모듈 삭제: {mod.name} ({mod.id})")
        self._refresh_modules()

    def _on_open_source(self):
        if self._selected_module is None:
            QMessageBox.information(self, "선택 필요", "모듈을 선택하세요.")
            return

        dev_path = self._selected_module.dev_path
        if dev_path and Path(dev_path).exists():
            os.startfile(dev_path)
            self._log_msg(f"소스 열기: {dev_path}")
        else:
            QMessageBox.warning(
                self, "경로 없음",
                f"개발 경로를 찾을 수 없습니다:\n{dev_path}",
            )

    # ──────────────────────────────────────────
    #  Module Reorder
    # ──────────────────────────────────────────
    def _on_move_up(self):
        self._move_module(-1)

    def _on_move_down(self):
        self._move_module(1)

    def _move_module(self, direction: int):
        """선택된 모듈을 위(-1) 또는 아래(+1)로 이동."""
        row = self._table.currentRow()
        modules = self._manager.modules
        if row < 0 or row >= len(modules):
            return

        new_row = row + direction
        if new_row < 0 or new_row >= len(modules):
            return

        # Swap order values
        mod_a = modules[row]
        mod_b = modules[new_row]

        # Ensure distinct order values: reassign sequential orders
        for i, m in enumerate(modules):
            m.order = i

        # Now swap the two
        modules[row].order, modules[new_row].order = (
            modules[new_row].order,
            modules[row].order,
        )

        # Save both module.json files
        self._save_module_order(mod_a)
        self._save_module_order(mod_b)

        # Re-sort and refresh
        modules.sort(key=lambda m: (m.order, m.name))
        self._refresh_table_keep_selection(new_row)
        self._log_msg(f"순서 변경: {mod_a.name} ↔ {mod_b.name}")

    def _save_module_order(self, mod: ModuleInfo):
        """module.json에 order 값 저장."""
        json_path = MODULES_DIR / mod.id / "module.json"
        if not json_path.exists():
            return
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["order"] = mod.order
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except (json.JSONDecodeError, OSError) as e:
            self._log_msg(f"order 저장 실패 ({mod.id}): {e}", color=RED)

    def _refresh_table_keep_selection(self, select_row: int):
        """테이블 갱신 후 지정 행 선택 유지."""
        modules = self._manager.modules
        self._table.setRowCount(len(modules))

        for row, mod in enumerate(modules):
            dev_exists = Path(mod.dev_path).exists() if mod.dev_path else False
            status_text = "Ready" if dev_exists else "N/A"
            status_color = GREEN if dev_exists else ORANGE

            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            status_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 0, status_item)

            self._table.setItem(row, 1, QTableWidgetItem(mod.name))
            self._table.setItem(row, 2, QTableWidgetItem(mod.category))

            ver_item = QTableWidgetItem(mod.version)
            ver_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 3, ver_item)

            method = mod.build_config.get("method", "none") if mod.build_config else "none"
            method_item = QTableWidgetItem(_METHOD_LABELS.get(method, "??"))
            method_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 4, method_item)

        if 0 <= select_row < len(modules):
            self._table.setCurrentCell(select_row, 0)
            self._selected_module = modules[select_row]
            self._update_detail(self._selected_module)

    # ──────────────────────────────────────────
    #  Output Folder & Settings
    # ──────────────────────────────────────────
    def _get_project_root(self) -> Path:
        return MODULES_DIR.parent

    def _on_open_dist(self):
        root = self._get_project_root()
        display_name = self._settings.get("app", {}).get("display_name", "")
        exe_name = display_name.replace(" ", "")
        target = root / "dist" / exe_name
        if not target.exists():
            target = root / "dist"
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(str(target))
        self._log_msg(f"dist 폴더 열기: {target}")

    def _on_open_installer(self):
        root = self._get_project_root()
        target = root / "installer" / "Output"
        if not target.exists():
            target = root / "installer"
        if not target.exists():
            target = root
        os.startfile(str(target))
        self._log_msg(f"installer 폴더 열기: {target}")

    def _on_settings(self):
        dlg = SettingsDialog(self._settings, parent=self)
        dlg.exec()
        if dlg.was_saved:
            # 설정 다시 로드하고 UI 갱신
            self._settings = load_settings()
            app = self._settings.get("app", {})
            self._display_name = app.get("display_name", "Integrated Analyzer")
            version = app.get("version", "1.0.0")
            self.setWindowTitle(f"Build Manager — {self._display_name} v{version}")
            self._subtitle.setText(self._display_name)
            self._log_msg(f"설정 저장 완료: {self._display_name} v{version}", color=GREEN)

    # ══════════════════════════════════════════
    #  BUILD EXECUTION
    # ══════════════════════════════════════════
    def _set_building(self, building: bool):
        """빌드 상태 설정 → 버튼 활성화/비활성화."""
        self._is_building = building
        self._build_one_btn.setEnabled(not building)
        self._build_all_btn.setEnabled(not building)

    def _show_progress(self, step_name: str):
        """진행 중 라벨만 업데이트 (done 증가 없이)."""
        self._progress_label.setText(f"[{self._build_done}/{self._build_total}]  {step_name}")

    def _advance_progress(self, step_name: str):
        """단계 완료 → done 증가 + 바/라벨 업데이트."""
        self._build_done += 1
        pct = int(self._build_done / self._build_total * 100) if self._build_total else 0
        self._progress_bar.setValue(pct)
        self._progress_label.setText(f"[{self._build_done}/{self._build_total}]  {step_name}")

    def _hide_progress(self):
        """프로그레스 바 숨김."""
        self._progress_widget.setVisible(False)
        self._progress_bar.setValue(0)
        self._progress_label.setText("")

    # ── 선택 빌드 ──
    def _on_build_selected(self):
        if self._selected_module is None:
            QMessageBox.information(self, "선택 필요", "빌드할 모듈을 선택하세요.")
            return
        if self._is_building:
            return

        self._build_queue = [self._selected_module]
        self._build_launcher_after = False
        self._build_total = 1
        self._build_done = 0
        self._progress_bar.setValue(0)
        self._progress_widget.setVisible(True)
        self._log_msg(f"━━━ 선택 빌드 시작: {self._selected_module.name} ━━━", color=ACCENT)
        self._set_building(True)
        self._build_next()

    # ── 전체 빌드 (선택 다이얼로그) ──
    def _on_build_all(self):
        if self._is_building:
            return

        modules = self._manager.modules
        if not modules:
            QMessageBox.information(self, "모듈 없음", "빌드할 모듈이 없습니다.")
            return

        dlg = BuildSelectDialog(modules, parent=self)
        if dlg.exec() != BuildSelectDialog.Accepted:
            return

        selected = dlg.get_selected()
        if not selected:
            return

        self._build_queue = selected
        self._build_selected_ids = {m.id for m in selected}
        self._build_launcher_after = True  # 전체 빌드 시 런처도 빌드
        self._build_total = len(selected) + 2  # 모듈 + 런처 + installer
        self._build_done = 0
        self._progress_bar.setValue(0)
        self._progress_widget.setVisible(True)
        names = ", ".join(m.name for m in selected)
        self._log_msg(
            f"━━━ 빌드 시작: {len(selected)}개 모듈 ({names}) + 런처 ━━━",
            color=ACCENT,
        )
        self._set_building(True)
        self._build_next()

    # ── 빌드 큐 처리 ──
    def _build_next(self):
        """큐에서 다음 모듈을 꺼내서 빌드 시작."""
        if not self._build_queue:
            if self._build_launcher_after:
                self._build_launcher_after = False
                self._start_launcher_build()
            else:
                self._log_msg("━━━ 빌드 완료 ━━━", color=GREEN)
                self._hide_progress()
                self._set_building(False)
                self._refresh_modules()
            return

        mod = self._build_queue.pop(0)
        self._current_build_module = mod
        build = mod.build_config or {}
        method = build.get("method", "none")
        self._show_progress(f"{mod.name} 빌드 중...")

        if method == "pyinstaller":
            self._start_pyinstaller_build(mod)
        elif method == "copy":
            self._do_copy_build(mod)
            self._build_next()  # copy는 즉시 완료 → 다음으로
        elif method == "copy_dir":
            self._start_copy_dir_build(mod)
        else:
            self._log_msg(f"  [{mod.name}] SKIP (method={method})", color=FG2)
            self._build_next()

    # ── PyInstaller 빌드 (QProcess) ──
    def _start_pyinstaller_build(self, mod: ModuleInfo):
        build = mod.build_config
        dev_path = mod.dev_path

        if not dev_path or not Path(dev_path).exists():
            self._log_msg(f"  [{mod.name}] FAIL: dev_path 없음 ({dev_path})", color=RED)
            self._build_next()
            return

        self._log_msg(f"  [{mod.name}] PyInstaller 빌드 시작...", color=ACCENT)

        # Build arguments
        args = ["-m", "PyInstaller", "--noconfirm"]

        if build.get("onefile", True):
            args.append("--onefile")
        else:
            args.append("--onedir")

        if build.get("windowed", True):
            args.append("--windowed")

        args.extend(["--name", build.get("build_name", mod.id)])
        args.extend(["--distpath", "dist"])

        for hi in build.get("hidden_imports", []):
            args.append(f"--hidden-import={hi}")

        for ad in build.get("add_data", []):
            parts = ad.split(";", 1)
            if len(parts) == 2:
                abs_src = str(Path(dev_path) / parts[0])
                args.extend(["--add-data", f"{abs_src};{parts[1]}"])

        args.append(build.get("entry", "main.py"))

        # Start QProcess
        self._build_process = QProcess(self)
        self._build_process.setWorkingDirectory(dev_path)
        self._build_process.setProcessChannelMode(QProcess.MergedChannels)
        self._build_process.readyReadStandardOutput.connect(self._on_build_stdout)
        self._build_process.finished.connect(self._on_build_finished)

        python_exe = sys.executable
        self._build_process.start(python_exe, args)

    def _on_build_stdout(self):
        """빌드 프로세스 stdout 읽기 → 로그 패널에 출력."""
        if self._build_process is None:
            return
        data = self._build_process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace").rstrip()
        if text:
            for line in text.splitlines():
                self._log_raw(line)

    def _on_build_finished(self, exit_code, exit_status):
        """빌드 프로세스 완료 처리."""
        mod = self._current_build_module
        if mod is None:
            self._build_next()
            return

        build = mod.build_config or {}

        if exit_code == 0:
            build_name = build.get("build_name", mod.id)
            built_exe = Path(mod.dev_path) / "dist" / f"{build_name}.exe"
            target = MODULES_DIR / mod.id / mod.entry_prod

            if built_exe.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(built_exe), str(target))
                self._log_msg(
                    f"  [{mod.name}] OK → modules/{mod.id}/{mod.entry_prod}",
                    color=GREEN,
                )
            else:
                self._log_msg(
                    f"  [{mod.name}] WARN: exe 없음 ({built_exe})",
                    color=ORANGE,
                )
        else:
            self._log_msg(
                f"  [{mod.name}] FAIL (exit code: {exit_code})",
                color=RED,
            )

        self._build_process = None
        self._current_build_module = None
        self._advance_progress(f"{mod.name} 완료")
        if self._selected_module and self._selected_module.id == mod.id:
            self._update_detail(self._selected_module)
        self._build_next()

    # ── Copy 빌드 ──
    def _do_copy_build(self, mod: ModuleInfo):
        build = mod.build_config or {}
        copy_from = build.get("copy_from", "")
        dev_path = mod.dev_path

        if not copy_from or not dev_path:
            self._log_msg(f"  [{mod.name}] SKIP: copy_from 미설정", color=ORANGE)
            return

        src = Path(dev_path) / copy_from
        target = MODULES_DIR / mod.id / mod.entry_prod

        if not src.exists():
            self._log_msg(f"  [{mod.name}] FAIL: 원본 없음 ({src})", color=RED)
            return

        try:
            target.parent.mkdir(parents=True, exist_ok=True)

            # src와 target이 동일 파일이면 복사 생략 (원본이 이미 제자리)
            try:
                same_file = target.exists() and src.resolve() == target.resolve()
            except OSError:
                same_file = False

            if same_file:
                self._log_msg(
                    f"  [{mod.name}] OK (copy, 원본이 이미 제자리) → modules/{mod.id}/{mod.entry_prod}",
                    color=GREEN,
                )
            else:
                shutil.copy2(str(src), str(target))
                self._log_msg(
                    f"  [{mod.name}] OK (copy) → modules/{mod.id}/{mod.entry_prod}",
                    color=GREEN,
                )
            self._advance_progress(f"{mod.name} 완료")
            if self._selected_module and self._selected_module.id == mod.id:
                self._update_detail(self._selected_module)
        except Exception as e:
            self._log_msg(f"  [{mod.name}] FAIL (copy): {e}", color=RED)

    # ── Copy Dir 빌드 (폴더째 복사, 백그라운드) ──
    def _start_copy_dir_build(self, mod: ModuleInfo):
        build = mod.build_config or {}
        copy_from = build.get("copy_from", ".")
        dev_path = mod.dev_path

        if not dev_path:
            self._log_msg(f"  [{mod.name}] SKIP: dev_path 미설정", color=ORANGE)
            self._build_next()
            return

        src = Path(dev_path) / copy_from
        if not src.exists():
            self._log_msg(f"  [{mod.name}] FAIL: 원본 없음 ({src})", color=RED)
            self._build_next()
            return

        target = MODULES_DIR / mod.id
        self._log_msg(f"  [{mod.name}] 폴더 복사 중...", color=ACCENT)

        self._copy_dir_worker = _CopyDirWorker(src, target, mod.to_json(), self)
        self._copy_dir_worker.finished.connect(
            lambda ok, err, m=mod: self._on_copy_dir_finished(ok, err, m)
        )
        self._copy_dir_worker.start()

    def _on_copy_dir_finished(self, success: bool, error: str, mod: ModuleInfo):
        if success:
            self._log_msg(
                f"  [{mod.name}] OK (copy_dir) → modules/{mod.id}/",
                color=GREEN,
            )
        else:
            self._log_msg(
                f"  [{mod.name}] FAIL (copy_dir): {error}",
                color=RED,
            )
        self._copy_dir_worker = None
        self._current_build_module = None
        self._advance_progress(f"{mod.name} 완료")
        if self._selected_module and self._selected_module.id == mod.id:
            self._update_detail(self._selected_module)
        self._build_next()

    # ── 런처 빌드 (전체 빌드 마지막 단계) ──
    def _start_launcher_build(self):
        """런처를 PyInstaller --onedir로 빌드 + modules 복사 + rename."""
        root = self._get_project_root()
        app = self._settings.get("app", {})
        build_name = app.get("build_name", "IntegratedAnalyzer")
        display_name = app.get("display_name", "Integrated Analyzer")
        exe_name = display_name.replace(" ", "")

        self._show_progress("런처 빌드 중...")
        self._log_msg(f"  [런처] PyInstaller 빌드 시작...", color=ACCENT)

        args = [
            "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
            "--name", build_name,
            "--icon", str(root / "assets" / "app.ico"),
            "--distpath", "dist",
            "--add-data", f"{root / 'config'};config",
            "--add-data", f"{root / 'assets'};assets",
            "--hidden-import=core", "--hidden-import=ui",
            "main.py",
        ]

        # 런처 빌드 완료 후 처리를 위해 메타데이터 저장
        self._launcher_meta = {
            "build_name": build_name,
            "exe_name": exe_name,
            "root": root,
        }

        self._build_process = QProcess(self)
        self._build_process.setWorkingDirectory(str(root))
        self._build_process.setProcessChannelMode(QProcess.MergedChannels)
        self._build_process.readyReadStandardOutput.connect(self._on_build_stdout)
        self._build_process.finished.connect(self._on_launcher_build_finished)

        self._build_process.start(sys.executable, args)

    def _on_launcher_build_finished(self, exit_code, exit_status):
        """런처 빌드 완료 → modules 복사 + rename."""
        meta = getattr(self, "_launcher_meta", {})
        build_name = meta.get("build_name", "")
        exe_name = meta.get("exe_name", "")
        root = meta.get("root", self._get_project_root())

        if exit_code != 0:
            self._log_msg(f"  [런처] FAIL (exit code: {exit_code})", color=RED)
            self._build_process = None
            self._log_msg("━━━ 빌드 완료 (런처 실패) ━━━", color=ORANGE)
            self._finish_full_build()
            return

        self._log_msg(f"  [런처] PyInstaller OK", color=GREEN)

        dist_build = root / "dist" / build_name
        dist_target = root / "dist" / exe_name

        try:
            # modules/ 복사 (선택된 모듈만)
            dst_modules = dist_build / "modules"
            if dst_modules.exists():
                self._robust_rmtree(dst_modules)
            dst_modules.mkdir(parents=True, exist_ok=True)

            selected_ids = getattr(self, "_build_selected_ids", None)
            src_modules = root / "modules"
            for mod_dir in src_modules.iterdir():
                if not mod_dir.is_dir():
                    continue
                if not (mod_dir / "module.json").exists():
                    continue
                if selected_ids and mod_dir.name not in selected_ids:
                    continue
                shutil.copytree(str(mod_dir), str(dst_modules / mod_dir.name))

            copied_count = len(list(dst_modules.iterdir()))
            self._log_msg(f"  [런처] modules/ 복사 완료 ({copied_count}개 모듈)", color=GREEN)

            # rename exe
            src_exe = dist_build / f"{build_name}.exe"
            dst_exe = dist_build / f"{exe_name}.exe"
            if src_exe.exists() and src_exe != dst_exe:
                if dst_exe.exists():
                    dst_exe.unlink()
                src_exe.rename(dst_exe)

            # rename folder
            if dist_target.exists() and dist_target != dist_build:
                self._robust_rmtree(dist_target)
            if dist_build != dist_target:
                dist_build.rename(dist_target)

            self._log_msg(
                f"  [런처] OK → dist/{exe_name}/{exe_name}.exe",
                color=GREEN,
            )

            total_size = _get_dir_size(dist_target)
            self._log_msg(
                f"  [빌드 크기] dist/{exe_name}/ 총 크기: {_format_file_size(total_size)}",
                color=ACCENT,
            )
        except OSError as e:
            self._log_msg(f"  [런처] 복사/rename 실패: {e}", color=RED)
            self._build_process = None
            self._log_msg("━━━ 빌드 완료 (런처 후처리 실패) ━━━", color=ORANGE)
            self._finish_full_build()
            return

        self._build_process = None
        self._advance_progress("런처 빌드 완료")
        self._start_inno_setup_build()

    # ── Inno Setup 빌드 (전체 빌드 마지막 단계) ──
    def _start_inno_setup_build(self):
        """setup.iss 생성 후 Inno Setup 컴파일."""
        root = self._get_project_root()
        gen_script = root / "installer" / "_generate_iss.ps1"

        if not gen_script.exists():
            self._log_msg("  [Installer] SKIP: _generate_iss.ps1 없음", color=ORANGE)
            self._finish_full_build()
            return

        # 1) setup.iss 생성
        self._show_progress("Installer 생성 중...")
        self._log_msg("  [Installer] setup.iss 생성 중...", color=ACCENT)
        self._inno_process = QProcess(self)
        self._inno_process.setWorkingDirectory(str(root))
        self._inno_process.setProcessChannelMode(QProcess.MergedChannels)
        self._inno_process.readyReadStandardOutput.connect(self._on_inno_stdout)
        self._inno_process.finished.connect(self._on_generate_iss_finished)
        self._inno_process.start(
            "powershell",
            ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(gen_script)],
        )

    def _on_inno_stdout(self):
        proc = getattr(self, "_inno_process", None)
        if proc is None:
            return
        data = proc.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace").rstrip()
        if text:
            for line in text.splitlines():
                self._log_raw(line)

    def _on_generate_iss_finished(self, exit_code, exit_status):
        """setup.iss 생성 완료 → ISCC 컴파일 시작."""
        root = self._get_project_root()
        self._inno_process = None

        if exit_code != 0:
            self._log_msg(f"  [Installer] setup.iss 생성 실패 (exit: {exit_code})", color=RED)
            self._finish_full_build()
            return

        self._log_msg("  [Installer] setup.iss 생성 OK", color=GREEN)

        # ISCC.exe 경로 탐색
        iscc_paths = [
            Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
            Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        ]
        iscc = None
        for p in iscc_paths:
            if p.exists():
                iscc = p
                break

        if iscc is None:
            self._log_msg(
                "  [Installer] SKIP: Inno Setup 6 미설치 (ISCC.exe 없음)",
                color=ORANGE,
            )
            self._log_msg(
                "    다운로드: https://jrsoftware.org/isdl.php",
                color=FG2,
            )
            self._finish_full_build()
            return

        # 2) ISCC 컴파일
        setup_iss = root / "installer" / "setup.iss"
        self._log_msg("  [Installer] Inno Setup 컴파일 시작...", color=ACCENT)

        self._inno_process = QProcess(self)
        self._inno_process.setWorkingDirectory(str(root / "installer"))
        self._inno_process.setProcessChannelMode(QProcess.MergedChannels)
        self._inno_process.readyReadStandardOutput.connect(self._on_inno_stdout)
        self._inno_process.finished.connect(self._on_inno_compile_finished)
        self._inno_process.start(str(iscc), [str(setup_iss)])

    def _on_inno_compile_finished(self, exit_code, exit_status):
        """Inno Setup 컴파일 완료."""
        self._inno_process = None
        root = self._get_project_root()

        if exit_code != 0:
            self._log_msg(f"  [Installer] Inno Setup 컴파일 실패 (exit: {exit_code})", color=RED)
        else:
            self._log_msg("  [Installer] Inno Setup 컴파일 OK", color=GREEN)

            output_dir = root / "installer" / "Output"
            if output_dir.exists():
                for exe in output_dir.glob("*_Setup.exe"):
                    size = exe.stat().st_size
                    self._log_msg(
                        f"  [Installer] → {exe.name} ({_format_file_size(size)})",
                        color=GREEN,
                    )

        self._advance_progress("Installer 생성 완료")
        self._finish_full_build()

    def _finish_full_build(self):
        """전체 빌드 파이프라인 최종 완료."""
        self._log_msg("━━━ 전체 빌드 완료 ━━━", color=GREEN)
        self._hide_progress()
        self._set_building(False)
        self._refresh_modules()

    # ──────────────────────────────────────────
    #  Utility
    # ──────────────────────────────────────────
    def _robust_rmtree(self, path: Path):
        """Windows 파일 잠금을 고려한 폴더 삭제."""
        import stat
        import time

        def _onerror(func, fpath, exc_info):
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)

        for attempt in range(3):
            try:
                shutil.rmtree(str(path), onerror=_onerror)
                return
            except OSError:
                if attempt < 2:
                    time.sleep(1)

        # 3회 실패 → 기존 폴더를 임시 이름으로 이동
        fallback = path.parent / f"{path.name}_old_{int(time.time())}"
        try:
            path.rename(fallback)
            self._log_msg(
                f"  [런처] 기존 폴더 삭제 불가 → {fallback.name}으로 이동",
                color=ORANGE,
            )
        except OSError as e:
            self._log_msg(f"  [런처] 기존 폴더 처리 실패: {e}", color=RED)
            raise

    # ──────────────────────────────────────────
    #  Log
    # ──────────────────────────────────────────
    def _log_msg(self, msg: str, color: str = FG2):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_panel.append(
            f"<span style='color:{FG2}'>{ts}</span> | "
            f"<span style='color:{color}'>{msg}</span>"
        )
        self._scroll_log()

    def _log_raw(self, text: str):
        """빌드 프로세스 출력을 그대로 표시 (타임스탬프 없이)."""
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._log_panel.append(
            f"<span style='color:{FG2}; font-size: 11px;'>{text}</span>"
        )
        self._scroll_log()

    def _scroll_log(self):
        sb = self._log_panel.verticalScrollBar()
        sb.setValue(sb.maximum())
