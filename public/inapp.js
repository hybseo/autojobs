/*
 * 앱 안 브라우저 안내 (2026-11-23 대표님 지시)
 * ---------------------------------------------------------------------
 * 링크드인·인스타그램·페이스북·카카오톡·네이버 앱 등에서 링크를 누르면 그 앱 안의 브라우저로 열립니다.
 * 여기서는 로그인이 잘 안 됩니다.
 *   - 구글: 앱 안 브라우저 로그인을 구글이 보안상 막습니다(403 disallowed_useragent).
 *   - 카카오·네이버: 휴대폰의 기존 로그인을 못 써서 아이디·비밀번호를 직접 쳐야 하는 경우가 많습니다.
 * 그래서 로그인 화면(/my/)에서 앱 안 브라우저면:
 *   - 카카오톡 안이면 휴대폰 기본 브라우저로 자동으로 넘깁니다(카카오톡이 제공하는 주소 형식).
 *   - 안드로이드는 「크롬으로 열기」 버튼, 아이폰은 「⋯ → 브라우저에서 열기」 안내와 「주소 복사」 버튼.
 *   - 구글 로그인 버튼은 회색으로 두고 이유를 적습니다.
 * 판단은 브라우저 정보(UA)로 합니다. 앱마다 표시가 달라 실제 기기에서 확인이 필요합니다.
 */
(function () {
  var ua = navigator.userAgent || '';
  var android = /Android/i.test(ua);
  var ios = /iPhone|iPad|iPod/i.test(ua);
  var NAMES = [
    [/KAKAOTALK/i, '카카오톡', 'kakao'],
    [/LinkedInApp/i, '링크드인', 'linkedin'],
    [/Instagram/i, '인스타그램', 'instagram'],
    [/FBAN|FBAV|FB_IAB|FBIOS/i, '페이스북', 'facebook'],
    [/NAVER\(inapp|NAVER\//i, '네이버', 'naver'],
    [/ Line\/|^Line\//i, '라인', 'line'],
    [/BAND\//i, '밴드', 'band'],
    [/DaumApps/i, '다음', 'daum'],
  ];
  var name = '', id = '';
  for (var i = 0; i < NAMES.length; i++) if (NAMES[i][0].test(ua)) { name = NAMES[i][1]; id = NAMES[i][2]; break; }
  var standalone = window.navigator.standalone === true ||
    (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches);
  // 이름이 없어도: 안드로이드 웹뷰(「; wv)」 표시), 아이폰에서 Safari 표시가 없는 화면(홈 화면 앱·크롬·파이어폭스·엣지 제외)
  var androidWV = android && /; wv\)/.test(ua);
  var iosWV = ios && !/Safari\//.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua) && !standalone;
  var inApp = !!name || androidWV || iosWV;
  if (!inApp) { window.SJInApp = { inApp: false }; return; }

  function chromeIntent(url) {
    var u = new URL(url, location.href);
    return 'intent://' + u.host + u.pathname + u.search + u.hash +
      '#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=' + encodeURIComponent(u.href) + ';end';
  }
  function kakaoExternal(url) { return 'kakaotalk://web/openExternal?url=' + encodeURIComponent(url); }

  /* 로그인 화면 위에 붙이는 안내 상자 */
  function banner() {
    var box = document.createElement('div');
    box.className = 'sj-inapp';
    var who = name ? name + ' 앱' : '앱';
    var h = document.createElement('p');
    h.className = 'sj-inapp-h';
    h.textContent = who + ' 안에서 열려 있어 로그인이 잘 안 될 수 있습니다.';
    box.appendChild(h);
    var p = document.createElement('p');
    p.className = 'sj-inapp-p';
    if (id === 'kakao') p.textContent = '휴대폰 브라우저로 옮겨 드리는 중입니다. 넘어가지 않으면 아래 버튼을 눌러 주세요.';
    else if (android) p.textContent = '아래 버튼을 누르면 크롬에서 같은 화면이 열립니다. 거기서 로그인해 주세요.';
    else p.textContent = '화면 위나 아래의 ⋯(또는 공유) 메뉴에서 「Safari로 열기」나 「브라우저에서 열기」를 눌러 주세요. 메뉴가 없으면 주소를 복사해 Safari에 붙여 넣으시면 됩니다.';
    box.appendChild(p);
    var row = document.createElement('div');
    row.className = 'sj-inapp-row';
    if (id === 'kakao') {
      var k = document.createElement('a');
      k.className = 'sj-inapp-btn'; k.href = kakaoExternal(location.href); k.textContent = '휴대폰 브라우저로 열기';
      row.appendChild(k);
    } else if (android) {
      var c = document.createElement('a');
      c.className = 'sj-inapp-btn'; c.href = chromeIntent(location.href); c.textContent = '크롬으로 열기';
      row.appendChild(c);
    }
    var cp = document.createElement('button');
    cp.type = 'button'; cp.className = 'sj-inapp-copy'; cp.textContent = '주소 복사';
    cp.addEventListener('click', function () {
      var done = function () { cp.textContent = '복사했습니다'; };
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(location.href).then(done, fallback);
        else fallback();
      } catch (e) { fallback(); }
      function fallback() {
        var t = document.createElement('textarea'); t.value = location.href; document.body.appendChild(t); t.select();
        try { document.execCommand('copy'); done(); } catch (e) { cp.textContent = location.href; }
        t.remove();
      }
    });
    row.appendChild(cp);
    box.appendChild(row);
    return box;
  }

  window.SJInApp = {
    inApp: true, name: name, id: id || (android ? 'android-webview' : ios ? 'ios-webview' : 'webview'),
    android: android, ios: ios, banner: banner,
    /* 카카오톡 안이면 자동으로 바깥 브라우저로 (로그인 화면에서 한 번만) */
    autoOpen: function () {
      if (id !== 'kakao') return;
      try { if (sessionStorage.getItem('sj_inapp_tried')) return; sessionStorage.setItem('sj_inapp_tried', '1'); } catch (e) { /* 무시 */ }
      location.href = kakaoExternal(location.href);
    },
  };
})();
