/*
 * 알림 전용 서비스 워커
 * =====================================================================
 * 하는 일은 딱 둘입니다. 알림이 오면 보여 주고, 알림을 누르면 해당 주소를 엽니다.
 *
 * 하지 않는 일: 페이지나 공고를 저장(캐시)하지 않습니다. fetch 처리도 없습니다.
 * 그래서 예전에 서비스 워커를 넣지 않았던 이유(폰에 옛 화면이 남아 마감된
 * 공고에 지원하는 일)와 부딪히지 않습니다. 이 파일에 fetch·caches 를 더하지 마세요.
 * 알림을 켠 사람의 브라우저에만 등록됩니다(public/member.js 의 enablePush).
 */
self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });

self.addEventListener('push', function (event) {
  var data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = {}; }
  var title = data.title || 'SEARCHJOB';
  event.waitUntil(self.registration.showNotification(title, {
    body: data.body || '새 소식이 있습니다.',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    data: { url: typeof data.url === 'string' && data.url.charAt(0) === '/' ? data.url : '/my/' },
  }));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || '/my/';
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i += 1) {
      var c = list[i];
      if (c.url.indexOf(self.location.origin) === 0 && 'focus' in c) {
        if ('navigate' in c) c.navigate(url);
        return c.focus();
      }
    }
    return self.clients.openWindow(url);
  }));
});
