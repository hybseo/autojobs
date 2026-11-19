/*
 * 오류 신고 (2026-11-20 대표님 지시)
 * =====================================================================
 * 모든 페이지 오른쪽 아래에 작은 「오류 신고」 버튼을 둡니다(Base.astro 가 불러옴).
 * 이용자는 버튼만 누르면 끝입니다. 고르거나 적을 것이 없습니다.
 * 원인은 함께 보내는 정보로 우리가 찾습니다:
 *   - 페이지 주소·제목, 브라우저 정보, 화면 크기
 *   - 이 페이지에서 난 화면 오류(최대 10개)와 서버 응답 실패(5xx)
 *   - 최근 동작(최대 20개): 연 페이지, 누른 메뉴·버튼 이름, 검색어, 필터 선택
 * 보내지 않는 것: 회원 번호·별명, 이메일·이름 등 입력 칸에 적은 내용(검색창만 예외).
 *
 * 화면 오류가 나면 버튼을 누르지 않아도 자동으로 한 번 기록합니다(kind=auto).
 * 같은 오류는 한 방문에 한 번, 한 페이지에서 최대 3건까지만 보냅니다.
 *
 * 서버: worker/index.js 의 errorReport·errorNote. 30일 뒤 삭제.
 * 이 파일을 바꾸면 개인정보처리방침(src/pages/privacy.astro 1·3번)과 꼬리말 안내도 맞춰 고치세요.
 */
(function () {
  if (window.__sjReport) return;
  window.__sjReport = true;

  var MAX_ERR = 10, MAX_ACT = 20, MAX_AUTO = 3;
  var errs = [], acts = [], sentSig = {}, autoSent = 0, autoTimer = null, pendingAuto = null;
  var origFetch = window.fetch ? window.fetch.bind(window) : null;

  function short(s, n) {
    s = String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
    return s.length > n ? s.slice(0, n) + '…' : s;
  }
  function stamp() { return new Date().toISOString().slice(0, 19); }
  function pathOf(u) {
    try {
      var x = new URL(u, location.href);
      var p = x.origin === location.origin ? x.pathname + x.search : x.origin + x.pathname;
      try { p = decodeURIComponent(p); } catch (e2) { /* 깨진 주소는 그대로 */ }
      return p;
    }
    catch (e) { return short(u, 200); }
  }
  function isOurs(u) { return /\/api\/error-report/.test(String(u || '')); }

  /* ── 최근 동작: 같은 탭 안에서는 페이지를 옮겨도 이어서 기록 ── */
  try { acts = JSON.parse(sessionStorage.getItem('sj_acts') || '[]') || []; } catch (e) { acts = []; }
  function act(t, v) {
    v = short(v, 120);
    var last = acts[acts.length - 1];
    if (last && last.t === t && last.v === v) return; // 같은 동작이 바로 겹치면 한 번만 (검색은 change·submit 둘 다 옴)
    acts.push({ t: t, v: v, at: stamp() });
    if (acts.length > MAX_ACT) acts = acts.slice(-MAX_ACT);
    try { sessionStorage.setItem('sj_acts', JSON.stringify(acts)); } catch (e) { /* 저장 안 돼도 이 페이지 기록은 남음 */ }
  }
  act('열기', pathOf(location.href));

  function inPanel(el) { return el && el.closest && el.closest('#sj-report'); }
  document.addEventListener('click', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('a,button,summary,[role=button],label') : null;
    if (!el || inPanel(el)) return;
    var name = short(el.getAttribute('aria-label') || el.textContent || el.getAttribute('title') || '', 40);
    if (el.tagName === 'A' && el.getAttribute('href')) act('누름', (name || '링크') + ' → ' + pathOf(el.href));
    else act('누름', name || el.tagName.toLowerCase());
  }, true);
  document.addEventListener('change', function (e) {
    var el = e.target;
    if (!el || inPanel(el) || !el.tagName) return;
    var key = el.name || el.id || el.tagName.toLowerCase();
    if (el.tagName === 'SELECT') act('선택', key + '=' + short(el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : el.value, 60));
    else if (el.type === 'checkbox' || el.type === 'radio') act('선택', key + (el.checked ? ' 켬' : ' 끔') + (el.value && el.value !== 'on' ? ' (' + short(el.value, 40) + ')' : ''));
    else if (el.type === 'search') act('검색', short(el.value, 60));
    else act('입력', key); // 이메일·이름 같은 입력 내용은 보내지 않고 칸 이름만
  }, true);
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f || inPanel(f)) return;
    var q = f.querySelector && f.querySelector('input[type=search]');
    act('검색', q ? short(q.value, 60) : pathOf(f.action || location.href));
  }, true);

  /* ── 화면 오류 기록 ── */
  function rec(x, auto) {
    x.at = stamp();
    errs.push(x);
    if (errs.length > MAX_ERR) errs = errs.slice(-MAX_ERR);
    if (auto) queueAuto(x);
  }
  window.addEventListener('error', function (e) {
    var t = e.target;
    if (t && t !== window && t.tagName) {
      // 우리 사이트의 스크립트·스타일 파일을 못 불러온 경우만 기록합니다.
      // 이미지 실패는 흔하고 화면 고장이 아니며, 구글 통계 같은 바깥 파일은 광고 차단 프로그램이 자주 막아 잡음만 됩니다.
      var src = t.src || t.href || '';
      var mine = false;
      try { mine = new URL(src, location.href).origin === location.origin; } catch (e3) { mine = false; }
      if ((t.tagName === 'SCRIPT' || t.tagName === 'LINK') && mine) rec({ t: '불러오기', m: '파일을 불러오지 못함', src: pathOf(src) }, false);
      return;
    }
    var m = e.message || '';
    if (!m || /^Script error\.?$/i.test(m)) return; // 다른 사이트 스크립트(광고·통계)의 오류는 내용이 가려져 와서 쓸모가 없음
    rec({ t: '화면', m: short(m, 300), src: pathOf(e.filename || '') + ':' + (e.lineno || 0) + ':' + (e.colno || 0), st: short(e.error && e.error.stack, 800) }, true);
  }, true);
  window.addEventListener('unhandledrejection', function (e) {
    var r = e.reason;
    var m = r && (r.message || (typeof r === 'string' ? r : '')) || '';
    if (!m) return;
    rec({ t: '화면', m: short(m, 300), st: short(r && r.stack, 800) }, true);
  });
  if (origFetch) {
    window.fetch = function (input, init) {
      var u = typeof input === 'string' ? input : (input && input.url) || '';
      var p = origFetch(input, init);
      if (!isOurs(u)) {
        p.then(function (r) {
          if (!r.ok) rec({ t: '서버', m: 'HTTP ' + r.status, src: pathOf(u) }, r.status >= 500);
        }, function (err) {
          rec({ t: '서버', m: '연결 실패 ' + short(err && err.message, 80), src: pathOf(u) }, false);
        });
      }
      return p;
    };
  }

  function payload(kind, sig) {
    return {
      kind: kind, sig: sig || undefined,
      page: (location.pathname + location.search).slice(0, 300),
      title: short(document.title, 150),
      ua: short(navigator.userAgent, 300),
      scr: window.innerWidth + 'x' + window.innerHeight + '@' + (window.devicePixelRatio || 1),
      errors: errs.slice(), actions: acts.slice(),
    };
  }
  function post(url, body) {
    if (!origFetch) return Promise.reject(new Error('fetch 없음'));
    return origFetch(url, {
      method: 'POST', credentials: 'same-origin', keepalive: true,
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { d._status = r.status; return d; }); });
  }

  /* 화면 오류 자동 기록: 1.5초 모아서 한 번에 (같은 오류가 연달아 나도 한 건) */
  function queueAuto(x) {
    var sig = (x.t + '|' + x.m + '|' + (x.src || '')).slice(0, 300);
    if (sentSig[sig] || autoSent >= MAX_AUTO) return;
    sentSig[sig] = 1;
    pendingAuto = sig;
    clearTimeout(autoTimer);
    autoTimer = setTimeout(function () {
      autoSent += 1;
      post('/api/error-report', payload('auto', pendingAuto)).catch(function () {});
    }, 1500);
  }

  /* ── 버튼 ── */
  function build() {
    if (document.getElementById('sj-report')) return;
    var box = document.createElement('div');
    box.id = 'sj-report';
    box.innerHTML =
      '<button type="button" class="sjr-btn" title="누르면 지금 보던 화면 정보(페이지·기기·오류 기록·최근 동작)가 함께 전송됩니다">오류 신고</button>' +
      '<div class="sjr-panel" role="status" aria-live="polite" hidden></div>';
    document.body.appendChild(box);
    var btn = box.querySelector('.sjr-btn');
    var panel = box.querySelector('.sjr-panel');

    // 공고 상세의 「회사 공고로 이동」 바(폰)가 있으면 그 위로 올립니다.
    function lift() {
      var bar = document.querySelector('.mbar');
      var up = bar && getComputedStyle(bar).display !== 'none';
      box.classList.toggle('sjr-up', !!up);
    }
    lift();
    window.addEventListener('resize', lift);

    function close() { panel.hidden = true; panel.innerHTML = ''; btn.disabled = false; }
    function show(html) { panel.innerHTML = html + '<button type="button" class="sjr-x" aria-label="닫기">닫기</button>'; panel.hidden = false; panel.querySelector('.sjr-x').onclick = close; }

    btn.addEventListener('click', function () {
      btn.disabled = true;
      show('<p>보내는 중…</p>');
      post('/api/error-report', payload('manual')).then(function (d) {
        if (!d.ok) throw new Error(d.error || ('HTTP ' + d._status));
        show(
          '<p><b>신고가 접수됐습니다. 고맙습니다.</b></p>' +
          '<p class="sjr-s">지금 보던 화면 정보가 함께 전달됐습니다. 확인해서 고치겠습니다.</p>' +
          '<textarea maxlength="500" rows="2" placeholder="더 알려주실 게 있으면 적어 주세요 (선택)"></textarea>' +
          '<button type="button" class="sjr-send">덧붙이기</button>'
        );
        var ta = panel.querySelector('textarea');
        panel.querySelector('.sjr-send').onclick = function () {
          var note = ta.value.trim();
          if (!note) { close(); return; }
          this.disabled = true;
          post('/api/error-report/note', { id: d.id, token: d.token, note: note }).then(function (r) {
            show(r.ok ? '<p><b>덧붙였습니다. 고맙습니다.</b></p>' : '<p>덧붙이지 못했습니다. 신고는 이미 접수됐습니다.</p>');
            setTimeout(close, 2500);
          }, function () { show('<p>덧붙이지 못했습니다. 신고는 이미 접수됐습니다.</p>'); });
        };
      }).catch(function (err) {
        var msg = err && /오늘은/.test(err.message) ? err.message
          : '지금은 신고를 받지 못했습니다. <a href="mailto:searchjob.kr@gmail.com">searchjob.kr@gmail.com</a> 으로 알려 주시면 확인하겠습니다.';
        show('<p>' + msg + '</p>');
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();
})();
