import * as fs from 'fs';
import * as http from 'http';
import * as os from 'os';
import * as path from 'path';
import { WebSocket } from 'ws';
import { injectLiveReload, serve, ServeHandle } from './serve';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function get(port: number, requestPath: string): Promise<{ status: number; body: string; contentType?: string }> {
  return new Promise((resolve, reject) => {
    http
      .get({ host: '127.0.0.1', port, path: requestPath }, (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk) => chunks.push(chunk));
        res.on('end', () =>
          resolve({
            status: res.statusCode ?? 0,
            body: Buffer.concat(chunks).toString('utf-8'),
            contentType: res.headers['content-type'],
          })
        );
      })
      .on('error', reject);
  });
}

describe('injectLiveReload', () => {
  it('inserts the client script before the closing body tag', () => {
    const html = '<html><body><p>hi</p></body></html>';
    const result = injectLiveReload(html);
    expect(result.indexOf('<script>')).toBeLessThan(result.indexOf('</body>'));
    expect(result).toContain("new WebSocket");
  });

  it('appends the script when there is no body tag', () => {
    const html = '<p>fragment</p>';
    const result = injectLiveReload(html);
    expect(result).toBe(`${html}<script>\n(function () {\n  var socket = new WebSocket('ws://' + location.host + '/__livereload');\n  socket.addEventListener('message', function (event) {\n    if (event.data === 'reload') location.reload();\n  });\n})();\n</script>`);
  });
});

describe('serve', () => {
  let contentDir: string;
  let outputDir: string;
  let handle: ServeHandle;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-serve-content-');
    outputDir = makeTempDir('ssg-serve-output-');
    fs.writeFileSync(path.join(contentDir, 'page.md'), '---\ntitle: Page\n---\nHello there');
  });

  afterEach(async () => {
    if (handle) await handle.close();
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
  });

  it('builds the site on startup and serves it with the live-reload script injected', async () => {
    handle = serve({ contentDir, outputDir, port: 0 });

    const index = await get(handle.port, '/');
    expect(index.status).toBe(200);
    expect(index.contentType).toContain('text/html');
    expect(index.body).toContain('Page');
    expect(index.body).toContain('/__livereload');

    const page = await get(handle.port, '/page.html');
    expect(page.status).toBe(200);
    expect(page.body).toContain('Hello there');
    expect(page.body).toContain('/__livereload');
  });

  it('serves non-html files without modification', async () => {
    handle = serve({ contentDir, outputDir, port: 0 });
    const css = await get(handle.port, '/style.css');
    expect(css.status).toBe(200);
    expect(css.contentType).toContain('text/css');
    expect(css.body).not.toContain('__livereload');
  });

  it('returns 404 for missing files', async () => {
    handle = serve({ contentDir, outputDir, port: 0 });
    const response = await get(handle.port, '/does-not-exist.html');
    expect(response.status).toBe(404);
  });

  it('rejects path traversal attempts outside the output directory', async () => {
    handle = serve({ contentDir, outputDir, port: 0 });
    const response = await get(handle.port, '/../../etc/passwd');
    expect(response.status).toBe(404);
  });

  it('rebuilds and pushes a reload message over WebSocket when content changes', async () => {
    handle = serve({ contentDir, outputDir, port: 0 });
    await handle.ready();

    const ws = new WebSocket(`ws://127.0.0.1:${handle.port}/__livereload`);
    await new Promise((resolve, reject) => {
      ws.on('open', resolve);
      ws.on('error', reject);
    });

    const reloadReceived = new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('timed out waiting for reload message')), 10000);
      ws.on('message', (data) => {
        if (data.toString() === 'reload') {
          clearTimeout(timer);
          resolve();
        }
      });
    });

    fs.writeFileSync(path.join(contentDir, 'page.md'), '---\ntitle: Page\n---\nUpdated content');

    await reloadReceived;

    const page = await get(handle.port, '/page.html');
    expect(page.body).toContain('Updated content');

    await new Promise<void>((resolve) => {
      ws.on('close', () => resolve());
      ws.close();
    });
  }, 15000);
});
