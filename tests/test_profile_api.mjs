import assert from 'node:assert/strict';
import { test } from 'node:test';
import { profileJson, saveProfileRequest } from '../src/profileApi.js';

function response(status, contentType, data) {
  return {
    status,
    ok: status >= 200 && status < 300,
    redirected: false,
    headers: { get: () => contentType },
    json: async () => data,
  };
}

test('valid authenticated save sends JSON and accepts saved profile', async () => {
  let calls = 0;
  const profile = { name: 'Pessoa Teste', experience: [{ role: 'Dev', company: 'Empresa' }] };
  const saved = await saveProfileRequest(profile, async (url, options) => {
    calls++;
    assert.equal(url, '/api/profile');
    assert.equal(options.method, 'PUT');
    assert.equal(options.credentials, 'same-origin');
    assert.deepEqual(JSON.parse(options.body), { profile });
    return response(200, 'application/json; charset=utf-8', { saved: true, profile });
  });
  assert.equal(calls, 1);
  assert.equal(saved.saved, true);
});

test('transient HTML page retries PUT exactly once and never treats HTML as saved', async () => {
  let calls = 0;
  const saved = await saveProfileRequest({ name: 'Pessoa Teste' }, async () => {
    calls++;
    return calls === 1
      ? response(502, 'text/html', undefined)
      : response(200, 'application/json', { saved: true, profile: { name: 'Pessoa Teste' } });
  });
  assert.equal(calls, 2);
  assert.equal(saved.saved, true);
});

test('persistent HTML fails with helpful error after one retry', async () => {
  let calls = 0;
  await assert.rejects(() => saveProfileRequest({}, async () => {
    calls++;
    return response(200, 'text/html', undefined);
  }), /servidor retornou uma página em vez de JSON/);
  assert.equal(calls, 2);
});

test('authentication or validation errors are not retried', async () => {
  let calls = 0;
  await assert.rejects(() => saveProfileRequest({}, async () => {
    calls++;
    return response(401, 'application/json', { detail: 'Acesso não autorizado' });
  }), /sessão expirou/);
  assert.equal(calls, 1);
});

test('bad PDF response does not generate raw unexpected-token error', async () => {
  await assert.rejects(() => profileJson(response(200, 'text/html'), 'ler o PDF'),
    /servidor retornou uma página em vez de JSON/);
});
