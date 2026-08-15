import fs from 'fs';
import os from 'os';
import path from 'path';
import net from 'net';
import http from 'http';
import { DevServer, injectReloadScript, LIVE_RELOAD_SCRIPT } from '../src/server';

function tmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function getFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const address = srv.address();
      const port = typeof address === 'object' && address ? address.port : 0;
      srv.close(() => resolve(port));
    });
  });
}

function httpGet(url: string): Promise<{ status: number; body: string }> {
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

async function waitFor(predicate: () => boolean, timeoutMs = 8000): Promise<void> {
  const start = Date.now();
  while (!predicate()) {
    if (Date.now() - start > timeoutMs) {
      throw new Error('waitFor timed out');
    }
    await new Promise((r) => setTimeout(r, 40));
  }
}

function writeFixture(content: string, tpl: string): void {
  fs.mkdirSync(path.join(tpl, 'layouts'), { recursive: true });
  fs.writeFileSync(
    path.join(tpl, 'layouts', 'default.hbs'),
    '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
  );
  fs.writeFileSync(path.join(tpl, 'page.hbs'), '<main><h1>{{title}}</h1><div>{{{html}}}</div></main>');
  fs.writeFileSync(
    path.join(tpl, 'index.hbs'),
    '<main><h1>Index</h1>{{#each pages}}<a href="{{slug}}.html">{{title}}</a>{{/each}}</main>'
  );
}

describe('injectReloadScript', () => {
  it('inserts the reload script before the closing body tag', () => {
    const html = '<html><body><p>hi</p></body></html>';
    const out = injectReloadScript(html);
    expect(out).toContain(LIVE_RELOAD_SCRIPT);
    expect(out.indexOf(LIVE_RELOAD_SCRIPT)).toBeLessThan(out.indexOf('</body>'));
  });

  it('appends the script when no body tag is present', () => {
    const out = injectReloadScript('<html><p>hi</p></html>');
    expect(out).toContain(LIVE_RELOAD_SCRIPT);
    expect(out.endsWith(LIVE_RELOAD_SCRIPT)).toBe(true);
  });
});

describe('DevServer', () => {
  it('serves built pages and injects the live-reload script', async () => {
    const content = tmpDir('ssg-serve-content-');
    const out = tmpDir('ssg-serve-out-');
    const tpl = tmpDir('ssg-serve-tpl-');
    try {
      writeFixture(content, tpl);
      fs.writeFileSync(path.join(content, 'hello.md'), '---\ntitle: Hello\n---\n# Hi\n');

      const port = await getFreePort();
      const server = new DevServer({
        contentDir: content,
        outputDir: out,
        templatesDir: tpl,
        port,
        host: '127.0.0.1',
      });
      await server.start();
      try {
        const index = await httpGet(`http://127.0.0.1:${port}/index.html`);
        expect(index.status).toBe(200);
        expect(index.body).toContain('Hello');
        expect(index.body).toContain(LIVE_RELOAD_SCRIPT);

        const page = await httpGet(`http://127.0.0.1:${port}/hello.html`);
        expect(page.status).toBe(200);
        expect(page.body).toContain('<h1>Hello</h1>');
        expect(page.body).toContain('<h1>Hi</h1>');
        expect(page.body).toContain(LIVE_RELOAD_SCRIPT);

        const missing = await httpGet(`http://127.0.0.1:${port}/nope.html`);
        expect(missing.status).toBe(404);
      } finally {
        await server.stop();
      }
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });

  it('rebuilds when a content file changes', async () => {
    const content = tmpDir('ssg-serve-content-');
    const out = tmpDir('ssg-serve-out-');
    const tpl = tmpDir('ssg-serve-tpl-');
    try {
      writeFixture(content, tpl);
      fs.writeFileSync(path.join(content, 'hello.md'), '---\ntitle: Hello\n---\n# Version One\n');

      const port = await getFreePort();
      const server = new DevServer({
        contentDir: content,
        outputDir: out,
        templatesDir: tpl,
        port,
        host: '127.0.0.1',
        debounceMs: 50,
      });
      await server.start();
      try {
        const before = await httpGet(`http://127.0.0.1:${port}/hello.html`);
        expect(before.body).toContain('Version One');

        fs.writeFileSync(path.join(content, 'hello.md'), '---\ntitle: Hello\n---\n# Version Two\n');

        await waitFor(() => {
          const html = fs.readFileSync(path.join(out, 'hello.html'), 'utf-8');
          return html.includes('Version Two');
        });

        const after = await httpGet(`http://127.0.0.1:${port}/hello.html`);
        expect(after.body).toContain('Version Two');
      } finally {
        await server.stop();
      }
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(out, { recursive: true, force: true });
      fs.rmSync(tpl, { recursive: true, force: true });
    }
  });
});
