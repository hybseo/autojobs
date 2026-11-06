/*
 * 새 공고·마감 임박 공고를 뽑아 회원 알림 서버로 보냅니다.
 * =====================================================================
 * 언제 도나: .github/workflows/notify.yml 이 「공고 갱신」이 끝난 뒤 실행합니다.
 * 무엇을 보내나
 *   fresh   최근 2일 안에 처음 본 진행중 공고 (id·제목·회사·산업)
 *   closing 마감까지 0~3일 남은 공고 (id·제목·회사·남은 일수)
 * 같은 공고를 다시 보내도 서버가 한 번만 처리합니다(중복 알림 없음).
 *
 * 보내는 곳과 비밀키는 환경변수로 받습니다.
 *   NOTIFY_URL     예) https://searchjob.co.kr
 *   NOTIFY_SECRET  Cloudflare 의 NOTIFY_SECRET 과 같은 값
 * 둘 중 하나라도 없으면 아무것도 하지 않고 정상 종료합니다(회원 기능 설정 전).
 * 이 단계가 실패해도 공고 갱신 자체는 실패로 만들지 않습니다(워크플로 쪽 설정).
 *
 * 산업 판정은 src/lib.js 의 industriesOf 와 같은 규칙입니다. lib.js 는 Astro 에서만
 * 불러올 수 있어 여기에 같은 규칙을 적었습니다. lib.js 를 바꾸면 여기도 맞추세요.
 *
 * 사용: node scripts/notify_delta.mjs [--dry]   (--dry 는 보내지 않고 요약만 출력)
 */
import fs from 'node:fs';
import { rolesOf, roleName } from '../src/roles.js';

const dry = process.argv.includes('--dry');
const URL_BASE = (process.env.NOTIFY_URL || '').replace(/\/$/, '');
const SECRET = process.env.NOTIFY_SECRET || '';
if (!dry && (!URL_BASE || !SECRET)) {
  console.log('NOTIFY_URL / NOTIFY_SECRET 이 없어 건너뜁니다(회원 기능 설정 전).');
  process.exit(0);
}

const jobsDoc = JSON.parse(fs.readFileSync('src/data/jobs.json', 'utf8'));
const registry = JSON.parse(fs.readFileSync('src/data/companies.json', 'utf8'));
const TAG_BY_JOB = (JSON.parse(fs.readFileSync('src/data/job-tags.json', 'utf8')).tags) || {};
const jobs = jobsDoc.jobs;

// ── lib.js 와 같은 규칙 ──
const parseDate = (s) => new Date(s + 'T00:00:00+09:00');
const TODAY = new Date((process.env.TODAY ?? jobsDoc.collectedAt) + 'T00:00:00+09:00');
const DAY = 86400000;
const normCo = (v) => String(v || '').replace(/[\s.,()㈜/]|주식회사/g, '').toLowerCase();
const CO_INDUSTRY = Object.fromEntries((registry.companies || []).map((c) => [c.slug, c.industry || []]));
const CO_AFFILIATE = Object.fromEntries(
  (registry.companies || []).filter((c) => c.affiliateIndustry).map((c) => [c.slug, c.affiliateIndustry]));
const industriesOf = (job) => {
  const table = CO_AFFILIATE[job.companySlug];
  if (table) {
    const target = normCo(job.company);
    for (const [name, inds] of Object.entries(table)) {
      const key = normCo(name);
      if (key && target.includes(key)) return inds;
    }
  }
  return CO_INDUSTRY[job.companySlug] || [];
};
const isGone = (j) => Boolean(j.goneAt);
const isOpen = (j) => !isGone(j) && (!j.closesAt || parseDate(j.closesAt) >= TODAY);
const daysLeft = (j) => (j.closesAt ? Math.ceil((parseDate(j.closesAt) - TODAY) / DAY) : Infinity);
const coName = Object.fromEntries((registry.companies || []).map((c) => [c.slug, c.name]));

const since = new Date(TODAY.getTime() - 2 * DAY).toISOString().slice(0, 10);
let fresh = jobs
  .filter((j) => isOpen(j) && j.firstSeenAt && j.firstSeenAt >= since)
  .map((j) => ({
    id: String(j.id), title: j.title, co: coName[j.companySlug] || j.company || '',
    slug: j.companySlug, ind: industriesOf(j),
    // 「내 키워드」 알림용: 직무 이름과 기술·역량 태그 (사이트의 직무·태그와 같은 규칙)
    role: rolesOf(j).map(roleName), tag: TAG_BY_JOB[j.id] || [],
  }));
let closing = jobs
  .filter((j) => isOpen(j) && j.closesAt && daysLeft(j) >= 0 && daysLeft(j) <= 3)
  .map((j) => ({ id: String(j.id), title: j.title, co: coName[j.companySlug] || j.company || '', days: daysLeft(j) }));

// --test: 실제 공고 대신 시험용 새 공고만 보냅니다(알림이 폰·PC 로 오는지 확인용).
//   · TEST_SLUGS(쉼표로 구분, 기본 toss) 기업을 팔로우한 회원에게 가는 공고 기업당 1건
//   · TEST_QUERY 가 있으면 그 검색어를 저장한 회원에게 가는 공고 1건
if (process.argv.includes('--test')) {
  const stamp = Date.now();
  const q = (process.env.TEST_QUERY || '').trim();
  const slugs = (process.env.TEST_SLUGS || 'toss').split(',').map((x) => x.trim()).filter(Boolean);
  fresh = slugs.map((slug) => ({
    id: `test-follow-${slug}-${stamp}`, title: `[알림 시험] ${coName[slug] || slug} 새 공고가 올라왔습니다`,
    co: coName[slug] || slug, slug, ind: [],
  }));
  const tk = (process.env.TEST_KEYWORDS || '').split(',').map((x) => x.trim()).filter(Boolean);
  if (tk.length) fresh.push({ id: `test-keyword-${stamp}`, title: `[알림 시험] 키워드 ${tk.join('·')} 공고`, co: '시험회사', slug: 'test', ind: tk, role: tk, tag: tk });
  if (q) fresh.push({ id: `test-search-${stamp}`, title: `[알림 시험] ${q} 관련 새 공고`, co: '시험회사', slug: 'test', ind: [] });
  closing = [];
}

console.log(`기준일 ${jobsDoc.collectedAt} · 새 공고 ${fresh.length}건 · 마감 임박 ${closing.length}건`);
if (dry) { console.log('(--dry) 보내지 않습니다.'); process.exit(0); }

const headers = { Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json', 'User-Agent': 'searchjob-notify/1.0 (+https://searchjob.co.kr)', Accept: 'application/json' };
async function call(path, body) {
  const r = await fetch(URL_BASE + path, { method: 'POST', headers, body: JSON.stringify(body) });
  const text = await r.text();
  let j = {};
  try { j = JSON.parse(text); } catch { /* 본문이 JSON 이 아님 */ }
  if (!r.ok) {
    const plain = text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 400);
    throw new Error(`${path} → ${r.status} (cf-ray ${r.headers.get('cf-ray') || '-'}) ${plain}`);
  }
  return j;
}

// 한 번에 너무 많이 보내지 않도록 500건씩 나눕니다.
const chunks = [];
const n = Math.max(Math.ceil(fresh.length / 500), Math.ceil(closing.length / 500), 1);
for (let i = 0; i < n; i += 1) chunks.push({ fresh: fresh.slice(i * 500, (i + 1) * 500), closing: closing.slice(i * 500, (i + 1) * 500) });
for (const c of chunks) {
  const r = await call('/api/internal/new-jobs', c);
  console.log('알림 대상 처리:', JSON.stringify(r));
}

// 쌓인 알림 보내기: 서버가 한 번에 일부만 처리하므로 다 끝날 때까지 반복합니다.
for (let i = 0; i < 100; i += 1) {
  const r = await call('/api/internal/flush', {});
  console.log('알림 발송:', JSON.stringify(r));
  if (r.skipped || !r.remaining) break;
}
console.log('끝');
