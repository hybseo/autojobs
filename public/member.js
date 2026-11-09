/*
 * 서치잡 회원 기능 — 브라우저 쪽 (모든 페이지에서 불러옴)
 * =====================================================================
 * 하는 일
 *   1) 머리줄의 「로그인」을 로그인한 사람에게는 「마이페이지」로 바꿈
 *   2) 기업 페이지에 「팔로우」, 공고 페이지에 「찜」, 공고 목록에 「이 검색 알림」 단추를 붙임
 *   3) /my/ 페이지(마이페이지) 전체를 그림
 *
 * 로그인하지 않은 방문자는 서버에 아무 요청도 보내지 않습니다(무료 한도 보호).
 * 로그인하면 이 브라우저에 sj_member=1 표시를 남기고, 그 표시가 있을 때만
 * /api/me 를 부릅니다. 단추를 눌렀을 때 로그인이 안 되어 있으면 /my/ 로 보냅니다.
 *
 * 화면 글자는 모두 textContent 로 넣습니다(회원이 저장한 제목이 코드로 실행되는 것을 막음).
 */
(function () {
  'use strict';

  var path = location.pathname;
  var FLAG = 'sj_member';
  var state = null; // /api/me 응답

  function flagged() { try { return localStorage.getItem(FLAG) === '1'; } catch (e) { return false; } }
  function setFlag(on) { try { if (on) localStorage.setItem(FLAG, '1'); else localStorage.removeItem(FLAG); } catch (e) { /* 무시 */ } }

  function el(tag, attrs, text) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === 'class') n.className = attrs[k]; else n.setAttribute(k, attrs[k]);
    });
    if (text != null) n.textContent = text;
    return n;
  }

  /* 구글 애널리틱스 이벤트 (2026-11-09).
     누가 했는지는 보내지 않습니다. 무엇을 했는지만 셉니다. 개인을 알아볼 수
     있는 값(회원번호·별명·검색어·공고 제목)은 넣지 않고, 기업 slug·종류처럼
     공개된 값만 넣습니다. gtag 가 없으면(차단 등) 조용히 넘어갑니다. */
  function track(name, params) {
    try { if (typeof window.gtag === 'function') window.gtag('event', name, Object.assign({ transport_type: 'beacon' }, params || {})); } catch (e) { /* 무시 */ }
  }
  function trackApi(url, body, r) {
    if (!r || !r.ok || !body) return;
    if (url === '/api/follow' && body.on) track('follow_company', { company: String(body.slug || '') });
    else if (url === '/api/bookmark' && body.on) track('bookmark_job');
    else if (url === '/api/search' && body.on) track('save_search');
    else if (url === '/api/keyword' && body.on) track('add_keyword', { kind: String(body.kind || '') });
    else if (url === '/api/consent') track('sign_up');
  }

  function api(url, body) {
    var opt = body === undefined
      ? { credentials: 'same-origin' }
      : { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    return fetch(url, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        var res = { ok: r.ok, status: r.status, data: j };
        trackApi(url, body, res);
        return res;
      });
    });
  }

  function toast(msg) {
    var t = el('div', { class: 'mem-toast', role: 'status' }, msg);
    document.body.appendChild(t);
    setTimeout(function () { t.classList.add('on'); }, 10);
    setTimeout(function () { t.classList.remove('on'); setTimeout(function () { t.remove(); }, 300); }, 2600);
  }

  function toLogin() { location.href = '/my/?next=' + encodeURIComponent(location.pathname + location.search); }

  function loadMe() {
    return api('/api/me').then(function (r) {
      state = r.ok ? r.data : null;
      if (state && state.user) setFlag(true); else setFlag(false);
      headerLink();
      return state;
    }).catch(function () { return null; });
  }

  /* ── 머리줄 로그인 링크 ── */
  function headerLink() {
    var a = document.getElementById('login-link');
    if (a && flagged()) { a.textContent = '마이페이지'; a.classList.add('in'); }

  }

  /* ── 기업 페이지: 팔로우 ── */
  function companyButton() {
    var m = path.match(/^\/company\/([^/]+)\/?$/);
    if (!m) return;
    var slug = decodeURIComponent(m[1]);
    var h1 = document.querySelector('main h1');
    if (!h1) return;
    var coName = (h1.textContent || '').trim();
    var b = el('button', { type: 'button', class: 'mem-btn' }, '＋ 팔로우');
    var wrap = el('div', { class: 'mem-bar' });
    wrap.appendChild(b);
    h1.insertAdjacentElement('afterend', wrap);
    var on = false;
    function paint() { b.textContent = on ? '✓ 팔로우 중' : '＋ 팔로우'; b.classList.toggle('on', on); }
    if (flagged()) loadMe().then(function (s) {
      if (s && s.follows) { on = s.follows.some(function (x) { return x.slug === slug; }); paint(); }
    });
    b.addEventListener('click', function () {
      if (!flagged()) return toLogin();
      api('/api/follow', { slug: slug, name: coName, on: !on }).then(function (r) {
        if (r.status === 401) return toLogin();
        if (!r.ok) return toast((r.data && r.data.error) || '저장하지 못했습니다.');
        on = !on; paint();
        toast(on ? '팔로우했습니다. 새 공고가 올라오면 알려 드립니다.' : '팔로우를 해제했습니다.');
      });
    });
  }

  /* ── 공고 페이지: 찜 ── */
  function jobButton() {
    var m = path.match(/^\/job\/([^/]+)\/?$/);
    if (!m) return;
    var id = decodeURIComponent(m[1]);
    var h1 = document.querySelector('main h1');
    if (!h1) return;
    var title = (h1.textContent || '').trim();
    var co = document.querySelector('main a[href^="/company/"]');
    var company = co ? (co.textContent || '').trim() : '';
    var b = el('button', { type: 'button', class: 'mem-btn' }, '♡ 찜');
    var wrap = el('div', { class: 'mem-bar' });
    wrap.appendChild(b);
    h1.insertAdjacentElement('afterend', wrap);
    var on = false;
    function paint() { b.textContent = on ? '♥ 찜한 공고' : '♡ 찜'; b.classList.toggle('on', on); }
    if (flagged()) loadMe().then(function (s) {
      if (s && s.bookmarks) { on = s.bookmarks.some(function (x) { return x.id === id; }); paint(); }
    });
    b.addEventListener('click', function () {
      if (!flagged()) return toLogin();
      api('/api/bookmark', { id: id, title: title, company: company, on: !on }).then(function (r) {
        if (r.status === 401) return toLogin();
        if (!r.ok) return toast((r.data && r.data.error) || '저장하지 못했습니다.');
        on = !on; paint();
        toast(on ? '찜했습니다. 마감이 가까워지면 알려 드립니다.' : '찜을 해제했습니다.');
      });
    });
  }

  /* ── 공고 목록: 이 검색 알림 ── */
  function searchButton() {
    if (!/^\/jobs\/?$/.test(path)) return;
    var app = document.getElementById('app');
    if (!app) return;
    var wrap = el('div', { class: 'mem-bar mem-search', hidden: '' });
    var b = el('button', { type: 'button', class: 'mem-btn' }, '🔔 이 검색 알림 받기');
    var hint = el('span', { class: 'mem-hint' }, '');
    wrap.appendChild(b); wrap.appendChild(hint);
    var saved = [];
    var wide = window.matchMedia ? window.matchMedia('(min-width:960px)') : { matches: false };
    function cur() {
      var p = new URLSearchParams(location.search);
      return { q: (p.get('q') || '').trim(), ind: p.get('ind') || '' };
    }
    /* PC: 제목 줄 오른쪽 칸(#mem-slot)에 붙입니다. 글이 다시 그려질 때마다 칸이 새로 생기므로 그때마다 옮깁니다.
       모바일: 예전처럼 목록 바로 위. */
    function place() {
      var slot = document.getElementById('mem-slot');
      if (wide.matches && slot) { if (wrap.parentNode !== slot) slot.appendChild(wrap); }
      else if (wrap.parentNode !== app.parentNode || wrap.nextSibling !== app) app.parentNode.insertBefore(wrap, app);
    }
    function paint() {
      place();
      var c = cur();
      var empty = !c.q && !c.ind;
      if (empty && !wide.matches) { wrap.hidden = true; return; }
      wrap.hidden = false;
      var on = !empty && saved.some(function (s) { return s.q === c.q && s.ind === c.ind; });
      b.textContent = on ? '🔔 알림 받는 중 ✓ (누르면 해제)' : '🔔 이 검색 알림 받기';
      b.classList.toggle('on', on);
      b.classList.toggle('off', empty);
      hint.textContent = empty
        ? '검색어를 입력하거나 산업을 고르면 켤 수 있습니다.'
        : '검색어「' + [c.q, c.ind].filter(Boolean).join(' · ') + '」에 맞는 새 공고를 알려 드립니다. (검색어·산업만 반영)';
      b.dataset.on = on ? '1' : '';
    }
    if (flagged()) loadMe().then(function (s) { if (s && s.searches) { saved = s.searches; } paint(); });
    var tm = null;
    function later() { clearTimeout(tm); tm = setTimeout(paint, 350); }
    new MutationObserver(function () { place(); later(); }).observe(app, { childList: true });
    document.addEventListener('input', later);
    if (wide.addEventListener) wide.addEventListener('change', paint);
    paint();
    b.addEventListener('click', function () {
      var c = cur();
      if (!c.q && !c.ind) return toast('먼저 위 검색창에 검색어를 입력하거나 산업을 골라 주세요.');
      if (!flagged()) return toLogin();
      var on = b.dataset.on === '1';
      api('/api/search', { q: c.q, ind: c.ind, on: !on }).then(function (r) {
        if (r.status === 401) return toLogin();
        if (!r.ok) return toast((r.data && r.data.error) || '저장하지 못했습니다.');
        if (on) saved = saved.filter(function (s) { return !(s.q === c.q && s.ind === c.ind); });
        else saved.push({ q: c.q, ind: c.ind });
        paint();
        toast(on ? '검색 알림을 해제했습니다.' : '저장했습니다. 맞는 새 공고가 올라오면 알려 드립니다.');
      });
    });
  }

  /* ── 웹푸시 ── */
  function urlB64ToUint8(s) {
    var p = (s + '='.repeat((4 - (s.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
    var raw = atob(p); var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
    return out;
  }
  function pushSupported() { return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window; }

  function enablePush(vapid) {
    if (!pushSupported()) return Promise.reject(new Error('unsupported'));
    return Notification.requestPermission().then(function (perm) {
      if (perm !== 'granted') throw new Error('denied');
      return navigator.serviceWorker.register('/sw.js');
    }).then(function () { return navigator.serviceWorker.ready; }).then(function (reg) {
      return reg.pushManager.getSubscription().then(function (sub) {
        return sub || reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8(vapid) });
      });
    }).then(function (sub) {
      var j = sub.toJSON();
      return api('/api/push/subscribe', { endpoint: j.endpoint, keys: j.keys }).then(function (r) { if (r && r.ok) track('enable_push'); return r; });
    });
  }
  function disablePush() {
    if (!pushSupported()) return Promise.resolve();
    return navigator.serviceWorker.getRegistration('/sw.js').then(function (reg) {
      if (!reg) return null;
      return reg.pushManager.getSubscription().then(function (sub) {
        if (!sub) return null;
        var ep = sub.endpoint;
        return sub.unsubscribe().then(function () { return api('/api/push/unsubscribe', { endpoint: ep }); });
      });
    });
  }

  /* ── 마이페이지 ── */
  var ERR = {
    not_ready: '이 로그인은 아직 준비 중입니다. 다른 방법으로 로그인해 주세요.',
    denied: '로그인을 취소하셨습니다.',
    state: '로그인 확인에 실패했습니다. 다시 시도해 주세요.',
    token: '로그인 처리에 실패했습니다. 잠시 뒤 다시 시도해 주세요.',
    profile: '프로필을 가져오지 못했습니다. 잠시 뒤 다시 시도해 주세요.',
    bad_provider: '알 수 없는 로그인 방식입니다.',
  };

  function section(root, title) {
    var s = el('section', { class: 'mem-sec' });
    s.appendChild(el('h2', null, title));
    root.appendChild(s);
    return s;
  }

  function listRow(parent, linkText, href, sub, onRemove) {
    var row = el('div', { class: 'mem-row' });
    var left = el('div', { class: 'mem-rl' });
    if (href) { var a = el('a', { href: href }, linkText); left.appendChild(a); } else left.appendChild(el('span', null, linkText));
    if (sub) left.appendChild(el('small', null, sub));
    row.appendChild(left);
    if (onRemove) {
      var x = el('button', { type: 'button', class: 'mem-x', 'aria-label': '삭제' }, '삭제');
      x.addEventListener('click', function () { onRemove(row, x); });
      row.appendChild(x);
    }
    parent.appendChild(row);
  }

  function renderLogin(root, s) {
    var p = new URLSearchParams(location.search);
    var next = p.get('next') || '/my/';
    var err = p.get('err');
    root.appendChild(el('h1', { class: 'h1' }, '로그인'));
    root.appendChild(el('p', { class: 'mem-lede' }, '관심 기업을 팔로우하고 공고를 찜하면, 새 공고와 마감 임박 소식을 알려 드립니다. 이메일·전화번호는 받지 않습니다.'));
    if (err && ERR[err]) root.appendChild(el('p', { class: 'mem-err' }, ERR[err]));
    var box = el('div', { class: 'mem-login' });
    var all = [['kakao', '카카오'], ['naver', '네이버'], ['google', '구글']];
    var on = {};
    var pre = {};
    ((s && s.providers) || []).forEach(function (x) { on[x.id] = true; });
    ((s && s.preview) || []).forEach(function (id) { pre[id] = true; });
    all.forEach(function (x) {
      var id = x[0];
      if (on[id] && pre[id]) {
        box.appendChild(el('span', { class: 'mem-prov mem-off', title: '업체의 승인 심사가 끝나면 열립니다' }, x[1] + ' (심사 중 · 곧 열립니다)'));
      } else if (on[id]) {
        var la = el('a', { class: 'mem-prov mem-' + id, href: '/auth/' + id + '/start?next=' + encodeURIComponent(next) }, x[1] + '로 시작하기');
        la.addEventListener('click', function () { track('login_click', { provider: id }); });
        box.appendChild(la);
      } else {
        box.appendChild(el('span', { class: 'mem-prov mem-off' }, x[1] + ' (준비 중)'));
      }
    });
    root.appendChild(box);
    root.appendChild(el('p', { class: 'mem-privacy' }, '성명, 이메일, 전화번호 등 개인정보는 받지 않습니다.'));
    root.appendChild(el('p', { class: 'mem-fine' }, '카카오·네이버·구글이 알려 주는 회원번호와 별명만 씁니다. 로그인하면 다음 화면에서 이용약관과 개인정보 수집·이용에 동의하는지 확인합니다. 동의하기 전에는 회원번호와 별명만 잠시 두며, 동의하지 않고 나가면 바로 지웁니다.'));
    var links = el('p', { class: 'mem-fine' });
    links.appendChild(el('a', { href: '/terms/' }, '이용약관'));
    links.appendChild(document.createTextNode(' · '));
    links.appendChild(el('a', { href: '/privacy/' }, '개인정보처리방침'));
    root.appendChild(links);
  }

  function renderConsent(root, s) {
    root.appendChild(el('h1', { class: 'h1' }, (s.user.nickname || '회원') + '님, 환영합니다'));
    root.appendChild(el('p', { class: 'mem-lede' }, '서비스를 쓰시려면 아래 내용에 동의해 주세요. 동의하지 않고 나가시면 회원번호와 별명을 바로 지웁니다.'));
    var form = el('form', { class: 'mem-consent' });
    function check(id, html, hrefText, href) {
      var lab = el('label', { class: 'mem-chk' });
      var inp = el('input', { type: 'checkbox', id: id });
      lab.appendChild(inp);
      lab.appendChild(document.createTextNode(' ' + html + ' '));
      if (href) lab.appendChild(el('a', { href: href, target: '_blank', rel: 'noopener' }, hrefText));
      form.appendChild(lab);
      return inp;
    }
    var a = check('c-age', '(필수) 만 14세 이상입니다.');
    var b = check('c-terms', '(필수) 이용약관에 동의합니다.', '[보기]', '/terms/');
    var c = check('c-priv', '(필수) 개인정보 수집·이용에 동의합니다.', '[보기]', '/privacy/');
    var go = el('button', { type: 'submit', class: 'mem-btn on' }, '동의하고 시작하기');
    var no = el('button', { type: 'button', class: 'mem-btn' }, '동의하지 않고 로그아웃');
    var acts = el('div', { class: 'mem-acts' });
    acts.appendChild(go); acts.appendChild(no);
    form.appendChild(acts);
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!(a.checked && b.checked && c.checked)) return toast('필수 항목에 모두 동의해 주세요.');
      api('/api/consent', {}).then(function (r) {
        if (!r.ok) return toast('저장하지 못했습니다. 다시 시도해 주세요.');
        var next = new URLSearchParams(location.search).get('next');
        if (next && next.charAt(0) === '/' && next.charAt(1) !== '/') location.href = next; else location.reload();
      });
    });
    no.addEventListener('click', function () {
      api('/auth/logout', {}).then(function () { setFlag(false); location.href = '/'; });
    });
    root.appendChild(form);
  }

  function dateOf(sec) {
    var d = new Date(sec * 1000);
    return (d.getMonth() + 1) + '/' + d.getDate();
  }

  function renderHome(root, s) {
    root.appendChild(el('h1', { class: 'h1' }, (s.user.nickname || '회원') + '님의 마이페이지'));

    // 알림
    var sp = section(root, '알림 설정');
    var info = el('p', { class: 'mem-lede' }, '');
    var pbtn = el('button', { type: 'button', class: 'mem-btn' }, '');
    sp.appendChild(info); sp.appendChild(pbtn);
    var sw = el('p', { class: 'mem-fine' }, '아이폰은 먼저 사파리에서 「홈 화면에 추가」로 설치한 뒤, 설치된 아이콘으로 열어야 알림을 켤 수 있습니다. ');
    sw.appendChild(el('a', { href: '/app/' }, '설치 방법 보기'));
    sp.appendChild(sw);
    function paintPush(devices) {
      if (!s.push) { info.textContent = '알림은 준비 중입니다.'; pbtn.hidden = true; return; }
      if (!pushSupported()) { info.textContent = '이 브라우저에서는 알림을 지원하지 않습니다. 아래 알림함에서 새 소식을 볼 수 있습니다.'; pbtn.hidden = true; return; }
      var on = devices > 0 && Notification.permission === 'granted';
      info.textContent = on ? '이 계정으로 알림을 받는 기기가 있습니다.' : '새 공고와 마감 임박을 폰·PC 알림으로 받으려면 켜 주세요.';
      pbtn.textContent = on ? '알림 끄기' : '알림 켜기';
      pbtn.classList.toggle('on', !on);
      pbtn.dataset.on = on ? '1' : '';
    }
    paintPush(s.pushDevices);
    pbtn.addEventListener('click', function () {
      var on = pbtn.dataset.on === '1';
      pbtn.disabled = true;
      var p = on ? disablePush() : enablePush(s.vapid);
      p.then(function () { s.pushDevices = on ? 0 : 1; paintPush(s.pushDevices); toast(on ? '알림을 껐습니다.' : '알림을 켰습니다.'); })
        .catch(function (e) { toast(e && e.message === 'denied' ? '브라우저에서 알림을 허용해 주세요.' : '알림을 켜지 못했습니다.'); })
        .then(function () { pbtn.disabled = false; });
    });

    // 내 키워드 (산업·직무·기술 태그 중 3개까지 — 하나라도 맞는 새 공고가 올라오면 알림)
    var KW_MAX = 3;
    var KW_LABEL = { ind: '산업', role: '직무', tag: '기술' };
    var kws = (s.keywords || []).slice();
    var sk = section(root, '내 키워드');
    var kwTitle = sk.querySelector('h2');
    var kwLede = el('p', { class: 'mem-lede' }, '관심 있는 산업·직무·기술을 3개까지 골라 두세요. 그중 하나라도 맞는 새 공고가 올라오면 알려 드립니다.');
    var kwChips = el('div', { class: 'mem-kw-sel' });
    var kwOpen = el('button', { type: 'button', class: 'mem-btn on' }, '＋ 키워드 고르기');
    var kwPanel = el('div', { class: 'mem-kw-panel', hidden: '' });
    sk.appendChild(kwLede); sk.appendChild(kwChips); sk.appendChild(kwOpen); sk.appendChild(kwPanel);
    var kwData = null;
    function kwHas(kind, value) { return kws.some(function (k) { return k.kind === kind && k.value === value; }); }
    function kwToggle(kind, value, on) {
      if (on && kws.length >= KW_MAX) return toast('내 키워드는 ' + KW_MAX + '개까지 고를 수 있습니다. 하나를 빼 주세요.');
      return api('/api/keyword', { kind: kind, value: value, on: on }).then(function (r) {
        if (r.status === 401) return toLogin();
        if (!r.ok) return toast((r.data && r.data.error) || '저장하지 못했습니다.');
        if (on) kws.push({ kind: kind, value: value });
        else kws = kws.filter(function (k) { return !(k.kind === kind && k.value === value); });
        paintKw();
      });
    }
    function paintKw() {
      kwTitle.textContent = '내 키워드 ' + kws.length + '/' + KW_MAX;
      kwChips.textContent = '';
      kws.forEach(function (k) {
        var c = el('button', { type: 'button', class: 'chip', 'aria-pressed': 'true', title: '누르면 뺍니다' }, KW_LABEL[k.kind] + ' · ' + k.value + ' ✕');
        c.addEventListener('click', function () { kwToggle(k.kind, k.value, false); });
        kwChips.appendChild(c);
      });
      kwOpen.hidden = kws.length >= KW_MAX;
      if (kws.length >= KW_MAX) kwPanel.hidden = true;
      if (!kwPanel.hidden) paintPanel();
    }
    var kwFilter = '';
    function paintPanel() {
      kwPanel.textContent = '';
      if (!kwData) { kwPanel.appendChild(el('p', { class: 'mem-fine' }, '불러오는 중…')); return; }
      var find = el('input', { type: 'search', class: 'mem-kw-find', placeholder: '키워드 찾기 (예: 영업, Python)', value: kwFilter });
      find.addEventListener('input', function () { kwFilter = find.value.trim(); paintList(); });
      kwPanel.appendChild(find);
      var list = el('div', { class: 'mem-kw-list' });
      kwPanel.appendChild(list);
      function group(title, items) {
        var shown = items.filter(function (x) { return !kwFilter || x[0].toLowerCase().indexOf(kwFilter.toLowerCase()) >= 0; });
        if (!shown.length) return;
        list.appendChild(el('h3', null, title));
        var box = el('div', { class: 'chips' });
        shown.forEach(function (x) {
          var on = kwHas(x.kind, x[0]);
          var c = el('button', { type: 'button', class: 'chip', 'aria-pressed': on ? 'true' : 'false' }, x[0]);
          c.appendChild(el('span', { class: 'n' }, String(x.n)));
          c.addEventListener('click', function () { kwToggle(x.kind, x[0], !on); });
          box.appendChild(c);
        });
        list.appendChild(box);
      }
      function paintList() {
        list.textContent = '';
        group('산업', kwData.ind.map(function (x) { return Object.assign([x[0]], { kind: 'ind', n: x[1] }); }));
        group('직무', kwData.role.map(function (x) { return Object.assign([x[0]], { kind: 'role', n: x[1] }); }));
        var cats = [];
        kwData.tag.forEach(function (x) { if (cats.indexOf(x[1]) < 0) cats.push(x[1]); });
        cats.forEach(function (cat) {
          group('기술 · ' + cat, kwData.tag.filter(function (x) { return x[1] === cat; })
            .map(function (x) { return Object.assign([x[0]], { kind: 'tag', n: x[2] }); }));
        });
        if (!list.firstChild) list.appendChild(el('p', { class: 'mem-fine' }, '찾는 키워드가 없습니다.'));
      }
      paintList();
    }
    kwOpen.addEventListener('click', function () {
      kwPanel.hidden = !kwPanel.hidden;
      kwOpen.textContent = kwPanel.hidden ? '＋ 키워드 고르기' : '닫기';
      if (kwPanel.hidden) return;
      paintPanel();
      if (!kwData) fetch('/keywords.json').then(function (r) { return r.json(); }).then(function (d) { kwData = d; paintPanel(); })
        .catch(function () { kwPanel.textContent = ''; kwPanel.appendChild(el('p', { class: 'mem-fine' }, '목록을 불러오지 못했습니다. 새로고침해 주세요.')); });
    });
    paintKw();

    // 알림함
    var sa = section(root, '새 소식');
    if (!s.alerts.length) sa.appendChild(el('p', { class: 'mem-empty' }, '아직 소식이 없습니다. 기업을 팔로우하거나 공고를 찜해 보세요.'));
    s.alerts.forEach(function (a) {
      listRow(sa, (a.company ? a.company + ' · ' : '') + a.title, '/job/' + encodeURIComponent(a.id) + '/',
        (a.kind === 'close' ? '마감 임박' : '새 공고') + ' · ' + (a.reason || '') + ' · ' + dateOf(a.at));
    });
    if (s.alerts.length) {
      var clr = el('button', { type: 'button', class: 'mem-btn' }, '알림함 비우기');
      clr.addEventListener('click', function () { api('/api/alerts/read', {}).then(function () { location.reload(); }); });
      sa.appendChild(clr);
    }

    // 팔로우
    var sf = section(root, '팔로우한 기업 ' + s.follows.length);
    if (!s.follows.length) sf.appendChild(el('p', { class: 'mem-empty' }, '기업 페이지에서 「팔로우」를 누르면 여기에 모입니다.'));
    s.follows.forEach(function (f) {
      listRow(sf, f.name || f.slug, '/company/' + encodeURIComponent(f.slug) + '/', '', function (row) {
        api('/api/follow', { slug: f.slug, on: false }).then(function (r) { if (r.ok) row.remove(); });
      });
    });

    // 찜 — 마감됐거나 내려간 공고는 「(마감된 공고입니다.)」로 표시하고 링크를 걸지 않습니다.
    // 지금 열려 있는 공고 번호 목록(/open-jobs.json)과 맞춰 봅니다. 찜 자체는 지우지 않습니다(사용자가 직접 삭제).
    var sb = section(root, '찜한 공고 ' + s.bookmarks.length);
    if (!s.bookmarks.length) sb.appendChild(el('p', { class: 'mem-empty' }, '공고 페이지에서 「찜」을 누르면 여기에 모입니다.'));
    var bkBox = el('div', { class: 'mem-bk' });
    sb.appendChild(bkBox);
    function paintBookmarks(openSet) {
      bkBox.textContent = '';
      var list = s.bookmarks.map(function (b) { return { b: b, closed: !!openSet && !openSet[b.id] }; });
      if (openSet) list.sort(function (x, y) { return (x.closed ? 1 : 0) - (y.closed ? 1 : 0); }); // 진행 중인 공고가 먼저
      list.forEach(function (x) {
        var b = x.b;
        var text = (b.company ? b.company + ' · ' : '') + (b.title || b.id);
        var remove = function (row) {
          api('/api/bookmark', { id: b.id, on: false }).then(function (r) { if (r.ok) row.remove(); });
        };
        if (x.closed) listRow(bkBox, text, null, '(마감된 공고입니다.)', remove);
        else listRow(bkBox, text, '/job/' + encodeURIComponent(b.id) + '/', openSet ? '' : '마감이 지났거나 내려간 공고는 열리지 않을 수 있습니다', remove);
      });
    }
    paintBookmarks(null);
    if (s.bookmarks.length) {
      fetch('/open-jobs.json').then(function (r) { return r.json(); }).then(function (d) {
        var set = {};
        (d.ids || []).forEach(function (id) { set[id] = true; });
        paintBookmarks(set);
      }).catch(function () { /* 목록을 못 받으면 예전처럼 링크로 둡니다 */ });
    }

    // 저장 검색
    var ss = section(root, '알림 받는 검색 ' + s.searches.length);
    if (!s.searches.length) ss.appendChild(el('p', { class: 'mem-empty' }, '공고 목록(공고 메뉴)에서 검색한 뒤, 결과 제목 오른쪽 위의 「🔔 이 검색 알림 받기」를 누르면 여기에 모입니다.'));
    s.searches.forEach(function (x) {
      var href = '/jobs/?' + new URLSearchParams(Object.assign({}, x.q ? { q: x.q } : {}, x.ind ? { ind: x.ind } : {})).toString();
      listRow(ss, [x.q, x.ind].filter(Boolean).join(' · '), href, '', function (row) {
        api('/api/search', { q: x.q, ind: x.ind, on: false }).then(function (r) { if (r.ok) row.remove(); });
      });
    });

    // 계정
    var sc = section(root, '계정');
    var out = el('button', { type: 'button', class: 'mem-btn' }, '로그아웃');
    out.addEventListener('click', function () {
      api('/auth/logout', {}).then(function () { setFlag(false); location.href = '/'; });
    });
    var del = el('button', { type: 'button', class: 'mem-btn mem-danger' }, '회원 탈퇴');
    del.addEventListener('click', function () {
      if (!window.confirm('탈퇴하면 팔로우·찜·저장 검색·알림 정보가 모두 즉시 삭제되며 되돌릴 수 없습니다. 탈퇴할까요?')) return;
      disablePush().catch(function () {}).then(function () { return api('/api/account/delete', {}); }).then(function (r) {
        if (!r.ok) return toast('탈퇴 처리에 실패했습니다. 잠시 뒤 다시 시도해 주세요.');
        setFlag(false); location.href = '/?bye=1';
      });
    });
    var acts = el('div', { class: 'mem-acts' });
    acts.appendChild(out); acts.appendChild(del);
    sc.appendChild(acts);
  }

  function myPage() {
    var root = document.getElementById('my');
    if (!root) return;
    root.textContent = '불러오는 중…';
    loadMe().then(function (s) {
      root.textContent = '';
      if (!s) { root.appendChild(el('p', { class: 'mem-err' }, '회원 서버에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요.')); return; }
      if (!s.user) return renderLogin(root, s);
      if (!s.user.consented) return renderConsent(root, s);
      renderHome(root, s);
    });
  }

  /* 홈의 간편로그인 안내: 로그인한 회원에게는 숨깁니다. 표시만 믿지 않고 서버에 한 번 확인합니다
     (로그인이 풀린 브라우저에 표시만 남았을 때 안내가 계속 숨지 않도록). */
  function homePromo() {
    var box = document.getElementById('home-promo');
    if (!box) return;
    if (flagged()) loadMe().then(function (s) { box.hidden = !!(s && s.user); });
  }

  headerLink();
  homePromo();
  if (path === '/my/' || path === '/my') myPage();
  else { companyButton(); jobButton(); searchButton(); }
})();
