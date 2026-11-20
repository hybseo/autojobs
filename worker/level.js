/*
 * 레벨 진단 — 회원 저장·이메일 (2026-11-20 대표님 결정)
 * =====================================================================
 * 화면: src/pages/level.astro + public/level/level.js
 *
 * 정한 것
 *   - 진단 안내(시작 화면)는 누구나 보지만, 진단은 SNS 간편로그인 회원만 합니다(가입 유도).
 *   - 처음 진단할 때 「레벨 진단 입력 내용 저장·이용」에 한 번 동의를 받습니다.
 *   - 진단할 때마다 입력 내용과 결과를 회원번호에 저장합니다. 회원당 최근 20회까지.
 *     다시 오면 지난 입력을 채워 주고, 지난 레벨과 비교해 보여 줍니다.
 *   - 실명·연락처는 받지 않습니다. 결과지에 적는 이름(선택)은 화면과 메일에만 쓰고 저장하지 않습니다.
 *   - 이메일(선택): 「결과를 이메일로 받기」를 고른 회원만. 결과 화면에서 주소를 적으면
 *     「이 주소로 보낼까요?」를 한 번 더 보여 주고(오타 방지), 누르면 바로 결과를 보냅니다.
 *     (2026-11-20 대표님 결정: 확인 메일 → 메일함 → 다시 돌아오는 단계는 번거로워 없앰)
 *     주소는 기억해 두고 다음 진단부터는 버튼 한 번으로 보냅니다.
 *     메일의 「레벨 진단 결과 보기」는 그 회차 결과 화면(/level/?run=번호)을 엽니다.
 *     보내는 것은 진단 결과뿐입니다(광고성 메일 아님 — 공고 추천 등은 따로 수신 동의가 필요).
 *   - 기업 등 외부에는 제공하지 않습니다. 인재검색을 열 때 공개 동의를 따로 받습니다.
 *   - 탈퇴하면 진단 기록·이메일을 바로 지웁니다. 진단 기록만 지울 수도 있습니다.
 *
 * 메일 발송: Resend(무료 월 3,000통·하루 100통). RESEND_API_KEY 와 MAIL_FROM(보내는 주소, 예:
 *   "서치잡 <noreply@도메인>")이 둘 다 설정되기 전에는 메일 기능이 꺼져 있고, 화면에도
 *   「준비 중」으로 나옵니다. 추측한 주소로 보내지 않기 위해 기본값을 두지 않았습니다.
 *   하루 MAIL_PER_DAY 통을 넘으면 그날은 보내지 않습니다(무료 한도 보호).
 */
import { json, fail, now, clean } from './util.js';
import { originOf } from './auth.js';

const KEEP_RUNS = 20;
const MAIL_PER_DAY = 95; // Resend 무료 하루 100통 — 여유분을 남김
const MAIL_PER_USER_DAY = 5;
const LV_NAME = { 6: '대기업 핵심권', 5: '대기업 도전권', 4: '중견 핵심권', 3: '중견 도전권', 2: '중소 핵심권', 1: '성장 단계' };

export const mailReady = (env) => !!(env.RESEND_API_KEY && env.MAIL_FROM);

async function member(env, userId) {
  return env.DB.prepare('SELECT * FROM level_members WHERE user_id = ?1').bind(userId).first();
}

/* GET /api/level — 진단 화면이 처음에 부릅니다. */
export async function levelState(env, user) {
  if (!user) return json({ user: null });
  if (!user.consented) return json({ user: { nickname: user.nickname }, consented: false });
  const db = env.DB;
  const m = await member(env, user.id);
  const runs = (await db.prepare(
    'SELECT id, created_at AS at, duty, rank, level FROM level_runs WHERE user_id = ?1 ORDER BY created_at DESC, id DESC LIMIT ?2',
  ).bind(user.id, KEEP_RUNS).all()).results;
  let last = null;
  if (runs.length) {
    const r = await db.prepare('SELECT id, created_at AS at, snap FROM level_runs WHERE id = ?1').bind(runs[0].id).first();
    try { last = { id: r.id, at: r.at, snap: JSON.parse(r.snap) }; } catch { last = null; }
  }
  return json({
    user: { nickname: user.nickname },
    consented: true,
    levelConsent: !!(m && m.consent_at),
    history: runs,
    last,
    email: m && m.email ? { addr: m.email } : null,
    mail: mailReady(env),
  });
}

/* GET /api/level/run?id= — 지난 진단 한 회차(결과 화면을 다시 그리는 데 쓰는 입력 내용). 본인 것만. */
export async function levelRun(env, user, id) {
  if (!user) return fail(401, '로그인이 필요합니다.');
  const r = await env.DB.prepare('SELECT id, created_at AS at, snap FROM level_runs WHERE id = ?1 AND user_id = ?2')
    .bind(Number(id) || 0, user.id).first();
  if (!r) return fail(404, '이 진단 기록을 찾지 못했습니다.');
  let snap = null;
  try { snap = JSON.parse(r.snap); } catch { snap = null; }
  return json({ id: r.id, at: r.at, snap });
}

/* POST /api/level/consent */
export async function levelConsent(env, user) {
  await env.DB.prepare(
    `INSERT INTO level_members (user_id, consent_at) VALUES (?1, ?2)
     ON CONFLICT (user_id) DO UPDATE SET consent_at = COALESCE(level_members.consent_at, ?2)`,
  ).bind(user.id, now()).run();
  return json({ ok: true });
}

/* POST /api/level/save { snap, result } — 진단 한 번 저장. 지난 진단(있으면)을 함께 돌려줍니다. */
export async function levelSave(env, user, b) {
  const m = await member(env, user.id);
  if (!m || !m.consent_at) return fail(403, '레벨 진단 저장에 동의해 주세요.');
  const snap = JSON.stringify(b.snap || {});
  if (snap.length > 30000) return fail(413, '입력 내용이 너무 깁니다.');
  const r = b.result || {};
  const level = Math.round(Number(r.level));
  if (!(level >= 1 && level <= 6)) return fail(400, 'level');
  const result = {
    duty: clean(r.duty, 60), sub: clean(r.sub, 60), rank: clean(r.rank, 20), level, raw: Math.round(Number(r.raw)) || null,
    items: Object.fromEntries(Object.entries(r.items || {}).slice(0, 8).map(([k, v]) => [clean(k, 10), v == null ? null : Math.round(Number(v) * 10) / 10])),
    concl: clean(r.concl, 400), strengths: clean(r.strengths, 120),
  };
  const db = env.DB;
  const prev = await db.prepare(
    'SELECT created_at AS at, duty, level FROM level_runs WHERE user_id = ?1 ORDER BY created_at DESC, id DESC LIMIT 1',
  ).bind(user.id).first();
  const t = now();
  const ins = await db.prepare(
    'INSERT INTO level_runs (user_id, created_at, duty, rank, level, snap, result) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)',
  ).bind(user.id, t, result.duty, result.rank, level, snap, JSON.stringify(result)).run();
  // 회원당 최근 KEEP_RUNS 회만 남깁니다.
  await db.prepare(
    `DELETE FROM level_runs WHERE user_id = ?1 AND id NOT IN
       (SELECT id FROM level_runs WHERE user_id = ?1 ORDER BY created_at DESC, id DESC LIMIT ?2)`,
  ).bind(user.id, KEEP_RUNS).run();
  return json({ ok: true, id: ins.meta ? ins.meta.last_row_id : null, prev: prev || null });
}

/* POST /api/level/delete { id? } — id 가 있으면 그 기록만, 없으면 진단 기록 전부와 이메일까지. */
export async function levelDelete(env, user, b) {
  const db = env.DB;
  if (b && b.id != null) {
    await db.prepare('DELETE FROM level_runs WHERE id = ?1 AND user_id = ?2').bind(Number(b.id), user.id).run();
    return json({ ok: true });
  }
  await db.batch([
    db.prepare('DELETE FROM level_runs WHERE user_id = ?1').bind(user.id),
    db.prepare('DELETE FROM level_members WHERE user_id = ?1').bind(user.id),
  ]);
  return json({ ok: true });
}

/* 탈퇴·동의 철회 때 부릅니다(index.js purgeUser·deleteAccount). */
export function levelPurgeStatements(db, userId) {
  return [
    db.prepare('DELETE FROM level_runs WHERE user_id = ?1').bind(userId),
    db.prepare('DELETE FROM level_members WHERE user_id = ?1').bind(userId),
  ];
}

/* ── 메일 ── */
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const okEmail = (e) => /^[^\s@<>"',;]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,24}$/.test(e);

async function mailBudget(env, userId) {
  const db = env.DB;
  const t = now();
  await db.prepare('DELETE FROM mail_log WHERE created_at < ?1').bind(t - 2 * 86400).run();
  const all = await db.prepare('SELECT COUNT(*) AS n FROM mail_log WHERE created_at >= ?1').bind(t - 86400).first();
  if (all && all.n >= MAIL_PER_DAY) return '오늘은 메일 발송이 많아 더 보낼 수 없습니다. 내일 다시 시도해 주세요.';
  const mine = await db.prepare('SELECT COUNT(*) AS n FROM mail_log WHERE user_id = ?1 AND created_at >= ?2').bind(userId, t - 86400).first();
  if (mine && mine.n >= MAIL_PER_USER_DAY) return `메일은 하루 ${MAIL_PER_USER_DAY}통까지 보낼 수 있습니다. 내일 다시 시도해 주세요.`;
  return null;
}

async function sendMail(env, userId, kind, to, subject, html, text) {
  let r;
  try {
    // MAIL_API 는 로컬 시험용(가짜 메일 서버). 실제 사이트에는 설정하지 않아 Resend 로 갑니다.
    r = await fetch(env.MAIL_API || 'https://api.resend.com/emails', {
      method: 'POST',
      headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ from: env.MAIL_FROM, to: [to], subject, html, text }),
    });
  } catch (e) {
    console.error('mail fail (network)', e && e.message);
    return false;
  }
  if (!r.ok) {
    console.error('mail fail', r.status, (await r.text().catch(() => '')).slice(0, 300));
    return false;
  }
  await env.DB.prepare('INSERT INTO mail_log (user_id, kind, created_at) VALUES (?1, ?2, ?3)').bind(userId, kind, now()).run();
  return true;
}

function frame(inner, origin) {
  return `<div style="font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#16181C;max-width:560px;margin:0 auto;padding:24px 16px;line-height:1.6">
<div style="font-weight:700;color:#A32E25;font-size:20px;margin-bottom:16px">SEARCHJOB</div>${inner}
<p style="font-size:12px;color:#858B92;border-top:1px solid #DDE1DE;padding-top:12px;margin-top:24px">이 메일은 서치잡 레벨 진단에서 「결과를 이메일로 받기」를 직접 신청하신 분께만 보냅니다. 광고 메일이 아닙니다.<br>
더 받지 않으려면 <a href="${origin}/level/" style="color:#2D5F7C">레벨 진단</a> 화면에서 이메일을 지우시면 됩니다.<br><a href="${origin}" style="color:#2D5F7C">searchjob.co.kr</a></p></div>`;
}

function resultMail(run, name, origin) {
  const r = JSON.parse(run.result || '{}');
  const who = name ? `${esc(name)} 님의` : '';
  const items = r.rank === '신입'
    ? [['학교', r.items.school], ['실무 경험', r.items.exp], ['기술 일치도', r.items.tech], ['영어·자격', r.items.spec]]
    : [['학교', r.items.school], ['회사 경력', r.items.co], ['평균 근속', r.items.ten], ['기술 일치도', r.items.tech]];
  const dots = (v) => (v == null ? '평가 제외' : '●'.repeat(Math.round(v / 2)) + '○'.repeat(5 - Math.round(v / 2)));
  const d = new Date(run.at * 1000 + 9 * 3600 * 1000).toISOString().slice(0, 10).replace(/-/g, '.');
  const link = `${origin}/level/?run=${run.id}`;
  const inner = `<p style="font-size:14px;color:#4B5158;margin:0">${who} 레벨 진단 결과 · ${d}</p>
<p style="font-size:15px;margin:6px 0 2px">${esc(r.duty)} · ${esc(r.rank)} 기준</p>
<p style="margin:0"><span style="font-size:44px;font-weight:700;color:#2D5F7C">${r.level}</span> <b style="font-size:18px">${LV_NAME[r.level] || ''}</b></p>
<table style="border-collapse:collapse;margin:14px 0;font-size:14px">${items.map(([k, v]) => `<tr><td style="padding:4px 14px 4px 0;color:#4B5158">${k}</td><td style="color:#2D5F7C;letter-spacing:2px">${dots(v)}</td></tr>`).join('')}</table>
${r.strengths ? `<p style="margin:0 0 8px"><b>강점</b> · ${esc(r.strengths)}</p>` : ''}
${r.concl ? `<p style="background:#E7EEF2;border-radius:8px;padding:10px 12px;margin:0">${esc(r.concl)}</p>` : ''}
<p style="margin:16px 0 0"><a href="${link}" style="display:inline-block;background:#2D5F7C;color:#fff;text-decoration:none;border-radius:8px;padding:10px 16px">레벨 진단 결과 보기</a></p>
<p style="font-size:12px;color:#858B92;margin-top:14px">평가 항목이 제한적입니다. 정해진 몇 가지 항목만으로 평가하며 실제 업무 성과·프로젝트 경험·리더십·대인 역량은 반영하지 못합니다. 결과는 참고로만 활용해 주세요.</p>`;
  const text = `${name ? name + ' 님의 ' : ''}레벨 진단 결과 (${d})\n${r.duty} · ${r.rank} 기준\n레벨 ${r.level} ${LV_NAME[r.level] || ''}\n${items.map(([k, v]) => `${k}: ${dots(v)}`).join('\n')}\n${r.concl || ''}\n\n레벨 진단 결과 보기: ${link}\n\n이 메일은 서치잡 레벨 진단에서 결과를 이메일로 받기를 신청하신 분께만 보냅니다.`;
  return { subject: `[서치잡] ${name ? name + ' 님의 ' : ''}레벨 진단 결과 — 레벨 ${r.level} ${LV_NAME[r.level] || ''}`, html: frame(inner, origin), text };
}

/* POST /api/level/email { email, id, name } — 화면에서 「이 주소로 보낼까요?」에 「보내기」를 누르면 부릅니다.
   주소를 기억하고 그 회차 결과를 바로 보냅니다. name 은 메일에만 쓰고 저장하지 않습니다. */
export async function levelEmail(req, env, user, b) {
  if (!mailReady(env)) return fail(503, '이메일 받기는 준비 중입니다.');
  const m = await member(env, user.id);
  if (!m || !m.consent_at) return fail(403, '레벨 진단 저장에 동의해 주세요.');
  const email = clean(b.email, 254).toLowerCase();
  if (!okEmail(email)) return fail(400, '이메일 주소를 확인해 주세요.');
  const run = await env.DB.prepare('SELECT id, created_at AS at, result FROM level_runs WHERE id = ?1 AND user_id = ?2')
    .bind(Number(b.id) || 0, user.id).first();
  if (!run) return fail(404, '보낼 진단 결과를 찾지 못했습니다.');
  const over = await mailBudget(env, user.id);
  if (over) return fail(429, over);
  const mail = resultMail(run, clean(b.name, 20) || user.nickname, originOf(req, env));
  const ok = await sendMail(env, user.id, 'result', email, mail.subject, mail.html, mail.text);
  if (!ok) return fail(502, '메일을 보내지 못했습니다. 주소를 확인하시고 잠시 뒤 다시 시도해 주세요.');
  await env.DB.prepare(
    'UPDATE level_members SET email = ?1, email_verified_at = ?2, email_token_hash = NULL, email_token_exp = NULL WHERE user_id = ?3',
  ).bind(email, now(), user.id).run();
  return json({ ok: true, to: email });
}

/* GET /api/level/verify — 예전 방식(확인 메일)의 링크. 이제 쓰지 않으므로 레벨 진단 화면으로 보냅니다. */
export async function levelVerify(req, env) {
  return Response.redirect(`${originOf(req, env)}/level/`, 302);
}

/* POST /api/level/send { id, name } — 등록된 주소로 결과를 보냅니다. name 은 메일에만 쓰고 저장하지 않습니다. */
export async function levelSend(req, env, user, b) {
  if (!mailReady(env)) return fail(503, '이메일 받기는 준비 중입니다.');
  const m = await member(env, user.id);
  if (!m || !m.email) return fail(400, '먼저 이메일 주소를 적어 주세요.');
  const run = await env.DB.prepare('SELECT id, created_at AS at, result FROM level_runs WHERE id = ?1 AND user_id = ?2')
    .bind(Number(b.id) || 0, user.id).first();
  if (!run) return fail(404, '보낼 진단 결과를 찾지 못했습니다.');
  const over = await mailBudget(env, user.id);
  if (over) return fail(429, over);
  const mail = resultMail(run, clean(b.name, 20) || user.nickname, originOf(req, env));
  const ok = await sendMail(env, user.id, 'result', m.email, mail.subject, mail.html, mail.text);
  return ok ? json({ ok: true, to: m.email }) : fail(502, '메일을 보내지 못했습니다. 잠시 뒤 다시 시도해 주세요.');
}

/* POST /api/level/email/remove — 등록한 이메일을 지웁니다. */
export async function levelEmailRemove(env, user) {
  await env.DB.prepare('UPDATE level_members SET email = NULL, email_verified_at = NULL, email_token_hash = NULL, email_token_exp = NULL WHERE user_id = ?1')
    .bind(user.id).run();
  return json({ ok: true });
}

/* 매일 아침 통계용(숫자만). */
export async function levelStats(db, t) {
  const one = async (sql, ...a) => (await db.prepare(sql).bind(...a).first()) || {};
  return {
    members: (await one('SELECT COUNT(*) AS n FROM level_members WHERE consent_at IS NOT NULL')).n || 0,
    runs24h: (await one('SELECT COUNT(*) AS n FROM level_runs WHERE created_at >= ?1', t - 86400)).n || 0,
    runsTotal: (await one('SELECT COUNT(*) AS n FROM level_runs')).n || 0,
    emails: (await one('SELECT COUNT(*) AS n FROM level_members WHERE email IS NOT NULL')).n || 0,
    mails24h: (await one('SELECT COUNT(*) AS n FROM mail_log WHERE created_at >= ?1', t - 86400)).n || 0,
    // 레벨 분포(2026-11-21 대표님 요청) — 회원마다 가장 최근 진단의 레벨만 세어 숫자로만 냅니다.
    // 누가·어떤 경력인지는 내지 않습니다(진단 기록은 본인만 본다고 안내했으므로).
    byLevel: ((await db.prepare(
      `SELECT level, COUNT(*) AS n FROM level_runs r
        WHERE id = (SELECT id FROM level_runs WHERE user_id = r.user_id ORDER BY created_at DESC, id DESC LIMIT 1)
        GROUP BY level ORDER BY level`,
    ).all()).results || []).map((x) => [x.level, x.n]),
  };
}
