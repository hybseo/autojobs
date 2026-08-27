import raw from './data/jobs.json';

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
        addressCountry: 'KR',
      },
    },
    url: pageUrl,
    directApply: false,
  };
};
