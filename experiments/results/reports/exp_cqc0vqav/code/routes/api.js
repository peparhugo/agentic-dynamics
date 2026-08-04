const { Router } = require('express');
const { nanoid } = require('nanoid');
const {
  insertUrl,
  findByCode,
  incrementHits,
  insertClick,
  getAllUrls,
  getStats,
} = require('../db');
const { shortenLimiter, apiLimiter } = require('../middleware/rateLimiter');

const router = Router();

const BASE62 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
const CODE_LENGTH = 7;

function generateCode() {
  return nanoid(CODE_LENGTH, BASE62);
}

function isValidURL(str) {
  try {
    const url = new URL(str);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

router.post('/api/shorten', shortenLimiter, (req, res) => {
  const { url } = req.body;

  if (!url || typeof url !== 'string') {
    return res.status(400).json({ error: 'Missing or invalid "url" field.' });
  }

  const trimmed = url.trim();
  if (!isValidURL(trimmed)) {
    return res.status(400).json({ error: 'Invalid URL. Must include http:// or https://.' });
  }

  for (let attempt = 0; attempt < 3; attempt++) {
    const code = generateCode();
    try {
      insertUrl.run(code, trimmed);
      return res.status(201).json({ code, short: `/${code}`, target: trimmed });
    } catch (err) {
      if (err.code === 'SQLITE_CONSTRAINT_PRIMARYKEY') continue;
      throw err;
    }
  }

  res.status(500).json({ error: 'Failed to generate unique code. Try again.' });
});

router.get('/api/urls', apiLimiter, (req, res) => {
  const urls = getAllUrls.all();
  res.json(urls);
});

router.get('/api/stats/:code', apiLimiter, (req, res) => {
  const stats = getStats.get(req.params.code);
  if (!stats) return res.status(404).json({ error: 'Code not found.' });
  res.json(stats);
});

router.get('/:code', (req, res) => {
  const { code } = req.params;

  if (code.length !== CODE_LENGTH || !/^[0-9A-Za-z]+$/.test(code)) {
    return res.status(404).json({ error: 'Invalid short code.' });
  }

  const entry = findByCode.get(code);
  if (!entry) return res.status(404).json({ error: 'URL not found.' });

  incrementHits.run(code);
  insertClick.run(code, req.ip, req.get('Referer') || null, req.get('User-Agent') || null);

  res.redirect(301, entry.target);
});

module.exports = router;
