/*
 * 요약의 자격요건에서 경력 구분을 읽어 jobs.json 에 넣습니다.
 *
 * 왜 수집기가 아니라 여기서 하는가
 * --------------------------------
 * 요약(summaries.json)은 수집기가 모르는 파일입니다. 수집기는 공고를
 * 받아 오는 일만 하고, 요약은 우리가 따로 써 둔 것입니다. 그래서 수집이
 * 끝난 뒤에 한 번 더 지나가며 채웁니다.
 *
 * 순서가 중요합니다 — fetch_jobs.py 가 jobs.json 을 통째로 다시 쓰므로,
 * 반드시 그 뒤에 돌아야 합니다. daily.yml 에 그 순서로 넣어 두었습니다.
 *
 * 무엇을 하는가 (2026-11-02 대표님 결정: 회사가 정한 경력 구분을 따른다)
 * ---------------------------------------------------------------------
 * career 가 「무관」인 공고만 봅니다. 수집기가 ATS 칸에서 읽은 값이
 * 요약보다 정확하므로, 값이 있는 공고는 건드리지 않습니다.
 *
 * fetch_jobs.py 의 career_from_title() 이 공고 **제목**에서 먼저 읽습니다.
 * 이 스크립트는 그 다음으로 **요약의 한 줄과 자격요건**을 봅니다.
 *
 *   2026-11-02 실측 (진행중 4,973건)
 *     손대기 전        무관 2,133건
 *     제목에서 읽은 뒤  무관 1,649건
 *     요약까지 읽은 뒤  무관   863건
 *
 * 패턴을 세 번 다듬었습니다. 1차에서 「신입」으로 읽은 56건을 전수
 * 확인했더니 대부분 오탐이었습니다.
 *
 *   「초대졸 이상」      학력입니다. 그래서 `대졸` 을 빼냈습니다
 *                       (두산퓨얼셀·JW중외제약 3건·루트로닉)
 *   「인턴 활동 경험」    인턴 경험을 요구하는 것이지 신입이 아닙니다.
 *                       그래서 `인턴` 단독을 빼냈습니다 (토스 3건·오늘의집)
 *   「신규입사자 온보딩」  뽑는 사람이 신입이 아니라, 신규 입사자를 돕는
 *                       업무입니다 (라이드플럭스·토스 2건)
 *   「신입 가능」        신입도 된다는 뜻입니다. 「신입」이 아니라
 *                       **신입/경력** 으로 봅니다 (42dot·스트라드비전 등)
 *
 * 다듬은 결과 신입 판정이 56건 → 4건이 되었고, 그 4건은 전수 확인했습니다
 * (딥엑스 2건 Entry-Level · NAVER 신입 대상 · 인터엑스 신입 기술영업).
 */
import fs from 'fs';

const JOBS = 'src/data/jobs.json';
const SUM = 'src/data/summaries.json';

/* 회사가 「무관」이라고 밝힌 것. 손대지 않습니다.
   이걸 「경력」으로 읽으면 정반대가 됩니다. 2026-11-02 에 120건 확인. */
const UNTOUCH = /무경력|경력\s*무관|경력\s*불문|경력\s*상관\s*없|연차\s*무관|경력\s*여부\s*무관|역량·?\s*경험\s*무관/;

/* 신입만 뽑는다고 밝힌 것.
   `대졸` 과 `인턴` 단독은 넣지 않습니다 — 위 설명 참고. */
const NEW_ONLY = /신입급|신입\s*(사원|대상|채용|모집|공채|선발)|Entry[-\s]?Level|대졸\s*신입|신입\s*기술영업|신입\s*엔지니어|생산\s*인턴/i;

/* 신입도 지원할 수 있다고 밝힌 것 → 경력과 함께 받는 자리입니다. */
const NEW_OK = /신입\s*(가능|지원|도)|신입\s*(또는|or)|졸업\s*예정자?\s*(포함|가능|지원|까지)|기졸업자?\s*(및|와)?\s*.{0,12}졸업\s*예정/;

/* 경력을 요구한 것. 「경력」 한 글자만으로는 보지 않습니다 —
   「경력 무관」·「경력기술서」에 걸립니다. */
const EXP = /경력\s*\d|\d+\s*년\s*(이상|차)|\d+\s*~\s*\d+\s*년|\d+\s*년\s*↑|경력\s*(사원|직|자)|유관\s*경력|관련\s*경력|실무\s*경력|\bsenior\b|\byears?\s*of\s*experience\b/i;

export function careerFromSummary(career, summary) {
  if (String(career || '').trim() !== '무관') return career;
  if (!summary || summary.skip) return career;
  const hay = [summary.gist, ...(summary.quals || [])].filter(Boolean).join(' | ');
  if (!hay || UNTOUCH.test(hay)) return career;
  const exp = EXP.test(hay);
  const only = NEW_ONLY.test(hay);
  const ok = NEW_OK.test(hay);
  if (only && !exp) return '신입';
  if (exp && (only || ok)) return '신입/경력';
  if (ok) return '신입/경력';
  if (exp) return '경력';
  return career;
}

/* 직접 돌릴 때만 파일을 고칩니다. import 만 하면 아무 일도 일어나지
   않습니다(시험에서 함수만 쓰기 위해). */
const direct = process.argv[1] && process.argv[1].endsWith('career_from_summary.mjs');
if (direct) {
  const read = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
  let doc;
  let S;
  try {
    doc = read(JOBS);
    S = read(SUM).summaries || {};
  } catch (e) {
    console.log(`  ! 경력 구분: 파일을 읽지 못했습니다 — ${e.message}`);
    console.log('    jobs.json 은 그대로 둡니다.');
    process.exit(0);          // 수집 결과를 버리지 않습니다
  }

  const rows = doc.jobs || doc;
  const moved = {};
  let n = 0;
  for (const j of rows) {
    const got = careerFromSummary(j.career, S[j.id]);
    if (got === j.career) continue;
    moved[`${j.career} → ${got}`] = (moved[`${j.career} → ${got}`] || 0) + 1;
    j.career = got;
    n += 1;
  }

  if (!n) {
    console.log('  · 경력 구분: 요약에서 더 읽을 것이 없습니다.');
  } else {
    console.log(`  · 경력 구분: 요약에서 ${n}건을 읽었습니다`);
    for (const [k, v] of Object.entries(moved).sort((a, b) => b[1] - a[1])) {
      console.log(`      ${k}  ${v}건`);
    }
    fs.writeFileSync(JOBS, `${JSON.stringify(doc, null, 1)}\n`);
  }
}
