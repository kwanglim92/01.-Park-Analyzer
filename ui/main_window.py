"""
Launcher Main Window.

좌측: 검색 바 + Pinned 섹션 + Module 가로 막대 그래프
우측: 선택된 Module의 Tool 카드
하단: 고정 높이 로그 패널
"""
import webbrowser
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QTextEdit,
    QSizePolicy, QLineEdit, QDialog, QDialogButtonBox, QMessageBox,
    QListWidget,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QCursor

from core.module_manager import ModuleManager, ModuleInfo
from core.settings import load_settings, save_settings
from ui.styles import (
    BG, BG2, BG3, FG, FG2, ACCENT, GREEN, RED, ORANGE, PURPLE, TEAL,
)

# ── Bar Colors ──
_BAR_COLORS = [ACCENT, PURPLE, TEAL, GREEN, ORANGE, "#f5c2e7", "#fab387"]
_PINNED_KEY = "⭐ Pinned"


# ═══════════════════════════════════════════════════
#  Release Notes Dialog
# ═══════════════════════════════════════════════════
class ChangelogDialog(QDialog):
    """변경사항 팝업 — 좌측 버전 리스트 + 우측 내용 표시."""

    def __init__(self, tool_name: str, changelog: list[dict], parent=None):
        super().__init__(parent)
        self._changelog = changelog
        self.setWindowTitle(f"변경사항 — {tool_name}")
        self.setMinimumSize(520, 340)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG}; color: {FG}; }}
            QLabel {{ background: transparent; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel(f"📋 {tool_name}")
        title.setStyleSheet(f"color: {FG}; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        if not changelog:
            empty = QLabel("변경사항이 없습니다.")
            empty.setStyleSheet(f"color: {FG2}; font-size: 13px;")
            layout.addWidget(empty)
        else:
            body = QHBoxLayout()
            body.setSpacing(12)

            # 좌측: 버전 리스트
            self._ver_list = QListWidget()
            self._ver_list.setFixedWidth(120)
            self._ver_list.setStyleSheet(
                f"QListWidget {{ background: {BG2}; color: {FG}; border: 1px solid {BG3}; "
                f"border-radius: 5px; font-size: 12px; }}"
                f"QListWidget::item {{ padding: 6px; }}"
                f"QListWidget::item:selected {{ background: {ACCENT}; color: {BG}; border-radius: 3px; }}"
            )
            for entry in changelog:
                self._ver_list.addItem(entry.get("version", ""))
            self._ver_list.currentRowChanged.connect(self._on_ver_selected)
            body.addWidget(self._ver_list)

            # 우측: 내용 표시
            self._content_view = QTextEdit()
            self._content_view.setReadOnly(True)
            self._content_view.setStyleSheet(
                f"QTextEdit {{ background: {BG2}; color: {FG}; border: 1px solid {BG3}; "
                f"border-radius: 5px; padding: 8px; font-size: 13px; }}"
            )
            body.addWidget(self._content_view, 1)

            layout.addLayout(body, 1)

            # 첫 번째 항목 선택
            self._ver_list.setCurrentRow(0)

        # Close button
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.close)
        btn_box.setStyleSheet(f"""
            QPushButton {{
                background: {BG2}; color: {FG}; border: 1px solid {BG3};
                border-radius: 4px; padding: 6px 16px;
            }}
            QPushButton:hover {{ background: {BG3}; }}
        """)
        layout.addWidget(btn_box)

    def _on_ver_selected(self, row):
        if 0 <= row < len(self._changelog):
            self._content_view.setPlainText(self._changelog[row].get("content", ""))


# ═══════════════════════════════════════════════════
#  Category Bar (가로 막대)
# ═══════════════════════════════════════════════════
class CategoryBar(QFrame):
    """클릭 가능한 카테고리 가로 막대."""
    clicked = Signal(str)

    def __init__(self, category: str, count: int, max_count: int,
                 color: str, parent=None):
        super().__init__(parent)
        self._category = category
        self._color = color
        self._selected = False
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        name = QLabel(category)
        name.setStyleSheet(f"color: {FG}; font-size: 12px; font-weight: bold;")
        name.setFixedWidth(110)
        layout.addWidget(name)

        # Bar fill
        bar_bg = QFrame()
        bar_bg.setFixedHeight(22)
        bar_bg.setStyleSheet(f"background: {BG3}; border-radius: 4px;")
        bar_bg_layout = QHBoxLayout(bar_bg)
        bar_bg_layout.setContentsMargins(0, 0, 0, 0)
        bar_bg_layout.setSpacing(0)

        ratio = count / max(max_count, 1)
        fill_pct = max(int(ratio * 100), 12)

        bar_fill = QFrame()
        bar_fill.setFixedHeight(22)
        bar_fill.setStyleSheet(f"background: {color}; border-radius: 4px;")
        bar_bg_layout.addWidget(bar_fill, fill_pct)
        bar_bg_layout.addStretch(100 - fill_pct)

        layout.addWidget(bar_bg, 1)

        badge = QLabel(f" {count} ")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(28, 22)
        badge.setStyleSheet(
            f"background: {color}; color: {BG}; font-size: 11px; "
            f"font-weight: bold; border-radius: 4px;"
        )
        layout.addWidget(badge)

        self._apply_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()

    def _apply_style(self):
        border = self._color if self._selected else BG3
        bg = BG2 if self._selected else BG
        self.setStyleSheet(
            f"CategoryBar {{ background: {bg}; border: 1px solid {border}; "
            f"border-radius: 8px; }}"
            f"CategoryBar QLabel {{ background: transparent; border: none; }}"
            f"CategoryBar QFrame {{ border: none; }}"
        )

    def enterEvent(self, event):
        if not self._selected:
            self.setStyleSheet(
                f"CategoryBar {{ background: {BG2}; "
                f"border: 1px solid {BG3}; border-radius: 8px; }}"
                f"CategoryBar QLabel {{ background: transparent; border: none; }}"
                f"CategoryBar QFrame {{ border: none; }}"
            )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.clicked.emit(self._category)
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════════
#  Module Card
# ═══════════════════════════════════════════════════
class ModuleCard(QFrame):
    """분석 모듈 카드."""
    pin_toggled = Signal(str, bool)  # (module_id, is_pinned)

    _STYLE_N = f"""
        ModuleCard {{ background: {BG2}; border: 1px solid {BG3}; border-radius: 10px; }}
        ModuleCard QLabel {{ background: transparent; border: none; }}
    """
    _STYLE_H = f"""
        ModuleCard {{ background: {BG2}; border: 1px solid {ACCENT}; border-radius: 10px; }}
        ModuleCard QLabel {{ background: transparent; border: none; }}
    """

    def __init__(self, module: ModuleInfo, manager: ModuleManager,
                 color: str, is_pinned: bool = False,
                 log_callback=None, parent=None):
        super().__init__(parent)
        self._module = module
        self._manager = manager
        self._color = color
        self._pinned = is_pinned
        self._log = log_callback or (lambda msg: None)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(140)
        self.setStyleSheet(self._STYLE_N)
        self._build_ui()

    def enterEvent(self, e):
        self.setStyleSheet(self._STYLE_H)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.setStyleSheet(self._STYLE_N)
        super().leaveEvent(e)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(16, 12, 16, 12)

        # ── Row 1: Accent + Name + Pin + Version ──
        r1 = QHBoxLayout()
        r1.setSpacing(10)

        accent = QFrame()
        accent.setFixedSize(4, 32)
        accent.setStyleSheet(
            f"background: {self._color}; border-radius: 2px; border: none;"
        )
        r1.addWidget(accent)

        name_lbl = QLabel(self._module.name)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(f"color: {FG}; font-size: 15px; font-weight: bold;")
        r1.addWidget(name_lbl, 1)

        # Pin button
        self._pin_btn = QPushButton("⭐" if self._pinned else "☆")
        self._pin_btn.setFixedSize(28, 28)
        self._pin_btn.setCursor(Qt.PointingHandCursor)
        self._pin_btn.setToolTip("즐겨찾기 토글")
        self._pin_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"font-size: 16px; color: {ORANGE if self._pinned else FG2}; }}"
            f"QPushButton:hover {{ color: {ORANGE}; }}"
        )
        self._pin_btn.clicked.connect(self._toggle_pin)
        r1.addWidget(self._pin_btn)

        ver_lbl = QLabel(f"v{self._module.version}")
        ver_lbl.setStyleSheet(f"color: {FG2}; font-size: 10px;")
        ver_lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
        r1.addWidget(ver_lbl)

        layout.addLayout(r1)

        # ── Row 2: Description ──
        desc = QLabel(self._module.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {FG2}; font-size: 12px; padding-left: 14px;")
        layout.addWidget(desc, 1)

        # ── Row 3: Status + Buttons ──
        r3 = QHBoxLayout()
        r3.setContentsMargins(14, 0, 0, 0)
        r3.setSpacing(6)

        self._dot = QLabel()
        self._dot.setFixedSize(8, 8)
        r3.addWidget(self._dot)

        self._status = QLabel()
        self._status.setStyleSheet("font-size: 11px;")
        r3.addWidget(self._status)

        wiki_ok = "O" if self._module.manual_wiki else "X"
        sp_ok = "O" if self._module.manual_sharepoint else "X"
        wiki_color = GREEN if self._module.manual_wiki else RED
        sp_color = GREEN if self._module.manual_sharepoint else RED
        doc_lbl = QLabel()
        doc_lbl.setText(
            f'MC-Wiki: <span style="color:{wiki_color}">{wiki_ok}</span>'
            f' | SP: <span style="color:{sp_color}">{sp_ok}</span>'
        )
        doc_lbl.setTextFormat(Qt.RichText)
        doc_lbl.setStyleSheet(f"color: {FG2}; font-size: 10px;")
        r3.addWidget(doc_lbl)

        r3.addStretch()

        # Changelog button
        changelog_btn = QPushButton("Log")
        changelog_btn.setFixedHeight(30)
        changelog_btn.setCursor(Qt.PointingHandCursor)
        changelog_btn.setToolTip("Release Notes")
        changelog_btn.setStyleSheet(
            f"QPushButton {{ background: {BG3}; color: {FG2}; border: none; "
            f"border-radius: 4px; font-size: 12px; padding: 4px 12px; }}"
            f"QPushButton:hover {{ background: {ACCENT}; color: {BG}; }}"
        )
        changelog_btn.clicked.connect(self._show_changelog)
        r3.addWidget(changelog_btn)

        # Manual link button
        manual_btn = QPushButton("Manual")
        manual_btn.setFixedHeight(30)
        manual_btn.setCursor(Qt.PointingHandCursor)
        manual_btn.setToolTip("웹 매뉴얼 열기")
        manual_btn.setStyleSheet(
            f"QPushButton {{ background: {BG3}; color: {FG2}; border: none; "
            f"border-radius: 4px; font-size: 12px; padding: 4px 12px; }}"
            f"QPushButton:hover {{ background: {ACCENT}; color: {BG}; }}"
        )
        manual_btn.clicked.connect(self._open_manual)
        r3.addWidget(manual_btn)

        # Launch button
        self._btn = QPushButton("▶  Run")
        self._btn.setFixedHeight(30)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: {BG}; border: none; "
            f"border-radius: 4px; font-size: 12px; font-weight: bold; "
            f"padding: 4px 14px; }}"
            f"QPushButton:hover {{ background: #7ba8e8; }}"
            f"QPushButton:disabled {{ background: {BG3}; color: {FG2}; }}"
        )
        self._btn.clicked.connect(self._on_launch)
        r3.addWidget(self._btn)

        layout.addLayout(r3)
        self._refresh()

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self._pin_btn.setText("⭐" if self._pinned else "☆")
        self._pin_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"font-size: 16px; color: {ORANGE if self._pinned else FG2}; }}"
            f"QPushButton:hover {{ color: {ORANGE}; }}"
        )
        self.pin_toggled.emit(self._module.id, self._pinned)

    def _show_changelog(self):
        dlg = ChangelogDialog(self._module.name, self._module.changelog, self)
        dlg.exec()

    def _open_manual(self):
        wiki = self._module.manual_wiki
        sp = self._module.manual_sharepoint

        if wiki and sp:
            msg = QMessageBox(self)
            msg.setWindowTitle("매뉴얼")
            msg.setText(f"{self._module.name}\n\n열고 싶은 매뉴얼을 선택하세요.")
            wiki_btn = msg.addButton("MC-Wiki", QMessageBox.ActionRole)
            sp_btn = msg.addButton("SharePoint", QMessageBox.ActionRole)
            both_btn = msg.addButton("둘 다 열기", QMessageBox.ActionRole)
            msg.addButton("취소", QMessageBox.RejectRole)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked == wiki_btn:
                webbrowser.open(wiki)
                self._log(f"📖 {self._module.name} MC-Wiki 매뉴얼 열기")
            elif clicked == sp_btn:
                webbrowser.open(sp)
                self._log(f"📖 {self._module.name} SharePoint 매뉴얼 열기")
            elif clicked == both_btn:
                webbrowser.open(wiki)
                webbrowser.open(sp)
                self._log(f"📖 {self._module.name} 매뉴얼 열기 (MC-Wiki + SharePoint)")
        elif wiki:
            webbrowser.open(wiki)
            self._log(f"📖 {self._module.name} MC-Wiki 매뉴얼 열기")
        elif sp:
            webbrowser.open(sp)
            self._log(f"📖 {self._module.name} SharePoint 매뉴얼 열기")
        else:
            QMessageBox.information(
                self, "매뉴얼",
                f"{self._module.name}\n\n아직 등록된 매뉴얼 주소가 없습니다.",
            )

    def _refresh(self):
        if self._module.is_running:
            c, t = ACCENT, "실행 중"
            self._btn.setEnabled(False)
        elif self._module.is_available:
            c, t = GREEN, "Ready"
            self._btn.setEnabled(True)
        else:
            c, t = ORANGE, "경로 없음"
            self._btn.setEnabled(False)
        self._dot.setStyleSheet(f"background: {c}; border-radius: 4px;")
        self._status.setText(t)
        self._status.setStyleSheet(f"color: {c}; font-size: 11px;")

    def _on_launch(self):
        ok = self._manager.launch(self._module)
        if ok:
            self._log(f"✅ {self._module.name} 실행")
        else:
            self._log(f"❌ {self._module.name} 실행 실패")
        self._refresh()

    def refresh_status(self):
        self._refresh()


# ═══════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self._settings = load_settings()
        self._display_name = self._settings.get("app", {}).get(
            "display_name", "Integrated Analyzer"
        )
        self.setWindowTitle(f"🔬 {self._display_name}")
        self.setMinimumSize(900, 540)
        self._manager = ModuleManager()
        self._cards: list[ModuleCard] = []
        self._bars: dict[str, CategoryBar] = {}
        self._selected_cat: str = ""
        self._cat_colors: dict[str, str] = {}
        self._pinned_ids: list[str] = self._settings.get("pinned", [])

        self._build_ui()
        self._discover_modules()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_all)
        self._timer.start(3000)

        w = self._settings.get("window", {}).get("width", 1100)
        h = self._settings.get("window", {}).get("height", 700)
        self.resize(w, h)

    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet(f"background: {BG}; color: {FG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(24, 16, 24, 12)
        root.setSpacing(0)

        # ══════════════════════════════════════
        #  HEADER
        # ══════════════════════════════════════
        hdr = QHBoxLayout()
        title = QLabel(f"🔬 {self._display_name}")
        title.setStyleSheet(f"color: {FG}; font-size: 26px; font-weight: bold;")
        hdr.addWidget(title)
        hdr.addStretch()
        ver = self._settings.get("app", {}).get("version", "1.0.0")
        ver_lbl = QLabel(f"v{ver}")
        ver_lbl.setStyleSheet(f"color: {FG2}; font-size: 12px;")
        hdr.addWidget(ver_lbl)
        root.addLayout(hdr)
        root.addSpacing(16)

        # ══════════════════════════════════════
        #  BODY — Left (search+bars) + Right (cards)
        # ══════════════════════════════════════
        body = QHBoxLayout()
        body.setSpacing(20)

        # ── Left Panel ──
        left = QWidget()
        left.setFixedWidth(320)
        left.setStyleSheet(f"background: {BG};")
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(8)

        # Summary
        self._summary_label = QLabel()
        self._summary_label.setStyleSheet(
            f"color: {FG2}; font-size: 12px; padding: 2px 0;"
        )
        left_vbox.addWidget(self._summary_label)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Tool 검색...")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedHeight(32)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background: {BG2}; color: {FG}; border: 1px solid {BG3};
                border-radius: 6px; padding: 4px 10px; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self._search.textChanged.connect(self._on_search)
        left_vbox.addWidget(self._search)
        left_vbox.addSpacing(4)

        # Pinned section (dynamic)
        self._pinned_label = QLabel(f"⭐ Pinned")
        self._pinned_label.setStyleSheet(
            f"color: {ORANGE}; font-size: 11px; font-weight: bold; padding: 2px 0;"
        )
        self._pinned_label.setVisible(False)
        left_vbox.addWidget(self._pinned_label)

        self._pinned_layout = QVBoxLayout()
        self._pinned_layout.setSpacing(4)
        left_vbox.addLayout(self._pinned_layout)

        # Module bars
        self._bar_layout = QVBoxLayout()
        self._bar_layout.setSpacing(6)
        left_vbox.addLayout(self._bar_layout)
        left_vbox.addStretch()

        body.addWidget(left)

        # ── Right Panel (scrollable cards) ──
        right = QWidget()
        right.setStyleSheet(f"background: {BG};")
        right_vbox = QVBoxLayout(right)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(8)

        self._right_title = QLabel("Module을 선택하세요")
        self._right_title.setStyleSheet(
            f"color: {FG2}; font-size: 14px; font-weight: bold; padding: 2px 0;"
        )
        right_vbox.addWidget(self._right_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background: {BG}; border: none; }}")

        self._card_container = QWidget()
        self._card_container.setStyleSheet(f"background: {BG};")
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 4, 0)
        self._card_layout.setSpacing(10)
        self._card_layout.addStretch()

        scroll.setWidget(self._card_container)
        right_vbox.addWidget(scroll, 1)

        body.addWidget(right, 1)
        root.addLayout(body, 1)

        # ══════════════════════════════════════
        #  LOG PANEL (fixed height)
        # ══════════════════════════════════════
        root.addSpacing(12)
        self._log_panel = QTextEdit()
        self._log_panel.setReadOnly(True)
        self._log_panel.setFixedHeight(90)
        root.addWidget(self._log_panel)

    # ──────────────────────────────────────────
    #  Module Discovery
    # ──────────────────────────────────────────
    def _discover_modules(self):
        self._log_msg(f"{self._display_name} 시작")
        modules = self._manager.discover()

        if not modules:
            self._log_msg("⚠ 탐색된 모듈 없음 — modules/ 폴더를 확인하세요")
            return

        categories = self._manager.get_categories()
        max_count = max(len(ms) for ms in categories.values())

        self._summary_label.setText(
            f"총 {len(modules)}개 Tool  ·  {len(categories)}개 Module"
        )

        # Create bars
        for i, (cat, cat_modules) in enumerate(categories.items()):
            color = _BAR_COLORS[i % len(_BAR_COLORS)]
            self._cat_colors[cat] = color

            bar = CategoryBar(cat, len(cat_modules), max_count, color)
            bar.clicked.connect(self._on_category_selected)
            self._bar_layout.addWidget(bar)
            self._bars[cat] = bar

        # Build pinned shortcuts
        self._rebuild_pinned()

        # Auto-select first category
        first_cat = list(categories.keys())[0]
        self._on_category_selected(first_cat)

        self._log_msg(f"{len(modules)}개 Tool 탐색 완료")

    # ──────────────────────────────────────────
    #  Category Selection
    # ──────────────────────────────────────────
    def _on_category_selected(self, category: str):
        self._selected_cat = category

        for cat, bar in self._bars.items():
            bar.set_selected(cat == category)

        self._show_tools(category)

    def _show_tools(self, category: str):
        """우측 카드 영역에 Tool 표시."""
        # 기존 카드 제거
        self._cards.clear()
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        color = self._cat_colors.get(category, ACCENT)
        cat_mods = self._manager.get_categories().get(category, [])

        self._right_title.setText(f"{category}  ({len(cat_mods)})")
        self._right_title.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: bold; padding: 2px 0;"
        )

        for mod in cat_mods:
            pinned = mod.id in self._pinned_ids
            card = ModuleCard(mod, self._manager, color, pinned,
                              log_callback=self._log_msg)
            card.pin_toggled.connect(self._on_pin_toggled)
            self._card_layout.insertWidget(
                self._card_layout.count() - 1, card
            )
            self._cards.append(card)

    # ──────────────────────────────────────────
    #  Search
    # ──────────────────────────────────────────
    def _on_search(self, text: str):
        text = text.strip().lower()
        for cat, bar in self._bars.items():
            if not text:
                bar.setVisible(True)
                continue
            cat_mods = self._manager.get_categories().get(cat, [])
            match = any(
                text in m.name.lower() or text in m.description.lower()
                for m in cat_mods
            )
            bar.setVisible(match)

    # ──────────────────────────────────────────
    #  Pinned / Favorites
    # ──────────────────────────────────────────
    def _on_pin_toggled(self, module_id: str, is_pinned: bool):
        if is_pinned and module_id not in self._pinned_ids:
            self._pinned_ids.append(module_id)
        elif not is_pinned and module_id in self._pinned_ids:
            self._pinned_ids.remove(module_id)

        self._settings["pinned"] = self._pinned_ids
        save_settings(self._settings)
        self._rebuild_pinned()

    def _rebuild_pinned(self):
        """좌측 Pinned 섹션 재구성."""
        # Clear existing
        while self._pinned_layout.count():
            item = self._pinned_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_pinned = bool(self._pinned_ids)
        self._pinned_label.setVisible(has_pinned)

        if not has_pinned:
            return

        for mod in self._manager.modules:
            if mod.id not in self._pinned_ids:
                continue

            btn = QPushButton(f"  ⭐ {mod.name}")
            btn.setFixedHeight(30)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {BG2}; color: {FG}; border: 1px solid {BG3};
                    border-radius: 6px; padding: 2px 8px; font-size: 11px;
                    text-align: left;
                }}
                QPushButton:hover {{ border-color: {ORANGE}; background: {BG3}; }}
            """)
            btn.clicked.connect(lambda checked=False, m=mod: self._launch_pinned(m))
            self._pinned_layout.addWidget(btn)

    def _launch_pinned(self, mod: ModuleInfo):
        ok = self._manager.launch(mod)
        if ok:
            self._log_msg(f"✅ {mod.name} 실행 (Pinned)")
        else:
            self._log_msg(f"❌ {mod.name} 실행 실패")
        self._refresh_all()

    # ──────────────────────────────────────────
    #  Refresh
    # ──────────────────────────────────────────
    def _refresh_all(self):
        for card in self._cards:
            card.refresh_status()

    # ──────────────────────────────────────────
    #  Log
    # ──────────────────────────────────────────
    def _log_msg(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_panel.append(
            f"<span style='color:{FG2}'>{ts}</span> │ {msg}"
        )
        sb = self._log_panel.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ──────────────────────────────────────────
    #  Close
    # ──────────────────────────────────────────
    def closeEvent(self, event):
        self._settings["window"]["width"] = self.width()
        self._settings["window"]["height"] = self.height()
        self._settings["pinned"] = self._pinned_ids
        save_settings(self._settings)
        self._timer.stop()
        event.accept()
