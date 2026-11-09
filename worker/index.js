/*
 * 서치잡 회원 기능 서버 (Cloudflare Worker)
 * =====================================================================
 * 이 서버는 /api/* 와 /auth/* 주소의 요청만 받습니다.
 * wrangler.jsonc 의 assets.run_worker_first 가 그 두 갈래만 서버로 보내고,
 * 나머지(공고·기업·산업 페이지 전부)는 예전처럼 서버를 거치지 않고 정적
 * 파일로 나갑니다. 그래서 일반 방문이 Worker 무료 한도(하루 10만 건)에
 * 잡히지 않습니다. 로그인한 사람의 요청만 셉니다.
 *
 * 주소 목록
 *   GET  /auth/{kakao|naver|google}/start       로그인 시작
 *   GET  /auth/{…}/callback                      로그인 마무리 (업체가 돌려보냄)
 *   POST /auth/logout                            로그아웃
 *   GET  /api/me                                 내 정보 + 팔로우·찜·저장검색·알림함
 *   POST /api/consent                            약관·개인정보 동의
 *   POST /api/follow  {slug, name, on}           기업 팔로우 켜기/끄기
 *   POST /api/bookmark {id, title, company, on}  공고 찜 켜기/끄기
 *   POST /api/search  {q, ind, on}               검색 저장 켜기/끄기
 *   POST /api/keyword                            내 키워드(산업·직무·태그, 최대 3개) 등록·해제
 *   POST /api/push/subscribe | /api/push/unsubscribe
 *   POST /api/alerts/read                        알림함 비우기
 *   POST /api/account/delete                     회원 탈퇴
 *   POST /api/internal/new-jobs                  (비밀키) 새 공고 → 알림 대상 찾기
 *   POST /api/internal/flush                     (비밀키) 쌓인 알림을 폰으로 보내기
 *   POST /api/internal/stats                     (비밀키) 회원 수 통계(숫자만, 이름·별명 없음)
 *
 * 필요한 설정은 docs 의 「회원기능 설정 안내」 에 있습니다.
 */
import { ensureSchema } from './schema.js';
import {
  PROVIDERS, enabledProviders, startLogin, finishLogin, currentUser, logout, originOf,
} from './auth.js';
import { pushReady, sendPush } from './push.js';
import { json, fail, now, clean, safeEqual, allowedPushEndpoint } from './util.js';

const MAX_FOLLOWS = 200;
const MAX_BOOKMARKS = 500;
const MAX_SEARCHES = 20;
const MAX_DEVICES = 10; // 한 회원이 알림을 받을 수 있는 기기 수. 넘으면 가장 오래된 기기부터 지웁니다.
const FLUSH_BATCH = 20; // 한 번에 보낼 사람 수 (Worker 무료 한도: 바깥 호출 50회/실행)

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const path = url.pathname;
    try {
      if (!env.DB) return fail(503, '회원 기능이 아직 켜지지 않았습니다.');
      await ensureSchema(env.DB);

      // ── 로그인 ──
      let m = path.match(/^\/auth\/(kakao|naver|google)\/(start|callback)$/);
      if (m && req.method === 'GET') {
        return m[2] === 'start' ? startLogin(req, env, m[1]) : finishLogin(req, env, m[1]);
      }
      if (path === '/auth/logout' && req.method === 'POST') {
        if (!sameOrigin(req, env)) return fail(403, 'origin');
        // 약관에 동의하지 않고 나가는 사람의 회원번호·별명은 바로 지웁니다.
        const leaving = await currentUser(req, env);
        if (leaving && !leaving.consented) await purgeUser(env, leaving.id);
        const clear = await logout(req, env);
        return json({ ok: true }, 200, { 'Set-Cookie': clear });
      }

      if (path.startsWith('/api/internal/')) return internal(req, env, path);

      // ── 내 정보 (로그인 전에도 호출: 어떤 로그인이 열려 있는지 알려 줌) ──
      if (path === '/api/me' && req.method === 'GET') return me(req, env);

      // 이하 쓰기 요청은 같은 사이트에서 온 것만 받습니다.
      if (req.method !== 'POST') return fail(405, 'method');
      if (!sameOrigin(req, env)) return fail(403, 'origin');
      const user = await currentUser(req, env);
      if (!user) return fail(401, '로그인이 필요합니다.');

      if (path === '/api/consent') return consent(env, user);
      if (path === '/api/account/delete') return deleteAccount(req, env, user);
      // 동의 전에는 팔로우·찜 같은 이용 정보를 저장하지 않습니다(회원번호·별명만 임시로 있음).
      if (!user.consented) return fail(403, '약관과 개인정보 수집에 동의해 주세요.');

      const body = await req.json().catch(() => ({}));
      if (path === '/api/follow') return follow(env, user, body);
      if (path === '/api/bookmark') return bookmark(env, user, body);
      if (path === '/api/search') return saveSearch(env, user, body);
      if (path === '/api/keyword') return saveKeyword(env, user, body);
      if (path === '/api/push/subscribe') return subscribe(env, user, body);
      if (path === '/api/push/unsubscribe') return unsubscribe(env, user, body);
      if (path === '/api/alerts/read') return alertsRead(env, user);
      return fail(404, 'not found');
    } catch (e) {
      console.error('worker error', e && e.stack ? e.stack : e);
      return fail(500, '일시적인 오류입니다. 잠시 뒤 다시 시도해 주세요.');
    }
  },
};

/* 다른 사이트가 우리 주소로 몰래 요청을 보내는 것을 막습니다. */
function sameOrigin(req, env) {
  const o = req.headers.get('Origin');
  if (!o) return false;
  return o === originOf(req, env) || o === new URL(req.url).origin;
}

async function me(req, env) {
  const providers = enabledProviders(env).map((p) => ({ id: p, label: PROVIDERS[p].label }));
  // 심사 중인 로그인 업체: 버튼만 「심사 중」으로 막습니다. /auth/{업체}/start 주소는 그대로 열려 있어
  // 시험 계정(업체 쪽에 등록된 아이디)은 직접 주소로 로그인할 수 있습니다. 승인되면 이 값을 지웁니다.
  const preview = String(env.PREVIEW_PROVIDERS || '').split(',').map((x) => x.trim()).filter(Boolean);
  const base = { providers, preview, push: pushReady(env), vapid: env.VAPID_PUBLIC_KEY || null };
  const user = await currentUser(req, env);
  if (!user) return json({ ...base, user: null });
  if (!user.consented) return json({ ...base, user: { nickname: user.nickname, provider: user.provider, consented: false } });

  const db = env.DB;
  const [follows, bookmarks, searches, alerts, subs, keywords] = await Promise.all([
    db.prepare('SELECT company_slug AS slug, name FROM follows WHERE user_id = ?1 ORDER BY created_at DESC').bind(user.id).all(),
    db.prepare('SELECT job_id AS id, title, company FROM bookmarks WHERE user_id = ?1 ORDER BY created_at DESC').bind(user.id).all(),
    db.prepare('SELECT q, ind FROM saved_searches WHERE user_id = ?1 ORDER BY created_at DESC').bind(user.id).all(),
    db.prepare(
      `SELECT kind, job_id AS id, title, company, reason, created_at AS at FROM alerts
        WHERE user_id = ?1 ORDER BY created_at DESC, id DESC LIMIT 50`,
    ).bind(user.id).all(),
    db.prepare('SELECT COUNT(*) AS n FROM push_subs WHERE user_id = ?1').bind(user.id).first(),
    db.prepare('SELECT kind, value FROM keywords WHERE user_id = ?1 ORDER BY created_at').bind(user.id).all(),
  ]);
  return json({
    ...base,
    user: { nickname: user.nickname, provider: user.provider, consented: true },
    follows: follows.results,
    bookmarks: bookmarks.results,
    searches: searches.results,
    keywords: keywords.results,
    alerts: alerts.results,
    pushDevices: subs ? subs.n : 0,
  });
}

async function consent(env, user) {
  await env.DB.prepare('UPDATE users SET consent_at = ?1 WHERE id = ?2 AND consent_at IS NULL').bind(now(), user.id).run();
  return json({ ok: true });
}

async function count(env, table, userId) {
  const r = await env.DB.prepare(`SELECT COUNT(*) AS n FROM ${table} WHERE user_id = ?1`).bind(userId).first();
  return r ? r.n : 0;
}

async function follow(env, user, b) {
  const slug = clean(b.slug, 80);
  if (!/^[a-z0-9][a-z0-9-]*$/i.test(slug)) return fail(400, 'slug');
  if (b.on) {
    if ((await count(env, 'follows', user.id)) >= MAX_FOLLOWS) return fail(400, `팔로우는 ${MAX_FOLLOWS}곳까지 가능합니다.`);
    await env.DB.prepare('INSERT OR IGNORE INTO follows (user_id, company_slug, name, created_at) VALUES (?1, ?2, ?3, ?4)')
      .bind(user.id, slug, clean(b.name, 80), now()).run();
  } else {
    await env.DB.prepare('DELETE FROM follows WHERE user_id = ?1 AND company_slug = ?2').bind(user.id, slug).run();
  }
  return json({ ok: true });
}

async function bookmark(env, user, b) {
  const id = clean(b.id, 60);
  if (!/^[A-Za-z0-9._-]+$/.test(id)) return fail(400, 'id');
  if (b.on) {
    if ((await count(env, 'bookmarks', user.id)) >= MAX_BOOKMARKS) return fail(400, `찜은 ${MAX_BOOKMARKS}건까지 가능합니다. 마이페이지에서 지난 찜을 삭제해 주세요.`);
    await env.DB.prepare('INSERT OR IGNORE INTO bookmarks (user_id, job_id, title, company, created_at) VALUES (?1, ?2, ?3, ?4, ?5)')
      .bind(user.id, id, clean(b.title, 200), clean(b.company, 80), now()).run();
  } else {
    await env.DB.prepare('DELETE FROM bookmarks WHERE user_id = ?1 AND job_id = ?2').bind(user.id, id).run();
  }
  return json({ ok: true });
}

async function saveSearch(env, user, b) {
  const q = clean(b.q, 80);
  const ind = clean(b.ind, 40);
  if (!q && !ind) return fail(400, '저장할 검색어나 산업이 없습니다.');
  if (b.on) {
    if ((await count(env, 'saved_searches', user.id)) >= MAX_SEARCHES) return fail(400, `저장 검색은 ${MAX_SEARCHES}개까지 가능합니다.`);
    await env.DB.prepare('INSERT OR IGNORE INTO saved_searches (user_id, q, ind, created_at) VALUES (?1, ?2, ?3, ?4)')
      .bind(user.id, q, ind, now()).run();
  } else {
    await env.DB.prepare('DELETE FROM saved_searches WHERE user_id = ?1 AND q = ?2 AND ind = ?3').bind(user.id, q, ind).run();
  }
  return json({ ok: true });
}

const KW_KINDS = ['ind', 'role', 'tag'];
const MAX_KEYWORDS = 3;

async function saveKeyword(env, user, b) {
  const kind = String(b.kind || '');
  const value = clean(b.value, 40);
  if (!KW_KINDS.includes(kind) || !value) return fail(400, '키워드가 올바르지 않습니다.');
  if (b.on) {
    if ((await count(env, 'keywords', user.id)) >= MAX_KEYWORDS) return fail(400, `내 키워드는 ${MAX_KEYWORDS}개까지 가능합니다.`);
    await env.DB.prepare('INSERT OR IGNORE INTO keywords (user_id, kind, value, created_at) VALUES (?1, ?2, ?3, ?4)')
      .bind(user.id, kind, value, now()).run();
  } else {
    await env.DB.prepare('DELETE FROM keywords WHERE user_id = ?1 AND kind = ?2 AND value = ?3').bind(user.id, kind, value).run();
  }
  return json({ ok: true });
}

async function subscribe(env, user, b) {
  const endpoint = clean(b.endpoint, 600);
  const p256dh = clean(b.keys?.p256dh, 200);
  const auth = clean(b.keys?.auth, 100);
  // 알림 서버 주소는 브라우저 회사의 알림 서버만 받습니다 (util.js allowedPushEndpoint 참고).
  if (!allowedPushEndpoint(endpoint) || !p256dh || !auth) return fail(400, 'subscription');
  // 같은 기기를 다른 계정으로 쓰는 경우 주인이 바뀝니다.
  await env.DB.prepare(
    `INSERT INTO push_subs (endpoint, user_id, p256dh, auth, created_at) VALUES (?1, ?2, ?3, ?4, ?5)
     ON CONFLICT (endpoint) DO UPDATE SET user_id = ?2, p256dh = ?3, auth = ?4, created_at = ?5`,
  ).bind(endpoint, user.id, p256dh, auth, now()).run();
  // 기기가 너무 많으면 오래된 것부터 지웁니다.
  await env.DB.prepare(
    `DELETE FROM push_subs WHERE user_id = ?1 AND endpoint NOT IN
       (SELECT endpoint FROM push_subs WHERE user_id = ?1 ORDER BY created_at DESC, rowid DESC LIMIT ?2)`,
  ).bind(user.id, MAX_DEVICES).run();
  return json({ ok: true });
}

async function unsubscribe(env, user, b) {
  const endpoint = clean(b.endpoint, 600);
  await env.DB.prepare('DELETE FROM push_subs WHERE endpoint = ?1 AND user_id = ?2').bind(endpoint, user.id).run();
  return json({ ok: true });
}

async function alertsRead(env, user) {
  await env.DB.prepare('DELETE FROM alerts WHERE user_id = ?1').bind(user.id).run();
  return json({ ok: true });
}

// 회원 한 명의 모든 기록 삭제 (탈퇴·동의 없이 나감 공용)
async function purgeUser(env, id) {
  const db = env.DB;
  await db.batch([
    db.prepare('DELETE FROM push_subs WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM alerts WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM saved_searches WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM keywords WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM bookmarks WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM follows WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM sessions WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM users WHERE id = ?1').bind(id),
  ]);
}

async function deleteAccount(req, env, user) {
  const id = user.id;
  const db = env.DB;
  await db.batch([
    db.prepare('DELETE FROM push_subs WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM alerts WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM saved_searches WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM keywords WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM bookmarks WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM follows WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM sessions WHERE user_id = ?1').bind(id),
    db.prepare('DELETE FROM users WHERE id = ?1').bind(id),
  ]);
  const clear = await logout(req, env);
  return json({ ok: true }, 200, { 'Set-Cookie': clear });
}

// ───────────────────────── 알림 만들기·보내기 (GitHub 가 호출) ─────────────────────────

async function internal(req, env, path) {
  if (req.method !== 'POST') return fail(405, 'method');
  const given = (req.headers.get('Authorization') || '').replace(/^Bearer\s+/i, '');
  if (!env.NOTIFY_SECRET || !safeEqual(given, env.NOTIFY_SECRET)) return fail(401, 'unauthorized');
  const body = await req.json().catch(() => ({}));
  if (path === '/api/internal/new-jobs') return newJobs(env, body);
  if (path === '/api/internal/flush') return flush(env);
  if (path === '/api/internal/stats') return stats(env);
  return fail(404, 'not found');
}

const norm = (s) => String(s || '').toLowerCase();

/*
 * 새로 올라온 공고와 마감 임박 공고를 받아 알림함에 넣습니다.
 *   body.fresh  [{id, title, co, slug, ind:[…]}]  새 공고
 *   body.closing [{id, title, co, days}]          마감 3일 이내 공고
 * 같은 공고를 두 번 보내와도 processed_jobs / alerts 의 UNIQUE 로 한 번만 처리됩니다.
 */
async function newJobs(env, b) {
  const db = env.DB;
  const t = now();
  const fresh = Array.isArray(b.fresh) ? b.fresh.slice(0, 2000) : [];
  const closing = Array.isArray(b.closing) ? b.closing.slice(0, 2000) : [];
  let made = 0;

  // 1) 새 공고 — 이미 처리한 것은 건너뜀
  const seen = new Set();
  if (fresh.length) {
    const ids = fresh.map((j) => String(j.id));
    for (let i = 0; i < ids.length; i += 90) {
      const part = ids.slice(i, i + 90);
      const rs = await db.prepare(`SELECT job_id FROM processed_jobs WHERE job_id IN (${part.map(() => '?').join(',')})`).bind(...part).all();
      rs.results.forEach((r) => seen.add(r.job_id));
    }
  }
  const todo = fresh.filter((j) => !seen.has(String(j.id)));

  if (todo.length) {
    const searches = (await db.prepare('SELECT user_id, q, ind FROM saved_searches').all()).results;
    const kws = (await db.prepare('SELECT user_id, kind, value FROM keywords').all()).results;
    const stmts = [];
    for (const j of todo) {
      const id = String(j.id);
      const title = clean(j.title, 200);
      const co = clean(j.co, 80);
      const inds = Array.isArray(j.ind) ? j.ind.map(String) : [];
      const hay = norm(`${title} ${co}`);
      // 팔로우한 기업
      const fs = await db.prepare('SELECT user_id FROM follows WHERE company_slug = ?1').bind(clean(j.slug, 80)).all();
      const targets = new Map(); // user_id → reason
      fs.results.forEach((r) => targets.set(r.user_id, `${co} 팔로우`));
      // 저장 검색: 단어가 모두 들어 있고(q), 산업이 맞으면(ind)
      for (const s of searches) {
        if (targets.has(s.user_id)) continue;
        const words = norm(s.q).split(/\s+/).filter(Boolean);
        if (!words.every((w) => hay.includes(w))) continue;
        if (s.ind && !inds.includes(s.ind)) continue;
        targets.set(s.user_id, `저장 검색 「${[s.q, s.ind].filter(Boolean).join(' · ')}」`);
      }
      // 내 키워드: 산업·직무·태그 중 하나라도 맞으면 (사람마다 처음 맞은 것 하나만 이유로 적음)
      const roleNames = Array.isArray(j.role) ? j.role.map(String) : [];
      const tagNames = Array.isArray(j.tag) ? j.tag.map(String) : [];
      for (const k of kws) {
        if (targets.has(k.user_id)) continue;
        const hit = k.kind === 'ind' ? inds.includes(k.value)
          : k.kind === 'role' ? roleNames.includes(k.value)
            : tagNames.includes(k.value);
        if (hit) targets.set(k.user_id, `내 키워드 「${k.value}」`);
      }
      for (const [uid, reason] of targets) {
        stmts.push(db.prepare(
          `INSERT OR IGNORE INTO alerts (user_id, kind, job_id, title, company, reason, created_at, pushed)
           VALUES (?1, 'new', ?2, ?3, ?4, ?5, ?6, 0)`,
        ).bind(uid, id, title, co, reason, t));
      }
      stmts.push(db.prepare('INSERT OR IGNORE INTO processed_jobs (job_id, at) VALUES (?1, ?2)').bind(id, t));
    }
    for (let i = 0; i < stmts.length; i += 80) await db.batch(stmts.slice(i, i + 80));
    made += stmts.length;
  }

  // 2) 마감 임박 — 찜한 사람에게 한 번만
  if (closing.length) {
    const stmts = [];
    for (const j of closing) {
      const id = String(j.id);
      const bs = await db.prepare('SELECT user_id FROM bookmarks WHERE job_id = ?1').bind(id).all();
      const d = Number(j.days);
      const when = d <= 0 ? '오늘 마감' : `${d}일 남음`;
      for (const r of bs.results) {
        stmts.push(db.prepare(
          `INSERT OR IGNORE INTO alerts (user_id, kind, job_id, title, company, reason, created_at, pushed)
           VALUES (?1, 'close', ?2, ?3, ?4, ?5, ?6, 0)`,
        ).bind(r.user_id, id, clean(j.title, 200), clean(j.co, 80), `찜한 공고 · ${when}`, t));
      }
    }
    for (let i = 0; i < stmts.length; i += 80) await db.batch(stmts.slice(i, i + 80));
    made += stmts.length;
  }

  // 3) 오래된 기록 정리: 알림함 60일, 처리 기록 120일, 만료 로그인, 1년 미접속 회원
  await db.batch([
    db.prepare('DELETE FROM alerts WHERE created_at < ?1').bind(t - 60 * 86400),
    db.prepare('DELETE FROM processed_jobs WHERE at < ?1').bind(t - 120 * 86400),
    db.prepare('DELETE FROM sessions WHERE expires_at < ?1').bind(t),
    // 동의하지 않고 하루가 지난 로그인 기록 (회원번호·별명만 있음)
    db.prepare('DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE consent_at IS NULL AND last_login_at < ?1)').bind(t - 86400),
    db.prepare('DELETE FROM users WHERE consent_at IS NULL AND last_login_at < ?1').bind(t - 86400),
  ]);
  const old = (await db.prepare('SELECT id FROM users WHERE last_login_at < ?1 LIMIT 50').bind(t - 365 * 86400).all()).results;
  for (const u of old) {
    await db.batch([
      db.prepare('DELETE FROM push_subs WHERE user_id = ?1').bind(u.id),
      db.prepare('DELETE FROM alerts WHERE user_id = ?1').bind(u.id),
      db.prepare('DELETE FROM saved_searches WHERE user_id = ?1').bind(u.id),
      db.prepare('DELETE FROM keywords WHERE user_id = ?1').bind(u.id),
      db.prepare('DELETE FROM bookmarks WHERE user_id = ?1').bind(u.id),
      db.prepare('DELETE FROM follows WHERE user_id = ?1').bind(u.id),
      db.prepare('DELETE FROM sessions WHERE user_id = ?1').bind(u.id),
      db.prepare('DELETE FROM users WHERE id = ?1').bind(u.id),
    ]);
  }
  return json({ ok: true, fresh: fresh.length, handled: todo.length, rows: made, purged: old.length });
}

/*
 * 아직 폰으로 안 보낸 알림을 사람별로 묶어 한 통씩 보냅니다.
 * 한 번 호출에 FLUSH_BATCH 명까지만 처리하고 남았는지(remaining)를 알려 주므로,
 * 호출하는 쪽이 remaining 이 0 이 될 때까지 반복합니다.
 */
async function flush(env) {
  if (!pushReady(env)) return json({ ok: true, skipped: 'push keys not set', remaining: 0 });
  const db = env.DB;
  const users = (await db.prepare(
    `SELECT DISTINCT a.user_id FROM alerts a
       JOIN push_subs p ON p.user_id = a.user_id
      WHERE a.pushed = 0 LIMIT ?1`,
  ).bind(FLUSH_BATCH).all()).results;

  let sent = 0;
  let gone = 0;
  for (const { user_id: uid } of users) {
    const alerts = (await db.prepare(
      'SELECT id, kind, job_id, title, company FROM alerts WHERE user_id = ?1 AND pushed = 0 ORDER BY id LIMIT 30',
    ).bind(uid).all()).results;
    if (!alerts.length) continue;
    const news = alerts.filter((a) => a.kind === 'new');
    const close = alerts.filter((a) => a.kind === 'close');
    const lines = [];
    if (news.length) lines.push(`새 공고 ${news.length}건`);
    if (close.length) lines.push(`마감 임박 ${close.length}건`);
    const first = alerts[0];
    const message = {
      title: 'SEARCHJOB',
      body: `${lines.join(' · ')} — ${first.company ? `${first.company} ` : ''}${first.title}`.slice(0, 160),
      url: alerts.length === 1 ? `/job/${first.job_id}/` : '/my/',
    };
    const subs = (await db.prepare('SELECT endpoint, p256dh, auth FROM push_subs WHERE user_id = ?1 LIMIT 5').bind(uid).all()).results;
    for (const s of subs) {
      const r = await sendPush(s, message, env);
      if (r === 'ok') sent += 1;
      if (r === 'gone') { gone += 1; await db.prepare('DELETE FROM push_subs WHERE endpoint = ?1').bind(s.endpoint).run(); }
    }
    // 보내기를 시도했으면 다시 시도하지 않게 표시합니다(알림함에는 그대로 남음).
    await db.prepare(`UPDATE alerts SET pushed = 1 WHERE user_id = ?1 AND id IN (${alerts.map(() => '?').join(',')})`)
      .bind(uid, ...alerts.map((a) => a.id)).run();
  }
  // 알림을 받을 기기가 없는 사람의 알림은 보낼 곳이 없으니 보낸 것으로 처리합니다.
  await db.prepare(
    'UPDATE alerts SET pushed = 1 WHERE pushed = 0 AND user_id NOT IN (SELECT user_id FROM push_subs)',
  ).run();
  const rem = await db.prepare(
    `SELECT COUNT(DISTINCT a.user_id) AS n FROM alerts a JOIN push_subs p ON p.user_id = a.user_id WHERE a.pushed = 0`,
  ).first();
  return json({ ok: true, sent, gone, remaining: rem ? rem.n : 0 });
}


/*
 * 회원 수 통계 — 숫자만 돌려줍니다(이름·별명·번호는 나가지 않음).
 * 가입자 = 약관에 동의한 회원(consent_at 있음). 동의 전 임시 기록은 pending 으로 따로 셉니다.
 */
async function stats(env) {
  const db = env.DB;
  const t = now();
  const KST = 9 * 3600;
  const dayStart = Math.floor((t + KST) / 86400) * 86400 - KST; // 오늘 0시(한국시간)
  const one = async (sql, ...b) => (await db.prepare(sql).bind(...b).first()) || {};
  const total = await one('SELECT COUNT(*) AS n FROM users WHERE consent_at IS NOT NULL');
  const pending = await one('SELECT COUNT(*) AS n FROM users WHERE consent_at IS NULL');
  const byProv = (await db.prepare('SELECT provider, COUNT(*) AS n FROM users WHERE consent_at IS NOT NULL GROUP BY provider').all()).results;
  const today = await one('SELECT COUNT(*) AS n FROM users WHERE consent_at >= ?1', dayStart);
  const week = await one('SELECT COUNT(*) AS n FROM users WHERE consent_at >= ?1', dayStart - 6 * 86400);
  const active7 = await one('SELECT COUNT(*) AS n FROM users WHERE consent_at IS NOT NULL AND last_login_at >= ?1', t - 7 * 86400);
  const pushUsers = await one('SELECT COUNT(DISTINCT user_id) AS n FROM push_subs');
  const pushDevices = await one('SELECT COUNT(*) AS n FROM push_subs');
  const usersWith = async (table) => (await one(`SELECT COUNT(DISTINCT user_id) AS n FROM ${table}`)).n || 0;
  const rows = async (table) => (await one(`SELECT COUNT(*) AS n FROM ${table}`)).n || 0;
  return json({
    ok: true,
    members: total.n || 0,
    byProvider: Object.fromEntries(byProv.map((r) => [r.provider, r.n])),
    signedUpToday: today.n || 0,
    signedUpLast7Days: week.n || 0,
    loggedInLast7Days: active7.n || 0,
    pendingConsent: pending.n || 0,
    pushUsers: pushUsers.n || 0,
    pushDevices: pushDevices.n || 0,
    usersUsing: {
      follow: await usersWith('follows'),
      bookmark: await usersWith('bookmarks'),
      savedSearch: await usersWith('saved_searches'),
      keyword: await usersWith('keywords'),
    },
    rows: {
      follows: await rows('follows'),
      bookmarks: await rows('bookmarks'),
      savedSearches: await rows('saved_searches'),
      keywords: await rows('keywords'),
      alerts: await rows('alerts'),
    },
  });
}
