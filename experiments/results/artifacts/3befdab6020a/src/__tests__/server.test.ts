import http from 'http';
import fs from 'fs';
import path from 'path';
import os from 'os';
import WebSocket from 'ws';
import { createServer, ServeOptions } from '../server';

function get(port: number, url: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http.get(`http://localhost:${port}${url}`, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => resolve({ status: res.statusCode || 0, body }));
    }).on('error', reject);
  });
}

function writeFile(dir: string, name: string, content: string): void {
  fs.writeFileSync(path.join(dir, name), content, 'utf-8');
}

describe('dev server', () => {
  let tmpDir: string;
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;
  let server: http.Server;
  let port: number;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-test-'));
    contentDir = path.join(tmpDir, 'content');
    outputDir = path.join(tmpDir, 'dist');
    templatesDir = path.join(tmpDir, 'templates');
    fs.mkdirSync(contentDir);
    fs.mkdirSync(outputDir);
    fs.mkdirSync(templatesDir);
  });

  afterEach(() => {
    if (server) {
      const watcher = (server as any)._watcher;
      if (watcher && typeof watcher.close === 'function') {
        watcher.close();
      }
      server.close();
    }
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  async function startServer(overrides: Partial<ServeOptions> = {}): Promise<void> {
    writeFile(contentDir, 'hello.md', `---
title: Hello World
date: '2024-01-01'
tags: []
---
Welcome to my site.`);

    const options: ServeOptions = {
      content: contentDir,
      output: outputDir,
      templates: templatesDir,
      port: 0,
      ...overrides,
    };

    server = createServer(options);

    await new Promise<void>((resolve) => {
      server.listen(options.port, () => resolve());
    });

    const addr = server.address();
    if (addr && typeof addr === 'object') {
      port = addr.port;
    }

    await new Promise((r) => setTimeout(r, 100));
  }

  it('serves HTML files from output directory', async () => {
    await startServer();

    const { status, body } = await get(port, '/hello.html');
    expect(status).toBe(200);
    expect(body).toContain('Hello World');
    expect(body).toContain('<!DOCTYPE html>');
  });

  it('serves index.html for root path', async () => {
    await startServer();

    const { status, body } = await get(port, '/');
    expect(status).toBe(200);
    expect(body).toContain('Site Index');
  });

  it('returns 404 for missing files', async () => {
    await startServer();

    const { status, body } = await get(port, '/nonexistent.html');
    expect(status).toBe(404);
    expect(body).toContain('Not found');
  });

  it('injects live reload WebSocket script into HTML pages', async () => {
    await startServer();

    const { body } = await get(port, '/hello.html');
    expect(body).toContain('new WebSocket');
    expect(body).toContain(`ws://localhost:${port}`);
    expect(body).toContain('location.reload()');
  });

  it('injects live reload script into index page', async () => {
    await startServer();

    const { body } = await get(port, '/index.html');
    expect(body).toContain('new WebSocket');
  });

  it('does not inject live reload script into non-HTML files', async () => {
    writeFile(outputDir, 'style.css', 'body { color: red; }');
    await startServer();

    const { body } = await get(port, '/style.css');
    expect(body).not.toContain('new WebSocket');
  });

  it('listens on the specified port', async () => {
    await startServer();

    expect(port).toBeGreaterThan(0);
    const { status } = await get(port, '/hello.html');
    expect(status).toBe(200);
  });

  it('prevents directory traversal attacks', async () => {
    await startServer();

    const { status } = await get(port, '/../../../etc/passwd');
    expect(status).toBe(404);
  });

  it('reloads on file change via WebSocket', async () => {
    await startServer();

    const ws = new WebSocket(`ws://localhost:${port}`);

    const msgPromise = new Promise<string>((resolve, reject) => {
      ws.on('message', (data) => {
        resolve(data.toString());
      });
      ws.on('error', reject);
    });

    await new Promise<void>((resolve, reject) => {
      ws.on('open', () => resolve());
      ws.on('error', reject);
    });

    writeFile(contentDir, 'new.md', `---
title: New Page
date: '2024-01-01'
tags: []
---
New content.`);

    const msg = await msgPromise;
    expect(msg).toBe('reload');

    ws.close();
  }, 15000);

  it('builds pages on startup', async () => {
    writeFile(contentDir, 'alpha.md', `---
title: Alpha
date: '2024-01-01'
tags: []
---
Alpha content.`);

    writeFile(contentDir, 'beta.md', `---
title: Beta
date: '2024-01-01'
tags: []
---
Beta content.`);

    await startServer();

    const { body: indexBody } = await get(port, '/index.html');
    expect(indexBody).toContain('Alpha');
    expect(indexBody).toContain('Beta');

    const { body: alphaBody } = await get(port, '/alpha.html');
    expect(alphaBody).toContain('Alpha content');

    const { body: betaBody } = await get(port, '/beta.html');
    expect(betaBody).toContain('Beta content');
  });
});
