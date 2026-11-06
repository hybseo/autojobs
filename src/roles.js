/*
 * 직무 분류 규칙 (src/lib.js 에서 옮겨 왔습니다 · 2026-11-06)
 * ============================================================
 * 알림 발송 스크립트(scripts/notify_delta.mjs)도 같은 규칙으로 공고의 직무를 구해야
 * 「내 키워드」알림이 맞게 갑니다. lib.js 는 Astro 에서만 불러올 수 있어서(JSON 가져오기),
 * 규칙만 이 파일로 빼고 lib.js 가 다시 가져다 씁니다. 직무 규칙을 고칠 때는 여기만 고치세요.
 * 이 파일은 다른 파일을 불러오지 않습니다(Node 에서 그대로 실행 가능해야 합니다).
 */
export const ROLE_RULES = [
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
  // 2026-11-04 추가, 같은 날 수정. 변호사는 국내/해외 변호사 자격이
  // 서로 다른 채용 시장이라 하나로 묶으면 안 됩니다. "변호사" 단독
  // (자격 불명시)은 대표님 지시로 국내로 간주합니다 — 해외/영미권/
  // 국제/외국/미국/뉴욕주 같은 수식어가 "변호사" 바로 앞에 없으면
  // 전부 국내입니다. title 에서 이미 한 번 걸러지므로(rolesOf 가
  // title 매치가 있으면 본문은 보지 않음), 회사 소개문에 "변호사
  // 회원" "개업 변호사" 식으로 스쳐 지나가는 본문 오탐은 title 에
  // 아무 직무도 안 걸리는 공고(예: "AI Engineer")에서만 날 수 있는데,
  // 실제 오픈 공고로 확인했을 때 그런 오탐은 없었습니다.
  ['lawyer_kr',       '변호사(국내)', /(?<!해외\s*)(?<!영미권\s*)(?<!국제\s*)(?<!외국\s*)(?<!미국\s*)(?<!뉴욕주\s*)변호사(?!\s*\(미국\))/],
  ['lawyer_intl',     '변호사(해외)', /해외\s*변호사|영미권\s*변호사|국제\s*변호사|외국\s*변호사\s*자격|변호사\s*\(미국\)|미국\s*변호사|뉴욕주\s*변호사|\bJD\b\s*학위/i],
  // CPA 는 마케팅에서 Cost Per Action(또는 Acquisition)을 뜻하기도
  // 합니다. "CPA/ROAS 광고 효율" 처럼 붙어 나오면 그쪽입니다. 확인:
  // 2026-11-04 기준 CPA 로 걸린 공고 중 키다리스튜디오 퍼포먼스
  // 마케팅 1건이 "CPA/ROAS 광고 효율 개선"으로 그쪽이었습니다.
  ['cpa',             '회계사',      /공인\s*회계사|AICPA|\bCPA\b(?!\s*\/\s*ROAS)(?<!ROAS\s*\/\s*)/i],
  ['tax_accountant',  '세무사',      /세무사/],
  ['labor_attorney',  '노무사',      /노무사/],
  ['patent_attorney', '변리사',      /변리사/],
  ['legal_scrivener', '법무사',      /법무사/],
  ['hr',        '경영지원',       /인사|\bHR\b|재무|회계|총무|법무|\bIR\b|구매\s*담당|재경|감사|변리사|Procurement|Purchasing|\bSCM\b|Accounting/i],
  ['research',  '연구개발',       /연구원|연구소|\bR&D\b|연구\s*개발|선행\s*연구/i],
];

const ROLE_NAME = Object.fromEntries(ROLE_RULES.map(([k, label]) => [k, label]));

/** 공고 하나의 직무 코드들. 없으면 빈 배열입니다. */
/*
 * 본문에서 태그와 엔티티를 걷어내고 글자만 남깁니다.
 * 직무 분류가 본문 앞부분을 볼 때 씁니다.
 */
export const stripTags = (s) =>
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
