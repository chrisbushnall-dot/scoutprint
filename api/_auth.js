const crypto = require("node:crypto");

const COOKIE_NAME = "scoutprint_session";
const SESSION_SECONDS = 12 * 60 * 60;

function digest(value) {
  return crypto.createHash("sha256").update(String(value)).digest();
}

function constantTimeEqual(left, right) {
  return crypto.timingSafeEqual(digest(left), digest(right));
}

function signature(expires) {
  const secret = process.env.SCOUTPRINT_SESSION_SECRET || "";
  return crypto.createHmac("sha256", secret).update(String(expires)).digest("hex");
}

function parseCookies(header = "") {
  return Object.fromEntries(
    header
      .split(";")
      .map((part) => part.trim().split("="))
      .filter(([key, value]) => key && value)
      .map(([key, ...value]) => [key, decodeURIComponent(value.join("="))]),
  );
}

function hasValidSession(req) {
  if (!process.env.SCOUTPRINT_SESSION_SECRET) return false;
  const token = parseCookies(req.headers.cookie)[COOKIE_NAME];
  if (!token) return false;
  const [expiresRaw, supplied] = token.split(".");
  const expires = Number(expiresRaw);
  if (!Number.isFinite(expires) || expires <= Math.floor(Date.now() / 1000) || !supplied) {
    return false;
  }
  return constantTimeEqual(supplied, signature(expiresRaw));
}

function sessionCookie() {
  const expires = Math.floor(Date.now() / 1000) + SESSION_SECONDS;
  return `${COOKIE_NAME}=${expires}.${signature(expires)}; Path=/; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=Strict`;
}

function expiredCookie() {
  return `${COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict`;
}

module.exports = {
  constantTimeEqual,
  expiredCookie,
  hasValidSession,
  sessionCookie,
};
