import raw from './data/jobs.json';
import registry from './data/companies.json';
import { TAGS, TAG_TOP } from './tags.js';

export const COLLECTED_AT = raw.collectedAt;
export const JOBS = raw.jobs;

/*
 * 오늘 기준 시각. 빌드 시점 날짜를 쓰되, 검증용으로 고정값을 허용합니다.
 *
 * 반드시 parseDate 와 같은 기준(한국시간 자정)이어야 합니다.
 * new Date('2026-08-27') 는 UTC 자정 = 한국시간 오전 9시로 해석됩니다.
 * 그러면 closesAt(한국시간 자정)이 TODAY 보다 9시간 이르게 되어,
 * 마감일이 오늘인 공고가 하루 일찍 목록에서 사라집니다.
 * 실제로 현대오토에버 40건이 마감 당일에 통째로 빠진 적이 있습니다.
 */
export const TODAY = new Date((process.env.TODAY ?? COLLECTED_AT) + 'T00:00:00+09:00');

const day = 86400000;

/**
 * 수집 데이터가 며칠 지났는지.
 *
 * 빌드 시점에 계산합니다. 갱신이 밀리면 사이트도 다시 빌드되지 않으므로,
 * 이 값이 그대로 굳어 화면에 남습니다. 그게 목적입니다.
 * 갱신이 멈춰도 화면은 멀쩡해 보이는 것이 가장 위험합니다.
 * 구직자가 마감된 공고를 오늘 것으로 착각하게 됩니다.
 */
export const STALE_DAYS = (() => {
  const c = new Date(COLLECTED_AT + 'T00:00:00+09:00');
  const now = new Date();
  const kstToday = new Date(
    new Date(now.getTime() + 9 * 3600000).toISOString().slice(0, 10) + 'T00:00:00+09:00');
  return Math.max(0, Math.round((kstToday - c) / day));
})();
export const parseDate = (s) => new Date(s + 'T00:00:00+09:00');

/**
 * 상시채용 판정.
 *
 * 채용 시스템마다 상시채용을 표현하는 방식이 다릅니다.
 *  - 그리팅  : 마감일을 아예 비워둡니다. closesAt 이 빈 문자열입니다.
 *  - 리크루터: 마감일 칸이 필수라 먼 미래 날짜를 넣습니다. 2040-01-31 같은 값이 옵니다.
 * 그래서 "마감일 없음" 과 "접수 기간이 비정상적으로 김" 을 모두 상시로 봅니다.
 *
 * closesAt 이 비어 있는데 parseDate 를 태우면 Invalid Date 가 되고,
 * 그 뒤의 모든 날짜 비교가 조용히 false 가 됩니다. 반드시 여기서 먼저 걸러야 합니다.
 */
const ALWAYS_DAYS = 200;
export const isAlways = (j) => {
  if (!j.closesAt) return true;
  const s = parseDate(j.postedAt), e = parseDate(j.closesAt);
  return (e - s) / day > ALWAYS_DAYS;
};

/*
 * 회사가 채용 사이트에서 내린 공고.
 *
 * goneAt 은 수집기가 "어제까지 있었는데 오늘 사라졌다" 고 표시한 날짜입니다.
 * 페이지는 60일 남기지만(아래 STALE_DAYS 주석 참고) 목록에는 넣지 않습니다.
 * 지원할 수 없는 자리이기 때문입니다.
 */
export const isGone = (j) => Boolean(j.goneAt);

/*
 * 아직 지원할 수 있는 공고.
 *
 * 두 가지를 모두 봅니다.
 *   1) 마감일이 지나지 않았는가
 *   2) 회사가 내리지 않았는가(goneAt)
 *
 * 예전에는 마감일만 봤습니다. 그래서 마감일이 없는 상시채용 공고는 회사가
 * 내려도 목록에 남았습니다. 2026-09-28 기준 282건이 그런 상태였고, 그중에는
 * 18일 전에 사라진 망고부스트 공고처럼 원문이 이미 404 인 것도 있었습니다.
 * 구직자가 눌러도 지원할 수 없는 자리라 목록에서 뺍니다.
 */
export const openJobs = () =>
  JOBS.filter((j) => !isGone(j) && (!j.closesAt || parseDate(j.closesAt) >= TODAY));

/*
 * 마감된 공고. 기업 페이지 아카이브에 씁니다.
 *
 * 마감일이 지난 것과 회사가 내린 것을 모두 담습니다. 상시채용은 마감일이
 * 없지만 회사가 내리면 여기로 옵니다.
 */
export const closedJobs = () =>
  JOBS.filter((j) => isGone(j) || (j.closesAt && parseDate(j.closesAt) < TODAY));

/*
 * 마감 공고 보관 기간.
 *
 * 공고가 마감되면 다음 수집 때 데이터에서 빠지고, /job/{id}/ 페이지도
 * 사라져 404 가 됩니다. 구글은 색인한 주소를 한동안 계속 방문하므로
 * 404 가 쌓입니다. 실제로 색인 32개 중 14개가 404 였습니다.
 *
 * 그래서 마감 뒤에도 일정 기간 페이지를 남깁니다. 검색으로 들어온
 * 사람에게 "마감됐다" 고 알려주고 다른 공고로 안내하는 편이,
 * 빈손으로 돌려보내는 것보다 낫습니다.
 *
 * 60일로 잡은 근거: 구글이 404 를 색인에서 지우기까지 대개 1~2개월
 * 걸립니다. 실제로 이 사이트의 404 14건은 2026-07-16 에 처음 감지돼
 * 8-29 에도 재크롤링되고 있었습니다. 30일이면 보관이 끝나는 시점에
 * 구글이 아직 재방문 중이라 404 가 다시 생깁니다.
 *
 * 더 늘리면 마감 공고로도 검색 유입을 받을 수 있지만 데이터가 커집니다.
 * 하루 평균 11건이 마감되므로 30일 늘릴 때마다 약 330건이 쌓입니다.
 */
export const KEEP_DAYS = 60;

/** 보관 기간이 지나지 않은 마감 공고. 페이지를 남겨둡니다. */
export const isRecentlyClosed = (j) => {
  if (!j.closesAt) return false;
  const gone = (TODAY - parseDate(j.closesAt)) / day;
  return gone > 0 && gone <= KEEP_DAYS;
};

/** 남은 일수. 마감일이 없으면 Infinity 입니다. 정렬에 쓸 때 주의하세요. */
export const daysLeft = (j) =>
  j.closesAt ? Math.ceil((parseDate(j.closesAt) - TODAY) / day) : Infinity;

/** 정렬용 순번. 마감 있는 공고가 앞, 상시채용이 뒤로 갑니다. */
export const SORT_ALWAYS = 99999;
export const sortValue = (j) => (isAlways(j) ? SORT_ALWAYS : daysLeft(j));

/** 마감 임박순 비교기. 상시채용끼리는 최근 게시 순입니다. */
export const byDeadline = (a, b) => {
  const aa = isAlways(a), bb = isAlways(b);
  if (aa !== bb) return aa ? 1 : -1;
  if (aa) return (b.postedAt || '').localeCompare(a.postedAt || '');
  return daysLeft(a) - daysLeft(b);
};

/** 접수 기간 중 현재 위치. 0~1. 상시채용은 null 이라 게이지를 그리지 않습니다. */
export const progress = (j) => {
  if (isAlways(j)) return null;
  const s = parseDate(j.postedAt), e = parseDate(j.closesAt);
  return Math.max(0.02, Math.min(1, (TODAY - s) / (e - s)));
};

/*
 * 근무지 문자열에서 시도(addressRegion)를 뽑습니다.
 *
 * 구글 JobPosting 은 jobLocation.address.addressRegion 을 권장합니다.
 * 없다고 검색에서 빠지지는 않지만, 채울 수 있는 것은 채워둡니다.
 *
 * 원본 값이 제각각입니다. 실제로 관찰된 형태:
 *   "서울"            시도명 그대로
 *   "평택" "서산"      시군구명만
 *   "한국단자공업(인천 송도)"  회사명에 지역이 섞임
 *   "성서공장(본사)"    공장 이름만. 지역을 알 수 없음
 *   "미국" "독일"      해외
 *
 * 알 수 없으면 undefined 를 돌려줍니다. 억지로 추측하지 않습니다.
 * 잘못된 지역을 넣는 것이 비워두는 것보다 나쁩니다.
 */
// 순서가 중요합니다. 이름이 겹치는 경우 앞에 있는 것이 먼저 잡힙니다.
// "경기 광주시" 가 광주광역시로 잡히지 않도록 도 단위를 앞에 둡니다.
const SIDO = ['경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주',
              '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종'];

// 시군구 → 시도. 실제 데이터에 나온 것만 담았습니다.
// 추측으로 늘리지 말고, 새 값이 관찰될 때 확인 후 추가하세요.
const CITY_TO_SIDO = {
  평택: '경기', 수원: '경기', 판교: '경기', 성남: '경기', 화성: '경기',
  동탄: '경기', 여주: '경기', 안산: '경기', 용인: '경기', 시흥: '경기',
  서산: '충남', 천안: '충남', 아산: '충남', 당진: '충남',
  충주: '충북', 청주: '충북', 전의: '세종',
  포항: '경북', 구미: '경북', 경주: '경북', 김천: '경북',
  창원: '경남', 김해: '경남', 양산: '경남',
  익산: '전북', 전주: '전북', 광양: '전남', 여수: '전남',
};

export const addressRegion = (location) => {
  const s = (location || '').trim();
  if (!s) return undefined;

  // 여러 지역이 적힌 경우("서울/경기") 문자열에서 먼저 나오는 쪽을 씁니다.
  // 목록 순서로 고르면 "서울/경기" 가 경기로 잡혀 어색해집니다.
  // 같은 위치에서 겹치면 더 긴 이름이 우선입니다("경기 광주시" → 경기).
  let best;
  for (const v of SIDO) {
    const i = s.indexOf(v);
    if (i < 0) continue;
    if (!best || i < best.i) best = { i, v };
  }
  if (best) return best.v;

  for (const [city, sido] of Object.entries(CITY_TO_SIDO)) {
    if (s.includes(city)) return sido;
  }
  return undefined;   // 공장 이름만 있거나 해외인 경우
};

/*
 * 산업 분류.
 *
 * companies.json 의 industry 태그를 그대로 씁니다. 코드에 산업 목록을
 * 박아두지 않으므로, 태그만 붙이면 산업 페이지가 저절로 생깁니다.
 *
 * 한 회사가 여러 산업에 걸칩니다. 42dot 은 자동차부품이면서 IT 이고,
 * 원익은 기계장비이면서 반도체입니다. 그런 회사의 공고는 양쪽 산업에
 * 모두 나옵니다. 중복이지만 그게 실제에 맞습니다. 42dot 엔지니어를
 * 찾는 사람은 자동차에서도, IT 에서도 찾을 수 있어야 합니다.
 *
 * 주소에 한글을 쓸 수 없어 영문 슬러그를 둡니다.
 * 한번 정한 슬러그는 바꾸지 마세요. 색인된 주소가 깨집니다.
 */
const INDUSTRY_SLUG = {
  '자동차부품': 'auto-parts',
  '로봇': 'robotics',
  '반도체': 'semiconductor',
  '기계장비': 'machinery',
  '전기전자': 'electronics',
  '소재': 'materials',
  'IT': 'it',
  '물류': 'logistics',
  '화학': 'chemical',
  '기계': 'machinery',
  '금융': 'finance',
  '제약바이오': 'pharma-bio',
  /*
   * 조선·방산·철강·항공을 한 칸으로 묶습니다(2026-10-01).
   *
   * 네 분야를 따로 두면 각각 열 곳 안팎이라 페이지가 빈약합니다. 회사도
   * 서로 걸칩니다. 한화에어로스페이스는 방산이면서 항공, HD현대중공업은
   * 조선이면서 기계, 포스코는 철강이면서 소재입니다.
   *
   * 구직자 쪽에서도 이 분야는 묶이는 편이 자연스럽습니다. 조선 설계와
   * 방산 기계 설계는 후보가 겹칩니다.
   */
  /*
   * 중공업·화학·소재 — 2026-10-01.
   *
   * 처음에는 '중공업·방산'(heavy-defense)으로 조선·방산·철강·항공만
   * 담았는데 72건에 그쳤습니다. 기계장비·소재·화학·물류 태그도 각각
   * 1~57건이라 페이지를 만들 수 없는 크기였습니다.
   *
   * 넷을 한 칸으로 합쳤습니다. 들어가는 회사가 실제로 겹칩니다.
   *   포스코    철강이면서 소재(퓨처엠)
   *   한화      방산이면서 화학(솔루션)
   *   OCI      화학이면서 반도체 소재
   *
   * 이름에 방산이 빠졌지만 한화에어로스페이스·LIG·빅텍은 기계·전기전자
   * 태그도 함께 갖고 있고, 검색으로도 걸립니다.
   */
  '중공업·화학·소재': 'heavy-chem',
};

// slug → 회사 산업 목록
const CO_INDUSTRY = Object.fromEntries(
  (registry.companies || []).map((c) => [c.slug, c.industry || []]));

/*
 * 그룹 어댑터는 항목 하나가 여러 계열사를 담습니다.
 * LG그룹 하나에 LG전자·LG이노텍·로보스타가 함께 들어옵니다.
 * 그런데 계열사마다 산업이 다릅니다. 로보스타는 로봇이지 자동차부품이
 * 아닌데, 항목 태그를 그대로 쓰면 자동차부품까지 붙습니다.
 *
 * 그래서 companies.json 의 affiliateIndustry 로 계열사별 산업을 둡니다.
 * 계열사명이 표에 없으면 항목의 기본 industry 를 씁니다.
 */
const CO_AFFILIATE = Object.fromEntries(
  (registry.companies || [])
    .filter((c) => c.affiliateIndustry)
    .map((c) => [c.slug, c.affiliateIndustry]));

const normCo = (v) => String(v || '').replace(/[\s\.,()㈜/]|주식회사/g, '').toLowerCase();

export const industriesOf = (job) => {
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

export const industrySlug = (name) =>
  INDUSTRY_SLUG[name] || name.toLowerCase().replace(/[^a-z0-9]+/g, '-');

/*
 * 페이지와 필터로 내보낼 산업.
 *
 * 원칙: 그 산업을 겨냥해 회사를 모았을 때만 페이지를 만듭니다.
 *
 *   자동차부품  KAICA 742개사를 훑어 40곳 등록      → 페이지 있음
 *   로봇       목록 30곳을 만들어 훑음             → 페이지 있음
 *   반도체     KSIA 218곳 목록을 만들어 훑음        → 페이지 있음
 *   전기전자   KRX 상장사 295곳을 훑음              → 페이지 있음
 *   IT        KRX 상장사 231곳을 훑음              → 페이지 있음
 *   제약바이오  시총 상위 제약·바이오·의료기기를 훑음   → 페이지 있음
 *
 * 소재·기계장비·물류·화학 태그도 붙어 있지만 페이지는 만들지
 * 않습니다. 그 산업을 겨냥해 회사를 모은 적이 없고, 그룹 계열사를
 * 분류하다 파생된 것이기 때문입니다. 물류 1건짜리 페이지를 만들면
 * "왜 이 회사만 있지" 싶은 화면이 됩니다.
 *
 * 태그는 그대로 둡니다. 회사 정보로서 의미가 있고, 나중에 그 산업을
 * 제대로 파고들어 회사를 모으면 아래 목록에 한 줄 추가하는 것으로
 * 페이지가 열립니다.
 */
/*
 * 중공업·화학·소재 — 2026-10-01 추가.
 *
 * 조선·방산·철강·항공을 겨냥해 회사를 모았습니다. 한화오션·현대로템·
 * 현대제철·한국항공우주·휴스틸·동국제강을 새로 등록하고, HD현대 조선
 * 계열 6곳과 한화 방산 계열, 삼성중공업을 이 분류로 묶었습니다.
 *
 * 네 분야를 따로 두지 않은 이유: 각각 열 곳 안팎이라 페이지가 빈약하고,
 * 회사도 서로 걸칩니다(한화에어로스페이스는 방산이면서 항공,
 * HD현대중공업은 조선이면서 기계).
 */
const PAGE_INDUSTRIES = ['자동차부품', '반도체', '로봇', '전기전자', 'IT', '제약바이오', '중공업·화학·소재'];

/** 페이지를 만들 산업만. 각 산업의 접수중 공고 수와 함께 돌려줍니다. */
export const industries = () => {
  const m = new Map();
  for (const j of openJobs()) {
    for (const name of industriesOf(j)) {
      if (!PAGE_INDUSTRIES.includes(name)) continue;
      if (!m.has(name)) m.set(name, { name, slug: industrySlug(name), jobs: [] });
      m.get(name).jobs.push(j);
    }
  }
  return [...m.values()].sort((a, b) => b.jobs.length - a.jobs.length);
};

export const byIndustry = (slug) => industries().find((i) => i.slug === slug);


/*
 * 직무 분류.
 *
 * 왜 필요한가
 *   지금까지는 회사별로만 볼 수 있었습니다. 그런데 구직자는 "삼성에 뭐 있나"
 *   보다 "회로설계 자리 있나" 로 찾습니다. 자기 직무로 걸러 보게 합니다.
 *
 * 어떻게 나누는가
 *   공고에 직무 필드가 따로 없습니다. 회사마다 제각각이라 있어도 못 씁니다.
 *   제목과 본문의 말을 보고 정합니다.
 *
 *   제목을 먼저 봅니다. 제목에 없을 때만 본문 앞 600자를 봅니다.
 *   본문 전체를 보면 스쳐 지나간 단어까지 잡혀 엉뚱하게 분류됩니다.
 *   실제로 본문 1200자를 봤더니 "AI" 가 592건으로 부풀었습니다.
 *
 *   한 공고에 최대 세 개까지만 답니다. 더 달면 무엇으로 찾아도 다 나와서
 *   거르는 의미가 없어집니다.
 *
 * 2026-09-12 기준 2,418건 중 68% 가 분류됩니다.
 * 남은 32% 는 장학생 선발·그룹 공채·인재풀·해외법인 관리자처럼 직무가
 * 정해지지 않은 공고입니다. 억지로 붙이지 않습니다.
 *
 * 규칙을 고칠 때
 *   한 직무의 건수가 갑자기 튀면 너무 넓게 잡은 것입니다. 전체의 15% 를
 *   넘는 직무가 생기면 규칙을 좁히세요.
 *
 * 2026-10-28 손질
 * --------------
 * 위의 15% 규칙을 AI·머신러닝이 이미 넘고 있었습니다. 860건(16.2%)이었고
 * 그중 529건이 본문에서 걸린 것이었습니다. 본문 앞 600자는 회사 소개문이라,
 * 스트라드비전·라이드플럭스처럼 모든 공고 앞에 "AI 기반 …" 을 붙이는 회사는
 * 공고가 통째로 AI 직무가 됐습니다. 사내 변리사 공고까지 AI 였습니다.
 *
 * 구간을 담당업무·자격요건으로 좁혀도 나아지지 않았습니다(860 → 874건).
 * 자격요건에 "자율주행·로보틱스 분야 특허 경험" 처럼 분야가 적혀 있어
 * 그것을 직무로 읽기 때문입니다.
 *
 * 원인은 \bAI\b 가 너무 넓은 것이었습니다. 뒤에 오는 말을 요구하도록
 * 바꿨습니다(AI 엔지니어·AI 모델·AI 플랫폼 …). 그냥 "AI" 한 단어로는
 * 걸리지 않습니다.
 *
 *   AI·머신러닝  860건(16.2%) → 356건(6.7%)
 *   15% 넘는 직무 없음
 *
 * 영문 제목도 함께 넣었습니다. 영문으로만 쓴 공고가 1,357건인데 그중
 * 457건이 분류되지 않고 있었습니다. Embedded·Developer·Product Manager·
 * Designer 처럼 실제 제목에서 뽑은 말만 넣었고, 추측으로 넣지 않았습니다.
 *
 *   직무가 붙는 공고  3,680건(69.3%) → 4,061건(76.5%)
 *
 * 그래도 직무가 없는 공고는 기술 태그의 상위 분류로 분야를 보여줍니다
 * (rolesOrFields 참고). 둘을 합치면 86.3% 입니다.
 */
const ROLE_RULES = [
  ['backend',   '백엔드',        /백엔드|back-?end|서버\s*개발|서버\s*엔지니어|Spring|Node\.?js/i],
  ['frontend',  '프론트엔드',     /프론트|front-?end|웹\s*개발|퍼블리셔|React\b|Vue\b/i],
  ['mobile',    '모바일',        /\bAndroid\b|\biOS\b|모바일\s*앱|앱\s*개발|Flutter/i],
  ['embedded',  '임베디드·펌웨어',  /임베디드|펌웨어|firmware|\bBSP\b|디바이스\s*드라이버|\bMCU\b|\bEmbedded\b/i],
  ['sw',        '소프트웨어개발',   /\bSW\s*(개발|엔지니어)|소프트웨어\s*(개발|엔지니어)|Software\s*(Engineer|Development)|개발자|\bDeveloper\b|Platform\s*Engineer|Systems?\s*Engineer|Application\s*Engineer/i],
  ['ai',        'AI·머신러닝',    /\bAI\s*(엔지니어|개발|모델|연구|플랫폼|서비스|알고리즘|기술|도입|전환|사업|에이전트|Engineer|Research|Platform|Scientist|Agent|Lab)|인공지능|머신러닝|딥러닝|\bML\s*(엔지니어|파이프라인|Ops)|\bLLM\b|Perception|비전\s*알고리즘|\bVSLAM\b|Deep\s*Learning|생성형\s*AI|\bAI\s*\/\s*ML\b/i],
  ['data',      '데이터',        /데이터\s*(분석|엔지니어|사이언|플랫폼)|빅데이터|\bDBA\b|Data\s*(Engineer|Scientist|Analyst|Platform)/i],
  ['devops',    '인프라·DevOps', /\bDevOps\b|인프라|클라우드|\bSRE\b|쿠버네티스|시스템\s*엔지니어|Infrastructure\s*Engineer/i],
  ['security',  '보안',          /보안|시큐리티|Security|취약점|모의해킹/i],
  ['gamedev',   '게임개발',       /게임\s*(개발|클라이언트|서버|기획)|클라이언트\s*개발|Unity|언리얼|\bRPG\b|Game\s*(Design|Client|Server)/i],
  ['circuit',   '회로·전장설계',   /회로\s*설계|아날로그\s*설계|전장\s*(설계|개발)|\bPCB\b|전력\s*변환|\bHW\s*개발|하드웨어\s*(설계|개발)/i],
  ['semi',      '반도체설계',      /반도체\s*설계|\bSoC\b|\bRTL\b|Verilog|물리\s*설계|\bDFT\b/i],
  ['process',   '반도체공정',      /반도체\s*공정|포토|식각|증착|\bCMP\b|수율|패키징|공정\s*(개발|기술)/i],
  ['mech',      '기구설계',       /기구\s*(설계|개발)|금형|구조\s*해석|\bCAE\b|선행\s*설계/i],
  ['control',   '제어·로보틱스',   /제어\s*(개발|알고리즘)|로봇\s*제어|모션\s*제어|\bSLAM\b|로보틱스|Control\s*Algorithm/i],
  ['chem',      '화학·소재',      /소재\s*(개발|연구)|화학\s*합성|고분자|촉매|전해질/i],
  ['bio',       '바이오·신약',     /신약|후보물질|비임상|전임상|세포\s*배양|항체|\bCMC\b|제형/i],
  ['clinical',  '임상·인허가',     /임상|\bCRA\b|인허가|허가\s*담당|\bMSL\b|약물감시/i],
  ['qa',        '품질·QA',       /\bQA\b|\bQC\b|품질\s*(관리|보증)|신뢰성|\bGMP\b|밸리데이션|Quality\s*(Assurance|Engineer)/i],
  ['prod',      '생산·제조',      /생산\s*(관리|기술|직)|제조\s*(기술|관리)|설비\s*(엔지니어|관리|보전)|오퍼레이터|현장직|기계\s*보전|Field\s*Service|\bTechnician\b/i],
  ['safety',    '안전·환경',      /안전\s*(관리|보건)|\bEHS\b|환경\s*안전|산업\s*안전/i],
  ['sales',     '영업',          /영업|세일즈|\bSales\b|사업\s*개발|Account\s*Manager|Business\s*Development/i],
  ['marketing', '마케팅',        /마케팅|브랜드\s*매니저|홍보|\bMarketing\b|Brand\s*Manager/i],
  ['pm',        '기획·PM',       /서비스\s*기획|프로덕트|\bPM\b|\bPO\b|사업\s*기획|전략\s*기획|Product\s*(Manager|Owner)|Program\s*Manager|Project\s*Manager/i],
  ['design',    '디자인',        /디자인|\bUX\b|그래픽|아트|일러스트|\bDesigner\b|\bArtist\b|\bVFX\b/i],
  ['hr',        '경영지원',       /인사|\bHR\b|재무|회계|총무|법무|\bIR\b|구매\s*담당|재경|감사|변리사|Procurement|Purchasing|\bSCM\b|Accounting/i],
  ['research',  '연구개발',       /연구원|연구소|\bR&D\b|연구\s*개발|선행\s*연구/i],
];

const ROLE_NAME = Object.fromEntries(ROLE_RULES.map(([k, label]) => [k, label]));

/** 공고 하나의 직무 코드들. 없으면 빈 배열입니다. */
/*
 * 본문에서 태그와 엔티티를 걷어내고 글자만 남깁니다.
 * 직무 분류가 본문 앞부분을 볼 때 씁니다.
 */
const stripTags = (s) =>
  String(s || '')
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;|&#160;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&[a-z]+;|&#\d+;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();

export const rolesOf = (job) => {
  const title = job.title || '';
  let got = ROLE_RULES.filter(([, , re]) => re.test(title)).map(([k]) => k);
  if (!got.length) {
    // 제목에 없을 때만 본문을 봅니다. 앞부분에 담당업무가 나옵니다.
    //
    // 태그를 먼저 벗깁니다 (2026-10-28).
    //   예전에는 받아온 HTML 을 그대로 600자 잘랐습니다. 그런데 그 600자의
    //   절반(평균 53.5%)이 <div style="..."> 같은 태그라, 실제로는 300자쯤만
    //   보고 있었습니다. 600자가 통째로 태그인 공고도 56건 있었습니다.
    //   벗기고 자르면 같은 600자로 두 배를 읽습니다.
    const body = stripTags(job.description).slice(0, 600);
    if (body) got = ROLE_RULES.filter(([, , re]) => re.test(body)).map(([k]) => k);
  }
  return got.slice(0, 3);
};

export const roleName = (code) => ROLE_NAME[code] || code;


/*
 * 기술·역량 태그 (2026-10-28)
 * ===========================
 * 사전은 tags.js 에 있습니다. 여기서는 공고 하나에 붙는 태그를 셉니다.
 *
 * 왜 본문 전체를 보는가
 *   직무는 제목을 먼저 보고 본문은 보조로 씁니다. 한 공고에 직무가 여럿이면
 *   거르는 의미가 없기 때문입니다. 태그는 반대입니다. 요구하는 기술이
 *   여럿이면 길도 여럿이어야 맞습니다. 그래서 본문 전체를 봅니다.
 *
 * 태그를 매번 세는 것이 느리지 않은가
 *   공고 5,311건 × 하위 252개 = 134만 번입니다. 빌드할 때 한 번이라
 *   괜찮습니다. 느려지면 수집 단계에서 미리 계산해 jobs.json 에
 *   담는 쪽으로 옮기세요.
 *
 * 나중에 요약이 생기면
 *   요약에서 뽑는 편이 정확합니다. 공고 20건으로 재보니 원문 기준 114개,
 *   요약 기준 95개였고 줄어든 19개는 전부 안내문에서 걸린 것이었습니다
 *   ("채용담당자 유선 문의", 복지의 "영어 Fluent"). 요약에는 그런 글이
 *   없어 저절로 걸러집니다. 요약이 쌓이면 여기를 요약 기준으로 바꾸세요.
 */
const tagText = (job) =>
  (job.title || '') + '\n' + stripTags(job.description);

/** 공고 하나에 붙는 기술 태그 이름들. 없으면 빈 배열입니다. */
export const tagsOf = (job) => {
  const text = tagText(job);
  const out = [];
  for (const [, subs] of TAGS) {
    for (const [name, re] of subs) {
      if (re.test(text)) out.push(name);
    }
  }
  return out;
};

/** 태그가 속한 상위 분류들. 중복은 없앱니다. */
export const tagTopsOf = (job) => [
  ...new Set(tagsOf(job).map((t) => TAG_TOP[t]).filter(Boolean)),
];

/** 태그별 접수중 건수. 태그 페이지를 만들 때 씁니다. */
export const tagCounts = () => {
  const n = {};
  for (const j of openJobs()) {
    for (const t of tagsOf(j)) n[t] = (n[t] || 0) + 1;
  }
  return n;
};


/*
 * 공고가 어느 길에 속하는지 (2026-10-28)
 * ======================================
 * 직무가 붙지 않는 공고가 1,250건(23.5%) 있습니다. 제목이 영문이거나
 * ("Senior Product Manager"), 제목이 너무 짧거나("R&D_TBR 타이어 설계"),
 * 그룹 공채처럼 직무가 정해지지 않은 공고입니다.
 *
 * 그런 공고도 기술 태그는 붙는 경우가 많습니다. 태그의 상위 분류를
 * 「분야」로 보여주면 길이 생깁니다. 사전을 두 번 쓰는 셈이라 새 규칙을
 * 따로 만들지 않아도 됩니다.
 *
 *   직무만          4,061건 (76.5%)
 *   + 분야로 보완    4,583건 (86.3%)
 *
 * 직무가 있으면 분야는 보여주지 않습니다. 둘 다 보여주면 같은 말이
 * 두 줄로 겹칩니다.
 */
export const fieldsOf = (job) =>
  rolesOf(job).length ? [] : tagTopsOf(job).slice(0, 3);

/** 직무 또는 분야. 화면에서 "이 공고가 속한 곳" 을 보여줄 때 씁니다. */
export const pathsOf = (job) => {
  const roles = rolesOf(job);
  if (roles.length) return roles.map((r) => ({ kind: 'role', code: r, name: roleName(r) }));
  return fieldsOf(job).map((f) => ({ kind: 'field', code: f, name: f }));
};

/** 공고가 있는 직무만. 건수와 함께 많은 순으로 돌려줍니다. */
export const roles = () => {
  const m = new Map();
  for (const j of openJobs()) {
    for (const code of rolesOf(j)) {
      if (!m.has(code)) m.set(code, { code, name: roleName(code), jobs: [] });
      m.get(code).jobs.push(j);
    }
  }
  return [...m.values()].sort((a, b) => b.jobs.length - a.jobs.length);
};

export const byRole = (code) => roles().find((r) => r.code === code);

/*
 * 회사 목록.
 *
 * 대표 이름은 companies.json 의 name 을 씁니다.
 *
 * 예전에는 첫 공고의 company 값을 썼는데, 그룹 어댑터는 계열사가 한
 * 항목에 섞여 있어 데이터 순서에 따라 이름이 바뀌었습니다. LG그룹
 * 페이지 제목이 어느 날은 "LG전자", 어느 날은 "LG Magna" 가 됐습니다.
 * 실제로 마감 공고 화면에서 제목은 LG전자인데 아래 목록은
 * "LG Magna 진행중 공고" 로 나와 어긋났습니다.
 */
const REG_NAME = Object.fromEntries(
  (registry.companies || []).map((c) => [c.slug, c.name]));

export const companies = () => {
  const m = new Map();
  for (const j of JOBS) {
    if (!m.has(j.companySlug))
      m.set(j.companySlug, {
        slug: j.companySlug,
        name: REG_NAME[j.companySlug] || j.company,
        jobs: [],
      });
    m.get(j.companySlug).jobs.push(j);
  }
  return [...m.values()].sort((a, b) => a.name.localeCompare(b.name, 'ko'));
};

/*
 * 페이지를 만들어 둘 회사 목록. (2026-10-21)
 *
 * 왜 companies() 와 따로 두는가
 * -----------------------------
 * companies() 는 "공고가 있는 회사" 입니다. 그래서 그 회사의 공고가
 * 하나도 없는 날에는 목록에서 빠지고, /company/그회사/ 페이지도 같이
 * 사라집니다. 다음 날 공고가 올라오면 페이지도 돌아옵니다.
 *
 * 문제는 그 사이입니다. 구글은 전에 수집해 둔 주소로 다시 오는데,
 * 페이지가 없으니 404 를 받습니다. 2026-10-20 하루 치 기록에서
 * 실제로 이런 404 가 잡혔습니다.
 *
 *   /company/daou-tech/   /company/ckd/   /company/apsystems/
 *
 * 그날 기준 등록된 425곳 중 48곳이 공고 0건이었습니다. 회사는 멀쩡히
 * 살아 있고 지금 뽑는 자리가 없을 뿐인데, 검색엔진에는 "없는 주소" 로
 * 보입니다. 한 번 그렇게 찍히면 다시 수집하러 오는 간격이 길어집니다.
 *
 * 그래서 등록돼 있고 끄지 않은 회사는 공고가 0건이어도 페이지를
 * 남깁니다. 화면에는 "지금은 진행중인 공고가 없습니다" 가 나옵니다.
 * 공고가 올라오면 그 자리가 저절로 채워집니다.
 *
 * companies() 는 왜 안 고쳤는가
 * ------------------------------
 * 홈의 "기업별로 보기" 목록과 소개 페이지의 기업 수가 그걸 씁니다.
 * 거기까지 늘리면 방문자에게 빈 페이지로 가는 링크를 48개 보여주고,
 * 기업 수도 실제 공고가 있는 곳보다 부풀려집니다. 사람이 보는 목록과
 * 검색엔진에 열어두는 주소는 달라도 됩니다.
 *
 * enabled:false 는 넣지 않습니다
 * -------------------------------
 * 수집을 일부러 끈 회사입니다. 다시 켤 생각이 없는 곳까지 페이지를
 * 남길 이유는 없습니다. 끈 회사의 주소가 검색엔진에 남아 있다면 그건
 * 404 가 맞습니다.
 */
const REG_ENABLED = (registry.companies || [])
  .filter((c) => c && c.slug && c.enabled !== false);

export const companyPages = () => {
  const list = companies();
  const have = new Set(list.map((c) => c.slug));
  const extra = REG_ENABLED
    .filter((c) => !have.has(c.slug))
    .map((c) => ({ slug: c.slug, name: c.name, jobs: [] }));
  return [...list, ...extra].sort((a, b) => a.name.localeCompare(b.name, 'ko'));
};

/*
 * 공고가 없는 회사도 이름을 찾을 수 있어야 합니다. 못 찾으면 기업
 * 페이지가 제목을 만들다가 빌드가 멈춥니다.
 */
export const byCompany = (slug) =>
  companyPages().find((c) => c.slug === slug);

/*
 * 회사명 검색 별칭.
 *
 * 회사명이 영문이면 한글로 검색해도 안 나옵니다. "네이버" 로 찾으면
 * NAVER WEBTOON 만 걸렸는데, 그건 공고 제목에 "[네이버웹툰]" 이 한글로
 * 들어 있었기 때문입니다. NAVER·NAVER Cloud 는 제목까지 영문이라
 * 아무리 쳐도 안 나왔습니다.
 *
 * 반대도 마찬가지입니다. 한글 회사명을 영문으로 검색하는 사람도 있습니다.
 *
 * 그래서 검색용 텍스트에 다른 표기를 함께 넣습니다. 화면에는 보이지
 * 않고 검색에만 쓰입니다.
 */
const NAME_ALIAS = {
  'NAVER': '네이버',
  'NAVER Cloud': '네이버 네이버클라우드 클라우드',
  'NAVER LABS': '네이버 네이버랩스 랩스',
  'NAVER WEBTOON': '네이버 네이버웹툰 웹툰',
  'SNOW': '스노우 네이버',
  'SK on': '에스케이온 SK온',
  'SK ons': '에스케이온 SK온',
  'SK siltron': '에스케이실트론 SK실트론',
  'LG Magna': '엘지마그나 LG마그나',
  'HL Klemove': '에이치엘클레무브 HL클레무브 만도',
  '42dot': '포티투닷',
  'OCI': '오씨아이',
};

/** 검색용 별칭. 없으면 빈 문자열입니다. */
export const searchAlias = (name) => NAME_ALIAS[name] || '';

/**
 * JobPosting 구조화 데이터.
 * 구글은 페이지에 직무 설명 본문이 있을 것을 요구합니다.
 * 본문이 없는 공고(이미지 게시)에는 스키마를 넣지 않습니다. null 을 반환합니다.
 *
 * validThrough 는 마감일이 있을 때만 넣습니다. 빈 값으로 넣으면
 * "T23:59:59+09:00" 같은 깨진 날짜가 나가 구조화 데이터 오류가 됩니다.
 *
 * datePosted 는 필수입니다 (2026-10-06)
 * -------------------------------------
 * 구글 Search Console 이 "'datePosted' 입력란이 누락되었습니다" 를 심각한
 * 문제로 보고했습니다. 당시 351건이 postedAt 이 비어 있었습니다. 게시일을
 * 아예 주지 않는 채용 시스템이 있기 때문입니다(시프트업·SOOP·네오위즈,
 * 그리팅 일부, LS전선).
 *
 * 그래서 순서를 둡니다.
 *   1. postedAt     소스가 준 실제 게시일
 *   2. firstSeenAt  우리 데이터에 처음 나타난 날 (fetch_jobs.py 가 붙입니다.
 *                   한 번 정하면 바뀌지 않습니다)
 *   3. 둘 다 없으면 스키마를 넣지 않습니다. 빈 값으로 보내면 오류가 되고,
 *      안 보내면 그냥 카드 대상이 아닌 것이 됩니다. 빈 값보다 낫습니다.
 */

/*
 * 구글에 보낼 게시일을 고릅니다.
 *
 * 미래 날짜를 걸러내는 이유 (2026-10-07)
 * --------------------------------------
 * LG 는 게시일로 쓸 값이 접수 시작일(recStartDate)뿐인데, 접수가 아직
 * 시작되지 않은 공고를 미리 올려둡니다. 실제로 수집일이 10-07 인데
 * "[LG전자] R&D 석/박사 해외 유학생 채용" 의 게시일이 10-09 로
 * 들어왔습니다.
 *
 * 공고가 지금 화면에 보이고 있다면 게시는 이미 된 것입니다. 그런데
 * datePosted 를 모레로 적으면 "아직 게시되지 않은 공고" 라는 뜻이 되어
 * 구조화 데이터가 사실과 달라집니다. 그런 경우에는 우리가 처음 본 날로
 * 되돌립니다. 그게 확인된 사실입니다.
 *
 * 마감일(validThrough)은 미래여야 정상이므로 손대지 않습니다.
 *
 * 비교 기준은 TODAY 가 아니라 COLLECTED_AT 입니다. TODAY 는 검증용으로
 * 바꿀 수 있는 값이고, 여기서 묻는 것은 "수집한 날 기준으로 이미 게시된
 * 공고인가" 입니다.
 */
const pickDatePosted = (j) => {
  const posted = (j.postedAt || '').trim();
  if (posted && posted <= COLLECTED_AT) return posted;
  return (j.firstSeenAt || '').trim();
};

/*
 * 이 공고가 자체 상세 페이지를 가지는가.
 *
 * 왜 함수로 빼는가 (2026-10-10)
 * -----------------------------
 * 같은 규칙이 네 군데에 흩어져 있었고 그중 셋이 서로 달랐습니다.
 *
 *   JobCard.astro      본문이 "빈 값만 아니면" 내부 링크
 *   job/[id].astro     본문이 "50자 이상" 일 때만 페이지 생성
 *   job/[id].astro     관련 공고 링크도 "빈 값만 아니면" 내부 링크
 *   lib.js 스키마       "50자 미만이면" 스키마 없음
 *
 * 그래서 본문이 1~49자인 공고는 링크는 걸리는데 페이지가 없어 404 가
 * 납니다. 2026-10-10 기준 컴투스 공고 1건이 실제로 그랬습니다
 * (본문이 '<p><br></p>' 11자).
 *
 * 숫자를 고칠 일이 생겨도 이제 이 한 줄만 고치면 네 곳이 같이 바뀝니다.
 */
export const DETAIL_MIN = 50;
/*
 * 판정은 "다 치운 뒤에 남는 내용" 으로 합니다 (2026-10-20).
 *
 * 원래는 받아온 본문 길이를 그대로 재고 있었습니다. 그런데 본문에
 * 그림이 통째로 박혀 있는 공고가 있어서(cleanBody 주석 참고), 읽을
 * 글은 한 줄도 없는데 길이가 50만 자로 잡히는 일이 생깁니다. 그러면
 * 상세 페이지를 만들어 놓고 빈 화면을 보여 주게 됩니다.
 *
 * 그래서 화면에 실제로 그릴 내용으로 잽니다. 2026-10-20 기준 이 변경으로
 * 상세 페이지 유무가 바뀌는 공고는 0건입니다(전수 6,670건 확인). 앞으로
 * 그림만 들어온 공고가 생기면 그때는 페이지를 만들지 않고 원문으로
 * 보냅니다 — 빈 페이지보다 그게 맞습니다.
 *
 * cleanBody 는 이 줄보다 아래에 적혀 있습니다. 함수 몸통은 부를 때
 * 실행되므로 순서는 문제되지 않습니다.
 */
export const hasDetail = (j) => {
  const body = cleanBody(j.description);
  return !!body && body.trim().length >= DETAIL_MIN;
};

/*
 * 공고 본문의 이미지를 "보일 때 불러오기" 로 바꿉니다 (2026-10-12)
 * ------------------------------------------------------------------
 * 느린 쪽 100명 중 1명이 첫 화면을 보는 데 8.1초를 기다리고 있었습니다.
 * 모바일에서 이 정도면 대부분 떠납니다.
 *
 * 원인은 공고 본문에 박혀 있는 이미지입니다. 본문은 회사 채용 시스템에서
 * 받아온 HTML 을 그대로 그리는데, 그 안에 첨부 이미지가 들어 있습니다.
 *
 *   본문에 이미지가 든 공고   1,681건 / 전체 6,244건
 *   이미지 총 개수            3,191개 (한 공고에 최대 22개)
 *   가장 많은 곳              opening-attachments.greetinghr.com  1,683개
 *
 * 이 이미지들은 대부분 화면 아래쪽에 있어 처음에는 보이지도 않는데,
 * 브라우저는 기본적으로 전부 내려받고 나서야 페이지를 다 그렸다고
 * 판단합니다. 그래서 첫 화면이 늦어집니다.
 *
 * loading="lazy" 를 붙이면 화면에 들어올 때까지 미룹니다. 요즘 브라우저는
 * 화면에 가까운 이미지는 알아서 미리 받으므로, 위쪽 이미지가 늦게 뜨는
 * 일은 없습니다.
 *
 * decoding="async" 는 그림을 푸는 작업이 화면 그리기를 막지 않게 합니다.
 *
 * 왜 수집할 때가 아니라 그릴 때 손대는가
 * ---------------------------------------
 * 수집기(fetch_jobs.py)에서 바꾸면 공고갱신을 한 번 돌려야 반영됩니다.
 * 한 시간 반이 걸립니다. 여기서 바꾸면 이미 모아둔 6,244건에 바로
 * 적용되고, 고칠 곳도 한 군데입니다.
 *
 * 이미 loading 이 붙어 있는 것은 건드리지 않습니다. 회사가 일부러
 * 적어 뒀을 수 있어 우리가 뒤집지 않습니다.
 *
 * 첫 번째 이미지는 미루면 안 됩니다
 * ----------------------------------
 * 처음에 전부 미뤘더니 오히려 느려졌습니다. 재 보고 알았습니다.
 *
 *            첫 화면 뜨는 시점(LCP)    load 완료
 *   개선 전          560ms              645ms
 *   전부 미룸      1,000ms  ← 나빠짐     562ms
 *   첫 장만 남김     아래 측정값 참고
 *
 * 본문 맨 위 이미지는 대개 화면 안에 들어와 있고, 바로 그것이 "첫
 * 화면이 떴다" 를 판정하는 기준이 됩니다. 그걸 미루면 판정도 같이
 * 늦어집니다. 그래서 첫 장은 그대로 두고 둘째부터 미룹니다.
 *
 * 공고당 이미지가 1개인 것이 1,031건으로 가장 많은데, 그런 공고는
 * 아무것도 바뀌지 않습니다. 이미지가 여러 개인 650여 건에서 효과가
 * 납니다. 한 공고에 22개까지 있습니다.
 */
/*
 * 공고 본문에서 남의 <script> 를 걷어냅니다. (2026-10-16)
 *
 * 왜 필요한가
 * -----------
 * 본문은 회사가 쓴 HTML 을 그대로 보여줍니다(job/[id].astro 의 set:html).
 * 그래서 회사 페이지에 있던 <script> 태그까지 같이 들어옵니다.
 * 2026-10-16 기준 상세페이지가 있는 5,137건 중 21건이 그랬고, 전부
 * 네오위즈였습니다. 들어 있던 것은 이렇습니다.
 *
 *   <script src="/js/share-buttons.js"></script>
 *
 * 주소가 "/" 로 시작하는 상대 주소라, 우리 페이지에서는 네오위즈가 아니라
 * searchjob.co.kr/js/share-buttons.js 를 찾습니다. 그런 파일은 없으니
 * 404 가 납니다. 구글 서치콘솔에서 쫓던 404 중 일부가 이것이었습니다.
 *
 * 더 큰 문제는 구조화 데이터였습니다
 * -----------------------------------
 * 구조화 데이터는 <script type="application/ld+json"> 안에 JSON 으로
 * 넣습니다. 그 JSON 안에 본문이 들어가는데, 본문에 </script> 가 있으면
 * 브라우저가 거기서 블록이 끝난 줄 알고 JSON 을 잘라 버립니다.
 *
 *   PARSE FAIL: Unterminated string in JSON at position 2455
 *
 * 그래서 그 21건은 구글 채용정보에 노출되지 않았습니다. 서치콘솔이
 * "파싱할 수 없는 구조화된 데이터 · 잘못된 값 유형" 으로 알려준 것이
 * 이것입니다.
 *
 * 잘리는 문제 자체는 ldJson() 의 escape 로 막았습니다. 여기서 또 한 번
 * 지우는 이유는 다릅니다. 남이 쓴 자바스크립트를 우리 페이지에서 실행할
 * 이유가 없습니다.
 *
 * <style> <link> <iframe> 는 두는 이유
 * ------------------------------------
 * 같이 확인했더니 <link> 65건, <style> 19건, <iframe> 106건이 있었습니다.
 * iframe 은 대부분 유튜브 회사 소개 영상이어서 지우면 내용이 사라집니다.
 * style 19건은 전부 body·a·p 같은 공통 요소를 건드려서 위험하긴 한데,
 * 지우면 회사가 꾸민 글꼴과 색이 함께 사라집니다. 2026-10-16 에
 * script 만 지우기로 정했습니다. 문제가 생기면 그때 다시 봅니다.
 *
 * 닫는 태그가 없는 경우도 지웁니다
 * ---------------------------------
 * <script ...> 만 있고 </script> 가 없으면 브라우저는 그 뒤 본문 전체를
 * 코드로 읽습니다. 쌍을 먼저 지우고, 남은 한쪽도 지웁니다.
 */
export const stripScripts = (htmlText) => {
  if (!htmlText) return htmlText;
  return htmlText
    .replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi, '')
    .replace(/<script\b[^>]*>/gi, '')
    .replace(/<\/script\s*>/gi, '');
};

/*
 * 본문에 통째로 박힌 그림을 걷어냅니다. (2026-10-20)
 *
 * 무슨 일이 있었나
 * ----------------
 * 2026-10-19 15:00 공고갱신부터 배포가 멈췄습니다. 빌드가 이렇게
 * 끝났습니다.
 *
 *   [page-size-guard] 가장 큰 페이지
 *     1.  6,337KB  /job/slworld-130983/      ← 한도 3,994KB
 *   → 가장 큰 페이지에 남은 여유 -2,241KB
 *
 * 에스엘 공고 하나 때문입니다. 본문이 3,073KB 인데 그중 2,652KB 가
 * 그림 두 장이었습니다.
 *
 * 보통 그림은 주소만 들어옵니다(<img src="https://...">). 그러면 본문에
 * 들어가는 건 주소 한 줄입니다. 그런데 어떤 채용 시스템은 그림 파일
 * 자체를 글자로 바꿔서 본문 안에 적어 넣습니다.
 *
 *   <img src="data:image/png;base64,iVBORw0KGgoAAAANSUh...">
 *                                   └─ 이게 190만 자까지 이어집니다
 *
 * 그림 1장이 본문 190만 자가 됩니다. 게다가 페이지에는 본문이 두 번
 * 들어갑니다 — 사람이 읽는 쪽과 구글에 보내는 구조화 데이터 쪽.
 * 그래서 3MB 공고가 6.3MB 페이지가 됩니다.
 *
 * 얼마나 있나 (2026-10-20 전수 조사)
 * -----------------------------------
 *   박혀 있는 공고        41건 / 6,670건
 *   박힌 그림 합계         6.27MB
 *   가장 큰 것            에스엘 slworld-130983 (190만 자 1장)
 *   회사                  에스엘·케이씨텍·세방전지·동아쏘시오·GC계열 등
 *
 * 걷어내면
 * --------
 *   에스엘      3,073KB → 421KB   (읽을 글자 48,699자 그대로 남음)
 *   케이씨텍      313KB →  73KB
 *   클래시스      549KB →   1KB   (읽을 글자 931자)
 *   GC계열 20건    40KB →  0.3KB  (회사 로고였습니다)
 *
 * 상세 페이지가 없어지는 공고는 0건입니다. 41건 모두 그림을 빼도 읽을
 * 내용이 남습니다. GC계열은 박힌 것이 로고라 빼는 쪽이 오히려 낫습니다.
 *
 * <img> 는 태그를 통째로 지웁니다
 * -------------------------------
 * 안쪽 글자만 비워 <img src=""> 로 남기면 브라우저가 지금 보고 있는
 * 페이지 주소를 그림으로 또 받아 갑니다. 처음 만들 때 실제로 23건이
 * 그렇게 남는 것을 확인하고 고쳤습니다.
 *
 * ";base64," 를 반드시 같이 봅니다
 * --------------------------------
 * 그냥 "data:" 로 찾으면 안 됩니다. 기술스택을 적은 공고 5건에
 * "Data: PostgreSQL, MySQL..." 같은 영어 문장이 있습니다. 그것까지
 * 지워 버립니다. 조사해 보고 알았습니다.
 *
 * 왜 수집할 때가 아니라 그릴 때 하는가
 * -------------------------------------
 * lazyImages 와 같은 이유입니다. 수집기를 고치면 공고갱신을 한 번
 * 돌려야 반영되고 한 시간 반이 걸립니다. 여기서 고치면 이미 모아둔
 * 것에 바로 적용됩니다.
 *
 * 그림이 안 보이게 됩니다
 * -----------------------
 * 에스엘 공고의 모집 포스터는 화면에서 사라집니다. 대신 글로 적힌
 * 48,699자가 남고, 포스터는 "원문 사이트" 를 눌러 보면 됩니다.
 * 6MB 를 받다가 멈추는 것보다 낫다고 보고 이렇게 정했습니다.
 */
const BASE64_DATA = /data:[a-z0-9.+-]*\/?[a-z0-9.+-]*;base64,/i;
export const stripDataImages = (htmlText) => {
  if (!htmlText) return htmlText;
  return htmlText
    // 그림 태그는 통째로.
    .replace(/<img\b[^>]*>/gi, (tag) => (BASE64_DATA.test(tag) ? '' : tag))
    .replace(/<source\b[^>]*>/gi, (tag) => (BASE64_DATA.test(tag) ? '' : tag))
    // 그 밖의 자리(style 의 background-image 등)는 내용물만 비웁니다.
    .replace(/data:[a-z0-9.+-]*\/?[a-z0-9.+-]*;base64,[A-Za-z0-9+/=\s]*/gi, '');
};

/*
 * 본문을 손보는 순서를 한 군데로 모았습니다. (2026-10-20)
 *
 * 화면에 그리는 쪽과 구글에 보내는 쪽이 같은 내용이어야 합니다. 전에
 * 같은 규칙이 네 군데에 흩어져 셋이 서로 달라서 404 가 났습니다
 * (hasDetail 주석 참고). 또 그러지 않게 여기 하나만 둡니다.
 *
 * 순서가 중요합니다. <script> 를 먼저 지웁니다. 지울 태그 안에 들어
 * 있는 <img> 를 따로 건드리지 않게 하기 위해서입니다.
 */
export const cleanBody = (htmlText) => stripDataImages(stripScripts(htmlText));

export const lazyImages = (htmlText) => {
  if (!htmlText) return htmlText;
  let n = 0;
  return htmlText.replace(/<img\b[^>]*>/gi, (tag) => {
    n += 1;
    // 첫 장은 화면 안에 있을 가능성이 높아 그대로 둡니다.
    if (n === 1) return tag;
    if (/\bloading\s*=/i.test(tag)) return tag;
    const extra = /\bdecoding\s*=/i.test(tag)
      ? ' loading="lazy"'
      : ' loading="lazy" decoding="async"';
    // 홑따옴표로 닫히는 경우(/>)를 살려 둡니다.
    return tag.replace(/\s*\/?>$/, (end) => extra + end);
  });
};

/*
 * 구조화 데이터를 <script> 안에 안전하게 넣습니다. (2026-10-16)
 *
 * 무슨 일이 있었나
 * ----------------
 * 그냥 JSON.stringify 한 값을 넣고 있었습니다. 그런데 JSON 은 "<" 를
 * 특별하게 다루지 않습니다. 본문 안에 </script> 가 있으면 그 글자가
 * 그대로 나가고, 브라우저는 거기서 <script> 블록이 끝났다고 봅니다.
 * JSON 은 문장 중간에서 잘려 버립니다.
 *
 *   PARSE FAIL: Unterminated string in JSON at position 2455
 *
 * 구글은 이것을 "파싱할 수 없는 구조화된 데이터" 로 보고하고, 그 페이지는
 * 채용정보 검색 결과에서 빠집니다. 2026-10-16 메일로 알려 왔습니다.
 *
 * 어떻게 막나
 * -----------
 * "<" ">" "&" 를 JSON 의 유니코드 표기로 바꿉니다. < 는 JSON 규격
 * 그대로이고, 읽는 쪽에서 되돌리면 글자가 완전히 같습니다. 즉 구글이
 * 받는 내용은 하나도 달라지지 않고, 블록이 끊기는 일만 없어집니다.
 *
 * U+2028 · U+2029 도 같이 바꿉니다. JSON 은 허용하지만 자바스크립트
 * 문자열에서는 줄바꿈으로 취급되어, 엄격한 파서에서 사고가 납니다.
 * s2w 공고 14건에 실제로 들어 있었습니다.
 *
 * 왜 Base.astro 가 아니라 여기 두는가
 * ------------------------------------
 * 구조화 데이터를 내는 페이지가 홈·산업·직무·기업·공고 다섯 종류입니다.
 * 넣는 곳은 Base.astro 한 군데지만, 규칙은 데이터 쪽 규칙이라 다른
 * 스키마 함수들과 함께 둡니다. 새 페이지를 만들어도 Base 를 쓰면
 * 자동으로 적용됩니다.
 */
export const ldJson = (obj) =>
  JSON.stringify(obj)
    .replace(/</g, '\\u003C')
    .replace(/>/g, '\\u003E')
    .replace(/&/g, '\\u0026')
    // U+2028 · U+2029 는 소스에 그대로 적으면 자바스크립트가 줄바꿈으로
    // 읽어 파일 자체가 깨집니다. 그래서 문자 코드로 만들어 씁니다.
    .replace(new RegExp(String.fromCharCode(0x2028), 'g'), '\\u2028')
    .replace(new RegExp(String.fromCharCode(0x2029), 'g'), '\\u2029');

export const jobPostingSchema = (j, pageUrl) => {
  if (!hasDetail(j)) return null;
  const datePosted = pickDatePosted(j);
  if (!datePosted) return null;
  const employmentType =
    j.career === '신입' ? 'FULL_TIME' : j.career === '무관' ? 'OTHER' : 'FULL_TIME';
  return {
    '@context': 'https://schema.org',
    '@type': 'JobPosting',
    title: j.title,
    // 화면에 그리는 쪽(job/[id].astro)과 반드시 같은 내용이어야 합니다.
    // 둘 다 cleanBody 하나를 씁니다.
    description: cleanBody(j.description),
    identifier: { '@type': 'PropertyValue', name: j.company, value: j.id },
    datePosted,
    ...(j.closesAt ? { validThrough: j.closesAt + 'T23:59:59+09:00' } : {}),
    employmentType,
    hiringOrganization: {
      '@type': 'Organization',
      name: j.company,
    },
    jobLocation: {
      '@type': 'Place',
      address: {
        '@type': 'PostalAddress',
        addressLocality: j.location || undefined,
        // 알아낼 수 있을 때만 넣습니다. 원본에 없는 주소를 지어내지 않습니다.
        addressRegion: addressRegion(j.location),
        addressCountry: 'KR',
      },
    },
    url: pageUrl,
    directApply: false,
  };
};
