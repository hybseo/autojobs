import raw from './data/jobs.json';
import registry from './data/companies.json';

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

/** 아직 지원할 수 있는 공고. 상시채용은 마감이 없으므로 항상 포함됩니다. */
export const openJobs = () =>
  JOBS.filter((j) => !j.closesAt || parseDate(j.closesAt) >= TODAY);

/** 마감된 공고. 기업 페이지 아카이브에 씁니다. 상시채용은 마감되지 않습니다. */
export const closedJobs = () =>
  JOBS.filter((j) => j.closesAt && parseDate(j.closesAt) < TODAY);

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
const PAGE_INDUSTRIES = ['자동차부품', '반도체', '로봇', '전기전자', 'IT', '제약바이오'];

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
 */
const ROLE_RULES = [
  ['backend',   '백엔드',        /백엔드|back-?end|서버\s*개발|서버\s*엔지니어|Spring|Node\.?js/i],
  ['frontend',  '프론트엔드',     /프론트|front-?end|웹\s*개발|퍼블리셔|React\b|Vue\b/i],
  ['mobile',    '모바일',        /\bAndroid\b|\biOS\b|모바일\s*앱|앱\s*개발|Flutter/i],
  ['embedded',  '임베디드·펌웨어',  /임베디드|펌웨어|firmware|\bBSP\b|디바이스\s*드라이버|\bMCU\b/i],
  ['sw',        '소프트웨어개발',   /\bSW\s*(개발|엔지니어)|소프트웨어\s*(개발|엔지니어)|Software\s*Engineer|개발자/i],
  ['ai',        'AI·머신러닝',    /\bAI\b|인공지능|머신러닝|딥러닝|\bML\b|\bLLM\b|Perception|비전\s*알고리즘/i],
  ['data',      '데이터',        /데이터\s*(분석|엔지니어|사이언|플랫폼)|빅데이터|\bDBA\b|Data\s*(Engineer|Scientist|Analyst)/i],
  ['devops',    '인프라·DevOps', /\bDevOps\b|인프라|클라우드|\bSRE\b|쿠버네티스|시스템\s*엔지니어/i],
  ['security',  '보안',          /보안|시큐리티|Security|취약점|모의해킹/i],
  ['gamedev',   '게임개발',       /게임\s*(개발|클라이언트|서버|기획)|클라이언트\s*개발|Unity|언리얼/i],
  ['circuit',   '회로·전장설계',   /회로\s*설계|아날로그\s*설계|전장\s*(설계|개발)|\bPCB\b|전력\s*변환|\bHW\s*개발|하드웨어\s*(설계|개발)/i],
  ['semi',      '반도체설계',      /반도체\s*설계|\bSoC\b|\bRTL\b|Verilog|물리\s*설계|\bDFT\b/i],
  ['process',   '반도체공정',      /반도체\s*공정|포토|식각|증착|\bCMP\b|수율|패키징|공정\s*(개발|기술)/i],
  ['mech',      '기구설계',       /기구\s*(설계|개발)|금형|구조\s*해석|\bCAE\b|선행\s*설계/i],
  ['control',   '제어·로보틱스',   /제어\s*(개발|알고리즘)|로봇\s*제어|모션\s*제어|\bSLAM\b|로보틱스/i],
  ['chem',      '화학·소재',      /소재\s*(개발|연구)|화학\s*합성|고분자|촉매|전해질/i],
  ['bio',       '바이오·신약',     /신약|후보물질|비임상|전임상|세포\s*배양|항체|\bCMC\b|제형/i],
  ['clinical',  '임상·인허가',     /임상|\bCRA\b|인허가|허가\s*담당|\bMSL\b|약물감시/i],
  ['qa',        '품질·QA',       /\bQA\b|\bQC\b|품질\s*(관리|보증)|신뢰성|\bGMP\b|밸리데이션/i],
  ['prod',      '생산·제조',      /생산\s*(관리|기술|직)|제조\s*(기술|관리)|설비\s*(엔지니어|관리|보전)|오퍼레이터|현장직|기계\s*보전/i],
  ['safety',    '안전·환경',      /안전\s*(관리|보건)|\bEHS\b|환경\s*안전|산업\s*안전/i],
  ['sales',     '영업',          /영업|세일즈|\bSales\b|사업\s*개발/i],
  ['marketing', '마케팅',        /마케팅|브랜드\s*매니저|홍보/i],
  ['pm',        '기획·PM',       /서비스\s*기획|프로덕트|\bPM\b|\bPO\b|사업\s*기획|전략\s*기획/i],
  ['design',    '디자인',        /디자인|\bUX\b|그래픽|아트|일러스트/i],
  ['hr',        '경영지원',       /인사|\bHR\b|재무|회계|총무|법무|\bIR\b|구매\s*담당|재경|감사/i],
  ['research',  '연구개발',       /연구원|연구소|\bR&D\b|연구\s*개발|선행\s*연구/i],
];

const ROLE_NAME = Object.fromEntries(ROLE_RULES.map(([k, label]) => [k, label]));

/** 공고 하나의 직무 코드들. 없으면 빈 배열입니다. */
export const rolesOf = (job) => {
  const title = job.title || '';
  let got = ROLE_RULES.filter(([, , re]) => re.test(title)).map(([k]) => k);
  if (!got.length) {
    // 제목에 없을 때만 본문을 봅니다. 앞부분에 담당업무가 나옵니다.
    const body = (job.description || '').slice(0, 600);
    if (body) got = ROLE_RULES.filter(([, , re]) => re.test(body)).map(([k]) => k);
  }
  return got.slice(0, 3);
};

export const roleName = (code) => ROLE_NAME[code] || code;

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

export const byCompany = (slug) => companies().find((c) => c.slug === slug);

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
 */
export const jobPostingSchema = (j, pageUrl) => {
  if (!j.description || j.description.trim().length < 50) return null;
  const employmentType =
    j.career === '신입' ? 'FULL_TIME' : j.career === '무관' ? 'OTHER' : 'FULL_TIME';
  return {
    '@context': 'https://schema.org',
    '@type': 'JobPosting',
    title: j.title,
    description: j.description,
    identifier: { '@type': 'PropertyValue', name: j.company, value: j.id },
    datePosted: j.postedAt,
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
