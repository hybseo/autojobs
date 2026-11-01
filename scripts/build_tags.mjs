/*
 * 공고 요약에서 태그를 뽑아 src/data/job-tags.json 을 만듭니다.
 *
 *   node scripts/build_tags.mjs
 *
 * 왜 요약에서 뽑나
 * ----------------
 * 사전(src/tags.js)은 2026-10-28 에 공고 **본문** 5,311건에서 만들었고
 * 그때 부착률이 72.5% 였습니다. 같은 사전을 **요약** 에 돌리니 88.3% 가
 * 나왔습니다. 요약은 회사 소개문·복지·전형절차를 이미 걷어낸 글이라
 * 걸릴 것만 걸립니다. 본문에서 뽑던 시절의 오탐(「채용담당자 유선 문의」
 * 안내문에 걸려 535건 중 474건이 오탐이던 것)이 애초에 생기지 않습니다.
 *
 * 무엇을 보고 뽑나
 * ----------------
 * 제목 + 요약 다섯 칸(gist·duties·quals·prefs)입니다.
 * 제목도 공고가 준 글이고, 제목에만 적힌 기술이 흔합니다.
 * 근무지(loc)는 보지 않습니다. 지명이 기술 태그에 걸릴 이유가 없습니다.
 *
 * 순서 — 구체적인 것부터
 * ----------------------
 * 실행명세에 「공고 하나에 태그는 4개까지. 구체적인 것부터 —
 * AUTOSAR 가 임베디드보다 앞섭니다」라고 적혀 있습니다.
 * 구체성을 재는 자로 **전체 건수가 적은 것** 을 씁니다. AUTOSAR 18건이
 * 임베디드·펌웨어 228건보다 앞섭니다. 건수가 같으면 이름순으로 둡니다
 * (돌릴 때마다 순서가 바뀌면 안 되기 때문입니다).
 *
 * 건수는 자가 아니라 대용물입니다. 어색한 순서가 보이면 사전에 우선순위
 * 칸을 따로 두는 쪽으로 고치면 됩니다.
 *
 * 1건짜리 태그 (2026-11-01 대표님 결정)
 * -------------------------------------
 * 원칙 4 는 「2건 이상이면 페이지를 만든다」입니다. 1건짜리는 눌러도
 * 그 공고 하나뿐이라 길이 아닙니다. 그래서 **페이지는 만들지 않되,
 * 카드와 상세에는 그대로 보여줍니다.** 누를 수 없는 표시로 둡니다.
 * link:false 가 그 뜻입니다.
 *
 * 이미지 공고
 * -----------
 * 본문이 이미지뿐인 공고는 요약이 없어 태그도 없습니다. 요약이 들어오면
 * 이 스크립트를 다시 돌리면 그 공고에만 태그가 붙습니다.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), 'utf8'));

const { TAGS } = await import(path.join(ROOT, 'src/tags.js'));
const SLUG = read('src/data/tag-slug.json').slug;

/* 사전을 평평하게 폅니다. 분류는 그대로 들고 갑니다. */
const dict = [];
for (const [cat, list] of TAGS) for (const [name, re] of list) dict.push({ cat, name, re });

/* 슬러그. 표에 없으면 이름의 영문 토막으로 만듭니다. */
const autoSlug = (name) =>
  (name.match(/[A-Za-z0-9][A-Za-z0-9+#.]*/g) || [])
    .map((s) =>
      s.toLowerCase().replace(/\+\+/g, 'pp').replace(/#/g, 'sharp').replace(/[^a-z0-9]/g, ''))
    .filter(Boolean)
    .join('-');
const slugOf = (name) => SLUG[name] || autoSlug(name);

/* 진행중 판정. 마감일이 없거나 형식이 아니면 상시로 봅니다. */
const today = new Date().toISOString().slice(0, 10);
const isOpen = (j) => {
  const c = String(j.closesAt || '').slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(c)) return true;
  return c >= today;
};

const raw = read('src/data/jobs.json');
const jobs = Array.isArray(raw) ? raw : raw.jobs || [];
const summaries = read('src/data/summaries.json').summaries || {};

/* 1. 공고마다 걸리는 태그를 모읍니다 */
const hit = new Map();
const count = new Map();
let open = 0, withSum = 0;
for (const j of jobs) {
  if (!isOpen(j)) continue;
  open++;
  const s = summaries[j.id];
  if (!s || s.skip) continue;
  withSum++;
  const hay = [j.title, s.gist, ...(s.duties || []), ...(s.quals || []), ...(s.prefs || [])]
    .filter(Boolean).join('\n');
  const names = [...new Set(dict.filter((d) => d.re.test(hay)).map((d) => d.name))];
  hit.set(j.id, names);
  for (const n of names) count.set(n, (count.get(n) || 0) + 1);
}

/* 2. 구체적인 것부터 줄 세웁니다 */
const order = (a, b) => (count.get(a) - count.get(b)) || (a < b ? -1 : a > b ? 1 : 0);
const tags = {};
for (const [id, names] of hit) {
  if (!names.length) continue;
  tags[id] = [...names].sort(order);
}

/* 3. 태그 색인. 페이지를 만들 태그와 아닌 태그를 가릅니다 */
const catOf = Object.fromEntries(dict.map((d) => [d.name, d.cat]));
const index = {};
for (const [name, n] of [...count.entries()].sort((a, b) => b[1] - a[1])) {
  index[name] = { slug: slugOf(name), cat: catOf[name], count: n, link: n >= 2 };
}

const taggedJobs = Object.keys(tags).length;
const sizes = Object.values(tags).map((v) => v.length).sort((a, b) => a - b);
const out = {
  _readme: [
    '공고별 기술·역량 태그. 요약(summaries.json)에서 뽑았습니다.',
    '',
    '  tags   공고 id → 태그 이름 배열. **구체적인 것부터** 줄 세워져 있습니다.',
    '         앞에서 4개가 목록 카드에 나갑니다. 상세에는 전부 보여줍니다.',
    '  index  태그 이름 → { slug, cat, count, link }',
    '         slug  주소. /tech/{slug}/ 로 갑니다. 한번 정하면 바꾸지 마세요.',
    '         count 이 태그가 붙은 진행중 공고 수',
    '         link  false 면 페이지를 만들지 않습니다 (1건짜리).',
    '               화면에는 보여주되 누를 수 없게 둡니다.',
    '',
    '본문이 이미지뿐이라 요약이 없는 공고는 여기에 없습니다.',
    '요약이 들어오면 scripts/build_tags.mjs 를 다시 돌리면 됩니다.',
    '',
    `만든 날 ${today} · 진행중 ${open}건 중 요약 있는 ${withSum}건을 훑어`,
    `${taggedJobs}건에 태그가 붙었습니다 (${(taggedJobs / withSum * 100).toFixed(1)}%).`,
  ],
  tags,
  index,
};

fs.writeFileSync(path.join(ROOT, 'src/data/job-tags.json'), JSON.stringify(out, null, 1) + '\n');

const linkable = Object.values(index).filter((v) => v.link).length;
console.log(`진행중 ${open} · 요약 있음 ${withSum} · 태그 붙음 ${taggedJobs} (${(taggedJobs / withSum * 100).toFixed(1)}%)`);
console.log(`태그 ${Object.keys(index).length}종 사용 · 페이지 만들 것 ${linkable}종 · 1건짜리 ${Object.keys(index).length - linkable}종`);
console.log(`공고당 태그 — 중간값 ${sizes[Math.floor(sizes.length / 2)]} · 최대 ${sizes[sizes.length - 1]}`);
console.log(`크기 ${(fs.statSync(path.join(ROOT, 'src/data/job-tags.json')).size / 1e6).toFixed(2)} MB`);
