/*
 * 버전2 화면 그리기 (2026-11-03 대표님 확정 시안)
 * ============================================================
 * 「서치잡 버전2 미리보기」(11-02 확정)의 화면 함수를 그대로 옮겼습니다.
 * 미리보기는 한 쪽짜리 앱이라 단추를 누르면 화면을 바꿔 그렸습니다.
 * 사이트는 쪽마다 주소가 있으므로 단추 대신 진짜 링크(<a href>)를 겁니다.
 * 검색엔진이 링크를 따라 공고를 찾아가야 하기 때문입니다.
 *
 * 이 파일은 두 곳에서 씁니다.
 *   · 빌드할 때 — 각 .astro 쪽이 불러 HTML 을 만듭니다
 *   · 브라우저에서 — /jobs/ 쪽이 거르기·검색할 때마다 다시 그립니다
 * 그래서 Node 전용 기능(fs 등)을 쓰지 않습니다.
 *
 * 함수는 모두 D(데이터 묶음, src/v2/data.js)를 첫 인자로 받습니다.
 */

export const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
export const num = (n) => Number(n || 0).toLocaleString('ko-KR');
export const md = (d) => (d ? `${Number(d.slice(5, 7))}.${d.slice(8, 10)}` : '');
export const ymd = (d) => (d ? `${Number(d.slice(5, 7))}월 ${Number(d.slice(8, 10))}일` : '');
const WD = ['일', '월', '화', '수', '목', '금', '토'];
/* 날짜 글자를 UTC 자정으로 읽습니다 — +09:00 으로 읽으면 하루 전 요일이 나옵니다. */
export const wd = (d) => WD[new Date(`${d}T00:00:00Z`).getUTCDay()];

/* 근무지 → 시·도. 지명만 적힌 것은 「지명 정리 대기」로 묶습니다.
   회사 본사로 추측해 채우지 않는다는 결정(2026-11-01)을 그대로 따릅니다. */
const SIDO = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종', '경기', '강원', '충북', '충남',
  '전북', '전남', '경북', '경남', '제주'];
export const UNSET = '제공정보 없음';
export const regionOf = (loc) => {
  const v = (loc || '').trim();
  if (!v || v === UNSET || v === '미표기') return UNSET;
  for (const s of SIDO) if (v.indexOf(s) === 0) return s;
  if (/해외|Overseas/i.test(v)) return '해외';
  if (/전국|복수|각지/.test(v)) return '전국·복수';
  return '지명 정리 대기';
};
export const ddText = (j) => (j.al ? '상시' : j.d <= 0 ? '오늘' : `D-${j.d}`);
export const hot = (j) => !j.al && j.d <= 3;
const initial = (n) => (n || '?').trim().charAt(0);

/* 을/를 — 한글이 아니면 붙이지 않습니다 (lib.js objParticle 주석 참고). */
const particle = (word) => {
  const ch = String(word || '').trim().slice(-1);
  const code = ch.charCodeAt(0);
  if (!(code >= 0xac00 && code <= 0xd7a3)) return '';
  return (code - 0xac00) % 28 === 0 ? '를' : '을';
};

/* ── 찾아보기 표 (D 마다 한 번) ─────────────────────── */
const IDX = new WeakMap();
const idx = (D) => {
  let x = IDX.get(D);
  if (x) return x;
  x = {
    co: Object.fromEntries(D.companies.map((c) => [c.s, c])),
    role: Object.fromEntries(D.roles.map((r) => [r.code, r.n])),
    ind: Object.fromEntries(D.industries.map((i) => [i.n, i])),
  };
  IDX.set(D, x);
  return x;
};
export const roleName = (D, c) => idx(D).role[c] || c;
export const coOf = (D, slug, fallback) =>
  idx(D).co[slug] || { s: slug, n: fallback || slug, i: [], o: 0, x: 0, w: 0, b: '' };

/* ── 주소 ───────────────────────────────────────────── */
export const jobsHref = (p) => {
  const q = Object.entries(p || {}).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v)}`);
  return `/jobs/${q.length ? `?${q.join('&')}` : ''}`;
};
const coHref = (slug) => `/company/${slug}/`;
const indHref = (D, name) => {
  const i = idx(D).ind[name];
  return i ? `/industry/${i.s}/` : jobsHref({ ind: name });
};
const roleHref = (code) => `/role/${code}/`;
const tagHref = (D, name) => {
  const t = D.tagIndex[name];
  return t && t.k ? `/tech/${t.s}/` : jobsHref({ tag: name });
};
const jobHref = (j) => (j.h ? `/job/${j.id}/` : j.u);

/* ── 공고 카드 ─────────────────────────────────────── */
export function card(D, j, hidden = false) {
  const co = coOf(D, j.c, j.n);
  const ind = j.i[0] || (co.i || [])[0] || '';
  const bare = !j.h;
  const ch = [];
  if (j.r[0]) ch.push(`<span>${esc(roleName(D, j.r[0]))}</span>`);
  if (j.k) ch.push(`<span class="k">${esc(j.k)}</span>`);
  ch.push(`<span>${esc(j.l ? j.l : UNSET)}</span>`);
  /* 카드 다이어트 (2026-11-02 대표님 승인) — 목록에는 한 줄 요약만 둡니다. */
  let sum = '';
  if (j.s) {
    const line = j.s.g || (j.s.d || [])[0] || '';
    if (line) sum = `<p class="gistline">${esc(line)}</p>`;
  }
  /* 회사 공고로 바로 넘어가는 카드에는 부가설명을 적지 않습니다
     (2026-11-02 대표님 지시). 아랫줄의 「회사 공고 ↗」와 왼쪽 주황 선이 그 뜻입니다. */
  const tg = j.g.slice(0, 2).map((t) => `<i>${esc(t)}</i>`).join('');
  const foot = `<span class="dd${hot(j) ? ' hot' : ''}">${ddText(j)}</span>`
    + `<span>${j.cl ? `${md(j.cl)} 마감` : (j.f ? `${md(j.f)} 등록` : '')}</span>`
    + (bare ? '<span class="ext">회사 공고 ↗</span>' : (tg ? `<span class="tg">${tg}</span>` : ''));
  const inner = `<div class="co"><span class="av">${esc(initial(co.n))}</span>`
    + `<b>${esc(co.n)}</b>${ind ? `<span>· ${esc(ind)}</span>` : ''}</div>`
    + `<h3>${esc(j.t)}</h3>`
    + `<div class="ch">${ch.join('')}</div>`
    + sum
    + `<div class="foot">${foot}</div>`;
  const h = hidden ? ' hidden' : '';
  if (bare) return `<a class="card bare" href="${esc(j.u)}" target="_blank" rel="noopener nofollow"${h}>${inner}</a>`;
  return `<a class="card" href="/job/${esc(j.id)}/"${h}>${inner}</a>`;
}

/*
 * 목록.
 *   more: 'link'   — 처음 n 건만 그리고 「N건 더 보기」는 전체 목록으로 가는 링크 (홈)
 *         'reveal' — 전부 그리되 n 건 뒤는 숨겨 두고 단추로 60건씩 엽니다 (산업·기업·기술 쪽)
 *                    검색엔진은 숨긴 카드까지 다 읽습니다
 *         'state'  — 브라우저가 다시 그리는 /jobs/ 쪽. 단추가 S.n 을 늘립니다
 */
export function listOf(D, arr, n, more = 'state', href = '/jobs/') {
  if (!arr.length) return '<div class="empty">조건에 맞는 공고가 없습니다.</div>';
  const lim = n || arr.length;
  if (more === 'reveal') {
    let html = `<div class="list">${arr.map((j, i) => card(D, j, i >= lim)).join('')}</div>`;
    if (arr.length > lim) html += `<button class="more-btn" data-reveal="60">${num(arr.length - lim)}건 더 보기</button>`;
    return html;
  }
  let html = `<div class="list">${arr.slice(0, lim).map((j) => card(D, j)).join('')}</div>`;
  if (arr.length > lim) {
    html += more === 'link'
      ? `<a class="more-btn" href="${esc(href)}" style="display:block;text-align:center">${num(arr.length - lim)}건 더 보기</a>`
      : `<button class="more-btn" data-more="1">${num(arr.length - lim)}건 더 보기</button>`;
  }
  return html;
}

const counts = (arr, pick) => {
  const m = {};
  arr.forEach((j) => { [].concat(pick(j)).forEach((k) => { if (k || k === 0) m[k] = (m[k] || 0) + 1; }); });
  return m;
};
const topKeys = (m, n) => Object.keys(m)
  .sort((a, b) => m[b] - m[a] || a.localeCompare(b, 'ko')).slice(0, n || 99);

/* 한 회사가 연달아 maxRun 건을 넘기지 않게 흩뜨립니다 (미리보기 주석 그대로). */
export function spread(arr, maxRun) {
  const pool = arr.slice();
  const out = [];
  let last = null; let run = 0;
  while (pool.length) {
    let i = 0;
    if (last !== null && run >= maxRun) {
      while (i < pool.length && pool[i].c === last) i += 1;
      if (i === pool.length) i = 0;
    }
    const j = pool.splice(i, 1)[0];
    if (j.c === last) run += 1; else { last = j.c; run = 1; }
    out.push(j);
  }
  return out;
}
/* 마감일이 같은 묶음 안에서 남은 건수가 많은 회사부터 돌아가며 뽑습니다. */
export function balance(arr, maxRun) {
  const by = {}; const order = [];
  arr.forEach((j) => { if (!by[j.c]) { by[j.c] = []; order.push(j.c); } by[j.c].push(j); });
  const out = [];
  let last = null; let run = 0; let left = arr.length;
  while (left > 0) {
    let pick = null; let best = -1;
    for (const c of order) {
      const n = by[c].length;
      if (!n || (c === last && run >= maxRun)) continue;
      if (n > best) { best = n; pick = c; }
    }
    if (pick === null) pick = last;
    const j = by[pick].shift();
    left -= 1;
    if (pick === last) run += 1; else { last = pick; run = 1; }
    out.push(j);
  }
  return out;
}
const byDl = (a, b) => (a.al ? 99999 : a.d) - (b.al ? 99999 : b.d);

/* ── 머리 (모든 쪽) ────────────────────────────────── */
export const NAVS = [['home', '홈', '/'], ['jobs', '공고', '/jobs/'], ['companies', '기업', '/companies/'],
  ['industries', '산업', '/industry/'], ['roles', '직무', '/role/'], ['techs', '기술', '/tech/'],
  ['scan', '점검 기록', '/scan/']];

export function scanBar(D) {
  const m = D.meta;
  /* 갱신이 밀렸을 때만 나타납니다 — 숨기는 것보다 알리는 편이 낫습니다.
     구직자가 마감된 공고를 오늘 것으로 알고 지원하는 쪽이 훨씬 나쁩니다. */
  if (m.stale >= 1) {
    return `<span class="stale">${m.stale}일 전 정보 · 마감된 공고가 있을 수 있습니다</span>`
      + `<span><b>${esc(m.at)}</b> 수집 · <b>${num(m.watched)}</b>개사 공식 채용페이지</span>`
      + `<a href="/scan/">점검 기록 →</a>`;
  }
  /* 날짜만 씁니다. 시각은 뺍니다 (2026-11-04 대표님 지시 — 버전1처럼 2026.11.04). */
  return `<span class="ok"><b>${esc(m.at.replace(/-/g, '.'))}</b> 확인 완료</span>`
    + `<span><b>${num(m.watched)}</b>개사 공식 채용페이지 · 하루 두 번</span>`
    + `<a href="/scan/">${m.streakFrom.replace(/-/g, '. ')}부터 <b>${m.streak}일 연속</b> →</a>`;
}

/* ── 홈 ─────────────────────────────────────────────── */
export function viewHome(D) {
  const m = D.meta;
  const peak = D.hist.reduce((a, b) => (b.n > a.n ? b : a), D.hist[0]);
  const max = peak.n || 1;
  const bars = D.hist.map((h) => {
    const pct = Math.round((h.n / max) * 100);
    return `<a href="${jobsHref({ day: h.day })}" class="${h.n >= max * 0.6 ? 'hot' : ''}"`
      + ` title="${ymd(h.day)} 마감 ${h.n}건">`
      + `<span class="v">${h.n ? h.n : ''}</span>`
      + `<span class="b" style="height:${Math.max(pct, 1)}%"></span></a>`;
  }).join('');
  const xs = D.hist.map((h, i) => {
    const w = wd(h.day);
    return `<span class="${w === '토' || w === '일' ? 'we' : ''}">${i === 0 ? md(h.day) : Number(h.day.slice(8, 10))}</span>`;
  }).join('');

  const inds = D.industries.slice().sort((a, b) => b.c - a.c).map((i) =>
    `<a class="tile" href="/industry/${esc(i.s)}/"><span class="t">${esc(i.n)}</span>`
    + `<span class="n">${num(i.c)}${i.w ? `<span class="w">오늘 +${i.w}</span>` : ''}</span></a>`).join('');

  const today = D.jobs.filter((j) => j.cl === m.at);
  const fresh = spread(D.jobs.filter((j) => j.f >= m.ago7).sort((a, b) => (b.f || '').localeCompare(a.f || '')), 3);
  const soon = D.jobs.filter((j) => !j.al && j.d > 0 && j.d <= 3).sort((a, b) => a.d - b.d);

  let h = '<section class="graph">'
    + `<h2>${ymd(peak.day)}(${wd(peak.day)}) 하루에 <em>${num(peak.n)}건</em>이 마감됩니다</h2>`
    + `<p class="cap">앞으로 14일 · 마감일 있는 공고 ${num(m.dated)}건 · 막대를 누르면 그날 마감 공고</p>`
    + `<div class="bars">${bars}</div><div class="xaxis">${xs}</div></section>`
    + '<div class="nums">'
    + `<div class="${m.todayClose ? 'urgent' : ''}"><span class="n">${num(m.todayClose)}</span><span class="l">오늘 마감</span></div>`
    + `<div><span class="n">${num(m.week)}</span><span class="l">최근 7일 새로 열린 공고</span></div>`
    + `<div><span class="n">${num(m.open)}</span><span class="l">지금 지원 가능</span></div>`
    + `<div><span class="n">${num(m.always)}</span><span class="l">상시 채용</span></div>`
    + '</div>'
    + scanStrip(D)
    + '<section class="sect inds"><div class="sect-h"><h2>분야로 바로 가기</h2>'
    + '<a class="more" href="/industry/">산업 전체 →</a></div>'
    + `<div class="tiles">${inds}</div></section>`;

  const todayHref = jobsHref({ day: m.at });
  const freshHref = jobsHref({ recent: m.ago7, sort: 'new' });
  if (today.length) h += '<section class="sect"><div class="sect-h"><h2>오늘 마감 · 아직 지원할 수 있습니다</h2>'
    + `<a class="more" href="${todayHref}">${num(today.length)}건 전체 →</a></div>`
    + `${listOf(D, today, 5, 'link', todayHref)}</section>`;
  if (fresh.length) h += '<section class="sect"><div class="sect-h"><h2>최근 7일 새로 열린 공고</h2>'
    + `<a class="more" href="${freshHref}">${num(fresh.length)}건 전체 →</a></div>`
    + `${listOf(D, fresh, 5, 'link', freshHref)}</section>`;
  h += '<section class="sect"><div class="sect-h"><h2>3일 안에 마감</h2>'
    + `<a class="more" href="/jobs/">${num(soon.length)}건 전체 →</a></div>`
    + `${listOf(D, soon, 5, 'link', '/jobs/')}</section>`;
  return h;
}

/* 34일 점검 막대 (2026-11-02) — 날짜마다 막대가 빠짐없이 서 있는 그림. */
export function scanStrip(D) {
  const m = D.meta;
  const days = D.scans.slice(0, 34).reverse();
  if (!days.length) return '';
  /* 눈금을 상위 10% 값에 맞춥니다 — 하루 1,363건이 들어온 날이 있어
     최대값에 맞추면 나머지가 전부 바닥에 붙습니다. */
  const sorted = days.map((s) => s.n).sort((a, b) => a - b);
  const cap = Math.max(sorted[Math.floor(sorted.length * 0.9)] || 1, 1);
  const bars = days.map((s) => {
    const hh = Math.min(Math.round((s.n / cap) * 100), 100);
    return `<span class="sc" title="${md(s.day)} ${s.t.join(' · ')} 확인 · 신규 ${s.n}건">`
      + `<i style="height:${Math.max(hh, 4)}%"></i></span>`;
  }).join('');
  return '<section class="scanstrip"><div class="sh">'
    + `<b>${m.streak}일</b> 하루도 빠짐없이 확인했습니다`
    + `<span class="meta">하루 두 번 · ${num(m.watched)}개사 공식 채용페이지</span>`
    + '<a href="/scan/">점검 기록 →</a></div>'
    + `<div class="sbars">${bars}</div>`
    + `<div class="sfoot"><span>${md(days[0].day)}</span>`
    + '<span>칸 = 그날 확인함 · 높이 = 그날 처음 본 공고 수</span>'
    + `<span>${md(days[days.length - 1].day)}</span></div></section>`;
}

/* ── 공고 목록 (/jobs/) ─────────────────────────────── */
export const CLEAR = () => ({ ind: null, tag: null, car: null, reg: null, co: null, role: null, day: null, recent: null });
export const newState = () => ({ q: '', sort: 'dl', tab: '마감', f: CLEAR(), n: 40, sidedown: false });

export function filtered(D, S) {
  const f = S.f;
  const q = S.q.trim().toLowerCase();
  const X = idx(D);
  return D.jobs.filter((j) => {
    if (f.ind && j.i.indexOf(f.ind) < 0) return false;
    if (f.tag && j.g.indexOf(f.tag) < 0) return false;
    if (f.car && (j.k || '미기재') !== f.car) return false;
    if (f.role && j.r.indexOf(f.role) < 0) return false;
    if (f.co && j.c !== f.co) return false;
    if (f.reg && regionOf(j.l) !== f.reg) return false;
    if (f.day && j.cl !== f.day) return false;
    if (f.recent && j.f < f.recent) return false;
    if (q) {
      const co = X.co[j.c];
      const hay = `${j.t} ${co ? co.n : j.n} ${j.n} ${j.g.join(' ')} ${j.l || ''} ${j.r.map((r) => X.role[r] || r).join(' ')}`.toLowerCase();
      if (hay.indexOf(q) < 0) return false;
    }
    return true;
  });
}

function tabs(S, dn, an) {
  const one = (key, label, n) => `<button class="tab" data-tab="${key}" aria-selected="${S.tab === key}">`
    + `${label} <span class="tn">${num(n)}</span></button>`;
  return `<div class="tabs" role="tablist">${one('마감', '마감 있는 공고', dn)}${one('상시', '상시채용', an)}</div>`;
}

export function viewJobs(D, S) {
  const arr = filtered(D, S);
  const all = D.jobs;
  const f = S.f;
  const cInd = counts(all, (j) => j.i);
  const cTag = counts(all, (j) => j.g);
  const cCar = counts(all, (j) => j.k || '미기재');
  const cReg = counts(all, (j) => regionOf(j.l));

  const fgroup = (title, m, key, limit) => {
    const ks = topKeys(m, limit);
    const cur = f[key];
    if (cur && ks.indexOf(cur) < 0) ks.unshift(cur);
    return `<div><h4>${title}</h4><div class="f">`
      + ks.map((k) => `<button data-f="${key}" data-v="${esc(k)}" aria-pressed="${cur === k}">`
        + `<span>${esc(k)}</span><span class="n">${num(m[k] || 0)}</span></button>`).join('')
      + (cur ? `<button data-f="${key}" data-v="" style="color:var(--steel)">선택 해제</button>` : '')
      + '</div></div>';
  };
  const side = `<div class="side"${S.sidedown ? '' : ' data-narrow-hide="1"'}>`
    + fgroup('산업', cInd, 'ind', 8)
    + fgroup('기술', cTag, 'tag', 12)
    + fgroup('경력', cCar, 'car', 9)
    + fgroup('근무지', cReg, 'reg', 10)
    + '</div>';

  const chosen = [];
  ['ind', 'tag', 'car', 'reg', 'role', 'co', 'day', 'recent'].forEach((k) => {
    if (!f[k]) return;
    const label = k === 'co' ? coOf(D, f[k]).n : k === 'role' ? roleName(D, f[k])
      : k === 'day' ? `${ymd(f[k])} 마감` : k === 'recent' ? '최근 7일 신규' : f[k];
    chosen.push(`<button class="chip" aria-pressed="true" data-f="${k}" data-v="">${esc(label)} ✕</button>`);
  });
  if (S.q.trim()) chosen.unshift(`<button class="chip" aria-pressed="true" data-q="">「${esc(S.q.trim())}」 ✕</button>`);

  /* 같은 마감일 안에서 한 회사가 몰리는 것을 막습니다. */
  let dated = [];
  const buckets = {};
  arr.forEach((j) => { if (!j.al) (buckets[j.d] = buckets[j.d] || []).push(j); });
  Object.keys(buckets).map(Number).sort((a, b) => a - b).forEach((k) => {
    dated = dated.concat(balance(buckets[k], 3));
  });
  let always = arr.filter((j) => j.al)
    .sort((a, b) => (b.f || '').localeCompare(a.f || '') || a.t.localeCompare(b.t, 'ko'));
  always = spread(always, 3);

  if (f.day) S.tab = '마감';            // 그래프에서 날짜를 고르면 마감 쪽입니다
  const head = `<div class="head-row"><h1 class="h1">공고 ${num(arr.length)}건</h1><div id="mem-slot" class="mem-slot"></div></div>`
    + `<p class="sub">${arr.length !== all.length ? `전체 ${num(all.length)}건 가운데`
      : `${num(D.meta.watched)}개사 공식 채용페이지 · ${esc(D.meta.at)} 기준`}</p>`
    + (chosen.length ? `<div class="chips" style="margin-top:12px">${chosen.join('')}</div>` : '')
    + '<button class="filter-toggle" data-side="1" style="margin-top:12px">'
    + `${S.sidedown ? '필터 접기 ▲' : '산업 · 기술 · 경력 · 근무지로 좁히기 ▼'}</button>`;

  /* 상시채용에는 마감일이 없어 마감 임박순이 뜻을 잃습니다 — 그 탭은 최근 등록순만. */
  const onAlways = S.tab === '상시';
  let pool = onAlways ? always : dated;
  if (onAlways || S.sort === 'new') {
    pool = spread(pool.slice().sort((a, b) => (b.f || '').localeCompare(a.f || '') || a.t.localeCompare(b.t, 'ko')), 3);
  }
  const main = tabs(S, dated.length, always.length)
    + `<div class="count"><span>보이는 공고 <b>${num(Math.min(S.n, pool.length))}</b> / ${num(pool.length)}</span>`
    + '<span class="sorts">'
    + (onAlways ? '<button data-sort="new" aria-pressed="true">최근 등록순</button>'
      : `<button data-sort="dl" aria-pressed="${S.sort === 'dl'}">마감 임박순</button>`
        + `<button data-sort="new" aria-pressed="${S.sort === 'new'}">최근 등록순</button>`)
    + `</span></div>${listOf(D, pool, S.n, 'state')}`;

  return `${head}<div class="cols" style="margin-top:16px">${side}<div>${main}</div></div>`;
}

/* ── 공고 상세 ─────────────────────────────────────── */
/*
 * j 는 toRow 모양입니다. 진행중이 아닌 공고(마감·보관)도 여기로 옵니다.
 * opt.closed   마감일이 지났다
 * opt.gone     회사가 채용페이지에서 내렸다 (goneAt)
 * opt.archived 요약이 없는 보관 쪽 — 검색에 내보내지 않습니다
 */
export function viewJob(D, j, opt = {}) {
  const co = coOf(D, j.c, j.n);
  const s = j.s || {};
  const ch = [];
  if (j.r[0]) ch.push(`<span>${esc(roleName(D, j.r[0]))}</span>`);
  if (j.k) ch.push(`<span class="k">${esc(j.k)}</span>`);
  ch.push(`<span>${esc(j.l || UNSET)}</span>`);
  const live = !opt.closed && !opt.gone;
  /* 마감일이 지났어도 회사가 공고를 안 내렸으면 링크를 남깁니다 (연장일 수 있음).
     회사가 실제로 내린 공고는 링크를 걸지 않습니다. */
  const canGo = !opt.gone && !!j.u;
  const goLabel = live ? '회사 공고로 이동 ↗' : '회사 공고에서 확인 ↗';
  const dLabel = live ? ddText(j) : '마감';
  const when = opt.gone ? `${md(opt.gone)} 회사 채용페이지에서 내려감`
    : j.cl ? `${j.cl.replace(/-/g, '. ')} 마감` : '마감일 없음 · 상시 채용';

  /* 여기서 갈 수 있는 곳 — 건수 적은 것부터 (좁은 문이 더 쓸모 있습니다). */
  const sameCo = D.jobs.filter((x) => x.c === j.c && x.id !== j.id).length;
  const doors = [];
  if (sameCo) doors.push([coHref(j.c), `${co.n}의 다른 공고`, sameCo]);
  if (j.i[0] && j.r[0]) {
    const n1 = D.jobs.filter((x) => x.i.indexOf(j.i[0]) >= 0 && x.r.indexOf(j.r[0]) >= 0).length;
    if (n1) doors.push([jobsHref({ ind: j.i[0], role: j.r[0] }), `${j.i[0]} × ${roleName(D, j.r[0])}`, n1]);
  }
  j.g.slice(0, 3).forEach((t) => {
    const n2 = (D.tagIndex[t] || {}).n || 0;
    if (n2) doors.push([tagHref(D, t), `${t}${particle(t)} 쓰는 공고`, n2]);
  });
  const reg = regionOf(j.l);
  if (reg !== UNSET && reg !== '지명 정리 대기') {
    const n3 = D.jobs.filter((x) => regionOf(x.l) === reg).length;
    if (n3) doors.push([jobsHref({ reg }), `${reg} 공고`, n3]);
  }
  doors.sort((a, b) => a[2] - b[2]);

  const h2 = (t, mb) => `<h2 style="font-family:var(--mono);font-size:11px;letter-spacing:.14em;`
    + `text-transform:uppercase;color:var(--ink-3);margin-bottom:${mb}px">${t}</h2>`;
  const rail = '<div class="rail">'
    + `<div class="dbox"><div class="d${live && hot(j) ? ' hot' : ''}">${dLabel}</div>`
    + `<div class="w">${when}</div>`
    + '<div class="acts">'
    + (canGo ? `<a class="go" href="${esc(j.u)}" target="_blank" rel="noopener nofollow">${goLabel}</a>` : '')
    + '</div></div>'
    + `<div class="paper">${h2('이 공고 점검 이력', 11)}<div class="hist">`
    + (j.f ? `<div><span class="dt">${md(j.f)}</span><span>처음 확인</span></div>` : '')
    + (opt.gone
      ? `<div><span class="dt">${md(opt.gone)}</span><span>회사 채용페이지에서 내려감</span></div>`
      : `<div><span class="dt">${md(D.meta.at)} ${D.meta.scanTimes[0] || ''}</span><span>확인 · 살아 있음</span></div>`)
    + '</div></div>'
    + (doors.length ? `<div class="paper">${h2('여기서 갈 수 있는 곳', 9)}<div class="doors">`
      + doors.map((d) => `<a href="${esc(d[0])}"><span>${esc(d[1])}</span><span class="n">${num(d[2])}</span></a>`).join('')
      + '</div></div>' : '')
    + '</div>';

  const ind0 = j.i[0];
  let body = '<div><div class="crumb">'
    + (ind0 ? `<a href="${indHref(D, ind0)}">${esc(ind0)}</a>` : '')
    + (ind0 && j.r[0] ? ' › ' : '')
    + (j.r[0] ? `<a href="${roleHref(j.r[0])}">${esc(roleName(D, j.r[0]))}</a>` : '')
    + '</div>';
  if (!live) {
    body += '<div class="paper closed-note">'
      + (opt.gone
        ? '<b>이 공고는 회사 채용페이지에서 내려갔습니다.</b><span>아래에서 같은 기업·분야의 진행중 공고를 확인하세요.</span>'
        : `<b>마감된 공고입니다 (${esc(j.cl)}).</b><span>회사 채용페이지에 아직 올라와 있으면 연장되었을 수 있습니다. 회사 공고에서 확인하세요.</span>`)
      + '</div>';
  }
  body += `<div class="paper jhead"><h1>${esc(j.t)}</h1><div class="ch">${ch.join('')}</div>`
    + `<div class="coline"><span class="av">${esc(initial(co.n))}</span><div>`
    + `<div class="nm"><a href="${coHref(j.c)}">${esc(co.n)}</a></div>`
    + (co.b ? `<div class="bio">${esc(co.b)}</div>` : '')
    + '</div></div>'
    + `<div class="mdd"><b class="${live && hot(j) ? 'hot' : ''}">${dLabel}</b><span>${when}</span></div>`
    + '</div>';

  if (s.g) body += `<p class="gist">${esc(s.g)}</p>`;
  const block = (title, items) => (!items || !items.length ? ''
    : `<div class="paper block"><h2>${title}</h2><ul>${items.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>`);
  body += block('주요 업무', s.d);
  body += block('자격 요건', s.q);
  if (j.g.length) body += `<div class="paper block"><h2>기술 · 도구 — ${j.g.length}개 전부</h2>`
    + `<div class="tg">${j.g.map((t) => {
      const ti = D.tagIndex[t];
      return ti && ti.k ? `<a href="/tech/${esc(ti.s)}/">${esc(t)}</a>` : `<span>${esc(t)}</span>`;
    }).join('')}</div></div>`;
  body += block('우대 사항', s.p);
  if (!opt.archived) {
    body += '<div class="paper block"><h2>근무 조건</h2><dl class="cond">'
      + `<dt>근무지</dt><dd>${esc(j.l || UNSET)}</dd>`
      + `<dt>경력</dt><dd>${esc(j.k || UNSET)}</dd>`
      + `<dt>마감</dt><dd>${j.cl ? `${esc(j.cl)}${live ? ` (${ddText(j)})` : ' (마감)'}` : '상시 채용 · 마감일 없음'}</dd>`
      + `<dt>처음 확인</dt><dd>${esc(j.f || '-')}</dd>`
      + '</dl></div>'
      /* 요약은 우리가 원문을 읽고 추린 것입니다. 원문이 고쳐지면 뒤처질 수 있어
         지원 전에 회사 공고를 보라고 분명히 적습니다 (2026-11-02). */
      + '<p class="fromsrc">이 요약은 회사 공고를 읽고 추린 것입니다. 지원 전에 회사 공고에서 원문을 확인하세요.</p>';
  }
  if (canGo) body += '<div class="acts tail" style="margin-top:12px">'
    + `<a class="go" href="${esc(j.u)}" target="_blank" rel="noopener nofollow">${goLabel}</a></div>`;
  body += '</div>';

  /* 폰: 화면 아래에 붙는 지원 줄 (2026-11-03 폰 시안) */
  const mbar = canGo ? `<div class="mbar"><span class="d${live && hot(j) ? ' hot' : ''}">${dLabel}</span>`
    + `<a class="go" href="${esc(j.u)}" target="_blank" rel="noopener nofollow">${goLabel}</a></div>` : '';

  return `<div class="detail">${body}${rail}</div>${mbar}`;
}

/* ── 기업 목록 ─────────────────────────────────────── */
export function viewCompanies(D, S = { sort: 'dl', ind: null, q: '', n: 9999 }) {
  const m = D.meta;
  let cs = D.companies.slice();
  if (S.ind) cs = cs.filter((c) => (c.i || []).indexOf(S.ind) >= 0);
  if (S.q && S.q.trim()) {
    const q = S.q.trim().toLowerCase();
    cs = cs.filter((c) => `${c.n} ${c.b || ''}`.toLowerCase().indexOf(q) >= 0);
  }
  if (S.sort === 'new') cs.sort((a, b) => b.w - a.w || b.o - a.o);
  else if (S.sort === 'ko') cs.sort((a, b) => a.n.localeCompare(b.n, 'ko'));
  else cs.sort((a, b) => b.o - a.o || a.n.localeCompare(b.n, 'ko'));

  const cInd = {};
  D.companies.forEach((c) => { (c.i || []).forEach((i) => { cInd[i] = (cInd[i] || 0) + 1; }); });

  const rows = cs.map((c) => `<a class="row" href="${coHref(c.s)}" data-o="${c.o}" data-w="${c.w}" data-ind="${esc((c.i || []).join('|'))}" data-n="${esc(`${c.n} ${c.b || ''}`.toLowerCase())}">`
    + `<span class="av">${esc(initial(c.n))}</span>`
    + `<span class="nm">${esc(c.n)} <span class="in">${esc((c.i || [])[0] || '')}</span>`
    + `${c.b ? `<span class="bio">${esc(c.b)}</span>` : ''}</span>`
    + `<span class="rt">${c.o ? `<span class="n">${num(c.o)}</span>${c.w ? `<span class="w">오늘 +${c.w}</span>` : ''}`
      : '<span class="z">공고 없음</span>'}</span></a>`).join('');

  return '<h1 class="h1">우리가 매일 확인하는 기업</h1>'
    + `<p class="sub">공식 채용페이지만 직접 확인합니다 · 하루 두 번 · ${esc(m.at)} 기준</p>`
    + '<div class="statrow">'
    + `<div><span class="n">${num(m.watched)}</span><span class="l">확인 중인 기업</span></div>`
    + `<div><span class="n">${num(m.hiring)}</span><span class="l">지금 뽑는 기업</span></div>`
    + `<div><span class="n">${num(m.empty)}</span><span class="l">공고 없음</span></div>`
    + '</div>'
    + `<div class="count" style="margin-top:18px"><span id="coCount">${num(cs.length)}개사</span>`
    + '<span class="sorts">'
    + `<button data-sort="dl" aria-pressed="${S.sort === 'dl'}">공고 많은 순</button>`
    + `<button data-sort="new" aria-pressed="${S.sort === 'new'}">오늘 신규순</button>`
    + `<button data-sort="ko" aria-pressed="${S.sort === 'ko'}">가나다</button>`
    + '</span></div>'
    + '<div class="chips" style="margin-bottom:12px">'
    + Object.keys(cInd).sort((a, b) => cInd[b] - cInd[a]).map((i) =>
      `<button class="chip" data-ind="${esc(i)}" aria-pressed="${S.ind === i}">${esc(i)}<span class="n">${cInd[i]}</span></button>`).join('')
    + '</div>'
    + `<div class="rows" id="coRows">${rows}</div>`;
}

/* ── 기업 상세 ─────────────────────────────────────── */
export function viewCompany(D, slug) {
  const c = coOf(D, slug);
  const mine = D.jobs.filter((j) => j.c === c.s);
  const rs = counts(mine, (j) => j.r);
  const firsts = mine.map((j) => j.f).filter(Boolean).sort();
  const fresh = mine.filter((j) => j.f === D.meta.at);
  const sorted = mine.slice().sort(byDl);
  return '<div class="crumb">'
    + ((c.i || [])[0] ? `<a href="${indHref(D, c.i[0])}">← ${esc(c.i[0])}</a>` : '<a href="/companies/">← 기업</a>')
    + '</div>'
    + `<div class="paper"><h1 class="h1">${esc(c.n)}</h1>`
    + `<p class="sub">${esc((c.i || []).join(' · ') || '산업 미분류')}</p>`
    + (c.b ? `<p style="margin-top:12px;font-size:13.5px;color:var(--ink-2);line-height:1.7">${esc(c.b)}</p>` : '')
    + '</div>'
    + '<div class="statrow">'
    + `<div><span class="n">${num(c.o)}</span><span class="l">진행중</span></div>`
    + `<div><span class="n">${num(c.w)}</span><span class="l">오늘 신규</span></div>`
    + `<div><span class="n">${num(c.x)}</span><span class="l">최근 마감 (60일 보관)</span></div>`
    + '</div>'
    + (Object.keys(rs).length ? '<section class="sect"><div class="sect-h"><h2>많이 뽑는 직무</h2></div>'
      + `<div class="chips">${topKeys(rs, 10).map((r) => `<a class="chip" href="${roleHref(r)}">${esc(roleName(D, r))}`
        + `<span class="n">${rs[r]}</span></a>`).join('')}</div></section>` : '')
    + `<section class="sect"><div class="sect-h"><h2>진행중 공고 ${num(mine.length)}건</h2></div>`
    + (mine.length ? listOf(D, sorted, 40, 'reveal') : '<div class="empty">지금은 진행중인 공고가 없습니다. 공고가 올라오면 이 자리에 나옵니다.</div>')
    + '</section>'
    + '<section class="sect"><div class="sect-h"><h2>점검 이력</h2></div><div class="paper"><div class="hist">'
    + (firsts.length ? `<div><span class="dt">${md(firsts[0])}</span><span>이 회사의 가장 오래된 공고를 처음 확인</span></div>` : '')
    + `<div><span class="dt">${md(D.meta.at)} ${D.meta.scanTimes[0] || ''}</span><span>확인 · 신규 ${fresh.length}건</span></div>`
    + '</div></div></section>';
}

/* ── 산업 · 직무 ───────────────────────────────────── */
export function viewIndustries(D) {
  const rows = D.industries.slice().sort((a, b) => b.c - a.c).map((i) => `<a class="row" href="/industry/${esc(i.s)}/">`
    + `<span class="nm">${esc(i.n)}<span class="bio">${i.k}개 기업</span></span>`
    + `<span class="rt"><span class="n">${num(i.c)}</span>${i.w ? `<span class="w">오늘 +${i.w}</span>` : ''}</span></a>`).join('');
  return `<h1 class="h1">산업</h1><p class="sub">공고 수는 진행중 기준 · ${esc(D.meta.at)}</p>`
    + `<div class="rows" style="margin-top:16px">${rows}</div>`
    + '<section class="sect"><div class="sect-h"><h2>직무</h2>'
    + '<a class="more" href="/role/">직무 전체 →</a></div>'
    + `<div class="chips">${D.roles.slice().sort((a, b) => b.c - a.c).slice(0, 14)
      .map((r) => `<a class="chip" href="${roleHref(r.code)}">${esc(r.n)}<span class="n">${r.c}</span></a>`).join('')}</div></section>`;
}
export function viewRoles(D) {
  const rows = D.roles.slice().sort((a, b) => b.c - a.c).map((r) => `<a class="row" href="${roleHref(r.code)}">`
    + `<span class="nm">${esc(r.n)}</span>`
    + `<span class="rt"><span class="n">${num(r.c)}</span></span></a>`).join('');
  return `<h1 class="h1">직무 ${D.roles.length}개</h1>`
    + '<p class="sub">공고 제목에서 먼저 읽고, 제목에 없으면 본문에서 읽습니다</p>'
    + `<div class="rows" style="margin-top:16px">${rows}</div>`;
}
function scopeView(D, title, sub, arr, extra) {
  const cTag = counts(arr, (j) => j.g);
  const cCo = counts(arr, (j) => j.c);
  const fresh = arr.filter((j) => j.f === D.meta.at).length;
  const soon = arr.filter((j) => !j.al && j.d <= 3).length;
  const sorted = arr.slice().sort(byDl);
  return `<h1 class="h1">${esc(title)} <span class="mono">${num(arr.length)}</span></h1>`
    + `<p class="sub">${sub}</p>`
    + '<div class="statrow">'
    + `<div><span class="n">${num(Object.keys(cCo).length)}</span><span class="l">기업</span></div>`
    + `<div><span class="n">${num(fresh)}</span><span class="l">오늘 신규</span></div>`
    + `<div><span class="n">${num(soon)}</span><span class="l">3일 내 마감</span></div>`
    + '</div>'
    + (extra || '')
    + '<section class="sect"><div class="sect-h"><h2>기술로 좁히기</h2></div><div class="chips">'
    + topKeys(cTag, 14).map((t) => `<a class="chip" href="${tagHref(D, t)}">${esc(t)}<span class="n">${cTag[t]}</span></a>`).join('')
    + '</div></section>'
    + '<section class="sect"><div class="sect-h"><h2>이 분야 기업</h2></div><div class="chips">'
    + topKeys(cCo, 12).map((s) => `<a class="chip" href="${coHref(s)}">${esc(coOf(D, s).n)}<span class="n">${cCo[s]}</span></a>`).join('')
    + '</div></section>'
    + `<section class="sect"><div class="sect-h"><h2>공고</h2></div>${listOf(D, sorted, 40, 'reveal')}</section>`;
}
export function viewIndustry(D, name) {
  const arr = D.jobs.filter((j) => j.i.indexOf(name) >= 0);
  const cRole = counts(arr, (j) => j.r);
  const extra = '<section class="sect"><div class="sect-h"><h2>이 분야 직무로 좁히기</h2></div>'
    + `<div class="chips">${topKeys(cRole, 12).map((r) => `<a class="chip" href="${jobsHref({ ind: name, role: r })}">${esc(roleName(D, r))}`
      + `<span class="n">${cRole[r]}</span></a>`).join('')}</div></section>`;
  return '<div class="crumb"><a href="/industry/">← 산업</a></div>'
    + scopeView(D, `${name} 채용`, `진행중 공고 · ${esc(D.meta.at)} 기준`, arr, extra);
}
export function viewRole(D, code) {
  const arr = D.jobs.filter((j) => j.r.indexOf(code) >= 0);
  return '<div class="crumb"><a href="/role/">← 직무</a></div>'
    + scopeView(D, `${roleName(D, code)} 채용`,
      '제목에서 읽은 직무를 먼저 쓰고, 제목에 없으면 본문에서 읽었습니다', arr);
}

/* ── 기술 ───────────────────────────────────────────── */
export function viewTechs(D) {
  const cats = {};
  Object.keys(D.tagIndex).forEach((t) => {
    const c = D.tagIndex[t].c || '기타';
    (cats[c] = cats[c] || []).push(t);
  });
  const html = Object.keys(cats).sort((a, b) => cats[b].length - cats[a].length).map((c) =>
    `<div class="taggroup"><h4>${esc(c)}</h4><div class="chips">`
    + cats[c].sort((a, b) => D.tagIndex[b].n - D.tagIndex[a].n).map((t) =>
      `<a class="chip" href="${tagHref(D, t)}">${esc(t)}<span class="n">${D.tagIndex[t].n}</span></a>`).join('')
    + '</div></div>').join('');
  return `<h1 class="h1">기술 · 역량 ${Object.keys(D.tagIndex).length}개</h1>`
    + `<p class="sub">공고 요약에서 뽑았습니다 · 괄호 안은 진행중 공고 수</p>${html}`;
}
export function viewTech(D, t) {
  const arr = D.jobs.filter((j) => j.g.indexOf(t) >= 0);
  const meta = D.tagIndex[t] || {};
  const withs = {};
  arr.forEach((j) => { j.g.forEach((o) => { if (o !== t) withs[o] = (withs[o] || 0) + 1; }); });
  const extra = '<section class="sect"><div class="sect-h"><h2>이 기술을 요구하는 공고가 함께 요구하는 것</h2></div>'
    + `<div class="rows">${topKeys(withs, 6).map((o) => `<a class="row" href="${tagHref(D, o)}">`
      + `<span class="nm">${esc(o)}</span><span class="rt"><span class="n">${withs[o]}</span>`
      + `<span class="z">${arr.length}건 중 겹침</span></span></a>`).join('')}</div></section>`;
  return `<div class="crumb"><a href="/tech/">← 기술 전체</a>${meta.c ? ` · ${esc(meta.c)}` : ''}</div>`
    + scopeView(D, `${t} 채용공고`, '이 기술을 요구하는 진행중 공고', arr, extra);
}

/* ── 점검 기록 ─────────────────────────────────────── */
export function viewScan(D) {
  const m = D.meta;
  const rows = D.scans.map((s) => `<div class="s"><span class="d">${md(s.day)}</span>`
    + `<span class="t">${s.t.join(' · ')} 완료</span>`
    + `<span class="n"><b>${num(s.n)}</b> 신규</span></div>`).join('');
  return `<h1 class="h1"><span class="mono">${m.streak}일</span> 하루도 빠짐없이 확인했습니다</h1>`
    + `<p class="sub">저장소에 남은 수집 기록을 그대로 꺼낸 것입니다 · 총 ${D.scans.length}일분</p>`
    + '<div class="nums">'
    + `<div><span class="n">${m.perDay}회</span><span class="l">하루 확인</span></div>`
    + `<div><span class="n">${num(m.watched)}</span><span class="l">확인 기업</span></div>`
    + `<div><span class="n">${num(m.todayNew)}</span><span class="l">오늘 신규</span></div>`
    + `<div><span class="n">${num(m.open)}</span><span class="l">지금 지원 가능</span></div>`
    + '</div>'
    + `<section class="sect"><div class="sect-h"><h2>날짜별 기록</h2></div><div class="scans">${rows}</div></section>`
    + '<section class="sect"><div class="sect-h"><h2>어떻게 모으나</h2></div><div class="paper">'
    + '<ul class="how">'
    + `<li>${num(m.watched)}개 기업의 공식 채용페이지만 직접 확인합니다</li>`
    + '<li>채용 플랫폼 전용 공고나 비공개 채용은 다루지 않습니다</li>'
    + `<li>마감된 공고도 60일 동안 남겨 둡니다 — 지금 ${num(m.closedKept)}건</li>`
    + `<li>요약은 ${num(m.summarized)}건 · 안내문이라 넘긴 공고 ${num(m.notice)}`
    + `건 · 이미지 공고 등 요약 못 한 공고 ${num(m.bare)}건은 회사 공고로 바로 보냅니다</li>`
    + '</ul></div></section>';
}
