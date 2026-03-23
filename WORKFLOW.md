# Park Analyzer — 빌드 & 배포 워크플로우 가이드

## 전체 흐름

```
[개별 프로젝트 폴더]              [Park Analyzer 폴더]

  96. Sample_Surface_Mapping      01. Park Analyzer/
  97. XY Stage Offset             ├── modules/
  80. Sliding Stage OPM           │   ├── sample_surface_mapping/
  03. VMoption                    │   │   ├── main.exe      ← 여기에 복사됨
  XX. 새 프로젝트                 │   │   └── module.json
                                  │   ├── xy_stage_offset/
       각각 .exe 빌드             │   │   ├── main.exe
            ↓                     │   │   └── module.json
       modules/에 복사             │   └── new_tool/         ← 새로 추가
            ↓                     │       ├── main.exe
       build_all.bat 실행          │       └── module.json
            ↓                     ├── build_all.bat
       코드 서명                   ├── build.bat
            ↓                     └── installer/
       Inno Setup                       └── setup.iss
            ↓                                ↓
       Park_Analyzer_Setup.exe         설치 프로그램 완성!
```

---

## 단계별 가이드

### Step 1: 개별 프로젝트에서 .exe 빌드

각 Tool은 자신의 프로젝트 폴더에서 PyInstaller `--onefile`로 빌드된다.

- 각 프로젝트 폴더의 `build.bat` 실행 (개별 빌드 시)
- 또는 **`build_all.bat`** 실행 시 모든 Tool을 한번에 빌드

| Tool | 프로젝트 폴더 | 빌드 결과물 |
|------|--------------|------------|
| Sample Surface Mapping | `96. Sample_Surface_Mapping` | `dist/SampleSurfaceMapping.exe` |
| XY Stage Offset | `97. XY Stage Positioning Offset Analysis` | `dist/XYStageOffset.exe` |
| Sliding Stage OPM | `80. Sliding Stage OPM Repeatability` | `dist/SlidingStageOPM.exe` |
| VM Option Generator | `03. VMoption` | `VMOptionGenerator.exe` |

### Step 2: modules/ 폴더에 등록

빌드된 .exe를 런처가 인식할 수 있도록 `modules/` 하위에 배치한다.

```
modules/
└── <tool_id>/
    ├── main.exe        ← 빌드된 .exe (이름은 module.json의 entry_prod와 일치)
    └── module.json     ← 모듈 메타데이터 (필수)
```

**module.json 필수 필드:**

| 필드 | 설명 | 예시 |
|------|------|------|
| `id` | 모듈 고유 ID (폴더명과 동일) | `"sample_surface_mapping"` |
| `name` | 런처에 표시될 이름 | `"Sample Surface Mapping"` |
| `category` | 분류 카테고리 | `"XY Stage"`, `"Utility"` |
| `version` | 버전 | `"1.0.0"` |
| `description` | 한줄 설명 | `"웨이퍼 표면 맵핑 및 패턴 분석"` |
| `icon` | 이모지 아이콘 | `"🗺️"` |
| `dev_path` | 개발 폴더 절대 경로 | `"C:/Users/Spare/Desktop/03. Program/96. ..."` |
| `entry_dev` | 개발 모드 진입점 | `"main.py"` |
| `entry_prod` | 배포 모드 진입점 (.exe) | `"main.exe"` |

> 새 Tool 추가 시 `modules/_template/module.json`을 복사해서 수정하면 편리하다.

### Step 3: build_all.bat 실행 (한방에 전체 빌드)

```
build_all.bat
```

이 스크립트가 수행하는 작업:

1. **[1~3/6]** 각 Tool을 PyInstaller `--onefile`로 빌드
2. **[4/6]** 빌드된 .exe를 `modules/`에 복사
3. **[5/6]** 런처를 PyInstaller `--onedir`로 빌드 + modules/ 폴더 포함
4. **[6/6]** 코드 서명

빌드 완료 후:

```
build.bat inno
```

이 명령으로 Inno Setup 설치 프로그램을 생성한다.

### Step 4: 배포

생성된 설치 프로그램 위치:

```
installer/Output/Park_Analyzer_Setup.exe
```

이 파일을 사용자에게 배포하면 된다.

---

## 새 Tool 추가 체크리스트

새로운 Tool을 Park Analyzer에 추가할 때 아래 순서를 따른다.

### 1. 프로젝트 폴더에 build.bat 만들기

기존 프로젝트(예: `96. Sample_Surface_Mapping`)의 `build.bat`를 복사한 뒤,
프로젝트 경로와 패키지명 등을 수정한다.

### 2. modules/ 에 모듈 등록

```bash
# 1) 폴더 생성
mkdir modules\my_new_tool

# 2) 템플릿 복사 후 수정
copy modules\_template\module.json modules\my_new_tool\module.json
# → id, name, dev_path 등을 자신의 Tool에 맞게 수정
```

### 3. build_all.bat에 빌드 명령 추가

`build_all.bat` 하단의 `=== 새 Tool 추가 템플릿 ===` 주석을 복사하여
빌드 섹션과 복사 섹션에 각각 추가한다.

### 4. 테스트

1. `build_all.bat` 실행하여 빌드 성공 확인
2. 런처 실행하여 새 Tool이 목록에 나타나는지 확인
3. 새 Tool 클릭하여 정상 실행되는지 확인
