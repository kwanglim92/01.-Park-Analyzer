"""
Module Edit Dialog.

모듈 추가/편집을 위한 폼 다이얼로그.
"""
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit,
    QFileDialog, QMessageBox, QFrame, QCheckBox,
    QScrollArea, QWidget, QSizePolicy, QListWidget,
)
from PySide6.QtCore import Qt

from ui.styles import BG, BG2, BG3, FG, FG2, ACCENT, GREEN, ORANGE

# ── 라벨 고정 너비 ──
_LABEL_W = 120


class ModuleEditDialog(QDialog):
    """모듈 추가/편집 다이얼로그."""

    def __init__(self, data: dict | None = None,
                 categories: list[str] | None = None,
                 is_new: bool = False, parent=None):
        super().__init__(parent)
        self._data = data or {}
        self._is_new = is_new
        self._categories = categories or []
        self._result_data: dict | None = None

        self.setWindowTitle("모듈 추가" if is_new else "모듈 편집")
        self.setMinimumSize(520, 560)
        self.resize(560, 680)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG}; color: {FG}; }}
            QLabel {{ background: transparent; border: none; }}
            QLineEdit, QComboBox {{
                background: {BG2}; color: {FG};
                border: 1px solid {BG3}; border-radius: 5px;
                padding: 5px 8px; font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
            QLineEdit:disabled {{ color: {FG2}; background: {BG3}; }}
            QCheckBox {{ color: {FG}; font-size: 13px; spacing: 6px; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; }}
        """)

        self._build_ui()
        self._load_data()

    # ──────────────────────────────────────
    #  UI
    # ──────────────────────────────────────
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ background: {BG}; border: none; }}")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        body = QWidget()
        body.setStyleSheet(f"background: {BG};")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(16)

        # Title
        title = QLabel("모듈 추가" if self._is_new else "모듈 편집")
        title.setStyleSheet(f"color: {FG}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # ════════ 기본 정보 ════════
        sec1 = self._section("기본 정보")
        sec1_layout = sec1.layout()

        self._id_edit = QLineEdit()
        self._id_edit.setEnabled(self._is_new)
        if not self._is_new:
            self._id_edit.setToolTip("모듈 ID는 변경할 수 없습니다")
        sec1_layout.addLayout(self._row("ID", self._id_edit))

        self._name_edit = QLineEdit()
        sec1_layout.addLayout(self._row("이름", self._name_edit))

        self._category_combo = QComboBox()
        self._category_combo.setEditable(True)
        self._category_combo.lineEdit().setPlaceholderText(
            "선택 또는 직접 입력"
        )
        for cat in self._categories:
            self._category_combo.addItem(cat)
        sec1_layout.addLayout(self._row("카테고리", self._category_combo))

        r_ver_icon = QHBoxLayout()
        r_ver_icon.setSpacing(12)
        self._version_edit = QLineEdit()
        self._version_edit.setFixedWidth(100)
        r_ver_icon.addWidget(self._version_edit)
        icon_lbl = QLabel("아이콘:")
        icon_lbl.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        icon_lbl.setFixedWidth(50)
        r_ver_icon.addWidget(icon_lbl)
        self._icon_edit = QLineEdit()
        self._icon_edit.setFixedWidth(60)
        r_ver_icon.addWidget(self._icon_edit)
        r_ver_icon.addStretch()
        sec1_layout.addLayout(self._row("버전", r_ver_icon))

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("모듈 설명을 입력하세요...")
        self._desc_edit.setFixedHeight(90)
        self._desc_edit.setStyleSheet(
            f"QTextEdit {{ background: {BG}; color: {FG}; border: 1px solid {BG3}; "
            f"border-radius: 5px; padding: 6px; font-size: 12px; }}"
        )
        sec1_layout.addLayout(self._row("설명", self._desc_edit))

        layout.addWidget(sec1)

        # ════════ 경로 & 빌드 ════════
        sec2 = self._section("경로 & 빌드")
        sec2_layout = sec2.layout()

        # -- 빌드 방식 (최상단) --
        self._method_combo = QComboBox()
        self._method_combo.addItems(["pyinstaller", "copy", "copy_dir", "none"])
        self._method_combo.currentTextChanged.connect(self._on_method_changed)
        sec2_layout.addLayout(self._row("빌드 방식", self._method_combo))

        # -- 개발 경로 (공통) --
        dev_row = QHBoxLayout()
        dev_row.setSpacing(6)
        self._dev_path_edit = QLineEdit()
        self._dev_path_edit.setPlaceholderText("C:/Users/.../MyProject")
        dev_row.addWidget(self._dev_path_edit, 1)
        browse_btn = QPushButton("찾아보기")
        browse_btn.setFixedHeight(30)
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.setStyleSheet(
            f"QPushButton {{ background: {BG3}; color: {FG}; border: none; "
            f"border-radius: 5px; padding: 0 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {ACCENT}; color: {BG}; }}"
        )
        browse_btn.clicked.connect(self._browse_dev_path)
        dev_row.addWidget(browse_btn)
        sec2_layout.addLayout(self._row("개발 경로", dev_row))

        # -- 진입점 (공통, 자동 동기화) --
        entry_row = QHBoxLayout()
        entry_row.setSpacing(12)
        self._entry_dev_edit = QLineEdit()
        self._entry_dev_edit.setPlaceholderText("main.py")
        entry_row.addWidget(self._entry_dev_edit, 1)
        prod_lbl = QLabel("배포:")
        prod_lbl.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        prod_lbl.setFixedWidth(36)
        entry_row.addWidget(prod_lbl)
        self._entry_prod_edit = QLineEdit()
        self._entry_prod_edit.setPlaceholderText("main.exe")
        entry_row.addWidget(self._entry_prod_edit, 1)
        sec2_layout.addLayout(self._row("진입점", entry_row))

        # ── PyInstaller 전용 ──
        self._pi_container = QWidget()
        self._pi_container.setStyleSheet(f"background: transparent;")
        pi_layout = QVBoxLayout(self._pi_container)
        pi_layout.setContentsMargins(0, 0, 0, 0)
        pi_layout.setSpacing(8)

        pi_name_row = QHBoxLayout()
        pi_name_row.setSpacing(12)
        self._build_entry_edit = QLineEdit()
        self._build_entry_edit.setPlaceholderText("main.py")
        pi_name_row.addWidget(self._build_entry_edit, 1)
        bname_lbl = QLabel("빌드 이름:")
        bname_lbl.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        bname_lbl.setFixedWidth(70)
        pi_name_row.addWidget(bname_lbl)
        self._build_name_edit = QLineEdit()
        self._build_name_edit.setPlaceholderText("MyTool")
        self._build_name_edit.textChanged.connect(self._sync_entry_prod_from_build_name)
        pi_name_row.addWidget(self._build_name_edit, 1)
        pi_layout.addLayout(self._row("빌드 진입점", pi_name_row))

        opt_row = QHBoxLayout()
        opt_row.setSpacing(20)
        self._onefile_check = QCheckBox("--onefile")
        self._windowed_check = QCheckBox("--windowed")
        opt_row.addWidget(self._onefile_check)
        opt_row.addWidget(self._windowed_check)
        opt_row.addStretch()
        pi_layout.addLayout(self._row("옵션", opt_row))

        self._hidden_edit = QLineEdit()
        self._hidden_edit.setPlaceholderText("core, ui, utils  (콤마 구분)")
        pi_layout.addLayout(self._row("Hidden Imports", self._hidden_edit))

        self._adddata_edit = QLineEdit()
        self._adddata_edit.setPlaceholderText("config;config, assets;assets  (콤마 구분)")
        pi_layout.addLayout(self._row("Add Data", self._adddata_edit))

        pi_hint = QLabel(
            "  빌드 이름 변경 시 배포 진입점(entry_prod)이 자동 동기화됩니다."
        )
        pi_hint.setStyleSheet(f"color: {FG2}; font-size: 11px; border: none;")
        pi_hint.setWordWrap(True)
        pi_layout.addWidget(pi_hint)

        sec2_layout.addWidget(self._pi_container)

        # ── Copy 전용 ──
        self._copy_container = QWidget()
        self._copy_container.setStyleSheet(f"background: transparent;")
        cp_layout = QVBoxLayout(self._copy_container)
        cp_layout.setContentsMargins(0, 0, 0, 0)
        cp_layout.setSpacing(8)

        cp_file_row = QHBoxLayout()
        cp_file_row.setSpacing(6)
        self._copy_from_edit = QLineEdit()
        self._copy_from_edit.setPlaceholderText("파일명 (예: VMOptionGenerator.exe)")
        cp_file_row.addWidget(self._copy_from_edit, 1)
        cp_browse_btn = QPushButton(".exe 찾기")
        cp_browse_btn.setFixedHeight(30)
        cp_browse_btn.setCursor(Qt.PointingHandCursor)
        cp_browse_btn.setStyleSheet(
            f"QPushButton {{ background: {BG3}; color: {FG}; border: none; "
            f"border-radius: 5px; padding: 0 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {ACCENT}; color: {BG}; }}"
        )
        cp_browse_btn.clicked.connect(self._browse_exe_file)
        cp_file_row.addWidget(cp_browse_btn)
        cp_layout.addLayout(self._row("복사 원본", cp_file_row))

        cp_hint = QLabel(
            "  .exe 선택 시 개발 경로·진입점이 자동 설정됩니다."
        )
        cp_hint.setStyleSheet(f"color: {FG2}; font-size: 11px; border: none;")
        cp_hint.setWordWrap(True)
        cp_layout.addWidget(cp_hint)

        sec2_layout.addWidget(self._copy_container)

        # ── Copy Dir 전용 ──
        self._copydir_container = QWidget()
        self._copydir_container.setStyleSheet(f"background: transparent;")
        cd_layout = QVBoxLayout(self._copydir_container)
        cd_layout.setContentsMargins(0, 0, 0, 0)
        cd_layout.setSpacing(8)

        cd_file_row = QHBoxLayout()
        cd_file_row.setSpacing(6)
        self._copydir_from_edit = QLineEdit()
        self._copydir_from_edit.setPlaceholderText(
            "하위 폴더 (기본: . = dev_path 전체)"
        )
        cd_file_row.addWidget(self._copydir_from_edit, 1)
        cd_browse_btn = QPushButton(".exe 찾기")
        cd_browse_btn.setFixedHeight(30)
        cd_browse_btn.setCursor(Qt.PointingHandCursor)
        cd_browse_btn.setStyleSheet(
            f"QPushButton {{ background: {BG3}; color: {FG}; border: none; "
            f"border-radius: 5px; padding: 0 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {ACCENT}; color: {BG}; }}"
        )
        cd_browse_btn.clicked.connect(self._browse_exe_for_copydir)
        cd_file_row.addWidget(cd_browse_btn)
        cd_layout.addLayout(self._row("복사 원본 폴더", cd_file_row))

        cd_hint = QLabel(
            "  exe + _internal/ 폴더를 통째로 modules/<id>/로 복사합니다.\n"
            "  .exe 선택 시 개발 경로·진입점·복사 폴더가 자동 설정됩니다."
        )
        cd_hint.setStyleSheet(f"color: {FG2}; font-size: 11px; border: none;")
        cd_hint.setWordWrap(True)
        cd_layout.addWidget(cd_hint)

        sec2_layout.addWidget(self._copydir_container)

        layout.addWidget(sec2)

        # ════════ 문서 관리 ════════
        sec4 = self._section("문서 관리")
        sec4_layout = sec4.layout()

        self._manual_wiki_edit = QLineEdit()
        self._manual_wiki_edit.setPlaceholderText("https://mc-wiki...")
        sec4_layout.addLayout(self._row("MC-Wiki URL", self._manual_wiki_edit))

        self._manual_sp_edit = QLineEdit()
        self._manual_sp_edit.setPlaceholderText("https://sharepoint...")
        sec4_layout.addLayout(self._row("SharePoint URL", self._manual_sp_edit))

        cl_lbl = QLabel("변경사항:")
        cl_lbl.setStyleSheet(f"color: {FG2}; font-size: 12px; border: none;")
        sec4_layout.addWidget(cl_lbl)

        _item_style = (
            f"background: {BG2}; color: {FG}; border: 1px solid {BG3}; "
            f"border-radius: 5px; padding: 4px; font-size: 12px;"
        )

        cl_body = QHBoxLayout()
        cl_body.setSpacing(8)

        # 좌측: 버전 리스트 + 추가/삭제 버튼
        cl_left = QVBoxLayout()
        cl_left.setSpacing(4)

        self._cl_list = QListWidget()
        self._cl_list.setFixedWidth(120)
        self._cl_list.setStyleSheet(
            f"QListWidget {{ {_item_style} }}"
            f"QListWidget::item {{ padding: 4px; }}"
            f"QListWidget::item:selected {{ background: {ACCENT}; color: {BG}; border-radius: 3px; }}"
        )
        self._cl_list.currentRowChanged.connect(self._on_cl_selected)
        cl_left.addWidget(self._cl_list, 1)

        cl_btn_row = QHBoxLayout()
        cl_btn_row.setSpacing(4)
        _cl_btn_style = (
            f"QPushButton {{ background: {BG2}; color: {FG}; border: 1px solid {BG3}; "
            f"border-radius: 4px; padding: 2px 8px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {BG3}; border-color: {ACCENT}; }}"
        )
        self._cl_ver_input = QLineEdit()
        self._cl_ver_input.setPlaceholderText("v1.0.0")
        self._cl_ver_input.setFixedWidth(60)
        self._cl_ver_input.setStyleSheet(f"{_item_style}")
        cl_btn_row.addWidget(self._cl_ver_input)

        cl_add_btn = QPushButton("+")
        cl_add_btn.setFixedSize(24, 24)
        cl_add_btn.setCursor(Qt.PointingHandCursor)
        cl_add_btn.setStyleSheet(_cl_btn_style)
        cl_add_btn.clicked.connect(self._on_cl_add)
        cl_btn_row.addWidget(cl_add_btn)

        cl_del_btn = QPushButton("−")
        cl_del_btn.setFixedSize(24, 24)
        cl_del_btn.setCursor(Qt.PointingHandCursor)
        cl_del_btn.setStyleSheet(_cl_btn_style)
        cl_del_btn.clicked.connect(self._on_cl_delete)
        cl_btn_row.addWidget(cl_del_btn)

        cl_left.addLayout(cl_btn_row)
        cl_body.addLayout(cl_left)

        # 우측: 선택된 버전의 내용 편집
        self._cl_content_edit = QTextEdit()
        self._cl_content_edit.setPlaceholderText("변경 내용을 입력하세요...")
        self._cl_content_edit.setStyleSheet(
            f"QTextEdit {{ {_item_style} }}"
            f"QTextEdit:focus {{ border-color: {ACCENT}; }}"
        )
        self._cl_content_edit.textChanged.connect(self._on_cl_content_changed)
        cl_body.addWidget(self._cl_content_edit, 1)

        sec4_layout.addLayout(cl_body)

        # changelog 내부 데이터
        self._cl_data: list[dict] = []
        self._cl_updating = False

        layout.addWidget(sec4)
        layout.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # ════════ 하단 버튼 (스크롤 밖) ════════
        btn_frame = QFrame()
        btn_frame.setStyleSheet(
            f"QFrame {{ background: {BG}; border-top: 1px solid {BG3}; }}"
        )
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(24, 12, 24, 16)
        btn_layout.setSpacing(10)

        # 경로 상태 표시
        self._status_lbl = QLabel()
        self._status_lbl.setStyleSheet(f"font-size: 12px;")
        btn_layout.addWidget(self._status_lbl)
        btn_layout.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.setFixedSize(90, 34)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {BG2}; color: {FG}; border: 1px solid {BG3}; "
            f"border-radius: 6px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {BG3}; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("저장")
        save_btn.setFixedSize(90, 34)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: {BG}; border: none; "
            f"border-radius: 6px; font-size: 13px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #7ba8e8; }}"
        )
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        outer.addWidget(btn_frame)

    # ──────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────
    def _section(self, title: str) -> QFrame:
        """카드형 섹션 프레임 생성."""
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {BG2}; border: 1px solid {BG3}; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(8)

        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 13px; font-weight: bold; border: none;"
        )
        layout.addWidget(lbl)
        return frame

    def _row(self, label_text: str, field) -> QHBoxLayout:
        """라벨 + 필드를 고정 너비 라벨로 정렬된 행으로 반환."""
        row = QHBoxLayout()
        row.setSpacing(10)

        lbl = QLabel(f"{label_text}:")
        lbl.setFixedWidth(_LABEL_W)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl.setStyleSheet(f"color: {FG2}; font-size: 12px; border: none;")
        row.addWidget(lbl)

        if isinstance(field, QHBoxLayout):
            row.addLayout(field, 1)
        else:
            row.addWidget(field, 1)
        return row

    # ──────────────────────────────────────
    #  Data
    # ──────────────────────────────────────
    def _load_data(self):
        d = self._data
        self._id_edit.setText(d.get("id", ""))
        self._name_edit.setText(d.get("name", ""))
        self._version_edit.setText(d.get("version", "1.0.0"))
        self._desc_edit.setPlainText(d.get("description", ""))
        self._icon_edit.setText(d.get("icon", ""))
        self._dev_path_edit.setText(d.get("dev_path", ""))
        self._entry_dev_edit.setText(d.get("entry_dev", "main.py"))
        self._entry_prod_edit.setText(d.get("entry_prod", "main.exe"))

        cat = d.get("category", "")
        idx = self._category_combo.findText(cat)
        if idx >= 0:
            self._category_combo.setCurrentIndex(idx)
        elif cat:
            self._category_combo.setEditText(cat)

        build = d.get("build", {})
        method = build.get("method", "pyinstaller")
        idx = self._method_combo.findText(method)
        if idx >= 0:
            self._method_combo.setCurrentIndex(idx)

        self._build_entry_edit.setText(build.get("entry", "main.py"))
        self._build_name_edit.setText(build.get("build_name", ""))
        self._onefile_check.setChecked(build.get("onefile", True))
        self._windowed_check.setChecked(build.get("windowed", True))

        hidden = build.get("hidden_imports", [])
        self._hidden_edit.setText(", ".join(hidden))

        add_data = build.get("add_data", [])
        self._adddata_edit.setText(", ".join(add_data))

        self._copy_from_edit.setText(build.get("copy_from", ""))
        self._copydir_from_edit.setText(
            build.get("copy_from", ".") if method == "copy_dir" else "."
        )

        # 문서 관리
        self._manual_wiki_edit.setText(d.get("manual_wiki", d.get("manual_url", "")))
        self._manual_sp_edit.setText(d.get("manual_sharepoint", ""))
        from core.module_manager import ModuleInfo
        changelog = ModuleInfo._parse_changelog(d.get("changelog", []))
        self._load_changelog(changelog)

        self._on_method_changed(method)
        self._update_status()

        # dev_path 변경 시 상태 자동 갱신
        self._dev_path_edit.textChanged.connect(self._update_status)

    def _on_method_changed(self, method: str):
        self._pi_container.setVisible(method == "pyinstaller")
        self._copy_container.setVisible(method == "copy")
        self._copydir_container.setVisible(method == "copy_dir")

        # 방식 변경 시 진입점 자동 동기화
        if method == "pyinstaller":
            self._sync_entry_prod_from_build_name()
        elif method == "none":
            # none이면 진입점 기본값
            if not self._entry_dev_edit.text().strip():
                self._entry_dev_edit.setText("main.py")
            if not self._entry_prod_edit.text().strip():
                self._entry_prod_edit.setText("main.exe")

    def _sync_entry_prod_from_build_name(self):
        """PyInstaller 빌드 이름 → entry_prod 자동 동기화."""
        if self._method_combo.currentText() != "pyinstaller":
            return
        build_name = self._build_name_edit.text().strip()
        if build_name:
            self._entry_prod_edit.setText(f"{build_name}.exe")

    def _update_status(self):
        dev = self._dev_path_edit.text().strip()
        if dev and Path(dev).exists():
            self._status_lbl.setText("Ready")
            self._status_lbl.setStyleSheet(f"color: {GREEN}; font-size: 12px;")
        elif dev:
            self._status_lbl.setText("경로 없음")
            self._status_lbl.setStyleSheet(f"color: {ORANGE}; font-size: 12px;")
        else:
            self._status_lbl.setText("")

    # ── Changelog 슬롯 ──
    def _on_cl_selected(self, row):
        """버전 리스트 선택 변경 → 우측 내용 갱신."""
        if self._cl_updating or row < 0 or row >= len(self._cl_data):
            if row < 0:
                self._cl_content_edit.setPlainText("")
            return
        self._cl_updating = True
        self._cl_content_edit.setPlainText(self._cl_data[row].get("content", ""))
        self._cl_updating = False

    def _on_cl_content_changed(self):
        """우측 내용 편집 → 데이터 반영."""
        if self._cl_updating:
            return
        row = self._cl_list.currentRow()
        if 0 <= row < len(self._cl_data):
            self._cl_data[row]["content"] = self._cl_content_edit.toPlainText()

    def _on_cl_add(self):
        """버전 추가."""
        ver = self._cl_ver_input.text().strip()
        if not ver:
            ver = f"v{self._version_edit.text().strip() or '1.0.0'}"
        self._cl_data.append({"version": ver, "content": ""})
        self._cl_list.addItem(ver)
        self._cl_list.setCurrentRow(self._cl_list.count() - 1)
        self._cl_ver_input.clear()

    def _on_cl_delete(self):
        """선택된 버전 삭제."""
        row = self._cl_list.currentRow()
        if row < 0:
            return
        self._cl_data.pop(row)
        self._cl_list.takeItem(row)

    def _load_changelog(self, changelog: list[dict]):
        """changelog 데이터를 UI에 로드."""
        self._cl_updating = True
        self._cl_data = [dict(e) for e in changelog]
        self._cl_list.clear()
        for entry in self._cl_data:
            self._cl_list.addItem(entry.get("version", ""))
        self._cl_content_edit.clear()
        self._cl_updating = False
        if self._cl_data:
            self._cl_list.setCurrentRow(0)

    def _browse_dev_path(self):
        path = QFileDialog.getExistingDirectory(
            self, "개발 경로 선택", self._dev_path_edit.text()
        )
        if path:
            self._dev_path_edit.setText(path.replace("\\", "/"))

    def _browse_exe_file(self):
        """exe 파일 선택 → dev_path, copy_from, entry_prod, entry_dev 자동 설정."""
        start_dir = self._dev_path_edit.text() or ""
        file_path, _ = QFileDialog.getOpenFileName(
            self, ".exe 파일 선택", start_dir,
            "실행 파일 (*.exe);;모든 파일 (*)",
        )
        if not file_path:
            return

        file_path = Path(file_path)
        folder = str(file_path.parent).replace("\\", "/")
        filename = file_path.name

        # 자동 채우기
        self._dev_path_edit.setText(folder)
        self._copy_from_edit.setText(filename)
        self._entry_prod_edit.setText(filename)
        self._entry_dev_edit.setText(filename)

    def _browse_exe_for_copydir(self):
        """exe 파일 선택 → dev_path(부모), entry_dev/prod, copy_from 자동 설정."""
        start_dir = self._dev_path_edit.text() or ""
        file_path, _ = QFileDialog.getOpenFileName(
            self, ".exe 파일 선택", start_dir,
            "실행 파일 (*.exe);;모든 파일 (*)",
        )
        if not file_path:
            return

        file_path = Path(file_path)
        folder = str(file_path.parent).replace("\\", "/")
        filename = file_path.name

        self._dev_path_edit.setText(folder)
        self._entry_dev_edit.setText(filename)
        self._entry_prod_edit.setText(filename)
        self._copydir_from_edit.setText(".")

    # ──────────────────────────────────────
    #  Save
    # ──────────────────────────────────────
    def _on_save(self):
        module_id = self._id_edit.text().strip()
        name = self._name_edit.text().strip()

        if not module_id:
            QMessageBox.warning(self, "입력 오류", "모듈 ID를 입력하세요.")
            return
        if not name:
            QMessageBox.warning(self, "입력 오류", "모듈 이름을 입력하세요.")
            return

        data = {
            "id": module_id,
            "name": name,
            "category": self._category_combo.currentText().strip() or "기타",
            "version": self._version_edit.text().strip() or "1.0.0",
            "description": self._desc_edit.toPlainText().strip(),
            "icon": self._icon_edit.text().strip(),
            "dev_path": self._dev_path_edit.text().strip(),
            "entry_dev": self._entry_dev_edit.text().strip() or "main.py",
            "entry_prod": self._entry_prod_edit.text().strip() or "main.exe",
            "changelog": [e for e in self._cl_data if e.get("version") or e.get("content")],
            "manual_wiki": self._manual_wiki_edit.text().strip(),
            "manual_sharepoint": self._manual_sp_edit.text().strip(),
        }

        method = self._method_combo.currentText()
        build = {"method": method}

        if method == "pyinstaller":
            build["entry"] = self._build_entry_edit.text().strip() or "main.py"
            build["build_name"] = self._build_name_edit.text().strip() or module_id
            build["onefile"] = self._onefile_check.isChecked()
            build["windowed"] = self._windowed_check.isChecked()

            hidden_text = self._hidden_edit.text().strip()
            build["hidden_imports"] = (
                [h.strip() for h in hidden_text.split(",") if h.strip()]
                if hidden_text else []
            )

            adddata_text = self._adddata_edit.text().strip()
            build["add_data"] = (
                [a.strip() for a in adddata_text.split(",") if a.strip()]
                if adddata_text else []
            )
        elif method == "copy":
            build["copy_from"] = self._copy_from_edit.text().strip()
        elif method == "copy_dir":
            build["copy_from"] = self._copydir_from_edit.text().strip() or "."

        data["build"] = build
        self._result_data = data
        self.accept()

    def get_data(self) -> dict | None:
        """다이얼로그 결과 데이터 반환. 취소 시 None."""
        return self._result_data
