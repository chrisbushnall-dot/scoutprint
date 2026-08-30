const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const login = require("../api/auth/login");
const session = require("../api/auth/session");
const proxy = require("../api/scoutprint");

process.env.SCOUTPRINT_LOGIN_PASSWORD = "test-password";
process.env.SCOUTPRINT_SESSION_SECRET = "test-session-secret-with-sufficient-entropy";
process.env.SCOUTPRINT_API_BASE_URL = "https://engine.example";
process.env.SCOUTPRINT_API_KEY = "test-api-key";

function response() {
  return {
    headers: {},
    statusCode: 200,
    setHeader(key, value) { this.headers[key] = value; },
    status(value) { this.statusCode = value; return this; },
    json(value) { this.body = value; return this; },
    send(value) { this.body = value; return this; },
  };
}

function authenticate() {
  const res = response();
  login({ method: "POST", body: { password: "test-password" }, headers: {} }, res);
  return res.headers["Set-Cookie"].split(";")[0];
}

test("login rejects invalid credentials", () => {
  const res = response();
  login({ method: "POST", body: { password: "wrong" }, headers: {} }, res);
  assert.equal(res.statusCode, 401);
});

test("login issues an HttpOnly session accepted by session endpoint", () => {
  const cookie = authenticate();
  const res = response();
  session({ method: "GET", headers: { cookie } }, res);
  assert.deepEqual(res.body, { authenticated: true });
  assert.match(cookie, /^scoutprint_session=/);
});

test("proxy rejects a request without a session", async () => {
  const res = response();
  await proxy({ method: "GET", query: { endpoint: "competitions" }, headers: {} }, res);
  assert.equal(res.statusCode, 401);
});

test("proxy allowlists the route and injects the VPS secret server-side", async () => {
  const cookie = authenticate();
  const originalFetch = global.fetch;
  global.fetch = async (url, options) => {
    assert.equal(String(url), "https://engine.example/players?name=Salah");
    assert.equal(options.headers["X-Scoutprint-API-Key"], "test-api-key");
    return new Response(JSON.stringify({ players: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  try {
    const res = response();
    await proxy({ method: "GET", query: { endpoint: "players", name: "Salah" }, headers: { cookie } }, res);
    assert.equal(res.statusCode, 200);
    assert.equal(res.body, '{"players":[]}');
  } finally {
    global.fetch = originalFetch;
  }
});

test("mobile results stay inside the viewport", () => {
  const styles = fs.readFileSync(path.join(__dirname, "../web/styles.css"), "utf8");
  assert.match(styles, /html\{[^}]*overflow-x:clip/);
  assert.match(styles, /\.shell\{[^}]*max-width:calc\(100vw - 20px\)/);
  assert.match(styles, /\.table-shell table\{[^}]*min-width:0[^}]*table-layout:fixed/);
  assert.match(styles, /\.table-shell th\{position:static/);
  assert.match(styles, /\.player-column\{min-width:0\}/);
});
