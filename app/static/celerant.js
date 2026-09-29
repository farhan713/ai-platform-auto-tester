// Browser-side client for the Celerant SQL-Agent API.
//
// Activity Logs, SQL Dev and Training call {console}/sql_agent/... straight
// from the page, so DevTools shows the real Celerant URL, payload and
// response (and "Copy as cURL" reproduces the actual call). Celerant allows
// cross-origin calls, and no server-held secret is involved — the optional
// bearer token is typed into the page anyway.
//
// Mirrors celerant_call() in server.py, which Insights still uses:
//   - versioned prefix (sql_agent) with a fallback prefix on FastAPI's bare
//     route-404 ({"detail": "Not Found"});
//   - role segment (1 = admin, 2 = celerant) appended to role-scoped paths,
//     dropping back to the plain path on 404 and remembering that for 10 min;
//   - retries for gateway blips: 503 "no healthy upstream" for any method,
//     plus 502/503/504 and network errors for GETs.
// Config comes from window.CELERANT_CFG, rendered by base.html.
(function () {
  const CFG = window.CELERANT_CFG || {};
  const PREFIX = (CFG.prefix || 'sql_agent').replace(/^\/+|\/+$/g, '');
  const FALLBACK = (CFG.fallback_prefix || '').replace(/^\/+|\/+$/g, '');
  const ROLE_MODE = CFG.role_path_mode || 'auto';
  const ROLE_FLAG = CFG.role_flag || '2';
  const DEFAULT_CONSOLE = CFG.default_console || 'https://celerantai.com';
  const ROLE_RETRY_AFTER_MS = 10 * 60 * 1000;
  const ROLE_KEY = 'sqa.celerant.roleUnsupportedUntil:';
  const _roleMemo = {};

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  /** Console origin with any trailing /sql_agent or /sql_agent_v2 removed. */
  function origin(consoleUrl) {
    const base = String(consoleUrl || DEFAULT_CONSOLE).trim().replace(/\/+$/, '');
    for (const suffix of ['/sql_agent_v2', '/sql_agent']) {
      if (base.endsWith(suffix)) return base.slice(0, -suffix.length);
    }
    return base;
  }

  function _roleUntil(base) {
    try {
      const v = sessionStorage.getItem(ROLE_KEY + base);
      if (v) return Number(v) || 0;
    } catch (_) {}
    return _roleMemo[base] || 0;
  }

  function _markRoleUnsupported(base) {
    const until = Date.now() + ROLE_RETRY_AFTER_MS;
    _roleMemo[base] = until;
    try { sessionStorage.setItem(ROLE_KEY + base, String(until)); } catch (_) {}
  }

  function _rolePathSupported(base) {
    if (ROLE_MODE === 'off') return false;
    if (ROLE_MODE === 'force') return true;
    return Date.now() >= _roleUntil(base);
  }

  async function _fetchWithTimeout(url, init, timeoutMs) {
    if (!timeoutMs) return fetch(url, init);
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      return await fetch(url, { ...init, signal: ctrl.signal });
    } catch (e) {
      if (e.name === 'AbortError') throw new Error(`Timed out after ${Math.round(timeoutMs / 1000)}s`);
      throw e;
    } finally {
      clearTimeout(timer);
    }
  }

  async function _send(url, init, timeoutMs) {
    const isGet = init.method === 'GET';
    let resp;
    for (let attempt = 0; attempt < 3; attempt++) {
      const last = attempt === 2;
      try {
        resp = await _fetchWithTimeout(url, init, timeoutMs);
      } catch (e) {
        if (!isGet || last) throw e;
        await sleep(1500 * (attempt + 1));
        continue;
      }
      const gatewayDown = resp.status === 503
        && (await resp.clone().text().catch(() => '')).includes('no healthy upstream');
      const readRetry = isGet && [502, 503, 504].includes(resp.status);
      if (last || !(gatewayDown || readRetry)) return resp;
      await sleep(1500 * (attempt + 1));
    }
    return resp;
  }

  async function _isRouteNotFound(resp) {
    if (resp.status !== 404) return false;
    try {
      const b = await resp.clone().json();
      return b && typeof b === 'object' && Object.keys(b).length === 1 && b.detail === 'Not Found';
    } catch (_) {
      return false;
    }
  }

  /**
   * Call {console}/{prefix}/{path}. Options:
   *   console, token, params (query object), json (PATCH/POST body),
   *   body (FormData etc.), roleScoped, roleFlag, timeoutMs.
   * Resolves to {ok, status, url, body, ms}; body is parsed JSON when
   * possible, otherwise text. Rejects only on network failure / timeout.
   */
  async function call(method, path, opts = {}) {
    const base = origin(opts.console);
    const cleanPath = String(path).replace(/^\/+/, '');
    const q = opts.params ? new URLSearchParams(opts.params).toString() : '';
    const qs = q ? '?' + q : '';
    const headers = {};
    if (opts.token) headers.Authorization = 'Bearer ' + opts.token;
    let body;
    if (opts.json !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(opts.json);
    } else if (opts.body !== undefined) {
      body = opts.body;
    }
    const init = { method: method.toUpperCase(), headers, body, credentials: 'omit' };
    const started = performance.now();

    let url;
    let resp;
    if (opts.roleScoped && _rolePathSupported(base)) {
      url = `${base}/${PREFIX}/${cleanPath.replace(/\/+$/, '')}/${opts.roleFlag || ROLE_FLAG}/${qs}`;
      resp = await _send(url, init, opts.timeoutMs);
      if (resp.status === 404) {
        if (ROLE_MODE !== 'force') _markRoleUnsupported(base);
        resp = null;
      }
    }
    if (!resp) {
      url = `${base}/${PREFIX}/${cleanPath}${qs}`;
      resp = await _send(url, init, opts.timeoutMs);
      if (FALLBACK && FALLBACK !== PREFIX && await _isRouteNotFound(resp)) {
        url = `${base}/${FALLBACK}/${cleanPath}${qs}`;
        resp = await _send(url, init, opts.timeoutMs);
      }
    }

    const text = await resp.text();
    let parsed = text;
    try { parsed = text ? JSON.parse(text) : null; } catch (_) {}
    return { ok: resp.ok, status: resp.status, url, body: parsed,
             ms: Math.round(performance.now() - started) };
  }

  /** responseHeader.message from a wrapped Celerant body, else a fallback. */
  function errorMessage(res) {
    const b = res && res.body;
    if (b && typeof b === 'object') {
      const m = b.responseHeader && b.responseHeader.message;
      if (m) return String(m);
      if (b.detail) return typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail);
    } else if (b) {
      return String(b).slice(0, 200);
    }
    return `HTTP ${res ? res.status : '—'}`;
  }

  /** Normalize an all_orgs record (new {org_id, org_name} or old {database_id, name} shape). */
  function normalizeOrg(o) {
    if (!o || typeof o !== 'object') return null;
    const s = v => String(v == null ? '' : v).trim();
    const histId = s(o.org_id) || s(o.database_id);
    const name = s(o.org_name) || s(o.name);
    const orgUuid = s(o.organization_id) || s(o.org_id);
    if (!histId && !name) return null;
    return { id: histId || orgUuid, name: name || histId,
             industry: s(o.industry_type), organization_id: orgUuid };
  }

  /** GET all_orgs/ (role-scoped) → name-sorted [{id, name, industry, organization_id}]. */
  async function orgs(consoleUrl, token) {
    const res = await call('GET', 'all_orgs/', { console: consoleUrl, token, roleScoped: true, timeoutMs: 30000 });
    if (!res.ok) throw new Error(errorMessage(res));
    const raw = (((res.body || {}).responseBody || {}).data) || [];
    return raw.map(normalizeOrg).filter(o => o && o.id)
      .sort((a, b) => (a.name || '').toLowerCase().localeCompare((b.name || '').toLowerCase()));
  }

  /** "2026-09-29" → "09-29-2026" (the date format history/feedback endpoints take). */
  function toMmDdYyyy(iso) {
    const s = String(iso || '').trim();
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
    if (m) return `${m[2]}-${m[3]}-${m[1]}`;
    return /^\d{2}-\d{2}-\d{4}$/.test(s) ? s : '';
  }

  window.Celerant = { call, orgs, origin, errorMessage, normalizeOrg, toMmDdYyyy };
})();
