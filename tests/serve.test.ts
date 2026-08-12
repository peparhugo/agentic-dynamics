import fs from 'fs';
import http from 'http';
import os from 'os';
import path from 'path';
import { WebSocket } from 'ws';
import { parseArgs, toServeOptions, USAGE } from '../src/cli';
import {
  DEFAULT_PORT,
  LIVE_RELOAD_SCRIPT_ID,
  WS_PATH,
  broadcastReload,
  createDevServer,
  injectLiveReload,
  liveReloadScript,
  resolveFilePath,
} from '../src/serve';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-'));
}

async function get(url: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const req = http
      .get(url, { agent: false }, (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => {
          res.destroy();
          resolve({ status: res.statusCode ?? 0, body });
        });
      })
      .on('error', reject);
    req.on('error', reject);
  });
}

async function closeWebSocket(ws: WebSocket): Promise<void> {
  if (ws.readyState === WebSocket.CLOSED) return;
  await new Promise<void>((resolve) => {
    ws.once('close', () => resolve());
    ws.close();
  });
}

async function waitFor(cond: () => boolean, timeout = 8000): Promise<void> {
  const start = Date.now();
  while (!cond()) {
    if (Date.now() - start > timeout) {
      throw new Error('timed out waiting for condition');
    }
    await new Promise((r) => setTimeout(r, 20));
  }
}

afterAll(async () => {
  await new Promise((r) => setTimeout(r, 250));
});

describe('parseArgs with serve', () => {
  it('uses the default port when none is given', () => {
    const options = parseArgs(['serve']);
    expect(options.command).toBe('serve');
    expect(options.port).toBe(DEFAULT_PORT);
  });

  it('parses the --port option', () => {
    const options = parseArgs(['serve', '--port', '5000']);
    expect(options.command).toBe('serve');
    expect(options.port).toBe(5000);
  });

  it('parses --port alongside directory options', () => {
    const options = parseArgs(['serve', '--content', 'pages', '--output', 'public', '--port', '8080']);
    expect(options.content).toBe('pages');
    expect(options.output).toBe('public');
    expect(options.port).toBe(8080);
  });

  it('throws on a non-numeric port', () => {
    expect(() => parseArgs(['serve', '--port', 'abc'])).toThrow(/Invalid port/);
  });

  it('documents the serve command in the usage text', () => {
    expect(USAGE).toContain('ssg serve');
    expect(USAGE).toContain('--port <port>');
  });

  it('converts CLI options into serve options', () => {
    const options = parseArgs(['serve', '--port', '4000']);
    const serve = toServeOptions(options);
    expect(serve.port).toBe(4000);
    expect(serve.output).toBe('./dist');
  });
});

describe('live reload script injection', () => {
  it('injects a WebSocket script before the closing body tag', () => {
    const html = '<!DOCTYPE html><html><body><h1>Hi</h1></body></html>';
    const out = injectLiveReload(html, 3000);
    expect(out).toContain(LIVE_RELOAD_SCRIPT_ID);
    expect(out).toContain('new WebSocket');
    expect(out).toContain(WS_PATH);
    expect(out).toContain('var port = 3000');
    expect(out).toContain('<h1>Hi</h1>');
    expect(out.indexOf(LIVE_RELOAD_SCRIPT_ID)).toBeLessThan(out.indexOf('</body>'));
  });

  it('appends the script when there is no body tag', () => {
    const out = injectLiveReload('<p>bare</p>', 4000);
    expect(out).toContain(LIVE_RELOAD_SCRIPT_ID);
    expect(out).toContain('var port = 4000');
    expect(out).toContain(WS_PATH);
  });

  it('builds a reload script for the requested port', () => {
    const script = liveReloadScript(1234);
    expect(script).toContain('var port = 1234');
    expect(script).toContain('location.reload');
    expect(script).toContain(WS_PATH);
  });
});

describe('resolveFilePath', () => {
  it('maps / to index.html', () => {
    const dir = makeTempDir();
    expect(resolveFilePath('/', dir)).toBe(path.join(dir, 'index.html'));
  });

  it('maps /about.html to about.html', () => {
    const dir = makeTempDir();
    expect(resolveFilePath('/about.html', dir)).toBe(path.join(dir, 'about.html'));
  });

  it('keeps resolved paths inside the output directory', () => {
    const dir = makeTempDir();
    const filePath = resolveFilePath('/../../etc/passwd', dir);
    expect(filePath).toBe(path.join(dir, 'etc', 'passwd'));
    expect(path.resolve(filePath as string).startsWith(path.resolve(dir))).toBe(true);
  });
});

describe('dev server', () => {
  it('serves built pages with live-reload injected', async () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();
    try {
      fs.writeFileSync(path.join(content, 'post.md'), '<!--\ntitle: Post\n-->\n# Post body');

      const dev = createDevServer({ content, output, templates, port: 0 });
      const port = await dev.listen();
      try {
        const res = await get(`http://127.0.0.1:${port}/post.html`);
        expect(res.status).toBe(200);
        expect(res.body).toContain('<title>Post</title>');
        expect(res.body).toContain('<h1>Post body</h1>');
        expect(res.body).toContain(LIVE_RELOAD_SCRIPT_ID);

        const index = await get(`http://127.0.0.1:${port}/`);
        expect(index.status).toBe(200);
        expect(index.body).toContain('<a href="post.html">Post</a>');
        expect(index.body).toContain(LIVE_RELOAD_SCRIPT_ID);
      } finally {
        await dev.stop();
      }
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
      fs.rmSync(templates, { recursive: true, force: true });
    }
  });

  it('returns 404 for missing pages', async () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();
    try {
      fs.writeFileSync(path.join(content, 'a.md'), '<!--\ntitle: A\n-->\n# A');
      const dev = createDevServer({ content, output, templates, port: 0 });
      const port = await dev.listen();
      try {
        const res = await get(`http://127.0.0.1:${port}/nope.html`);
        expect(res.status).toBe(404);
      } finally {
        await dev.stop();
      }
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
      fs.rmSync(templates, { recursive: true, force: true });
    }
  });

  it('rebuilds the site and broadcasts a reload when content changes', async () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();
    try {
      fs.writeFileSync(path.join(content, 'a.md'), '<!--\ntitle: A\n-->\n# A');
      const dev = createDevServer({ content, output, templates, port: 0 });
      const port = await dev.listen();
      await dev.ready;

      const ws = new WebSocket(`ws://127.0.0.1:${port}${WS_PATH}`);
      await new Promise<void>((resolve, reject) => {
        ws.once('open', () => resolve());
        ws.once('error', reject);
      });
      const messages: string[] = [];
      ws.on('message', (data) => messages.push(String(data)));

      fs.writeFileSync(path.join(content, 'a.md'), '<!--\ntitle: A2\n-->\n# A2');
      await waitFor(() => messages.includes('reload'));

      expect(messages).toContain('reload');
      expect(dev.getRebuildCount()).toBeGreaterThanOrEqual(1);
      const html = fs.readFileSync(path.join(output, 'a.html'), 'utf8');
      expect(html).toContain('<title>A2</title>');
      expect(html).toContain('<h1>A2</h1>');
      expect(html).not.toContain('<h1>A</h1>');

      await closeWebSocket(ws);
      await dev.stop();
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
      fs.rmSync(templates, { recursive: true, force: true });
    }
  });

  it('rebuilds when a template file changes', async () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();
    try {
      fs.writeFileSync(path.join(templates, 'default.hbs'), 'OLD {{title}}');
      fs.writeFileSync(path.join(content, 'a.md'), '<!--\ntitle: A\n-->\n# A');
      const dev = createDevServer({ content, output, templates, port: 0 });
      await dev.listen();
      await dev.ready;

      fs.writeFileSync(path.join(templates, 'default.hbs'), 'NEW {{title}}');
      await waitFor(() => {
        try {
          return fs.readFileSync(path.join(output, 'a.html'), 'utf8').includes('NEW A');
        } catch {
          return false;
        }
      });

      expect(fs.readFileSync(path.join(output, 'a.html'), 'utf8')).toContain('NEW A');
      await dev.stop();
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
      fs.rmSync(templates, { recursive: true, force: true });
    }
  });

  it('broadcastReload returns the number of connected clients notified', async () => {
    const content = makeTempDir();
    const output = makeTempDir();
    const templates = makeTempDir();
    try {
      fs.writeFileSync(path.join(content, 'a.md'), '<!--\ntitle: A\n-->\n# A');
      const dev = createDevServer({ content, output, templates, port: 0 });
      const port = await dev.listen();
      const ws = new WebSocket(`ws://127.0.0.1:${port}${WS_PATH}`);
      await new Promise<void>((resolve, reject) => {
        ws.once('open', () => resolve());
        ws.once('error', reject);
      });

      const message = new Promise<string>((resolve) => {
        ws.once('message', (data) => resolve(String(data)));
      });
      const sent = broadcastReload(dev.wss);
      expect(sent).toBe(1);
      expect(await message).toBe('reload');

      await closeWebSocket(ws);
      await dev.stop();
    } finally {
      fs.rmSync(content, { recursive: true, force: true });
      fs.rmSync(output, { recursive: true, force: true });
      fs.rmSync(templates, { recursive: true, force: true });
    }
  });
});
