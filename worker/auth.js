/*
 * 소셜 로그인 (카카오 · 네이버 · 구글)
 * =====================================================================
 * 흐름
 *   1) /auth/{업체}/start      → 업체의 로그인 화면으로 보냄 (state 값을 쿠키에 적어 둠)
 *   2) 업체가 /auth/{업체}/callback?code=…&state=… 로 돌려보냄
 *   3) state 가 쿠키와 같은지 확인 → code 를 토큰으로 바꿈 → 회원 번호·별명을 받음
 *   4) 우리 DB 에 회원을 만들거나 찾고, 로그인 쿠키를 심어 /my/ 로 보냄
 *
 * 업체별 키가 환경변수에 없으면 그 업체는 "준비 중" 으로 보입니다(enabledProviders).
 * 키 이름은 {대문자업체}_CLIENT_ID, {대문자업체}_CLIENT_SECRET 입니다.
 *
 * 받는 정보는 회원 번호와 별명뿐입니다. 이메일은 요청하지 않습니다.
 */
import { cookie, parseCookies, randomToken, safeNext, sha256Hex, now } from './util.js';

export const PROVIDERS = {
  kakao: {
    label: '카카오',
    authorize: 'https://kauth.kakao.com/oauth/authorize',
    token: 'https://kauth.kakao.com/oauth/token',
    me: 'https://kapi.kakao.com/v2/user/me',
    scope: 'profile_nickname',
    parse: (j) => ({
      uid: String(j.id),
      nickname: j.kakao_account?.profile?.nickname || j.properties?.nickname || '',
    }),
  },
  naver: {
    label: '네이버',
    authorize: 'https://nid.naver.com/oauth2.0/authorize',
    token: 'https://nid.naver.com/oauth2.0/token',
    me: 'https://openapi.naver.com/v1/nid/me',
    scope: '',
    parse: (j) => ({
      uid: String(j.response?.id || ''),
      nickname: j.response?.nickname || j.response?.name || '',
    }),
  },
  google: {
    label: '구글',
    authorize: 'https://accounts.google.com/o/oauth2/v2/auth',
    token: 'https://oauth2.googleapis.com/token',
    me: 'https://openidconnect.googleapis.com/v1/userinfo',
    scope: 'openid profile',
    parse: (j) => ({ uid: String(j.sub || ''), nickname: j.name || j.given_name || '' }),
  },
};

const SESSION_DAYS = 30;

export function enabledProviders(env) {
  return Object.keys(PROVIDERS).filter((p) => {
    const P = p.toUpperCase();
    return env[`${P}_CLIENT_ID`] && env[`${P}_CLIENT_SECRET`];
  });
}

/* 로그인 완료 후 돌아올 주소. 실제 사이트 주소 또는 지금 요청의 주소. */
export const originOf = (req, env) => (env.SITE_ORIGIN || new URL(req.url).origin).replace(/\/$/, '');

const isLocal = (origin) => /^http:\/\/(localhost|127\.0\.0\.1)/.test(origin);

export function startLogin(req, env, provider) {
  const cfg = PROVIDERS[provider];
  const P = provider.toUpperCase();
  const origin = originOf(req, env);
  if (!cfg || !env[`${P}_CLIENT_ID`] || !env[`${P}_CLIENT_SECRET`]) {
    return Response.redirect(`${origin}/my/?err=not_ready`, 302);
  }
  const url = new URL(req.url);
  const state = randomToken(24);
  const next = safeNext(url.searchParams.get('next') || '/my/');
  const params = new URLSearchParams({
    client_id: env[`${P}_CLIENT_ID`],
    redirect_uri: `${origin}/auth/${provider}/callback`,
    response_type: 'code',
    state,
  });
  if (cfg.scope) params.set('scope', cfg.scope);
  if (provider === 'google') params.set('prompt', 'select_account');
  const headers = new Headers({ Location: `${cfg.authorize}?${params}` });
  headers.append(
    'Set-Cookie',
    cookie('sj_oauth', JSON.stringify({ state, provider, next }), { maxAge: 600, secure: !isLocal(origin) }),
  );
  headers.set('Cache-Control', 'no-store');
  return new Response(null, { status: 302, headers });
}

async function exchangeCode(cfg, provider, env, origin, code, state) {
  const P = provider.toUpperCase();
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: env[`${P}_CLIENT_ID`],
    client_secret: env[`${P}_CLIENT_SECRET`],
    redirect_uri: `${origin}/auth/${provider}/callback`,
    code,
  });
  if (provider === 'naver') body.set('state', state);
  const r = await fetch(cfg.token, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json' },
    body,
  });
  if (!r.ok) return null;
  const j = await r.json().catch(() => null);
  return j && j.access_token ? j.access_token : null;
}

export async function finishLogin(req, env, provider) {
  const cfg = PROVIDERS[provider];
  const origin = originOf(req, env);
  const back = (err) => Response.redirect(`${origin}/my/?err=${err}`, 302);
  if (!cfg) return back('bad_provider');

  const url = new URL(req.url);
  if (url.searchParams.get('error')) return back('denied'); // 사용자가 동의 화면에서 취소
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  let saved = null;
  try { saved = JSON.parse(parseCookies(req).sj_oauth || 'null'); } catch { saved = null; }
  if (!code || !state || !saved || saved.state !== state || saved.provider !== provider) return back('state');

  const token = await exchangeCode(cfg, provider, env, origin, code, state);
  if (!token) return back('token');
  const meRes = await fetch(cfg.me, { headers: { Authorization: `Bearer ${token}` } });
  if (!meRes.ok) return back('profile');
  const me = cfg.parse(await meRes.json().catch(() => ({})));
  if (!me.uid) return back('profile');

  const t = now();
  const nickname = (me.nickname || '').slice(0, 40) || '회원';
  await env.DB.prepare(
    `INSERT INTO users (provider, provider_uid, nickname, created_at, last_login_at)
     VALUES (?1, ?2, ?3, ?4, ?4)
     ON CONFLICT (provider, provider_uid) DO UPDATE SET last_login_at = ?4`,
  ).bind(provider, me.uid, nickname, t).run();
  const user = await env.DB.prepare('SELECT id FROM users WHERE provider = ?1 AND provider_uid = ?2')
    .bind(provider, me.uid).first();

  const raw = randomToken(32);
  await env.DB.prepare('INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?1, ?2, ?3, ?4)')
    .bind(await sha256Hex(raw), user.id, t, t + SESSION_DAYS * 86400).run();

  const headers = new Headers({ Location: `${origin}${safeNext(saved.next)}` });
  headers.append('Set-Cookie', cookie('sj_sess', raw, { maxAge: SESSION_DAYS * 86400, secure: !isLocal(origin) }));
  headers.append('Set-Cookie', cookie('sj_oauth', '', { maxAge: 0, secure: !isLocal(origin) }));
  headers.set('Cache-Control', 'no-store');
  return new Response(null, { status: 302, headers });
}

/* 요청의 로그인 쿠키로 회원을 찾습니다. 없거나 만료면 null. */
export async function currentUser(req, env) {
  const raw = parseCookies(req).sj_sess;
  if (!raw) return null;
  const hash = await sha256Hex(raw);
  const row = await env.DB.prepare(
    `SELECT u.id, u.nickname, u.provider, u.consent_at, s.expires_at
       FROM sessions s JOIN users u ON u.id = s.user_id
      WHERE s.token_hash = ?1`,
  ).bind(hash).first();
  if (!row || row.expires_at < now()) return null;
  return { id: row.id, nickname: row.nickname, provider: row.provider, consented: !!row.consent_at, hash };
}

export async function logout(req, env) {
  const raw = parseCookies(req).sj_sess;
  if (raw) await env.DB.prepare('DELETE FROM sessions WHERE token_hash = ?1').bind(await sha256Hex(raw)).run();
  const origin = originOf(req, env);
  return cookie('sj_sess', '', { maxAge: 0, secure: !isLocal(origin) });
}
