"""워크플로우 스크립트 공통 유틸리티.

왜 필요한가
-----------
경로 계산, frontmatter 파싱, 태스크 ID 검증이 5개 스크립트에 흩어져 있으면 규약이 바뀔 때
한 곳만 고치고 나머지가 뒤처진다. 원본 저장소에서 태스크 ID 표기가 두 갈래로 갈린 것도
검증 로직이 스크립트마다 따로 있었기 때문이다. 여기가 유일한 정본이다.

의존성
------
표준 라이브러리만 쓴다. PyYAML을 쓰지 않는 이유는, 이 스크립트들이 pre-commit 훅과
SessionStart 훅에서 실행되는데 그 시점에 프로젝트 가상환경이 활성화되어 있다는 보장이
없기 때문이다. frontmatter는 우리가 쓰는 부분집합만 파싱한다(아래 한계 참조).

이 파서가 못 다루는 것
---------------------
- 중첩 3단계 이상 (progress.completed[] 까지가 한계)
- 여러 줄 문자열 (`|`, `>`)
- 인라인 배열 안의 콜론 (`[a: 1]`)
이 형태가 필요해지면 PyYAML 의존성을 추가하고 이 함수를 대체한다.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

# --- 규약 상수 (docs/workflow/artifact-paths.md 와 일치해야 함) ---

TASK_ID_RE = re.compile(r"^TASK-\d{3,}$")

#: workflow_design/ 아래 허용되는 디렉터리. 화이트리스트다 — 목록에 없으면 거부한다.
ALLOWED_WORKFLOW_DIRS = frozenset(
    {"02_tasks", "04_plan", "05_scenario", "06_dev", "07_verify", "08_reflect"}
)

#: Phase 별 산출물 파일명 패턴. {task_id} 를 치환해 쓴다.
PHASE_ARTIFACTS = {
    "1": ("04_plan", "PLAN_{task_id}.json"),
    "2a": ("05_scenario", "SCENARIO_{task_id}.json"),
    "2b": ("05_scenario", "TEST_{task_id}.json"),
    "3": ("06_dev", "DEV_{task_id}.json"),
    "4": ("07_verify", "VERIFY_{task_id}.json"),
    "5": ("08_reflect", "REFLECT_{task_id}.json"),
}

#: 체크포인트 고정 목록. (phase_dir, 파일명, 필수여부)
CHECKPOINTS = [
    ("phase1", "CP-1.1_codebase-analysis.md", False),
    ("phase1", "CP-1.2_design-route.md", False),
    ("phase1", "CP-1.3_context-plan.md", True),
    ("phase2a", "CP-2.1_path-branch.md", False),
    ("phase2a", "CP-2.2_canonical-scenarios.md", True),
    ("phase2a", "CP-2.3_validator-passed.md", True),
    ("phase2a", "CP-2.4_hitl1-approved.md", True),
    ("phase2b", "CP-2.5_red-code.md", True),
    ("phase2b", "CP-2.6_hitl2-approved.md", True),
    ("phase3", "CP-3.1_impl-strategy.md", False),
    ("phase3", "CP-3.2_tests-green.md", True),
    ("phase3", "CP-3.3_refactor.md", False),
    ("phase3", "CP-3.4_context-dev.md", True),
    ("phase4", "CP-4.1_rule-compliance.md", False),
    ("phase4", "CP-4.2_verification.md", True),
    ("phase4", "CP-4.3_hitl3-approved.md", True),
    ("phase5", "CP-5.1_kpt-analysis.md", False),
    ("phase5", "CP-5.2_context-reflect.md", True),
    ("phase5", "CP-5.3_hitl4-approved.md", True),
]

PHASE_ORDER = ["1", "2a", "2b", "3", "4", "5"]

PHASE_NAMES = {
    "1": "Plan",
    "2a": "Scenario",
    "2b": "Red",
    "3": "Green",
    "4": "Verify",
    "5": "Reflect",
}


# --- 경로 ---


def repo_root() -> Path:
    """저장소 루트를 반환한다.

    CWD가 하위 디렉터리여도 항상 같은 값을 준다. bare "memory-bank/..." 를 쓰면
    workflow_design/memory-bank/ 같은 오배치가 생기므로 모든 경로는 여기서 출발한다.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        # git 저장소가 아닌 경우 — 이 파일 기준으로 추정한다
        return Path(__file__).resolve().parent.parent


def memory_bank_root() -> Path:
    return repo_root() / "memory-bank"


def task_dir(task_id: str) -> Path:
    return memory_bank_root() / task_id


def workflow_design_root() -> Path:
    return repo_root() / "workflow_design"


def artifact_path(task_id: str, phase: str) -> Path | None:
    """Phase 산출물의 경로. 알 수 없는 phase 면 None."""
    spec = PHASE_ARTIFACTS.get(phase)
    if spec is None:
        return None
    subdir, pattern = spec
    return workflow_design_root() / subdir / pattern.format(task_id=task_id)


# --- 검증 ---


def is_valid_task_id(task_id: str) -> bool:
    return bool(TASK_ID_RE.match(task_id))


def task_id_error(task_id: str) -> str:
    """왜 유효하지 않은지 사람이 읽을 설명. 유효하면 빈 문자열."""
    if is_valid_task_id(task_id):
        return ""
    if re.match(r"^(TASK-)+task-", task_id, re.IGNORECASE):
        return f"이중접두: {task_id!r} — 'TASK-001' 처럼 접두사는 하나만 쓴다"
    if task_id.lower().startswith("task-"):
        return (
            f"형식 불일치: {task_id!r} — 대문자 'TASK-' + 3자리 이상 숫자만 허용한다 "
            "(docs/workflow/artifact-paths.md §1)"
        )
    return f"태스크 ID 형식이 아니다: {task_id!r} — 'TASK-\\d{{3,}}' 이어야 한다"


# --- frontmatter ---


def parse_frontmatter(path: Path) -> dict:
    """마크다운 파일 상단의 YAML frontmatter 를 dict 로 파싱한다.

    모듈 docstring의 '못 다루는 것'을 참조. 파일이 없거나 frontmatter 가 없으면 빈 dict.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}

    result: dict = {}
    container: dict | list | None = None
    container_key: str | None = None
    list_key: str | None = None

    for raw in text[3:end].splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()

        if indent == 0:
            container = None
            container_key = None
            list_key = None
            if line.startswith("- ") or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if value == "":
                # 하위 블록의 시작 — dict 인지 list 인지는 다음 줄에서 결정
                result[key] = {}
                container = result[key]
                container_key = key
            else:
                result[key] = _scalar(value)
            continue

        # 들여쓰기된 줄
        if container_key is None:
            continue

        if line.startswith("- "):
            item = line[2:].strip()
            target_key = list_key if list_key else container_key
            if list_key:
                bucket = container.setdefault(list_key, [])  # type: ignore[union-attr]
            else:
                if not isinstance(result.get(target_key), list):
                    result[target_key] = []
                bucket = result[target_key]
            if ":" in item and not item.startswith(("'", '"')):
                k, _, v = item.partition(":")
                bucket.append({k.strip(): _scalar(v.strip())})
            else:
                bucket.append(_scalar(item))
            continue

        if ":" in line:
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if not isinstance(container, dict):
                continue
            if v == "":
                list_key = k
                container[k] = []
            else:
                list_key = None
                container[k] = _scalar(v)

    return result


def _scalar(value: str):
    """YAML 스칼라를 파이썬 값으로. 따옴표 제거, bool/int 변환."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    low = value.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", ""):
        return None
    if value == "[]":
        return []
    if value.lstrip("-").isdigit():
        return int(value)
    return value


# --- 태스크 상태 ---


def list_tasks() -> list[dict]:
    """memory-bank 의 모든 태스크 상태를 읽는다.

    index.md 를 읽지 않고 activeContext.md 를 직접 읽는다 — index 는 파생물이라
    최신이 아닐 수 있고, 이 함수의 결과가 index 를 만드는 입력이다.
    """
    root = memory_bank_root()
    if not root.is_dir():
        return []

    tasks = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        ctx = entry / "activeContext.md"
        if not ctx.is_file():
            continue

        fm = parse_frontmatter(ctx)
        tasks.append(
            {
                "task_id": fm.get("task_id") or entry.name,
                "folder": entry.name,
                "title": fm.get("title") or "",
                "phase": str(fm.get("phase") or ""),
                "status": fm.get("status") or "ACTIVE",
                "last_updated": fm.get("last_updated") or "",
                "last_checkpoint": fm.get("last_checkpoint") or "",
                "blocked_reason": fm.get("blocked_reason") or "",
                "blocked_since": fm.get("blocked_since") or "",
                "unblock_condition": fm.get("unblock_condition") or "",
                "folder_mismatch": bool(fm.get("task_id"))
                and fm.get("task_id") != entry.name,
            }
        )
    return tasks


#: memory-bank 의 상태 → tasks.json 의 status 대응.
#: 두 곳에 상태가 있는 이유: tasks.json 은 태스크가 시작되기 전부터 존재하고
#: (요구사항 문서의 §1-2 표에서 생성), memory-bank 는 시작된 뒤에만 있다.
#: 시작된 태스크의 진실은 memory-bank 쪽이므로 그 방향으로만 동기화한다.
MEMORY_TO_TASKS_STATUS = {
    "ACTIVE": "in_progress",
    "BLOCKED": "blocked",
    "DONE": "done",
}


def tasks_json_path() -> Path:
    return workflow_design_root() / "02_tasks" / "tasks.json"


def sync_tasks_json_status() -> tuple[list[str], str]:
    """memory-bank 의 태스크 상태를 tasks.json 에 반영한다.

    왜 필요한가: Phase 5 가 activeContext.md 를 DONE 으로 바꿔도 tasks.json 은 todo 로
    남아 있었다. 그런데 /wf-start(인자 없음)와 depends_on 판정은 tasks.json 을 읽는다.
    그 결과 완료된 태스크가 다시 후보로 제시되고 선행 의존이 영원히 풀리지 않는다.

    반환: (바뀐 내용 설명 목록, 에러 메시지). 에러가 없으면 빈 문자열.
    """
    path = tasks_json_path()
    data, err = load_json(path)
    if err:
        # tasks.json 이 없는 것은 정상이다 — 아직 태스크를 추출하지 않았을 수 있다
        return [], "" if not path.is_file() else err
    if not isinstance(data, list):
        return [], f"tasks.json 최상위가 배열이 아니다: {path}"

    by_id = {t["task_id"]: t for t in list_tasks() if t.get("task_id")}
    changes: list[str] = []
    for task in data:
        if not isinstance(task, dict):
            continue
        tid = task.get("id")
        state = by_id.get(tid)
        if state is None:
            continue  # 아직 시작하지 않은 태스크 — tasks.json 이 진실이다
        want = MEMORY_TO_TASKS_STATUS.get(state["status"])
        if want and task.get("status") != want:
            changes.append(f"{tid}: {task.get('status')} → {want}")
            task["status"] = want

    if changes:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return changes, ""


def saved_checkpoints(task_id: str) -> list[str]:
    """저장된 체크포인트 파일명 목록 (phase 디렉터리 순)."""
    base = task_dir(task_id) / "checkpoints"
    if not base.is_dir():
        return []
    found = []
    for phase_dir, filename, _ in CHECKPOINTS:
        if (base / phase_dir / filename).is_file():
            found.append(filename)
    return found


def load_json(path: Path) -> tuple[dict | list | None, str]:
    """JSON 을 읽는다. 반환: (데이터, 에러메시지). 성공하면 에러는 빈 문자열."""
    if not path.is_file():
        return None, f"파일 없음: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except json.JSONDecodeError as exc:
        return None, f"JSON 파싱 실패: {path} — {exc}"
    except OSError as exc:
        return None, f"읽기 실패: {path} — {exc}"


def git_tracked(path: Path) -> bool:
    """git 이 이 파일을 추적하고 있는가.

    작업 트리에만 있는 파일은 세션이 끊기면 복구되지 않으므로, 산출물 검사는
    파일 존재가 아니라 추적 여부를 본다.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path)],
            capture_output=True,
            text=True,
            cwd=repo_root(),
        )
        return out.returncode == 0
    except FileNotFoundError:
        return False


# ============================================================================
# Foundation 계층 (docs/product, docs/architecture, docs/decisions)
#
# 워크플로우가 태스크 루프라면 Foundation 은 그 위 계층이다. 프로덕트 정의·아키텍처·
# 기술 결정 기록과, 요구사항 문서에서 태스크를 뽑아내는 데 필요한 것들을 여기 둔다.
# ============================================================================

#: docs/ 아래 허용 디렉터리. workflow_design 과 같은 이유로 화이트리스트다.
ALLOWED_DOC_DIRS = frozenset(
    {"product", "architecture", "decisions", "release", "workflow", "project_standard_docs"}
)

ADR_ID_RE = re.compile(r"^ADR-(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")

#: 문서 파일명은 케밥케이스. 원본 저장소는 케밥·스네이크가 섞여 있었다.
KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.(md|yaml|yml|json|css)$")

#: 템플릿·인덱스는 파일명 규칙에서 제외한다.
DOC_NAME_EXEMPT = frozenset({"_TEMPLATE.md", "README.md", "MEMORY.md", "CLAUDE.md"})


def docs_root() -> Path:
    return repo_root() / "docs"


def decisions_dir() -> Path:
    return docs_root() / "decisions"


def features_dir() -> Path:
    return docs_root() / "product" / "features"


def constraints_path() -> Path:
    return docs_root() / "architecture" / "constraints.yaml"


# --- ID 채번 ---


def next_adr_number() -> int:
    """다음 ADR 번호. 기존 최대값 + 1.

    번호를 재사용하지 않는다 — 삭제된 ADR 의 번호를 다시 쓰면 과거 문서가 가리키던
    참조가 다른 결정을 가리키게 된다.
    """
    highest = 0
    directory = decisions_dir()
    if directory.is_dir():
        for entry in directory.iterdir():
            match = ADR_ID_RE.match(entry.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return highest + 1


def next_task_number(tasks: list[dict]) -> int:
    """다음 태스크 번호. 기존 최대값 + 1.

    자릿수는 보존한다 (TASK-121 과 TASK-0121 은 다른 태스크다). 여기서는 번호만
    돌려주고, 포맷은 호출자가 기존 태스크의 자릿수에 맞춘다.
    """
    highest = 0
    for task in tasks:
        match = re.match(r"^TASK-(\d+)$", str(task.get("id", "")))
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def format_task_id(number: int, tasks: list[dict] | None = None) -> str:
    """번호를 태스크 ID 로. 기존 태스크의 자릿수를 따르되 최소 3자리."""
    width = 3
    if tasks:
        widths = [
            len(m.group(1))
            for t in tasks
            if (m := re.match(r"^TASK-(\d+)$", str(t.get("id", ""))))
        ]
        if widths:
            width = max(widths)
    return f"TASK-{number:0{max(width, 3)}d}"


def list_adrs() -> list[dict]:
    """ADR 목록. 번호 순."""
    directory = decisions_dir()
    if not directory.is_dir():
        return []

    records = []
    for entry in sorted(directory.iterdir()):
        match = ADR_ID_RE.match(entry.name)
        if not match:
            continue
        title, status, date = "", "", ""
        try:
            for line in entry.read_text(encoding="utf-8").splitlines()[:20]:
                stripped = line.strip()
                if stripped.startswith("# ") and not title:
                    title = stripped[2:].strip()
                elif stripped.startswith("- **상태**:"):
                    status = stripped.split(":", 1)[1].split("<!--")[0].strip()
                elif stripped.startswith("- **날짜**:"):
                    date = stripped.split(":", 1)[1].split("<!--")[0].strip()
        except OSError:
            pass
        records.append(
            {
                "number": int(match.group(1)),
                "id": f"ADR-{match.group(1)}",
                "file": entry.name,
                "title": title,
                "status": status or "?",
                "date": date,
            }
        )
    return records


# --- 요구사항 문서: §1-2 태스크 분리 표 ---

_TASK_TABLE_HEADING = re.compile(r"^#{2,4}\s*1-2\.?\s")


def parse_task_split_table(path: Path) -> tuple[list[dict], str]:
    """요구사항 문서의 '1-2. 태스크 분리' 표를 파싱한다.

    왜 표만 읽는가
    --------------
    문서 전체를 LLM 이 해석해 태스크를 추론하면 같은 문서에서도 실행할 때마다 다른
    분해가 나온다. 사람이 이미 표에 적어 둔 분해를 구조화하는 편이 안정적이고,
    문서와 태스크가 1:1 로 대응해 추적이 끊기지 않는다.

    반환: (행 목록, 에러메시지). 표를 찾지 못하면 ([], 사유).

    이 파서가 못 다루는 것
    ---------------------
    셀 안의 파이프(|)를 이스케이프한 경우, 여러 줄에 걸친 셀. 표는 한 행 한 줄이어야 한다.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [], f"읽기 실패: {path} — {exc}"

    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if _TASK_TABLE_HEADING.match(line) and "태스크 분리" in line:
            start = index
            break
    if start is None:
        return [], "'## 1-2. 태스크 분리' 섹션을 찾지 못했다"

    # 섹션 안에서 첫 표를 찾는다
    header_index = None
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("#") and not stripped.startswith("#####"):
            break  # 다음 섹션으로 넘어감
        if stripped.startswith("|") and stripped.endswith("|"):
            header_index = index
            break
    if header_index is None:
        return [], "'1-2. 태스크 분리' 섹션에 표가 없다"

    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    headers = cells(lines[header_index])
    rows: list[dict] = []
    for index in range(header_index + 2, len(lines)):  # +2 로 구분선을 건너뛴다
        stripped = lines[index].strip()
        if not stripped.startswith("|"):
            break
        values = cells(stripped)
        if len(values) < 2:
            continue
        row = {headers[i] if i < len(headers) else f"col{i}": v for i, v in enumerate(values)}
        row["_line"] = index + 1
        # 템플릿의 자리표시 행은 건너뛴다
        first = values[0]
        if not first or first.startswith("<") or first.startswith("---"):
            continue
        rows.append(row)

    if not rows:
        return [], "'1-2. 태스크 분리' 표에 데이터 행이 없다"
    return rows, ""


# --- constraints.yaml ---


def load_constraints() -> tuple[list[dict], str]:
    """architecture/constraints.yaml 을 읽는다. 반환: (제약 목록, 에러메시지).

    PyYAML 을 쓰지 않는 이유는 이 코드가 훅에서 실행되기 때문이다 — 그 시점에
    프로젝트 가상환경이 활성화되어 있다는 보장이 없다. constraints.yaml 이 쓰는
    부분집합만 파싱한다.

    못 다루는 것: 앵커/별칭, 여러 줄 문자열(| >), 흐름 스타일 매핑({a: 1}),
    3단계를 넘는 중첩. detect.paths 같은 인라인 배열은 다룬다.
    """
    path = constraints_path()
    if not path.is_file():
        return [], f"파일 없음: {path}"

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], f"읽기 실패: {exc}"

    constraints: list[dict] = []
    current: dict | None = None
    section: str | None = None  # 'detect' 같은 하위 매핑
    section_indent = 0
    in_list = False

    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()

        if indent == 0:
            in_list = line.startswith("constraints:")
            current, section = None, None
            continue
        if not in_list:
            continue

        if line.startswith("- "):
            if current:
                constraints.append(current)
            current, section = {}, None
            line = line[2:].strip()
            if not line:
                continue

        if current is None or ":" not in line:
            continue

        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()

        # 들여쓰기가 깊으면 하위 매핑(detect) 소속이다
        if section and indent > section_indent:
            current.setdefault(section, {})[key] = _yaml_scalar(value)
            continue

        if value == "":
            section, section_indent = key, indent
            current[key] = {}
        else:
            section = None
            current[key] = _yaml_scalar(value)

    if current:
        constraints.append(current)
    return constraints, ""


def _yaml_scalar(value: str):
    """constraints.yaml 의 스칼라와 인라인 배열을 파이썬 값으로."""
    value = value.split("  #")[0].strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_yaml_scalar(part.strip()) for part in inner.split(",")]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        body = value[1:-1]
        # YAML 큰따옴표 문자열의 이스케이프 처리 (정규식의 \\ 등)
        if value[0] == '"':
            body = body.replace('\\"', '"').replace("\\\\", "\\")
        return body
    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "~"):
        return None
    if value.lstrip("-").isdigit():
        return int(value)
    return value


# ============================================================================
# 브랜치 · 커밋
#
# git-flow 를 전제하되 브랜치 이름을 하드코딩하지 않는다. 스타터는 git-flow 가 아닌
# 프로젝트에도 쓰이므로 프로젝트가 기준 브랜치를 선언하게 한다.
# ============================================================================

#: 워크플로우 산출물 경로. 검증 이후 이것만 바뀐 것은 코드 변경이 아니다.
ARTIFACT_PREFIXES = ("workflow_design/", "memory-bank/", "docs/", ".claude/")


def base_branch() -> str:
    """기준 브랜치. feature 는 여기서 갈라지고 여기로 머지된다.

    우선순위:
      1. git config workflow.baseBranch   (프로젝트별 설정)
      2. develop 이 실재하면 develop      (git-flow)
      3. main / master 중 실재하는 것
    """
    try:
        out = subprocess.run(
            ["git", "config", "workflow.baseBranch"],
            capture_output=True, text=True, cwd=repo_root(),
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except FileNotFoundError:
        pass

    for candidate in ("develop", "main", "master"):
        if branch_exists(candidate):
            return candidate
    return "develop"


def branch_exists(name: str) -> bool:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", name],
            capture_output=True, text=True, cwd=repo_root(),
        )
        return out.returncode == 0
    except FileNotFoundError:
        return False


def current_branch() -> str:
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=repo_root(), check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def head_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=repo_root(), check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def worktree_dirty() -> list[str]:
    """커밋되지 않은 변경 목록. 깨끗하면 빈 리스트."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=repo_root(), check=True,
        )
        return [line for line in out.stdout.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def changed_files_between(base: str, head: str = "HEAD") -> tuple[list[str], str]:
    """두 커밋 사이에 바뀐 파일 목록. 반환: (파일들, 에러메시지)."""
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base}..{head}"],
            capture_output=True, text=True, cwd=repo_root(),
        )
        if out.returncode != 0:
            return [], (out.stderr.strip() or f"diff 실패: {base}..{head}")
        return [f for f in out.stdout.splitlines() if f], ""
    except FileNotFoundError:
        return [], "git 을 찾을 수 없다"


def is_source_file(path: str) -> bool:
    """워크플로우 산출물이 아닌 실제 코드·설정인가.

    Phase 4 승인 후에도 체크포인트 커밋이 이어지므로, HEAD 가 움직였다는 것만으로는
    코드가 바뀌었다고 볼 수 없다. 이 함수가 그 구분을 한다.
    """
    return not path.startswith(ARTIFACT_PREFIXES)
