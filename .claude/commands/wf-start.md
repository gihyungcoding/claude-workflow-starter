---
description: 새 개발 태스크의 워크플로우를 시작한다 (memory-bank 생성 → 브랜치 → Phase 1)
argument-hint: "<TASK-ID>"
---

인자로 받은 태스크의 워크플로우를 시작한다.

`wf-orchestrator` 스킬의 "신규 태스크 시작" 절차를 따른다.

## 절차

### 1. 태스크 확인

```bash
jq '.[] | select(.id == "$1")' workflow_design/02_tasks/tasks.json
```

- 없으면 중단하고 사용자에게 알린다. 태스크를 지어내지 않는다
- ID 형식이 `^TASK-\d{3,}$` 가 아니면 중단한다

### 2. 이미 시작됐는지 확인

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
ls "$REPO_ROOT/memory-bank/$1/" 2>/dev/null
```

디렉터리가 이미 있으면 **새로 만들지 않고** `/wf-resume` 을 안내한다.

### 2.5. 프로젝트 골격 확인

**브랜치를 만들기 전에 확인한다.** `CLAUDE.md` 의 테스트 명령을 실제로 돌려본다.

```bash
<CLAUDE.md 의 테스트 명령>
```

돌지 않거나 `CLAUDE.md` 의 해당 항목이 `TODO` 이면 **여기서 멈추고 안내한다.**

```
TASK-001 을 시작하기 전에 프로젝트 골격이 필요합니다.

  CLAUDE.md 의 테스트 명령: TODO
  backend/ 없음

부트스트랩은 워크플로우 태스크가 아니라 환경 준비입니다.
기준 브랜치(develop)에서 골격을 만들고 커밋한 뒤 다시 시작하세요.
  → /wf-init 의 4.5 절

지금 feature 브랜치를 만들면 골격이 이 태스크의 PR 에 섞입니다.
```

브랜치를 먼저 만들면 부트스트랩 커밋이 그 브랜치에 쌓이고, 기준 브랜치로 되돌아가
옮겨야 한다. 순서를 지키면 그 일이 없다.

### 3. 출처 문서 로드

태스크에 `source_refs.source_file` 이 있으면 그 요구사항 문서를 읽는다.

```bash
jq -r '.[] | select(.id == "$1") | .source_refs.source_file // empty' \
   workflow_design/02_tasks/tasks.json
```

태스크의 `description` 보다 문서에 맥락이 훨씬 많다. 특히:

- `## 1-1. 배경` — 왜 이 작업을 하는가
- `## 5. 구현 참고` — Phase 1이 코드베이스를 찾을 때의 출발점
- `## 6. 범위 외` — 하지 말아야 할 것

Foundation 문서도 확인해 둔다 (없으면 `wf-orchestrator` 의 안내를 따른다).

```bash
ls docs/architecture/architecture.md docs/decisions/README.md 2>/dev/null
```

### 4. WRU 적격성 확인

`docs/workflow/task-schema.md` §1 의 필수 조건 5개를 확인한다.
특히 **Green 단계에서 바뀌는 프로덕션 코드가 있는지**를 본다.

부적격이면 진행하기 전에 사용자에게 알리고 확인을 받는다.

### 5. Memory Bank 생성

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
mkdir -p "$REPO_ROOT/memory-bank/$1/checkpoints"/{phase1,phase2a,phase2b,phase3,phase4,phase5}
```

`activeContext.md` 와 `progress.md` 를 작성한다 (→ `docs/workflow/memory-bank-spec.md` §1, §2).
태스크의 `title`, `primary_category`, `acceptance_criteria` 를 옮겨 담는다.

### 6. 브랜치

**기준 브랜치에서 갈라낸다.** 기준을 주지 않으면 현재 HEAD 에서 분기하므로,
다른 태스크 작업 중에 시작하면 그 태스크의 미완성 커밋이 딸려온다.

```bash
BASE="$(git config workflow.baseBranch || echo develop)"

# 기준 브랜치가 실재하는지 — 없으면 조용히 현재 브랜치에서 갈라지지 않도록 멈춘다
git rev-parse --verify --quiet "$BASE" >/dev/null || {
  echo "기준 브랜치 '$BASE' 가 없습니다."
  echo "git config workflow.baseBranch <이름> 으로 지정하거나 브랜치를 만드세요."
  exit 1
}

# 커밋되지 않은 변경이 있으면 checkout 이 그것을 끌고 간다
[ -z "$(git status --porcelain)" ] || {
  echo "커밋되지 않은 변경이 있습니다. 커밋하거나 stash 후 다시 시도하세요."
  git status --short
  exit 1
}

git fetch origin --quiet 2>/dev/null || true          # 원격이 없어도 진행
git checkout "$BASE" && git pull --ff-only 2>/dev/null || true
git checkout -b "feature/task-<번호>-<짧은-slug>"
```

`|| true` 를 붙인 이유는 원격이 없는 로컬 저장소에서도 동작해야 하기 때문이다.

slug는 태스크 제목에서 뽑되 영문 소문자·하이픈으로 3~5단어.
기준 브랜치 이름은 `CLAUDE.md` 의 브랜치 모델을 따른다.

### 7. 커밋

```bash
git add "$REPO_ROOT/memory-bank/$1"
git commit -m "chore(memory-bank): $1 워크플로우 시작"
```

### 8. Phase 1 진입

`wf-plan` 스킬로 넘어간다.

---

## 인자가 없으면

`workflow_design/02_tasks/tasks.json` 에서 `status: "todo"` 이고 `depends_on` 이 모두 완료된
태스크를 우선순위 순으로 최대 5건 보여주고, `AskUserQuestion` 으로 고르게 한다.

태스크가 하나도 없으면 만드는 방법을 안내한다:

```
아직 태스크가 없습니다.

  요구사항 문서부터    /wf-feature <기능이름>
  문서에서 일괄 생성    /wf-tasks-from-doc <경로>
  한 건만 바로         /wf-task-new "설명"
```
