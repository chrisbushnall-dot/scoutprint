const { expiredCookie } = require("../_auth");

module.exports = function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });
  res.setHeader("Set-Cookie", expiredCookie());
  return res.status(200).json({ authenticated: false });
};
