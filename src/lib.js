import raw from './data/jobs.json';

export const COLLECTED_AT = raw.collectedAt;
export const JOBS = raw.jobs;

/** 오늘 기준. 빌드 시점 날짜를 쓰되, 샘플 데이터 검증용으로 고정값을 허용합니다. */
export const TODAY = new Date(process.env.TODAY ?? COLLECTED_AT);

const day = 86400000;
export const parseDate = (s) => new Date(s + 'T00:00:00+09:00');

/** 마감일이 지나지 않은 공고 */
export const openJobs = () =>
  JOBS.filter((j) => parseDate(j.closesAt) >= TODAY);

/** 마감된 공고. 기업 페이지 아카이브에 씁니다. */
export const closedJobs = () =>
  JOBS.filter((j) => parseDate(j.closesAt) < TODAY);

export const daysLeft = (j) =>
  Math.ceil((parseDate(j.closesAt) - TODAY) / day);

/** 접수 기간 중 현재 위치. 0~1. 상시 공고(200일 초과)는 null. */
export const progress = (j) => {
  const s = parseDate(j.postedAt), e = parseDate(j.closesAt);
  if ((e - s) / day > 200) return null;
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
    validThrough: j.closesAt + 'T23:59:59+09:00',
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
