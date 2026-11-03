/*
 * 버전2 화면이 쓰는 데이터 묶음 (2026-11-03)
 * ============================================================
 * 11-02 에 확정한 「서치잡 버전2 미리보기」는 data.json 하나를 읽어
 * 모든 화면을 그렸습니다. 사이트도 같은 모양의 묶음을 만들어
 * src/v2/views.js 의 함수에 넘깁니다. 그래야 미리보기와 같은 화면이
 * 나옵니다.
 *
 * 숫자는 전부 src/lib.js 에서 받습니다. 진행중 판정·산업·직무·태그·
 * 기업 집계를 여기서 다시 만들지 않습니다 — 그러면 홈의 숫자와 기업
 * 페이지의 숫자가 어긋납니다.
 *
 * 빌드 한 번에 한 번만 만듭니다 (아래 memo). 공고 상세가 7천 쪽이라
 * 쪽마다 새로 만들면 빌드가 몇 배로 길어집니다.
 */
import {
  COLLECTED_AT, STALE_DAYS, JOBS, openJobs, closedJobs, isRecentlyClosed, isAlways, daysLeft,
  industriesOf, industrySlug, industries, rolesOf, roles, roleName,
  companyPages, scanRuns, scanStreak, jobTags, summaryOf, noticeReason, hasDetail,
} from '../lib.js';
import registry from '../data/companies.json';
import introDoc from '../data/company-intro.json';
import tagDoc from '../data/job-tags.json';

const INTRO = introDoc.intro || {};
const REG = registry.companies || [];
const REG_BY_SLUG = Object.fromEntries(REG.map((c) => [c.slug, c]));
const TAG_INDEX = tagDoc.index || {};

const DAY = 86400000;
const KST = 9 * 3600000;
/* 날짜 더하기는 한국시간으로 셉니다 — index.astro 의 같은 주석 참고. */
export const plusDays = (n) =>
  new Date(new Date(`${COLLECTED_AT}T00:00:00+09:00`).getTime() + n * DAY + KST)
    .toISOString().slice(0, 10);

/*
 * 공고 한 건을 화면용 짧은 모양으로.
 * 미리보기 data.json 의 jobs 와 같은 이름을 씁니다.
 *   id c(회사 slug) t(제목) k(경력) l(근무지) cl(마감일) f(처음 본 날)
 *   u(원문 주소) i(산업) r(직무) g(태그) al(상시) d(남은 일수)
 *   s(요약 { g 한 줄, d 업무, q 자격, p 우대, l 근무지 원문 })
 *   h(우리 상세 페이지가 있는가)
 */
export const toRow = (j, full = true) => {
  const s = summaryOf(j);
  const row = {
    id: j.id,
    c: j.companySlug,
    n: j.company,
    t: j.title,
    k: j.career || '',
    l: j.location || '',
    cl: j.closesAt || '',
    f: (j.firstSeenAt || '').slice(0, 10),
    u: j.sourceUrl,
    i: industriesOf(j),
    r: rolesOf(j),
    g: jobTags(j),
  };
  if (isAlways(j)) row.al = 1;
  else row.d = daysLeft(j);
  if (s) {
    row.s = full
      ? { g: s.gist || '', d: s.duties || [], q: s.quals || [], p: s.prefs || [], l: s.loc || '' }
      : { g: s.gist || (s.duties || [])[0] || '' };
  } else if (noticeReason(j)) {
    row.sk = 1;
  }
  row.h = hasDetail(j) ? 1 : 0;
  return row;
};

let memo = null;

export const getData = () => {
  if (memo) return memo;
  const TODAY = COLLECTED_AT;
  const open = openJobs();
  const closed = closedJobs().filter(isRecentlyClosed);
  const jobs = open.map((j) => toRow(j));

  /* ── 기업 ─────────────────────────────────────────── */
  const openBy = {};
  const newBy = {};
  const closedBy = {};
  for (const j of open) {
    openBy[j.companySlug] = (openBy[j.companySlug] || 0) + 1;
    if ((j.firstSeenAt || '').slice(0, 10) === TODAY) newBy[j.companySlug] = (newBy[j.companySlug] || 0) + 1;
  }
  for (const j of closed) closedBy[j.companySlug] = (closedBy[j.companySlug] || 0) + 1;
  /* 등록 기업 전체를 싣습니다 — 「공고 없음」도 정보라는 10/28 결정.
     목록은 페이지가 있는 기업(companyPages)과 같습니다. 없는 주소로
     보내면 404 입니다. */
  const companies = companyPages().map((c) => {
    const r = REG_BY_SLUG[c.slug] || {};
    const name = r.name || c.name;
    /* 산업은 그 회사 공고에 붙은 것을 씁니다. 그룹 계열사는 공고마다
       산업이 다를 수 있어(industriesOf 의 affiliate 표) 등록부 값만 쓰면
       기업 목록의 산업 칩과 산업 페이지의 숫자가 어긋납니다. */
    const fromJobs = [];
    for (const j of c.jobs) for (const i of industriesOf(j)) if (!fromJobs.includes(i)) fromJobs.push(i);
    return {
      s: c.slug,
      n: name,
      i: fromJobs.length ? fromJobs : (r.industry || []),
      o: openBy[c.slug] || 0,
      x: closedBy[c.slug] || 0,
      w: newBy[c.slug] || 0,
      b: INTRO[name] || '',
    };
  }).sort((a, b) => b.o - a.o || a.n.localeCompare(b.n, 'ko'));

  /* ── 태그 사전 — 진행중 공고 수로 다시 셉니다 ─────────── */
  const live = {};
  for (const r of jobs) for (const t of r.g) live[t] = (live[t] || 0) + 1;
  const tagIndex = {};
  for (const [name, v] of Object.entries(TAG_INDEX)) {
    if (!live[name]) continue;
    tagIndex[name] = { s: v.slug || '', c: v.cat || '', n: live[name], k: v.link && v.slug ? 1 : 0 };
  }

  /* ── 마감 분포 14일 ───────────────────────────────── */
  const hist = [];
  for (let n = 0; n < 14; n += 1) {
    const day = plusDays(n);
    hist.push({ day, n: open.filter((j) => j.closesAt === day).length });
  }

  /* ── 점검 기록 — 최근 날짜가 앞 ───────────────────── */
  const scans = scanRuns().slice().reverse().map((r) => ({ day: r.day, t: r.times, n: r.new }));
  const streak = scanStreak();
  const todayRun = scans.find((s) => s.day === TODAY);

  /* ── 산업 · 직무 ──────────────────────────────────── */
  const inds = industries().map((x) => ({
    n: x.name,
    s: x.slug,
    c: x.jobs.length,
    w: x.jobs.filter((j) => (j.firstSeenAt || '').slice(0, 10) === TODAY).length,
    k: new Set(x.jobs.map((j) => j.companySlug)).size,
  }));
  const rs = roles().map((r) => ({ code: r.code, n: roleName(r.code), c: r.jobs.length }));

  const ago7 = plusDays(-6);
  const meta = {
    at: TODAY,
    scanTimes: todayRun ? todayRun.t : [],
    open: open.length,
    todayNew: open.filter((j) => (j.firstSeenAt || '').slice(0, 10) === TODAY).length,
    week: open.filter((j) => (j.firstSeenAt || '').slice(0, 10) >= ago7).length,
    ago7,
    todayClose: open.filter((j) => j.closesAt === TODAY).length,
    dated: open.filter((j) => !isAlways(j)).length,
    always: open.filter((j) => isAlways(j)).length,
    hiring: Object.keys(openBy).length,
    watched: companies.length,
    empty: companies.filter((c) => c.o === 0).length,
    streak,
    streakFrom: scans.length >= streak && streak ? scans[streak - 1].day : TODAY,
    perDay: 2,
    summarized: jobs.filter((j) => j.s).length,
    notice: jobs.filter((j) => j.sk).length,
    bare: jobs.filter((j) => !j.s && !j.sk).length,
    closedKept: closed.length,
    stale: STALE_DAYS,
  };

  memo = { meta, hist, industries: inds, roles: rs, companies, tagIndex, scans, jobs };
  return memo;
};

/* 산업 이름 → 주소. 산업 페이지가 있는 것만. */
export const indSlugOf = (name) => industrySlug(name);
export { JOBS };
