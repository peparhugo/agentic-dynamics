import fs from 'fs';
import http from 'http';
import os from 'os';
import path from 'path';
import { injectLiveReloadScript, startDevServer, LIVE_RELOAD_PATH, DevServerHandle } from '../src/server';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-'));
}

function writeFile(dir: string, name: string, content: string): string {
  const filePath = path.join(dir, name);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content);
  return filePath;
}

function getFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = http.createServer();
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      const port = typeof address === 'object' && address ? address.port : 0;
      server.close(() => resolve(port));
    });
    server.once('error', reject);
  });
}

function request(url: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http
      .get(url, { agent: false }, (res) => {
        let body = '';
        res.setEncoding('utf-8');
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => resolve({ status: res.statusCode ?? 0, body }));
      })
      .on('error', reject);
  });
}

async function waitFor(fn: () => Promise<boolean>, timeoutMs = 5000): Promise<void> {
  const start = Date.now();
  for (;;) {
    if (await fn()) return;
    if (Date.now() - start > timeoutMs) {
      throw new Error('timed out waiting for condition');
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

describe('injectLiveReloadScript', () => {
  it('inserts the WebSocket client script before the closing body tag', () => {
    const html = '<html><head></head><body><p>hi</p></body></html>';
    const injected = injectLiveReloadScript(html);
    expect(injected).toContain(LIVE_RELOAD_PATH);
    expect(injected.indexOf(LIVE_RELOAD_PATH)).toBeLessThan(injected.indexOf('</body>'));
    expect(injected).toContain('<p>hi</p>');
  });

  it('appends the script when there is no body tag', () => {
    const html = '<p>no body</p>';
    const injected = injectLiveReloadScript(html);
    expect(injected).toContain(LIVE_RELOAD_PATH);
    expect(injected.endsWith('</script>')).toBe(true);
  });
});

describe('startDevServer', () => {
  let root: string;
  let server: DevServerHandle | undefined;

  afterEach(async () => {
    if (server) {
      await server.close();
      server = undefined;
    }
    if (root) fs.rmSync(root, { recursive: true, force: true });
  });

  it('serves built pages from the output directory with live reload injected', async () => {
    root = makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    writeFile(contentDir, 'hello.md', '---\ntitle: Hello\n---\n\nBody text.\n');

    const port = await getFreePort();
    server = await startDevServer({ contentDir, outputDir, port, host: '127.0.0.1' });

    const home = await request(`http://127.0.0.1:${port}/`);
    expect(home.status).toBe(200);
    expect(home.body).toContain(LIVE_RELOAD_PATH);
    expect(home.body).toContain('href="hello.html"');

    const page = await request(`http://127.0.0.1:${port}/hello.html`);
    expect(page.status).toBe(200);
    expect(page.body).toContain('<h1>Hello</h1>');
    expect(page.body).toContain(LIVE_RELOAD_PATH);
  });

  it('returns 404 for missing files', async () => {
    root = makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    writeFile(contentDir, 'hello.md', 'Body.\n');

    const port = await getFreePort();
    server = await startDevServer({ contentDir, outputDir, port, host: '127.0.0.1' });

    const res = await request(`http://127.0.0.1:${port}/nope.html`);
    expect(res.status).toBe(404);
  });

  it('rebuilds when a watched file changes', async () => {
    root = makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    writeFile(contentDir, 'hello.md', '---\ntitle: Hello\n---\n\nBody text.\n');

    const port = await getFreePort();
    server = await startDevServer({ contentDir, outputDir, port, host: '127.0.0.1' });

    writeFile(contentDir, 'second.md', '---\ntitle: Second\n---\nSecond body.\n');

    await waitFor(async () => {
      const res = await request(`http://127.0.0.1:${port}/second.html`);
      return res.status === 200 && res.body.includes('<h1>Second</h1>');
    });
  });

  it('serves a custom port and reports it on the handle', async () => {
    root = makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    writeFile(contentDir, 'hello.md', 'Body.\n');

    const port = await getFreePort();
    server = await startDevServer({ contentDir, outputDir, port, host: '127.0.0.1' });

    expect(server.port).toBe(port);
    const home = await request(`http://127.0.0.1:${port}/`);
    expect(home.status).toBe(200);
  });
});
