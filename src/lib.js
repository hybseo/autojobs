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
const PAGE_INDUSTRIES = ['자동차부품', '반도체', '로봇', '전기전자', 'IT'];

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

export const companies = () => {
  const m = new Map();
  for (const j of JOBS) {
    if (!m.has(j.companySlug))
      m.set(j.companySlug, { slug: j.companySlug, name: j.company, jobs: [] });
    m.get(j.companySlug).jobs.push(j);
  }
  return [...m.values()].sort((a, b) => a.name.localeCompare(b.name, 'ko'));
};

export const byCompany = (slug) => companies().find((c) => c.slug === slug);

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
