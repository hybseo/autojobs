/*
 * 마감 공고 영구 이동 (2026-11-13)
 * ============================================================
 * src/data/job-redirects.json 에 적힌 "이 공고 id → 이 회사" 기록을 읽어,
 * dist/_redirects 에 301 줄로 더합니다. astro build 뒤에 돌립니다
 * (package.json 의 build 스크립트 참고).
 *
 * 왜 필요한가
 * -----------
 * 마감된 공고는 jobs.json 에 60일만 남습니다(src/lib.js KEEP_DAYS 참고).
 * 60일이 지나면 데이터와 상세 페이지가 함께 사라지는데, 구글은 그 주소를
 * 60일보다 더 오래 재크롤링하는 경우가 있어(실제로 44일째 사례 있음)
 * 404 가 다시 쌓입니다. 보관 기간을 늘려도 언젠가는 지워야 하므로 똑같은
 * 일이 반복됩니다.
 *
 * 그래서 공고 내용은 지우되, "이 주소는 이 회사로 보낸다"는 한 줄만 영원히
 * job-redirects.json 에 남겨 두고(scripts/fetch_jobs.py 의 record_redirects
 * 가 적습니다), 빌드 때마다 이 파일이 그 기록을 실제 301 넘겨보내기로
 * 바꿉니다. 본문을 들고 있는 것보다 훨씬 가볍습니다.
 *
 * 회사가 사라지면
 * ----------------
 * 기록을 남긴 뒤에 그 회사가 수집을 끄거나(enabled:false) 등록에서
 * 지워지면, 회사 페이지도 없어집니다. 그런 주소로 넘겨보내면 404 로
 * 바뀌어 보내는 것뿐이라 의미가 없습니다. 그래서 넘겨보낼 때마다 지금
 * companies.json 을 다시 봐서, 회사 페이지가 실제로 있는 것만 그 회사로
 * 보내고 없으면 홈(/)으로 보냅니다.
 *
 * _redirects 규칙 수 한도
 * ------------------------
 * 클라우드플레어는 _redirects 한 파일에 쓸 수 있는 줄 수에 한도가
 * 있습니다(문서 기준 정적 규칙 2,000줄). 마감이 하루 평균 11건이니
 * 한 달에 300여 건씩 늘어나므로, 몇 년 안에는 다른 방법(예: 워커에서
 * 직접 처리)으로 옮겨야 할 수 있습니다. 지금은 그 한도에 한참 못
 * 미치므로 당장은 이 방식이 가장 가볍고 확실합니다.
 */
import { readFileSync, writeFileSync, existsSync, appendFileSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const REDIRECTS_JSON = path.join(ROOT, 'src/data/job-redirects.json');
const COMPANIES_JSON = path.join(ROOT, 'src/data/companies.json');
const DIST_REDIRECTS = path.join(ROOT, 'dist/_redirects');

function readJson(p, fallback) {
  try {
    return JSON.parse(readFileSync(p, 'utf-8'));
  } catch {
    return fallback;
  }
}

const redirectDoc = readJson(REDIRECTS_JSON, { redirects: {} });
const entries = Object.entries(redirectDoc.redirects || {});
if (!entries.length) {
  console.log('[build_redirects] 넘겨보낼 마감 공고 기록이 없습니다. 건너뜁니다.');
  process.exit(0);
}

const companies = readJson(COMPANIES_JSON, { companies: [] }).companies || [];
// 회사 페이지는 enabled:false 가 아니면 만들어집니다 (src/lib.js companyPages 참고).
const livePages = new Set(companies.filter((c) => c && c.slug && c.enabled !== false).map((c) => c.slug));

/*
 * 되살아난 공고는 건너뜁니다.
 *
 * 마감됐다가 60일 뒤 데이터에서 빠져 여기 기록된 뒤에, 회사가 같은 id로
 * 다시 올리면(재게시) astro build 가 /job/{id}/ 에 진짜 상세 페이지를
 * 또 만듭니다. 그런데도 여기서 넘겨보내기를 추가하면 _redirects 가 실제
 * 파일보다 먼저 적용돼(클라우드플레어 문서) 그 진짜 페이지를 가립니다.
 * 2026-11-13 에 7건이 이렇게 걸려 있던 걸 찾아 뺐습니다.
 */
let toCompany = 0;
let toHome = 0;
let skippedRevived = 0;
const lines = [];
for (const [id, slug] of entries) {
  if (!id) continue;
  if (existsSync(path.join(ROOT, 'dist/job', id, 'index.html'))) {
    skippedRevived++;
    continue;
  }
  const target = livePages.has(slug) ? `/company/${slug}/` : '/';
  if (livePages.has(slug)) toCompany++; else toHome++;
  lines.push(`/job/${id}/  ${target}  301`);
}

if (!existsSync(path.dirname(DIST_REDIRECTS))) {
  console.log('[build_redirects] dist 가 없습니다. astro build 를 먼저 돌리세요.');
  process.exit(1);
}

const header = '\n# 마감 뒤 완전히 빠진 공고의 영구 넘겨보내기 (scripts/build_redirects.mjs 가 자동 생성, 손으로 고치지 마세요)\n';
appendFileSync(DIST_REDIRECTS, header + lines.join('\n') + '\n', 'utf-8');

console.log(`[build_redirects] ${lines.length}건 추가 (회사로 ${toCompany}건 · 홈으로 ${toHome}건`
  + `${skippedRevived ? ` · 되살아나서 건너뜀 ${skippedRevived}건` : ''}) → ${DIST_REDIRECTS}`);
if (lines.length > 1800) {
  console.log(`[build_redirects] 주의: ${lines.length}건은 클라우드플레어 _redirects 한도(약 2,000줄)에 가깝습니다. 위 주석 참고.`);
}
