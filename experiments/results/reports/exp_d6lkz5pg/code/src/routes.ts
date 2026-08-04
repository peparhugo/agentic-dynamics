import { Router, Request, Response } from "express";
import rateLimit from "express-rate-limit";
import { shorten } from "./shortener.js";
import { getByCode, recordClick, getClickCount, getClicksOverTime, getRecentClicks, getStats, deleteExpired } from "./db.js";

const router = Router();

const createLimit = rateLimit({
  windowMs: 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many requests. Try again in a minute." },
});

const analyticsLimit = rateLimit({
  windowMs: 60 * 1000,
  max: 30,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many requests. Try again in a minute." },
});

function isValidURL(str: string): boolean {
  try {
    const url = new URL(str);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

router.post("/api/shorten", createLimit, (req: Request, res: Response): void => {
  const { url, ttl } = req.body as { url?: string; ttl?: number };

  if (!url || typeof url !== "string") {
    res.status(400).json({ error: "Missing or invalid 'url' field" });
    return;
  }

  if (!isValidURL(url)) {
    res.status(400).json({ error: "URL must be a valid http or https URL" });
    return;
  }

  if (ttl !== undefined && (typeof ttl !== "number" || ttl <= 0 || !Number.isInteger(ttl))) {
    res.status(400).json({ error: "ttl must be a positive integer (seconds)" });
    return;
  }

  try {
    const code = shorten(url, ttl ?? null);
    res.status(201).json({ short_code: code, original_url: url, expires_in: ttl ?? null });
  } catch (err) {
    res.status(500).json({ error: "Failed to shorten URL" });
  }
});

router.get("/api/global-stats", analyticsLimit, (_req: Request, res: Response): void => {
  const stats = getStats();
  res.json(stats);
});

router.post("/api/cleanup", (_req: Request, res: Response): void => {
  const deleted = deleteExpired();
  res.json({ deleted_expired: deleted });
});

router.get("/api/:code/stats", analyticsLimit, (req: Request, res: Response): void => {
  const { code } = req.params;
  const record = getByCode(code);

  if (!record) {
    res.status(404).json({ error: "Short URL not found or expired" });
    return;
  }

  const dayParam = req.query.days as string | undefined;
  const days = dayParam ? parseInt(dayParam, 10) : 30;
  const clicksOverTime = getClicksOverTime(code, days);
  const recent = getRecentClicks(code, 20);

  res.json({
    short_code: code,
    original_url: record.original_url,
    created_at: new Date(record.created_at * 1000).toISOString(),
    expires_at: record.expires_at ? new Date(record.expires_at * 1000).toISOString() : null,
    total_clicks: getClickCount(code),
    clicks_over_time: clicksOverTime,
    recent_clicks: recent.map((c) => ({
      clicked_at: new Date(c.clicked_at * 1000).toISOString(),
      ip: c.ip,
      user_agent: c.user_agent,
      referer: c.referer,
    })),
  });
});

router.get("/:code", (req: Request, res: Response): void => {
  const { code } = req.params;

  const record = getByCode(code);
  if (!record) {
    res.status(404).json({ error: "Short URL not found or expired" });
    return;
  }

  const ip = req.ip ?? req.socket.remoteAddress ?? null;
  const userAgent = (req.headers["user-agent"] as string) ?? null;
  const referer = (req.headers["referer"] as string) ?? null;

  recordClick(code, ip, userAgent, referer);

  res.redirect(301, record.original_url);
});

export default router;
