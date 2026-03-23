"""
Park Analyzer — Dark Theme Stylesheet.

Catppuccin Mocha 기반 다크 테마 QSS.
Skill 01 (PySide6 Dark Theme) 패턴 적용.
"""

# ── Catppuccin Mocha Color Palette ──
BG = "#1e1e2e"       # Base background
BG2 = "#282840"      # Elevated surface
BG3 = "#313244"      # Highest surface
FG = "#cdd6f4"       # Primary text
FG2 = "#a6adc8"      # Secondary text
ACCENT = "#89b4fa"   # Accent blue
GREEN = "#a6e3a1"    # Pass / Success
RED = "#f38ba8"      # Fail / Error
ORANGE = "#fab387"   # Warning
PURPLE = "#cba6f7"   # Headers / Sections
TEAL = "#94e2d5"     # Info / Highlight


DARK_STYLE = f"""
/* ── Global ── */
QMainWindow {{
    background: {BG};
    color: {FG};
    font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
    font-size: 13px;
}}

/* ── Scroll Area ── */
QScrollArea {{
    border: none;
    background: {BG};
}}

/* ── Labels ── */
QLabel {{
    background: transparent;
}}

/* ── Buttons ── */
QPushButton {{
    background: {BG2};
    color: {FG};
    border: 1px solid {BG3};
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {BG3};
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background: {ACCENT};
    color: {BG};
}}
QPushButton:disabled {{
    background: {BG2};
    color: {BG3};
    border-color: {BG2};
}}
QPushButton[accent="true"] {{
    background: {ACCENT};
    color: {BG};
    font-weight: bold;
    border: none;
}}
QPushButton[accent="true"]:hover {{
    background: #7ba8e8;
}}
QPushButton[accent="true"]:disabled {{
    background: {BG3};
    color: {FG2};
}}

/* ── Log Panel (QTextEdit) ── */
QTextEdit {{
    background: {BG2};
    color: {FG2};
    border: 1px solid {BG3};
    border-radius: 6px;
    padding: 8px;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
}}

/* ── Scrollbar ── */
QScrollBar:vertical {{
    background: {BG};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BG3};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {FG2};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: {BG};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BG3};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {FG2};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ── Tooltips ── */
QToolTip {{
    background: {BG3};
    color: {FG};
    border: 1px solid {ACCENT};
    border-radius: 4px;
    padding: 4px 8px;
}}
"""
