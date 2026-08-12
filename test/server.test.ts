import fs from 'fs';
import http from 'http';
import os from 'os';
import path from 'path';
import { once } from 'events';
import WebSocket from 'ws';
import {
  DEFAULT_PORT,
  RELOAD_PATH,
  RELOAD_MESSAGE,
  injectReloadScript,
  startDevServer,
} from '../src/server';
import { parseArgs } from '../src/cli';
import type { DevServer } from '../src/server';

const POST = `---
title: Live Post
date: 2024-05-10
---
# Live Post

Hello from the dev server.
`;

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-'));
}

function writeContent(dir: string, files: Record<string, string>): void {
  fs.mkdirSync(dir, { recursive: true });
  for (const [name, contents] of Object.entries(files)) {
    fs.writeFileSync(path.join(dir, name), contents, 'utf-8');
  }
}

function cleanup(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

function getUrl(dev: DevServer, p: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const req = http.get(
      { host: 'localhost', port: dev.port, path: p, method: 'GET' },
      (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () =>
          resolve({
            status: res.statusCode || 0,
            body: Buffer.concat(chunks).toString('utf-8'),
          }),
        );
      },
    );
    req.on('error', reject);
  });
}

function getFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = http.createServer();
    srv.listen(0, () => {
      const address = srv.address();
      if (address && typeof address === 'object') {
        const port = address.port;
        srv.close(() => resolve(port));
      } else {
        srv.close(() => reject(new Error('no port')));
      }
    });
  });
}

describe('injectReloadScript', () => {
  it('injects a WebSocket reload script before </body>', () => {
    const html = '<html><body><h1>hi</h1></body></html>';
    const out = injectReloadScript(html);
    expect(out).toContain('new WebSocket');
    expect(out).toContain('location.reload');
    expect(out.indexOf('new WebSocket')).toBeLessThan(out.indexOf('</body>'));
  });

  it('appends the script when there is no </body> tag', () => {
    const out = injectReloadScript('<p>no body tag</p>');
    expect(out).toContain('new WebSocket');
  });

  it('honours a custom websocket path', () => {
    const out = injectReloadScript('<html></body></html>', '/custom');
    expect(out).toContain('/custom');
  });
});

describe('startDevServer', () => {
  let root: string;
  let contentDir: string;
  let templatesDir: string;
  let outputDir: string;

  beforeEach(() => {
    root = makeTempDir();
    contentDir = path.join(root, 'content');
    templatesDir = path.join(root, 'templates');
    outputDir = path.join(root, 'dist');
  });

  afterEach(() => {
    cleanup(root);
  });

  it('builds the site and serves HTML pages with the reload script', async () => {
    writeContent(contentDir, { 'post.md': POST });
    const port = await getFreePort();
    const dev = startDevServer({ port, contentDir, outputDir, templatesDir });

    try {
      await once(dev.server, 'listening');

      const index = await getUrl(dev, '/');
      expect(index.status).toBe(200);
      expect(index.body).toContain('new WebSocket');
      expect(index.body).toContain('<title>All pages</title>');

      const page = await getUrl(dev, '/post.html');
      expect(page.status).toBe(200);
      expect(page.body).toContain('<h1>Live Post</h1>');
      expect(page.body).toContain(RELOAD_PATH);
    } finally {
      await dev.close();
    }
  });

  it('serves static assets from the output directory', async () => {
    writeContent(contentDir, { 'post.md': POST });
    fs.mkdirSync(outputDir, { recursive: true });
    fs.writeFileSync(path.join(outputDir, 'styles.css'), 'body { color: red }', 'utf-8');
    const port = await getFreePort();
    const dev = startDevServer({ port, contentDir, outputDir, templatesDir });

    try {
      await once(dev.server, 'listening');
      const css = await getUrl(dev, '/styles.css');
      expect(css.status).toBe(200);
      expect(css.body).toContain('color: red');
      expect(css.body).not.toContain('new WebSocket');
    } finally {
      await dev.close();
    }
  });

  it('returns 404 for missing files', async () => {
    writeContent(contentDir, { 'post.md': POST });
    const port = await getFreePort();
    const dev = startDevServer({ port, contentDir, outputDir, templatesDir });

    try {
      await once(dev.server, 'listening');
      const missing = await getUrl(dev, '/nope.html');
      expect(missing.status).toBe(404);
    } finally {
      await dev.close();
    }
  });

  it('rebuilds the site and broadcasts a reload message when content changes', async () => {
    writeContent(contentDir, { 'post.md': POST });
    const port = await getFreePort();
    const dev = startDevServer({ port, contentDir, outputDir, templatesDir });

    try {
      await once(dev.server, 'listening');

      const ws = new WebSocket(`ws://localhost:${port}${RELOAD_PATH}`);
      await once(ws, 'open');

      const reloaded = once(ws, 'message');

      const updated = `---
title: Updated Post
---
# Updated

Fresh content.
`;
      fs.writeFileSync(path.join(contentDir, 'post.md'), updated, 'utf-8');

      const [msg] = await reloaded;
      expect(String(msg)).toBe(RELOAD_MESSAGE);

      const page = await getUrl(dev, '/post.html');
      expect(page.body).toContain('<h1>Updated</h1>');
      expect(page.body).toContain('Fresh content.');

      ws.close();
    } finally {
      await dev.close();
    }
  });

  it('rebuilds when a template file changes', async () => {
    writeContent(contentDir, { 'post.md': POST });
    writeContent(templatesDir, { 'default.hbs': '<html><body class="v1">{{{body}}}</body></html>' });
    const port = await getFreePort();
    const dev = startDevServer({ port, contentDir, outputDir, templatesDir });

    try {
      await once(dev.server, 'listening');

      const before = await getUrl(dev, '/post.html');
      expect(before.body).toContain('class="v1"');

      writeContent(templatesDir, { 'default.hbs': '<html><body class="v2">{{{body}}}</body></html>' });

      await new Promise<void>((resolve) => setTimeout(resolve, 500));

      const after = await getUrl(dev, '/post.html');
      expect(after.body).toContain('class="v2"');
      expect(after.body).not.toContain('class="v1"');
    } finally {
      await dev.close();
    }
  });
});

describe('serve CLI', () => {
  it('uses port 3000 by default and parses --port', () => {
    expect(parseArgs(['serve']).port).toBe(DEFAULT_PORT);
    expect(parseArgs(['serve']).command).toBe('serve');
    expect(parseArgs(['serve', '--port', '4000']).port).toBe(4000);
    expect(parseArgs(['serve', '--port=5000']).port).toBe(5000);
  });
});
