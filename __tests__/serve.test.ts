import fs from 'fs';
import os from 'os';
import path from 'path';
import http from 'http';
import { AddressInfo } from 'net';
import { WebSocket, RawData } from 'ws';
import { startDevServer, injectLiveReload, DevServer } from '../src/serve';
import { build } from '../src/ssg';

function makeTempRoot(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, content] of Object.entries(files)) {
    const filePath = path.join(root, rel);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content, 'utf8');
  }
}

function listen(server: http.Server): Promise<number> {
  return new Promise((resolve) => {
    server.once('listening', () => {
      const address = server.address() as AddressInfo | null;
      resolve(address ? address.port : 0);
    });
  });
}

function waitForMessage(socket: WebSocket, timeout = 8000): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      socket.off('message', onMessage);
      reject(new Error('timed out waiting for websocket message'));
    }, timeout);
    function onMessage(data: RawData): void {
      clearTimeout(timer);
      socket.off('message', onMessage);
      resolve(data.toString());
    }
    socket.on('message', onMessage);
  });
}

function waitForFile(filePath: string, timeout = 8000): Promise<void> {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const timer = setInterval(() => {
      if (fs.existsSync(filePath)) {
        clearInterval(timer);
        resolve();
      } else if (Date.now() - start > timeout) {
        clearInterval(timer);
        reject(new Error(`timed out waiting for ${filePath}`));
      }
    }, 50);
  });
}

async function get(port: number, pathname: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        host: '127.0.0.1',
        port,
        path: pathname,
        method: 'GET',
        headers: { connection: 'close' },
        agent: false,
      },
      (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk: string) => {
          body += chunk;
        });
        res.on('end', () => {
          resolve({ status: res.statusCode ?? 0, body });
        });
      }
    );
    req.on('error', reject);
    req.end();
  });
}

describe('injectLiveReload', () => {
  it('injects a WebSocket script before the closing body tag', () => {
    const html = '<!DOCTYPE html>\n<html><head></head><body><h1>hi</h1></body></html>';
    const out = injectLiveReload(html);
    expect(out).toContain('<script');
    expect(out).toContain('WebSocket');
    expect(out).toContain('/__live_reload');
    expect(out.indexOf('WebSocket')).toBeGreaterThan(out.indexOf('</body>') - 4000);
    expect(out.indexOf('<script')).toBeLessThan(out.indexOf('</body>'));
  });

  it('appends the script when there is no body tag', () => {
    const out = injectLiveReload('plain text');
    expect(out).toContain('plain text');
    expect(out).toContain('WebSocket');
  });
});

describe('dev server', () => {
  let root: string;
  let contentDir: string;
  let templateDir: string;
  let outputDir: string;
  let dev: DevServer;

  afterEach(async () => {
    if (dev) {
      await dev.close();
      dev = undefined as unknown as DevServer;
    }
    if (root) {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  beforeEach(() => {
    root = makeTempRoot('ssg-serve-');
    contentDir = path.join(root, 'content');
    templateDir = path.join(root, 'templates');
    outputDir = path.join(root, 'dist');
  });

  it('serves built pages with the live reload script injected', async () => {
    writeTree(root, {
      'content/a.md': '---\ntitle: A\n---\nBody text.',
    });
    build({ contentDir, outputDir, templateDir });

    dev = startDevServer({ contentDir, outputDir, templateDir, port: 0 });
    const port = await listen(dev.server);

    const { status, body } = await get(port, '/a.html');
    expect(status).toBe(200);
    expect(body).toContain('Body text.');
    expect(body).toContain('WebSocket');
    expect(body).toContain('/__live_reload');
  });

  it('serves index.html at the root', async () => {
    writeTree(root, {
      'content/a.md': '---\ntitle: A\n---\nBody.',
    });
    build({ contentDir, outputDir, templateDir });

    dev = startDevServer({ contentDir, outputDir, templateDir, port: 0 });
    const port = await listen(dev.server);

    const { status, body } = await get(port, '/');
    expect(status).toBe(200);
    expect(body).toContain('<h2>A</h2>');
    expect(body).toContain('WebSocket');
  });

  it('returns 404 for missing files', async () => {
    writeTree(root, {
      'content/a.md': '---\ntitle: A\n---\nBody.',
    });
    build({ contentDir, outputDir, templateDir });

    dev = startDevServer({ contentDir, outputDir, templateDir, port: 0 });
    const port = await listen(dev.server);

    const { status } = await get(port, '/nope.html');
    expect(status).toBe(404);
  });

  it('rebuilds and sends a reload message when content changes', async () => {
    writeTree(root, {
      'content/a.md': '---\ntitle: A\n---\nHello.',
    });
    build({ contentDir, outputDir, templateDir });

    dev = startDevServer({ contentDir, outputDir, templateDir, port: 0 });
    const port = await listen(dev.server);

    const ws = new WebSocket(`ws://127.0.0.1:${port}/__live_reload`);
    await new Promise<void>((resolve) => ws.once('open', () => resolve()));

    fs.writeFileSync(path.join(contentDir, 'b.md'), '---\ntitle: B\n---\nNew page.');

    const msg = await waitForMessage(ws);
    expect(msg).toBe('reload');
    await waitForFile(path.join(outputDir, 'b.html'));

    ws.terminate();
  });

  it('rebuilds and sends a reload message when templates change', async () => {
    writeTree(root, {
      'content/a.md': '---\ntitle: A\n---\nHello.',
      'templates/default.hbs': '<article>{{title}} v1</article>',
      'templates/layouts/default.hbs': '<html><head></head><body>{{{body}}}</body></html>',
    });
    build({ contentDir, outputDir, templateDir });

    dev = startDevServer({ contentDir, outputDir, templateDir, port: 0 });
    const port = await listen(dev.server);

    const ws = new WebSocket(`ws://127.0.0.1:${port}/__live_reload`);
    await new Promise<void>((resolve) => ws.once('open', () => resolve()));

    fs.writeFileSync(path.join(templateDir, 'default.hbs'), '<article>{{title}} v2</article>');

    const msg = await waitForMessage(ws);
    expect(msg).toBe('reload');

    ws.terminate();
  });
});
