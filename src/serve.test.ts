import fs from 'fs';
import http from 'http';
import os from 'os';
import path from 'path';
import WebSocket from 'ws';
import {
  startDevServer,
  injectLiveReloadScript,
  LIVE_RELOAD_SCRIPT,
  RELOAD_MESSAGE,
  DevServer,
} from './serve';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-'));
}

function get(url: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http
      .get(url, (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => resolve({ status: res.statusCode ?? 0, body }));
      })
      .on('error', reject);
  });
}

function connect(url: string): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    ws.once('open', () => resolve(ws));
    ws.once('error', reject);
  });
}

function waitForMessage(ws: WebSocket, timeoutMs = 5000): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('timed out waiting for message')), timeoutMs);
    ws.once('message', (data) => {
      clearTimeout(timer);
      resolve(data.toString());
    });
  });
}

describe('injectLiveReloadScript', () => {
  it('injects the script before </body>', () => {
    const html = '<html><body><h1>Hi</h1></body></html>';
    const out = injectLiveReloadScript(html);
    expect(out).toContain(LIVE_RELOAD_SCRIPT);
    expect(out.indexOf(LIVE_RELOAD_SCRIPT)).toBeLessThan(out.indexOf('</body>'));
  });

  it('appends the script when there is no </body>', () => {
    const html = '<html><h1>Hi</h1></html>';
    const out = injectLiveReloadScript(html);
    expect(out).toContain(LIVE_RELOAD_SCRIPT);
  });
});

describe('startDevServer', () => {
  let server: DevServer | undefined;

  afterEach(async () => {
    if (server) {
      await server.close();
      server = undefined;
    }
  });

  it('builds and serves pages with the live-reload script injected', async () => {
    const content = makeTempDir();
    const output = makeTempDir();
    fs.writeFileSync(path.join(content, 'hello.md'), '---\ntitle: Hello\n---\n# Hi\n');

    server = await startDevServer({ contentDir: content, outputDir: output, port: 0 });
    const base = `http://127.0.0.1:${server.port}`;

    const index = await get(`${base}/`);
    expect(index.status).toBe(200);
    expect(index.body).toContain(LIVE_RELOAD_SCRIPT);

    const page = await get(`${base}/hello.html`);
    expect(page.status).toBe(200);
    expect(page.body).toContain('<h1>Hi</h1>');
    expect(page.body).toContain(LIVE_RELOAD_SCRIPT);

    const missing = await get(`${base}/nope.html`);
    expect(missing.status).toBe(404);
  });

  it('reloads connected browsers when content changes', async () => {
    const content = makeTempDir();
    const output = makeTempDir();
    fs.writeFileSync(path.join(content, 'a.md'), '---\ntitle: A\n---\nA body\n');

    server = await startDevServer({ contentDir: content, outputDir: output, port: 0 });
    const ws = await connect(`ws://127.0.0.1:${server.port}`);
    const reloadPromise = waitForMessage(ws);

    fs.writeFileSync(path.join(content, 'b.md'), '---\ntitle: B\n---\nB body\n');

    const message = await reloadPromise;
    expect(message).toBe(RELOAD_MESSAGE);

    const page = await get(`http://127.0.0.1:${server.port}/b.html`);
    expect(page.status).toBe(200);

    ws.close();
  });

  it('serves static assets with an appropriate content type', async () => {
    const content = makeTempDir();
    const output = makeTempDir();
    fs.writeFileSync(path.join(content, 'a.md'), '---\ntitle: A\n---\nA body\n');
    fs.writeFileSync(path.join(output, 'style.css'), 'body { color: red; }');

    server = await startDevServer({ contentDir: content, outputDir: output, port: 0 });

    const css = await get(`http://127.0.0.1:${server.port}/style.css`);
    expect(css.status).toBe(200);
    expect(css.body).toContain('body { color: red; }');
    expect(css.body).not.toContain(LIVE_RELOAD_SCRIPT);
  });
});
