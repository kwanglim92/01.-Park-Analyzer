"""
Settings Manager.

JSON 설정 파일 로드/저장 with 기본값 병합.
"""
import json
from pathlib import Path

from loguru import logger

# ── Paths ──
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_SETTINGS_FILE = _CONFIG_DIR / "settings.json"

# ── Defaults ──
_DEFAULTS = {
    "app": {
        "version": "1.0.0",
        "display_name": "Integrated Analyzer",
        "build_name": "IntegratedAnalyzer",
        "dev_mode": True,
        "language": "ko",
    },
    "window": {
        "width": 1000,
        "height": 700,
    },
    "pinned": [],
}


def _deep_merge(base: dict, override: dict) -> dict:
    """base 딕셔너리에 override 값을 재귀적으로 병합."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings() -> dict:
    """설정 파일 로드. 없으면 기본값 사용."""
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                user_settings = json.load(f)
            return _deep_merge(_DEFAULTS, user_settings)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"설정 파일 로드 실패, 기본값 사용: {e}")
    return _DEFAULTS.copy()


def save_settings(settings: dict) -> None:
    """설정 파일 저장."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        logger.debug(f"설정 저장 완료: {_SETTINGS_FILE}")
    except OSError as e:
        logger.error(f"설정 저장 실패: {e}")
