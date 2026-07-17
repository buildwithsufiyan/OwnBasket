'use strict';

(() => {
  const DB_NAME = 'ownbasket-pwa';
  const STORE_NAME = 'pending-mutations';
  const ALLOWED = new Set(['cart:add', 'cart:update', 'cart:remove', 'wishlist:add', 'wishlist:remove']);
  let installPrompt = null;

  function cookie(name) {
    return document.cookie.split(';').map((item) => item.trim()).find((item) => item.startsWith(`${name}=`))?.split('=').slice(1).join('=') || '';
  }

  function openDb() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => request.result.createObjectStore(STORE_NAME, {keyPath: 'id', autoIncrement: true});
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function storeMutation(operation, payload) {
    if (!ALLOWED.has(operation)) throw new Error('Unsupported offline mutation');
    const db = await openDb();
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      transaction.objectStore(STORE_NAME).add({operation, payload, createdAt: Date.now()});
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
    const registration = await navigator.serviceWorker?.ready;
    if (registration?.sync) await registration.sync.register('ownbasket-pending-sync');
  }

  function requestFor(item) {
    const id = Number(item.payload?.id || item.payload?.productId);
    const routes = {
      'cart:add': ['/api/v2/cart/items/', 'POST', item.payload],
      'cart:update': [`/api/v2/cart/items/${id}/`, 'PATCH', {quantity: item.payload.quantity}],
      'cart:remove': [`/api/v2/cart/items/${id}/`, 'DELETE', null],
      'wishlist:add': ['/api/v2/wishlist/', 'POST', {productId: id}],
      'wishlist:remove': [`/api/v2/wishlist/${id}/`, 'DELETE', null]
    };
    return routes[item.operation];
  }

  async function flushPending() {
    if (!navigator.onLine || !document.cookie.includes('sessionid=')) return;
    const db = await openDb();
    const items = await new Promise((resolve, reject) => {
      const request = db.transaction(STORE_NAME).objectStore(STORE_NAME).getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    for (const item of items) {
      const [url, method, body] = requestFor(item) || [];
      if (!url) continue;
      const response = await fetch(url, {
        method, credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(cookie('csrftoken'))},
        body: body ? JSON.stringify(body) : null
      });
      if (response.ok || (response.status >= 400 && response.status < 500 && response.status !== 429)) {
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        transaction.objectStore(STORE_NAME).delete(item.id);
      } else if (response.status >= 500 || response.status === 429) {
        break;
      }
    }
  }

  function updateNetworkStatus() {
    const status = document.getElementById('pwa-network-status');
    if (!status) return;
    status.hidden = navigator.onLine;
    status.textContent = navigator.onLine ? '' : 'You are offline. Account, cart and checkout data will not be cached.';
  }

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    installPrompt = event;
    const button = document.getElementById('pwa-install');
    if (button) button.hidden = false;
  });

  document.addEventListener('DOMContentLoaded', () => {
    const button = document.getElementById('pwa-install');
    button?.addEventListener('click', async () => {
      if (!installPrompt) return;
      await installPrompt.prompt();
      installPrompt = null;
      button.hidden = true;
    });
    updateNetworkStatus();
    flushPending().catch(() => {});
  });

  window.addEventListener('online', () => { updateNetworkStatus(); flushPending().catch(() => {}); });
  window.addEventListener('offline', updateNetworkStatus);
  navigator.serviceWorker?.addEventListener('message', (event) => {
    if (event.data?.type === 'OWNBASKET_FLUSH_PENDING') flushPending().catch(() => {});
  });

  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/service-worker.js', {scope: '/'}).catch(() => {}));
  }

  window.OwnBasketPWA = {
    queueMutation: storeMutation,
    flushPending,
    requestNotificationPermission: () => {
      if (!('Notification' in window)) return Promise.resolve('unsupported');
      return Notification.requestPermission();
    }
  };
})();
