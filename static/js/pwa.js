'use strict';

(() => {
  const DB_NAME = 'ownbasket-pwa';
  const STORE_NAME = 'pending-mutations';
  const META_STORE = 'sync-metadata';
  const CONFLICT_STORE = 'sync-conflicts';
  const ALLOWED = new Set(['cart:add', 'cart:update', 'cart:remove', 'wishlist:add', 'wishlist:remove']);
  let installPrompt = null;

  function cookie(name) {
    return document.cookie.split(';').map((item) => item.trim()).find((item) => item.startsWith(`${name}=`))?.split('=').slice(1).join('=') || '';
  }

  function openDb() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, 3);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(STORE_NAME)) request.result.createObjectStore(STORE_NAME, {keyPath: 'id', autoIncrement: true});
        if (!request.result.objectStoreNames.contains(META_STORE)) request.result.createObjectStore(META_STORE);
        if (!request.result.objectStoreNames.contains(CONFLICT_STORE)) request.result.createObjectStore(CONFLICT_STORE, {keyPath: 'clientActionId'});
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function storeMutation(operation, payload) {
    if (!ALLOWED.has(operation)) throw new Error('Unsupported offline mutation');
    const allowedFields = {
      'cart:add': ['productId', 'quantity', 'size', 'color'], 'cart:update': ['itemId', 'quantity'],
      'cart:remove': ['itemId'], 'wishlist:add': ['productId'], 'wishlist:remove': ['productId']
    }[operation];
    const sanitized = {};
    for (const field of allowedFields) if (payload?.[field] !== undefined) sanitized[field] = payload[field];
    if (!Object.keys(sanitized).length) throw new Error('Offline mutation payload is empty');
    const actionId = self.crypto?.randomUUID?.() || `action-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const db = await openDb();
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      transaction.objectStore(STORE_NAME).add({
        operation, payload: sanitized, clientActionId: actionId,
        createdAt: Date.now(), attemptCount: 0, nextAttemptAt: 0
      });
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
    const registration = await navigator.serviceWorker?.ready;
    if (registration?.sync) await registration.sync.register('ownbasket-pending-sync');
  }

  async function meta(db, key, value) {
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(META_STORE, value === undefined ? 'readonly' : 'readwrite');
      const request = value === undefined ? transaction.objectStore(META_STORE).get(key) : transaction.objectStore(META_STORE).put(value, key);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function removeItems(db, ids) {
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      for (const id of ids) transaction.objectStore(STORE_NAME).delete(id);
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
  }

  async function deferItems(db, items) {
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      for (const item of items) {
        item.attemptCount = Math.min((item.attemptCount || 0) + 1, 10);
        item.nextAttemptAt = Date.now() + Math.min(60000, (2 ** item.attemptCount) * 1000);
        transaction.objectStore(STORE_NAME).put(item);
      }
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
  }

  async function storeConflicts(db, conflicts) {
    if (!conflicts.length) return;
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(CONFLICT_STORE, 'readwrite');
      for (const conflict of conflicts) transaction.objectStore(CONFLICT_STORE).put(conflict);
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
  }

  async function surfaceStoredConflicts() {
    const db = await openDb();
    const conflicts = await new Promise((resolve, reject) => {
      const transaction = db.transaction(CONFLICT_STORE, 'readwrite');
      const request = transaction.objectStore(CONFLICT_STORE).getAll();
      request.onsuccess = () => {
        for (const item of request.result) transaction.objectStore(CONFLICT_STORE).delete(item.clientActionId);
        resolve(request.result);
      };
      request.onerror = () => reject(request.error);
    });
    if (conflicts.length) window.dispatchEvent(new CustomEvent('ownbasket:sync-conflict', {detail: conflicts}));
  }

  async function flushPending() {
    if (!navigator.onLine || !document.cookie.includes('sessionid=')) return;
    const db = await openDb();
    const allItems = await new Promise((resolve, reject) => {
      const request = db.transaction(STORE_NAME).objectStore(STORE_NAME).getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const items = allItems.filter((item) => (item.nextAttemptAt || 0) <= Date.now()).slice(0, 20);
    if (!items.length) return;
    let baseVersion = await meta(db, 'serverVersion');
    if (baseVersion === undefined) {
      const capabilities = await fetch('/api/v2/sync/capabilities/', {credentials: 'same-origin', cache: 'no-store'});
      if (!capabilities.ok) return;
      baseVersion = Number((await capabilities.json()).serverVersion || 0);
      await meta(db, 'serverVersion', baseVersion);
    }
    const response = await fetch('/api/v2/sync/batches/', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(cookie('csrftoken'))},
        body: JSON.stringify({
          baseVersion,
          actions: items.map(({clientActionId, operation, payload}) => ({clientActionId, operation, payload}))
        })
    });
    if (response.ok) {
      const result = await response.json();
      await meta(db, 'serverVersion', result.serverVersion);
      await removeItems(db, items.map((item) => item.id));
      const conflicts = result.results.filter((item) => item.status !== 'applied');
      await storeConflicts(db, conflicts);
      if (conflicts.length) window.dispatchEvent(new CustomEvent('ownbasket:sync-conflict', {detail: conflicts}));
    } else if (response.status === 409) {
      await deferItems(db, items);
      window.dispatchEvent(new CustomEvent('ownbasket:sync-conflict', {detail: await response.json().catch(() => ({}))}));
    } else if (response.status === 429 || response.status >= 500) {
      await deferItems(db, items);
    } else {
      await removeItems(db, items.map((item) => item.id));
      window.dispatchEvent(new CustomEvent('ownbasket:sync-rejected', {detail: {status: response.status}}));
    }
    if (allItems.length > items.length && navigator.onLine) {
      const registration = await navigator.serviceWorker?.ready;
      if (registration?.sync) {
        await registration.sync.register('ownbasket-pending-sync');
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
    surfaceStoredConflicts().catch(() => {});
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
