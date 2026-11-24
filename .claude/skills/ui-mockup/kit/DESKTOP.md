# 데스크톱 부품 — `screens/desktop/<id>.html` 은 이 클래스와 COMPONENTS.md 의 부품만 조합한다

`components.css`(행·배지·버튼·입력·블록·아바타)는 그대로 쓰고, 그 위에 `desktop.css` 를 얹는다.
인라인 style·임의 색 금지. 패턴을 고르는 질문은 `references/desktop.md` §2.

## 뼈대

```html
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=1280">
<title>화면 제목</title>
<link id="tokens" rel="stylesheet" href="../../tokens.css"><link rel="stylesheet" href="../../components.css"><link rel="stylesheet" href="../../desktop.css"><script src="../../palette.js"></script>
</head>
<body class="desk">
<div class="shell">
  <aside class="sidenav">
    <div class="sidenav-brand"><p class="name">서비스 이름</p><p class="meta">지금 상황 한 줄</p></div>
    <nav class="nav">
      <a href="home.html" aria-current="page">(선 아이콘)홈</a>
      <a href="…">(선 아이콘)목록<span class="nav-count">12</span></a>
    </nav>
    <div class="sidenav-foot">(사람·설정 행)</div>
  </aside>
  <main class="main">
    <header class="d-head">
      <div><p class="eyebrow">…</p><h1>…</h1><p class="lead">…</p></div>
      <div class="d-actions"><a class="btn secondary" href="…">보조</a><a class="btn primary" href="…">주 행동</a></div>
    </header>
    …
  </main>
</div>
</body></html>
```
- 보조 열이 있으면 `<main class="main has-aside"><div class="col">(머리·본문)</div><aside class="aside">…</aside></main>`
- `h1` 은 화면당 1개(`d-head` 안). 링크는 다른 데스크톱 화면 파일로.

## 숫자 요약
`<div class="stats"><a class="stat" href="…"><span class="stat-label">답 기다림</span><span class="stat-num">3</span><span class="stat-sub">가장 오래된 것 5일째</span></a>…</div>`

## 목록·상세 나란히
```html
<div class="split">
  <div class="split-list">
    <a class="row" href="…" aria-current="true"><div class="row-main"><span class="badge is-info">…</span><p class="row-title">…</p><p class="row-sub">…</p></div></a>
    …
  </div>
  <div class="split-detail">
    <section class="block">…</section>
  </div>
</div>
```

## 상태 보드
```html
<div class="board">
  <section class="board-col"><div class="board-head"><span>상태 이름</span><span class="n">3</span></div>
    <a class="card" href="…"><p class="card-title">…</p><p class="card-sub">…</p><div class="card-foot"><span class="avatars">…</span><span>기한 글자</span></div></a>
  </section>
  …
</div>
```

## 월 달력
```html
<section class="cal is-weekend-wide">   <!-- 요일 폭이 같아야 하면 is-weekend-wide 를 뺀다 -->
  <div class="cal-head"><p class="h2">11월</p><div class="d-actions">(이전·다음 선 아이콘 버튼)</div></div>
  <div class="cal-grid">
    <div class="cal-dow">일</div>…<div class="cal-dow">토</div>
    <div class="cal-day is-out"><span class="d">27</span></div>
    <div class="cal-day is-clash"><span class="d">8</span><a class="cal-ev is-brand" href="…">12:00 …</a><a class="cal-ev" href="…">…</a></div>
    …
  </div>
</section>
```
- `cal-ev` 의 색 클래스는 배지 표와 같은 뜻으로만. 겹친 날은 `is-clash`(주의 색 바탕) + 칸 안 글자로 이유.

## 표 + 필터 + 일괄 작업
```html
<div class="with-filters">
  <nav class="filters">
    <div class="filters-group"><p>무엇으로 보기</p><a class="filter" aria-current="true" href="…">전체<span class="n">62</span></a>…</div>
  </nav>
  <div class="table-wrap">
    <div class="toolbar-d"><label class="search">(돋보기 선 아이콘)<input type="search" placeholder="이름으로 찾기"></label><a class="btn secondary small" href="…">…</a></div>
    <div class="bulkbar">2명 선택<a class="btn primary small" href="…">…</a></div>   <!-- 선택이 있을 때만 -->
    <table class="dtable"><thead><tr><th></th><th>이름</th>…</tr></thead>
      <tbody><tr aria-selected="true"><td><button class="check" role="checkbox" aria-checked="true"><span>(체크)</span></button></td>
        <td><a class="cell-main" href="…"><span class="avatar"><img src="../../assets/avatars/…" alt=""></span>이름</a></td><td class="muted">…</td></tr></tbody></table>
  </div>
</div>
```

## 측면 패널 (고치기)
`<aside class="aside"><section class="panel"><div class="panel-head"><p class="h2">…</p><a class="appbar-btn" href="…" aria-label="닫기">(×)</a></div>(field 들)<div class="panel-foot"><a class="btn secondary" href="…">취소</a><button class="btn primary">저장</button></div></section></aside>`

## 대화상자
화면 끝에 `<div class="dim"></div><div class="dialog" role="dialog" aria-label="…"><p class="h2">…</p><p class="lead">…</p><div class="dialog-foot"><a class="btn secondary" href="…">취소</a><a class="btn primary" href="…">확정하기</a></div></div>`
— 아래 깔리는 화면을 복사한 파일에 붙인다(모바일 시트와 같은 방식).

## 단독 페이지
`<body class="desk standalone"><div class="sheet-page"><header class="hero">…</header><section class="block">…</section><a class="btn primary full" href="…">…</a></div></body>`
