const { hasValidSession } = require("./_auth");

const GET_ENDPOINTS = [
  /^competitions$/,
  /^seasons$/,
  /^recent\/catalogue$/,
  /^intelligence\/catalogue$/,
  /^radar$/,
  /^league$/,
  /^team$/,
  /^matches$/,
  /^matches\/[A-Za-z0-9_-]+$/,
  /^players$/,
  /^recruitment\/roles$/,
  /^player\/[A-Za-z0-9._:%-]+\/profile$/,
  /^player\/[A-Za-z0-9._:%-]+\/intelligence$/,
];
const POST_ENDPOINTS = [/^search\/similar$/, /^comparison$/];

function allowed(endpoint, method) {
  const patterns = method === "GET" ? GET_ENDPOINTS : method === "POST" ? POST_ENDPOINTS : [];
  return patterns.some((pattern) => pattern.test(endpoint));
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (!hasValidSession(req)) return res.status(401).json({ error: "Authentication required" });

  const endpoint = typeof req.query.endpoint === "string" ? req.query.endpoint : "";
  if (!allowed(endpoint, req.method)) return res.status(400).json({ error: "Unsupported endpoint" });

  const baseUrl = process.env.SCOUTPRINT_API_BASE_URL;
  const apiKey = process.env.SCOUTPRINT_API_KEY;
  if (!baseUrl || !apiKey) return res.status(503).json({ error: "Scoutprint proxy is not configured" });

  const target = new URL(endpoint, `${baseUrl.replace(/\/$/, "")}/`);
  for (const [key, value] of Object.entries(req.query)) {
    if (key === "endpoint") continue;
    for (const item of Array.isArray(value) ? value : [value]) target.searchParams.append(key, item);
  }

  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Scoutprint-API-Key": apiKey,
      },
      body: req.method === "POST" ? JSON.stringify(req.body || {}) : undefined,
      signal: AbortSignal.timeout(65000),
    });
    const body = await upstream.text();
    res.status(upstream.status);
    res.setHeader("Content-Type", upstream.headers.get("content-type") || "application/json");
    return res.send(body);
  } catch (_error) {
    return res.status(502).json({ error: "Exact Scoutprint engine is temporarily unreachable" });
  }
};
