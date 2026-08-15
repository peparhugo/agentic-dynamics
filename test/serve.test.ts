import fs from 'fs';
import http from 'http';
import os from 'os';
import path from 'path';

import WebSocket from 'ws';

import { injectLiveReloadScript, LIVE_RELOAD_PATH, startServer, ServeHandle } from '../src/serve';

function tmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(root: string, relative: string, content: string): string {
  const full = path.join(root, relative);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content);
  return full;
}

function cleanup(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

function get(url: string, port: number): Promise<{ status: number; body: string; headers: http.IncomingHttpHeaders }> {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: 'localhost', port, path: url }, (res) => {
      let body = '';
      res.setEncoding('utf-8');
      res.on('data', (chunk) => (body += chunk));
      res.on('end', () => resolve({ status: res.statusCode ?? 0, body, headers: res.headers }));
    });
    req.on('error', reject);
  });
}

function connectReload(port: number): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://localhost:${port}${LIVE_RELOAD_PATH}`);
    ws.once('open', () => resolve(ws));
    ws.once('error', reject);
  });
}

function nextMessage(ws: WebSocket): Promise<string> {
  return new Promise((resolve) => {
    ws.once('message', (data) => resolve(data.toString()));
  });
}

describe('injectLiveReloadScript', () => {
  it('injects before the closing body tag', () => {
    const html = '<html><body><p>hi</p></body></html>';
    const result = injectLiveReloadScript(html);
    expect(result).toContain(LIVE_RELOAD_PATH);
    expect(result).toContain('location.reload()');
    expect(result.indexOf('<script')).toBeLessThan(result.indexOf('</body>'));
    expect(result).toContain('<p>hi</p>');
  });

  it('injects before the closing html tag when no body exists', () => {
    const html = '<html><p>hi</p></html>';
    const result = injectLiveReloadScript(html);
    expect(result.indexOf('<script')).toBeLessThan(result.indexOf('</html>'));
  });

  it('appends the script when there is no closing tag', () => {
    const html = '<p>hi</p>';
    const result = injectLiveReloadScript(html);
    expect(result).toContain(LIVE_RELOAD_PATH);
    expect(result.endsWith('</script>')).toBe(true);
  });
});

describe('startServer', () => {
  let root: string;
  let contentDir: string;
  let templatesDir: string;
  let outputDir: string;
  let handle: ServeHandle;

  beforeEach(async () => {
    root = tmpDir('ssg-serve-');
    contentDir = path.join(root, 'content');
    templatesDir = path.join(root, 'templates');
    outputDir = path.join(root, 'dist');

    writeFile(
      contentDir,
      'hello.md',
      `---
title: Hello World
---
# Welcome

This is **bold**.
`
    );
    writeFile(templatesDir, path.join('layouts', 'default.hbs'), '<html><body><main>{{{body}}}</main></body></html>');

    handle = await startServer({ content: contentDir, output: outputDir, templates: templatesDir, port: 0 });
  });

  afterEach(async () => {
    await handle.close();
    cleanup(root);
  });

  it('starts a server on the given port and builds the site', () => {
    expect(handle.port).toBeGreaterThan(0);
    expect(handle.address).toContain(`:${handle.port}`);
    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);
  });

  it('serves static files from the dist directory', async () => {
    const res = await get('/hello.html', handle.port);
    expect(res.status).toBe(200);
    expect(res.body).toContain('<h1>Welcome</h1>');
    expect(res.body).toContain('<strong>bold</strong>');
  });

  it('injects the live-reload script into served HTML pages', async () => {
    const res = await get('/hello.html', handle.port);
    expect(res.headers['content-type']).toContain('text/html');
    expect(res.body).toContain(LIVE_RELOAD_PATH);
    expect(res.body).toContain('location.reload()');
  });

  it('serves the index at the root path', async () => {
    const res = await get('/', handle.port);
    expect(res.status).toBe(200);
    expect(res.body).toContain('Site Index');
    expect(res.body).toContain('Hello World');
  });

  it('returns 404 for missing files', async () => {
    const res = await get('/missing.html', handle.port);
    expect(res.status).toBe(404);
  });

  it('rebuilds and broadcasts a reload message when content changes', async () => {
    const ws = await connectReload(handle.port);
    const reloadPromise = nextMessage(ws);

    writeFile(
      contentDir,
      'new.md',
      `---
title: New Page
---
Fresh content.
`
    );

    const message = await reloadPromise;
    expect(message).toBe('reload');
    ws.close();

    const res = await get('/new.html', handle.port);
    expect(res.status).toBe(200);
    expect(res.body).toContain('Fresh content.');
  });

  it('honours a custom --port value', async () => {
    await handle.close();
    cleanup(root);
    root = tmpDir('ssg-serve-port-');
    contentDir = path.join(root, 'content');
    templatesDir = path.join(root, 'templates');
    outputDir = path.join(root, 'dist');
    writeFile(contentDir, 'hello.md', '---\ntitle: Hi\n---\nBody\n');

    const server = await startServer({ content: contentDir, output: outputDir, templates: templatesDir, port: 43121 });
    try {
      expect(server.port).toBe(43121);
      const res = await get('/hello.html', server.port);
      expect(res.status).toBe(200);
    } finally {
      await server.close();
      cleanup(root);
    }
  });
});
