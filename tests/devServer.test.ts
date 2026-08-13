import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import WebSocket from 'ws';
import { DevServer, injectLiveReload, startDevServer } from '../src/devServer';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function waitForOpen(ws: WebSocket): Promise<void> {
  return new Promise((resolve, reject) => {
    ws.once('open', () => resolve());
    ws.once('error', reject);
  });
}

function waitForReload(ws: WebSocket): Promise<void> {
  return new Promise((resolve) => {
    ws.on('message', (data) => {
      if (data.toString() === 'reload') resolve();
    });
  });
}

describe('injectLiveReload', () => {
  it('inserts the script before a closing </body> tag', () => {
    const html = '<html><body><p>hi</p></body></html>';
    const result = injectLiveReload(html);
    expect(result.indexOf('<script>')).toBeLessThan(result.indexOf('</body>'));
    expect(result).toContain('WebSocket');
    expect(result).toContain('__livereload');
  });

  it('appends the script when there is no </body> tag', () => {
    const html = '<p>fragment</p>';
    const result = injectLiveReload(html);
    expect(result.startsWith(html)).toBe(true);
    expect(result).toContain('<script>');
  });
});

describe('startDevServer', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;
  let server: DevServer | undefined;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-dev-content-');
    outputDir = makeTmpDir('ssg-dev-output-');
    templatesDir = makeTmpDir('ssg-dev-templates-');
    fs.writeFileSync(
      path.join(contentDir, 'page.md'),
      '---\ntitle: Dev Page\n---\nHello dev server'
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

  it('builds the site up front and serves pages with the live-reload script injected', async () => {
    server = await startDevServer({ contentDir, outputDir, templatesDir, port: 0 });

    expect(fs.existsSync(path.join(outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(outputDir, 'page.html'))).toBe(true);

    const res = await fetch(`http://localhost:${server.port}/page.html`);
    const html = await res.text();

    expect(res.status).toBe(200);
    expect(html).toContain('Dev Page');
    expect(html).toContain('__livereload');
  });

  it('serves non-HTML assets unmodified with the correct content type', async () => {
    server = await startDevServer({ contentDir, outputDir, templatesDir, port: 0 });

    const res = await fetch(`http://localhost:${server.port}/style.css`);
    const css = await res.text();

    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain('text/css');
    expect(css).not.toContain('__livereload');
  });

  it('returns 404 for missing files', async () => {
    server = await startDevServer({ contentDir, outputDir, templatesDir, port: 0 });

    const res = await fetch(`http://localhost:${server.port}/does-not-exist.html`);
    expect(res.status).toBe(404);
  });

  it('rebuilds and notifies connected clients when a content file changes', async () => {
    server = await startDevServer({ contentDir, outputDir, templatesDir, port: 0 });

    const ws = new WebSocket(`ws://localhost:${server.port}/__livereload`);
    await waitForOpen(ws);
    const reloaded = waitForReload(ws);

    fs.writeFileSync(
      path.join(contentDir, 'new-page.md'),
      '---\ntitle: New Page\n---\nBrand new content'
    );

    await reloaded;

    expect(fs.existsSync(path.join(outputDir, 'new-page.html'))).toBe(true);
    ws.close();
  }, 10000);

  it('rebuilds when a template file changes', async () => {
    fs.mkdirSync(path.join(templatesDir, 'layouts'), { recursive: true });
    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<div class="v1">{{{body}}}</div>'
    );

    server = await startDevServer({ contentDir, outputDir, templatesDir, port: 0 });

    const initialHtml = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(initialHtml).toContain('class="v1"');

    const ws = new WebSocket(`ws://localhost:${server.port}/__livereload`);
    await waitForOpen(ws);
    const reloaded = waitForReload(ws);

    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<div class="v2">{{{body}}}</div>'
    );

    await reloaded;

    const updatedHtml = fs.readFileSync(path.join(outputDir, 'page.html'), 'utf-8');
    expect(updatedHtml).toContain('class="v2"');
    ws.close();
  }, 10000);
});
