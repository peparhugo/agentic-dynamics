import { describe, expect, it, beforeAll, afterAll } from 'vitest';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import WebSocket from 'ws';
import { injectReloadScript, startDevServer, type DevServer } from '../src/server.js';
import type { SiteConfig } from '../src/types.js';

describe('injectReloadScript', () => {
  it('injects before </body>', () => {
    const out = injectReloadScript('<html><body><p>x</p></body></html>', 3000);
    expect(out).toMatch(/<p>x<\/p><script>[\s\S]*WebSocket[\s\S]*<\/script><\/body>/);
  });

  it('appends when </body> is missing', () => {
    const out = injectReloadScript('<p>bare</p>', 3000);
    expect(out.startsWith('<p>bare</p>')).toBe(true);
    expect(out).toContain('WebSocket');
  });
});

describe('dev server (integration)', () => {
  const PORT = 4373;
  let server: DevServer;
  let config: SiteConfig;
  let root: string;

  beforeAll(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'sprout-dev-'));
    const sourceDir = path.join(root, 'content');
    const templateDir = path.join(root, 'templates', 'layouts');
    await fs.mkdir(sourceDir, { recursive: true });
    await fs.mkdir(templateDir, { recursive: true });
    await fs.writeFile(path.join(sourceDir, 'index.md'), '---\ntitle: Dev\n---\nLive!');
    await fs.writeFile(path.join(templateDir, 'default.hbs'), '<body>{{{content}}}</body>');
    config = {
      sourceDir,
      templateDir: path.join(root, 'templates'),
      outDir: path.join(root, 'out'),
      baseUrl: 'http://localhost',
      title: 'Dev',
      description: '',
      includeDrafts: false,
    };
    server = await startDevServer(config, PORT, () => {});
  }, 15000);

  afterAll(async () => {
    await server?.close();
    await fs.rm(root, { recursive: true, force: true });
  });

  it('serves built HTML with the reload script injected', async () => {
    const res = await fetch(`http://localhost:${PORT}/`);
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain('text/html');
    const html = await res.text();
    expect(html).toContain('Live!');
    expect(html).toContain('WebSocket');
  });

  it('returns 404 for missing paths', async () => {
    const res = await fetch(`http://localhost:${PORT}/nope/`);
    expect(res.status).toBe(404);
  });

  it('broadcasts "reload" over WebSocket when a source file changes', async () => {
    const ws = new WebSocket(`ws://localhost:${PORT}`);
    await new Promise<void>((resolve, reject) => {
      ws.once('open', resolve);
      ws.once('error', reject);
    });

    const reload = new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('no reload received')), 10000);
      ws.on('message', (data) => {
        clearTimeout(timer);
        resolve(data.toString());
      });
    });

    // Give chokidar a beat to settle, then touch a file.
    await new Promise((r) => setTimeout(r, 500));
    await fs.writeFile(
      path.join(config.sourceDir, 'index.md'),
      '---\ntitle: Dev\n---\nChanged!',
    );

    expect(await reload).toBe('reload');
    ws.close();

    // The rebuilt page is served.
    const html = await (await fetch(`http://localhost:${PORT}/`)).text();
    expect(html).toContain('Changed!');
  }, 15000);
});
