const { constantTimeEqual, sessionCookie } = require("../_auth");

module.exports = function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });
  const expected = process.env.SCOUTPRINT_LOGIN_PASSWORD || "";
  const supplied = typeof req.body?.password === "string" ? req.body.password : "";
  if (!expected || !supplied || !constantTimeEqual(supplied, expected)) {
    return res.status(401).json({ error: "Invalid credentials" });
  }
  res.setHeader("Set-Cookie", sessionCookie());
  return res.status(200).json({ authenticated: true });
};
