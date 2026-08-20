
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(clients.claim()));
self.addEventListener('push', e => {
  let data = { title: 'ClassMate', body: 'Новое уведомление' };
  try { data = e.data ? e.data.json() : data; } catch(x) {}
  e.waitUntil(self.registration.showNotification(data.title || 'ClassMate', {
    body: data.body || '',
    icon: '/static/images/favicon.svg',
    badge: '/static/images/favicon.svg'
  }));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.openWindow('/'));
});
