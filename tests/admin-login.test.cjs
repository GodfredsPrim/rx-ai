const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function setup(role) {
  const elements = Object.fromEntries(['login-pass', 'login-err', 'btn-do-login', 'login-modal'].map(id => [id, { value: 'test-code', style: { display: 'flex' } }]));
  const storage = new Map();
  const requests = [];
  const events = [];
  const context = vm.createContext({
    window: { BISARX_PORTAL: 'admin', BisaRxUI: { escapeHtml: s => s }, addEventListener() {} },
    document: { body: {}, getElementById: id => elements[id] || null, addEventListener() {}, querySelectorAll: () => [] },
    localStorage: { getItem: k => storage.get(k), setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
    URLSearchParams, Map, Set, console,
    fetch: async (url, options) => {
      requests.push({ url, options });
      return { ok: true, json: async () => url.endsWith('/session') ? { role } : { access_token: 'test-token' } };
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/js/app.js'), 'utf8'), context);
  context.events = events;
  vm.runInContext(`showToast = message => events.push(message);
    initApp = async session => { if (session.role !== 'admin') throw Error('Wrong role'); events.push('dashboard'); };`, context);
  return { context, elements, requests, storage, events };
}

test('admin sign-in verifies a fresh session before opening dashboard and announcing success', async () => {
  const state = setup('admin');
  await vm.runInContext('doLogin()', state.context);
  assert.deepEqual(state.events, ['dashboard', 'Welcome back!']);
  assert.equal(state.elements['login-modal'].style.display, 'none');
  assert.equal(state.requests.length, 2);
  assert.equal(state.requests[1].options.headers.Authorization, 'Bearer test-token');
  assert.ok(state.requests.every(r => r.options.cache === 'no-store'));
});

test('unverified session keeps sign-in visible and never announces success', async () => {
  const state = setup('guest');
  await vm.runInContext('doLogin()', state.context);
  assert.deepEqual(state.events, []);
  assert.equal(state.elements['login-modal'].style.display, 'flex');
  assert.match(state.elements['login-err'].innerHTML, /could not be verified/);
  assert.equal(state.storage.has('token'), false);
  assert.equal(state.elements['btn-do-login'].disabled, false);
});
