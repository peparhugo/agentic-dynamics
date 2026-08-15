import * as fs from 'fs';
import * as http from 'http';
import * as os from 'os';
import * as path from 'path';
import WebSocket from 'ws';
import { DevServer, injectLiveReload, startDevServer } from './serve';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function get(url: string): Promise<{ statusCode: number; body: string }> {
  return new Promise((resolve, reject) => {
    http
      .get(url, (res) => {
        let body = '';
        res.on('data', (chunk) => {
          body += chunk;
        });
        res.on('end', () => resolve({ statusCode: res.statusCode ?? 0, body }));
      })
      .on('error', reject);
  });
}

describe('injectLiveReload', () => {
  it('injects the reload script before </body>', () => {
    const html = '<html><body><h1>Hi</h1></body></html>';
    const result = injectLiveReload(html);

    expect(result).toContain('__livereload');
    expect(result.indexOf('<script>')).toBeLessThan(result.indexOf('</body>'));
  });

  it('appends the reload script when there is no </body> tag', () => {
    const html = '<h1>Hi</h1>';
    const result = injectLiveReload(html);

    expect(result.startsWith(html)).toBe(true);
    expect(result).toContain('__livereload');
  });
});

describe('dev server', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;
  let server: DevServer | undefined;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-serve-content-');
    outputDir = makeTmpDir('ssg-serve-output-');
    templatesDir = makeTmpDir('ssg-serve-templates-');
    fs.writeFileSync(path.join(contentDir, 'page.md'), '---\ntitle: Hello\n---\n\nHello world.');
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

  it('builds the site up front and serves pages with the live-reload script injected', async () => {
    server = await startDevServer({ contentDir, outputDir, templatesDir, port: 0 });

    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);

    const indexRes = await get(`${server.url}/`);
    expect(indexRes.statusCode).toBe(200);
    expect(indexRes.body).toContain('__livereload');

    const pageRes = await get(`${server.url}/page.html`);
    expect(pageRes.statusCode).toBe(200);
    expect(pageRes.body).toContain('Hello world.');
    expect(pageRes.body).toContain('__livereload');
  });

  it('returns 404 for a missing file', async () => {
    server = await startDevServer({ contentDir, outputDir, templatesDir, port: 0 });

    const res = await get(`${server.url}/does-not-exist.html`);
    expect(res.statusCode).toBe(404);
  });

  it('rebuilds and notifies connected WebSocket clients when a content file changes', async () => {
    server = await startDevServer({ contentDir, outputDir, templatesDir, port: 0 });

    const ws = new WebSocket(`ws://localhost:${server.port}/__livereload`);
    await new Promise<void>((resolve, reject) => {
      ws.once('open', () => resolve());
      ws.once('error', reject);
    });

    const reloadMessage = new Promise<string>((resolve) => {
      ws.once('message', (data) => resolve(data.toString()));
    });

    fs.writeFileSync(path.join(contentDir, 'page.md'), '---\ntitle: Hello\n---\n\nUpdated content.');

    expect(await reloadMessage).toBe('reload');

    const pageRes = await get(`${server.url}/page.html`);
    expect(pageRes.body).toContain('Updated content.');

    ws.close();
  }, 10000);
});
