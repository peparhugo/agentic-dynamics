import fs from 'fs';
import os from 'os';
import path from 'path';
import { AddressInfo } from 'net';
import { WebSocket } from 'ws';
import { injectLiveReload, startDevServer, DevServer } from './serve';

describe('injectLiveReload', () => {
  it('injects the live reload script before the closing body tag', () => {
    const html = '<html><body><h1>Hi</h1></body></html>';
    const out = injectLiveReload(html);
    expect(out).toContain('WebSocket');
    expect(out).toContain('location.reload');
    expect(out.indexOf('WebSocket')).toBeLessThan(out.indexOf('</body>'));
    expect(out).toContain('</body></html>');
  });

  it('appends the script when the html has no body tag', () => {
    const html = '<html><body><h1>Hi</h1>';
    const out = injectLiveReload(html);
    expect(out.startsWith(html)).toBe(true);
    expect(out).toContain('WebSocket');
  });
});

describe('startDevServer', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    fs.mkdirSync(contentDir);
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  async function start(
    overrides: Partial<Parameters<typeof startDevServer>[0]> = {}
  ): Promise<DevServer> {
    const dev = startDevServer({ contentDir, outputDir, port: 0, ...overrides });
    await Promise.all([
      new Promise<void>((resolve) => dev.server.once('listening', resolve)),
      dev.ready,
    ]);
    return dev;
  }

  function port(dev: DevServer): number {
    return (dev.server.address() as AddressInfo).port;
  }

  async function fetchText(dev: DevServer, pathname: string): Promise<string> {
    const res = await fetch(`http://localhost:${port(dev)}${pathname}`);
    expect(res.status).toBe(200);
    return res.text();
  }

  async function connectSocket(dev: DevServer): Promise<WebSocket> {
    const ws = new WebSocket(`ws://localhost:${port(dev)}`);
    await new Promise<void>((resolve, reject) => {
      ws.once('open', resolve);
      ws.once('error', reject);
    });
    return ws;
  }

  function nextMessage(ws: WebSocket, timeoutMs = 8000): Promise<any> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('timed out waiting for websocket message')), timeoutMs);
      ws.on('message', (data) => {
        clearTimeout(timer);
        resolve(JSON.parse(data.toString()));
      });
    });
  }

  it('builds and serves pages with the live reload script injected', async () => {
    fs.writeFileSync(
      path.join(contentDir, 'hello.md'),
      '---\ntitle: Hello\n---\n\n**World**.',
      'utf-8'
    );
    const dev = await start();
    try {
      const index = await fetchText(dev, '/');
      expect(index).toContain('<a href="hello.html">Hello</a>');

      const page = await fetchText(dev, '/hello.html');
      expect(page).toContain('<strong>World</strong>');
      expect(page).toContain('WebSocket');
      expect(page).toContain('location.reload');
    } finally {
      await dev.close();
    }
  });

  it('rebuilds and notifies clients when a content file changes', async () => {
    const file = path.join(contentDir, 'post.md');
    fs.writeFileSync(file, '---\ntitle: One\n---\n\nVersion 1', 'utf-8');
    const dev = await start();
    try {
      const ws = await connectSocket(dev);
      const message = nextMessage(ws);

      fs.writeFileSync(file, '---\ntitle: Two\n---\n\nVersion 2', 'utf-8');

      const msg = await message;
      expect(msg.type).toBe('reload');

      const updated = await fetchText(dev, '/post.html');
      expect(updated).toContain('Version 2');
      expect(updated).not.toContain('Version 1');
      ws.close();
    } finally {
      await dev.close();
    }
  });

  it('rebuilds and notifies clients when a template file changes', async () => {
    const templatesDir = path.join(root, 'templates');
    fs.mkdirSync(templatesDir);
    fs.writeFileSync(path.join(contentDir, 'about.md'), '---\ntitle: About\n---\n\nBody.', 'utf-8');
    fs.writeFileSync(path.join(templatesDir, 'default.hbs'), 'A:{{{html}}}', 'utf-8');
    const dev = await start({ templatesDir });
    try {
      expect(await fetchText(dev, '/about.html')).toContain('A:');

      const ws = await connectSocket(dev);
      const message = nextMessage(ws);

      fs.writeFileSync(path.join(templatesDir, 'default.hbs'), 'B:{{{html}}}', 'utf-8');

      const msg = await message;
      expect(msg.type).toBe('reload');
      expect(await fetchText(dev, '/about.html')).toContain('B:');
      ws.close();
    } finally {
      await dev.close();
    }
  });

  it('returns 404 for missing files', async () => {
    const dev = await start();
    try {
      const res = await fetch(`http://localhost:${port(dev)}/nope.html`);
      expect(res.status).toBe(404);
    } finally {
      await dev.close();
    }
  });

  it('serves html files from the dist directory', async () => {
    fs.writeFileSync(path.join(contentDir, 'page.md'), '---\ntitle: Page\n---\n\nx', 'utf-8');
    const dev = await start();
    try {
      const res = await fetch(`http://localhost:${port(dev)}/page.html`);
      expect(res.status).toBe(200);
      expect(res.headers.get('content-type')).toContain('text/html');
    } finally {
      await dev.close();
    }
  });
});
