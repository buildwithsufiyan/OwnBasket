{% load static %}
'use strict';

const VERSION = 'ownbasket-pwa-v2';
const SHELL_CACHE = `${VERSION}-shell`;
const ASSET_CACHE = `${VERSION}-assets`;
const PAGE_CACHE = `${VERSION}-pages`;
const OFFLINE_URL = '/offline/';
const APP_SHELL = [
  OFFLINE_URL,
  '/manifest.json',
  '{% static "css/production-foundation.css" %}',
  '{% static "css/pwa.css" %}',
  '{% static "js/pwa.js" %}',
  '{% static "images/pwa/icon-192.png" %}',
  '{% static "images/pwa/icon-512.png" %}',
  '{% static "images/pwa/icon-maskable-512.png" %}'
];

const PRIVATE_PREFIXES = [
  '/api/', '/admin/', '/account/', '/checkout/', '/cart/', '/wishlist/',
  '/my-orders/', '/invoice/', '/security/', '/marketplace/seller/',
  '/media/marketplace/seller-documents/'
];
const PUBLIC_MEDIA_PREFIXES = [
  '/media/products/', '/media/categories/', '/media/subcategories/', '/media/brands/',
  '/media/homepage/', '/media/banners/', '/media/sliders/', '/media/hero_banners/',
  '/media/home_brands/', '/media/home_categories/', '/media/promo_banners/',
  '/media/marketplace/store-logos/', '/media/marketplace/store-banners/'
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith('ownbasket-pwa-') && !key.startsWith(VERSION)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

function isPrivate(url) {
  return PRIVATE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
}

function isPublicPage(url) {
  return url.pathname === '/' || url.pathname === '/home/' || url.pathname.startsWith('/shop/') ||
    url.pathname.startsWith('/product/') || url.pathname.startsWith('/brand/') ||
    url.pathname.startsWith('/category/') || url.pathname.startsWith('/marketplace/store/');
}

async function trimCache(name, maximum) {
  const cache = await caches.open(name);
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - maximum)).map((key) => cache.delete(key)));
}

async function networkFirstPage(request) {
  const url = new URL(request.url);
  try {
    const response = await fetch(request);
    if (response.ok && isPublicPage(url) && response.headers.get('X-PWA-Cacheable') === 'public') {
      const cache = await caches.open(PAGE_CACHE);
      await cache.put(request, response.clone());
      await trimCache(PAGE_CACHE, 20);
    }
    return response;
  } catch (error) {
    return (isPublicPage(url) && await caches.match(request)) || await caches.match(OFFLINE_URL);
  }
}

async function cacheFirstAsset(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok && response.type === 'basic' && !response.headers.get('Cache-Control')?.includes('no-store')) {
    const cache = await caches.open(ASSET_CACHE);
    await cache.put(request, response.clone());
    await trimCache(ASSET_CACHE, 80);
  }
  return response;
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (isPrivate(url)) {
    event.respondWith(fetch(request));
    return;
  }
  if (request.mode === 'navigate') {
    event.respondWith(networkFirstPage(request));
    return;
  }
  if (url.pathname.startsWith('/static/') || PUBLIC_MEDIA_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    event.respondWith(cacheFirstAsset(request));
  }
});

self.addEventListener('sync', (event) => {
  if (event.tag !== 'ownbasket-pending-sync') return;
  event.waitUntil(flushPendingInWorker());
});

const SYNC_DB = 'ownbasket-pwa';
const MUTATION_STORE = 'pending-mutations';
const SYNC_META_STORE = 'sync-metadata';
const SYNC_CONFLICT_STORE = 'sync-conflicts';

function openSyncDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(SYNC_DB, 3);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(MUTATION_STORE)) request.result.createObjectStore(MUTATION_STORE, {keyPath: 'id', autoIncrement: true});
      if (!request.result.objectStoreNames.contains(SYNC_META_STORE)) request.result.createObjectStore(SYNC_META_STORE);
      if (!request.result.objectStoreNames.contains(SYNC_CONFLICT_STORE)) request.result.createObjectStore(SYNC_CONFLICT_STORE, {keyPath: 'clientActionId'});
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function dbRequest(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function flushPendingInWorker() {
  const db = await openSyncDb();
  const items = (await dbRequest(db.transaction(MUTATION_STORE).objectStore(MUTATION_STORE).getAll()))
    .filter((item) => (item.nextAttemptAt || 0) <= Date.now()).slice(0, 20);
  if (!items.length) return;
  const sessionResponse = await fetch('/api/v2/auth/session/', {credentials: 'same-origin', cache: 'no-store'});
  if (!sessionResponse.ok) return;
  const session = await sessionResponse.json();
  if (!session.authenticated || !session.csrfToken) return;
  let baseVersion = await dbRequest(db.transaction(SYNC_META_STORE).objectStore(SYNC_META_STORE).get('serverVersion'));
  if (baseVersion === undefined) {
    const capabilities = await fetch('/api/v2/sync/capabilities/', {credentials: 'same-origin', cache: 'no-store'});
    if (!capabilities.ok) return;
    baseVersion = Number((await capabilities.json()).serverVersion || 0);
  }
  const response = await fetch('/api/v2/sync/batches/', {
    method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': session.csrfToken},
    body: JSON.stringify({
      baseVersion,
      actions: items.map(({clientActionId, operation, payload}) => ({clientActionId, operation, payload}))
    })
  });
  if (response.ok) {
    const result = await response.json();
    await new Promise((resolve, reject) => {
      const stores = [MUTATION_STORE, SYNC_META_STORE, SYNC_CONFLICT_STORE];
      const transaction = db.transaction(stores, 'readwrite');
      for (const item of items) transaction.objectStore(MUTATION_STORE).delete(item.id);
      transaction.objectStore(SYNC_META_STORE).put(result.serverVersion, 'serverVersion');
      for (const conflict of result.results.filter((item) => item.status !== 'applied')) {
        transaction.objectStore(SYNC_CONFLICT_STORE).put(conflict);
      }
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
    const clients = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
    clients.forEach((client) => client.postMessage({type: 'OWNBASKET_SYNC_COMPLETE'}));
    return;
  }
  if (response.status === 429 || response.status >= 500) {
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(MUTATION_STORE, 'readwrite');
      for (const item of items) {
        item.attemptCount = Math.min((item.attemptCount || 0) + 1, 10);
        item.nextAttemptAt = Date.now() + Math.min(60000, (2 ** item.attemptCount) * 1000);
        transaction.objectStore(MUTATION_STORE).put(item);
      }
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
    throw new Error('Retryable OwnBasket sync failure');
  }
  const clients = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
  clients.forEach((client) => client.postMessage({type: 'OWNBASKET_FLUSH_PENDING'}));
}

self.addEventListener('push', (event) => {
  if (!event.data) return;
  let payload;
  try { payload = event.data.json(); } catch (error) { return; }
  const title = String(payload.title || 'OwnBasket').slice(0, 80);
  const options = {
    body: String(payload.body || '').slice(0, 240),
    icon: '{% static "images/pwa/icon-192.png" %}',
    badge: '{% static "images/pwa/icon-192.png" %}',
    data: {url: String(payload.url || '/home/')}
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || '/home/', self.location.origin);
  if (target.origin !== self.location.origin) return;
  event.waitUntil(self.clients.openWindow(target.href));
});
