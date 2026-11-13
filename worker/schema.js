/*
 * 회원 기능 데이터베이스 (Cloudflare D1)
 * =====================================================================
 * 표를 사람이 따로 만들 필요가 없습니다. 이 파일의 문장이 처음 요청이 올 때
 * 한 번 실행되어 없는 표만 만듭니다(CREATE TABLE IF NOT EXISTS).
 * 이미 있으면 아무 일도 하지 않으므로 몇 번을 돌려도 안전합니다.
 *
 * 받는 정보는 일부러 최소로 했습니다.
 *   - 로그인한 곳(카카오·네이버·구글)과 그곳이 준 회원 번호, 별명
 *   - 이메일·전화번호·실명은 받지 않습니다
 *   - 팔로우한 기업, 찜한 공고, 저장한 검색, 알림 받을 브라우저 주소
 * 개인정보처리방침(src/pages/privacy.astro)은 이 표 구성과 맞춰 적었습니다.
 * 표에 항목을 더하면 방침 글도 같이 고쳐야 합니다.
 */
export const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS users (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     provider TEXT NOT NULL,
     provider_uid TEXT NOT NULL,
     nickname TEXT,
     created_at INTEGER NOT NULL,
     last_login_at INTEGER NOT NULL,
     consent_at INTEGER,
     UNIQUE (provider, provider_uid)
   )`,
  // 로그인 상태. 쿠키에는 무작위 값만 있고, 여기에는 그 값의 해시만 둡니다.
  `CREATE TABLE IF NOT EXISTS sessions (
     token_hash TEXT PRIMARY KEY,
     user_id INTEGER NOT NULL,
     created_at INTEGER NOT NULL,
     expires_at INTEGER NOT NULL
   )`,
  `CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id)`,
  `CREATE TABLE IF NOT EXISTS follows (
     user_id INTEGER NOT NULL,
     company_slug TEXT NOT NULL,
     name TEXT,
     created_at INTEGER NOT NULL,
     PRIMARY KEY (user_id, company_slug)
   )`,
  `CREATE INDEX IF NOT EXISTS idx_follows_slug ON follows (company_slug)`,
  `CREATE TABLE IF NOT EXISTS bookmarks (
     user_id INTEGER NOT NULL,
     job_id TEXT NOT NULL,
     title TEXT,
     company TEXT,
     created_at INTEGER NOT NULL,
     PRIMARY KEY (user_id, job_id)
   )`,
  `CREATE INDEX IF NOT EXISTS idx_bookmarks_job ON bookmarks (job_id)`,
  `CREATE TABLE IF NOT EXISTS saved_searches (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     user_id INTEGER NOT NULL,
     q TEXT NOT NULL DEFAULT '',
     ind TEXT NOT NULL DEFAULT '',
     created_at INTEGER NOT NULL,
     UNIQUE (user_id, q, ind)
   )`,
  `CREATE INDEX IF NOT EXISTS idx_ss_user ON saved_searches (user_id)`,
  // 내 키워드 (산업·직무·기술 태그 중 최대 3개). kind: ind | role | tag
  `CREATE TABLE IF NOT EXISTS keywords (
     user_id INTEGER NOT NULL,
     kind TEXT NOT NULL,
     value TEXT NOT NULL,
     created_at INTEGER NOT NULL,
     PRIMARY KEY (user_id, kind, value)
   )`,
  `CREATE INDEX IF NOT EXISTS idx_kw_user ON keywords (user_id)`,
  // 알림 받을 브라우저. endpoint 는 브라우저가 준 주소(알림을 보낼 곳)입니다.
  `CREATE TABLE IF NOT EXISTS push_subs (
     endpoint TEXT PRIMARY KEY,
     user_id INTEGER NOT NULL,
     p256dh TEXT NOT NULL,
     auth TEXT NOT NULL,
     created_at INTEGER NOT NULL
   )`,
  `CREATE INDEX IF NOT EXISTS idx_push_user ON push_subs (user_id)`,
  // 알림함. pushed=0 은 아직 폰으로 보내지 않은 것입니다.
  `CREATE TABLE IF NOT EXISTS alerts (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     user_id INTEGER NOT NULL,
     kind TEXT NOT NULL,
     job_id TEXT NOT NULL,
     title TEXT NOT NULL,
     company TEXT,
     reason TEXT,
     created_at INTEGER NOT NULL,
     pushed INTEGER NOT NULL DEFAULT 0,
     UNIQUE (user_id, kind, job_id)
   )`,
  `CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts (user_id, created_at DESC)`,
  `CREATE INDEX IF NOT EXISTS idx_alerts_unpushed ON alerts (pushed, user_id)`,
  // 이미 알림 대상으로 처리한 공고. 같은 공고로 알림이 두 번 가지 않게 합니다.
  /* 기업 채용담당자의 「채용페이지 등록 요청」 (2026-11-13). 로그인과 무관합니다.
     회사명·채용페이지 주소·담당자 이메일(회신용)·이름(선택)·메모(선택)만 받고,
     같은 사람의 반복 요청을 막으려고 접속 주소의 해시(원래 주소는 저장하지 않음)를 둡니다.
     처리 뒤 1년이 지나면 지웁니다(stats 호출 때). 개인정보처리방침과 맞춰 두었습니다. */
  `CREATE TABLE IF NOT EXISTS company_requests (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     company TEXT NOT NULL,
     career_url TEXT NOT NULL,
     email TEXT NOT NULL,
     name TEXT,
     message TEXT,
     ip_hash TEXT,
     created_at INTEGER NOT NULL
   )`,
  `CREATE INDEX IF NOT EXISTS company_requests_at ON company_requests(created_at)`,
  `CREATE TABLE IF NOT EXISTS processed_jobs (
     job_id TEXT PRIMARY KEY,
     at INTEGER NOT NULL
   )`,
];

let ready = false;

export async function ensureSchema(db) {
  if (ready) return;
  await db.batch(SCHEMA.map((s) => db.prepare(s)));
  ready = true;
}
