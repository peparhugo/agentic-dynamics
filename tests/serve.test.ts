import fs from 'fs';
import os from 'os';
import path from 'path';
import http from 'http';
import WebSocket from 'ws';
import { startServer, DevServer } from '../src/serve';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function get(port: number, urlPath: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http
      .get(`http://127.0.0.1:${port}${urlPath}`, (res) => {
        let body = '';
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => resolve({ status: res.statusCode ?? 0, body }));
      })
      .on('error', reject);
  });
}

function waitForEvent(emitter: NodeJS.EventEmitter, event: string, timeoutMs = 5000): Promise<any> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Timed out waiting for "${event}"`)), timeoutMs);
    emitter.once(event, (arg) => {
      clearTimeout(timer);
      resolve(arg);
    });
  });
}

describe('dev server', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;
  let server: DevServer | undefined;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-serve-content-');
    outputDir = makeTmpDir('ssg-serve-dist-');
    templatesDir = makeTmpDir('ssg-serve-templates-');
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      `---\ntitle: Serve Page\n---\nHello from serve.`
    );
  });

  afterEach(async () => {
    if (server) {
      await server.close();
      server = undefined;
    }
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('builds the site on startup and serves it from the output directory', async () => {
    server = await startServer({ contentDir, outputDir, templatesDir, port: 0 });
    expect(fs.existsSync(path.join(outputDir, 'page.html'))).toBe(true);

    const res = await get(server.port, '/page.html');
    expect(res.status).toBe(200);
    expect(res.body).toContain('Serve Page');
  }, 20000);

  it('serves the index page at /', async () => {
    server = await startServer({ contentDir, outputDir, templatesDir, port: 0 });
    const res = await get(server.port, '/');
    expect(res.status).toBe(200);
    expect(res.body).toContain('Serve Page');
  }, 20000);

  it('injects a live-reload websocket script into served HTML pages', async () => {
    server = await startServer({ contentDir, outputDir, templatesDir, port: 0 });
    const res = await get(server.port, '/page.html');
    expect(res.body).toContain('WebSocket');
    expect(res.body).toContain('__livereload');
  }, 20000);

  it('returns 404 for missing files', async () => {
    server = await startServer({ contentDir, outputDir, templatesDir, port: 0 });
    const res = await get(server.port, '/does-not-exist.html');
    expect(res.status).toBe(404);
  }, 20000);

  it('rejects path traversal attempts outside the output directory', async () => {
    server = await startServer({ contentDir, outputDir, templatesDir, port: 0 });
    const res = await get(server.port, '/../../etc/passwd');
    expect(res.status).toBe(404);
  }, 20000);

  it('rebuilds and notifies connected clients over WebSocket when a content file changes', async () => {
    server = await startServer({ contentDir, outputDir, templatesDir, port: 0 });

    const socket = new WebSocket(`ws://127.0.0.1:${server.port}/__livereload`);
    await waitForEvent(socket, 'open');

    const messagePromise = waitForEvent(socket, 'message');
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      `---\ntitle: Updated Serve Page\n---\nUpdated content.`
    );

    const message = await messagePromise;
    expect(message.toString()).toBe('reload');

    const html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(html).toContain('Updated Serve Page');

    socket.close();
  }, 20000);

  it('rebuilds and notifies clients when a template file changes', async () => {
    fs.mkdirSync(path.join(templatesDir, 'layouts'));
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><body class="v1">{{{body}}}</body></html>'
    );

    server = await startServer({ contentDir, outputDir, templatesDir, port: 0 });
    let html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(html).toContain('class="v1"');

    const socket = new WebSocket(`ws://127.0.0.1:${server.port}/__livereload`);
    await waitForEvent(socket, 'open');

    const messagePromise = waitForEvent(socket, 'message');
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<html><body class="v2">{{{body}}}</body></html>'
    );

    await messagePromise;
    html = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(html).toContain('class="v2"');

    socket.close();
  }, 20000);

  it('uses the requested port and reports it back', async () => {
    server = await startServer({ contentDir, outputDir, templatesDir, port: 0 });
    expect(server.port).toBeGreaterThan(0);
  }, 20000);
});
