"""
Park Analyzer — Module Manager.

modules/ 폴더를 자동 스캔하여 module.json을 읽고,
subprocess로 각 분석 모듈을 실행합니다.
"""
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger

# ── Paths ──
def _get_project_root() -> Path:
    """빌드 환경에 따라 프로젝트 루트 결정."""
    if getattr(sys, "frozen", False):
        # PyInstaller: 실행 파일이 있는 폴더가 루트
        return Path(sys.executable).resolve().parent
    if "__compiled__" in globals() or hasattr(sys, "_nuitka_binary_dir"):
        # Nuitka standalone: 실행 파일이 있는 폴더가 루트
        return Path(sys.executable).resolve().parent
    # 개발 모드: core/ 의 상위 폴더
    return Path(__file__).resolve().parent.parent

_PROJECT_ROOT = _get_project_root()
MODULES_DIR = _PROJECT_ROOT / "modules"

# ── 빌드 감지 ──
_IS_NUITKA_BUILD = "__compiled__" in globals() or hasattr(sys, "_nuitka_binary_dir")
logger.debug(f"Project root: {_PROJECT_ROOT}")
logger.debug(f"Modules dir: {MODULES_DIR}")


@dataclass
class ModuleInfo:
    """분석 모듈 메타데이터."""
    id: str
    name: str
    category: str
    version: str = "1.0.0"
    description: str = ""
    icon: str = "📊"
    dev_path: str = ""
    entry_dev: str = "main.py"
    entry_prod: str = "main.exe"
    changelog: list[str] = field(default_factory=list)
    manual_url: str = ""

    # Runtime state
    _process: Optional[subprocess.Popen] = field(
        default=None, repr=False, compare=False
    )

    @classmethod
    def from_json(cls, json_path: Path) -> "ModuleInfo":
        """module.json 파일에서 ModuleInfo 생성."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            id=data.get("id", json_path.parent.name),
            name=data.get("name", json_path.parent.name),
            category=data.get("category", "기타"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            icon=data.get("icon", "📊"),
            dev_path=data.get("dev_path", ""),
            entry_dev=data.get("entry_dev", "main.py"),
            entry_prod=data.get("entry_prod", "main.exe"),
            changelog=data.get("changelog", []),
            manual_url=data.get("manual_url", ""),
        )

    @property
    def is_available(self) -> bool:
        """모듈 실행 가능 여부 (경로 유효성)."""
        if self._is_dev_mode():
            dev = Path(self.dev_path)
            return dev.exists() and (dev / self.entry_dev).exists()
        else:
            return self._find_prod_exe() is not None

    def _find_prod_exe(self) -> Path | None:
        """배포 모드에서 실행 파일 경로 탐색.
        1. modules/<id>/dist/<entry_prod>  (standalone 빌드)
        2. modules/<id>/<entry_prod>       (단일 exe, e.g. VMoption)
        """
        dist_exe = MODULES_DIR / self.id / "dist" / self.entry_prod
        if dist_exe.exists():
            return dist_exe
        root_exe = MODULES_DIR / self.id / self.entry_prod
        if root_exe.exists():
            return root_exe
        return None

    @property
    def is_running(self) -> bool:
        """모듈이 현재 실행 중인지."""
        return self._process is not None and self._process.poll() is None

    @staticmethod
    def _is_dev_mode() -> bool:
        """Nuitka 빌드 여부로 개발/배포 모드 판단."""
        if _IS_NUITKA_BUILD:
            return False
        if getattr(sys, "frozen", False):
            return False  # PyInstaller
        return True


class ModuleManager:
    """모듈 자동탐색 및 lifecycle 관리."""

    def __init__(self):
        self._modules: list[ModuleInfo] = []

    @property
    def modules(self) -> list[ModuleInfo]:
        return self._modules

    def discover(self) -> list[ModuleInfo]:
        """modules/ 폴더를 스캔하여 module.json 자동 수집."""
        self._modules.clear()

        if not MODULES_DIR.exists():
            logger.warning(f"modules/ 폴더 없음: {MODULES_DIR}")
            return self._modules

        for folder in sorted(MODULES_DIR.iterdir()):
            if not folder.is_dir():
                continue
            json_path = folder / "module.json"
            if not json_path.exists():
                continue
            try:
                module = ModuleInfo.from_json(json_path)
                self._modules.append(module)
                status = "✅" if module.is_available else "⚠"
                logger.info(f"{status} 모듈 탐색: {module.name} ({module.category})")
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.error(f"module.json 파싱 실패 ({folder.name}): {e}")

        logger.info(f"총 {len(self._modules)}개 모듈 탐색 완료")
        return self._modules

    def get_categories(self) -> dict[str, list[ModuleInfo]]:
        """카테고리별로 그룹핑된 모듈 목록 반환."""
        categories: dict[str, list[ModuleInfo]] = {}
        for module in self._modules:
            categories.setdefault(module.category, []).append(module)
        return categories

    def launch(self, module: ModuleInfo) -> bool:
        """subprocess로 모듈 실행."""
        if module.is_running:
            logger.warning(f"{module.name} 이미 실행 중")
            return False

        try:
            if module._is_dev_mode():
                dev_path = Path(module.dev_path)
                entry = dev_path / module.entry_dev
                if not entry.exists():
                    logger.error(f"진입점 없음: {entry}")
                    return False

                if module.entry_dev.endswith(".exe"):
                    cmd = [str(entry)]
                else:
                    cmd = [sys.executable, str(entry)]
                cwd = str(dev_path)
            else:
                exe = module._find_prod_exe()
                if exe is None:
                    logger.error(f"실행 파일 없음: {module.id}/{module.entry_prod}")
                    return False
                cmd = [str(exe)]
                cwd = str(exe.parent)

            logger.info(f"모듈 실행: {module.name}")
            logger.debug(f"  cmd: {cmd}")
            logger.debug(f"  cwd: {cwd}")

            module._process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            return True

        except OSError as e:
            logger.error(f"모듈 실행 실패 ({module.name}): {e}")
            return False

    def terminate(self, module: ModuleInfo) -> None:
        """실행 중인 모듈 종료."""
        if module.is_running and module._process:
            module._process.terminate()
            logger.info(f"모듈 종료: {module.name}")
