import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import WebSocket from 'ws';
import { serve } from '../src/serve';
import type { ServeHandle } from '../src/serve';

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

function waitForMessage(socket: WebSocket): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Timed out waiting for WebSocket message')), 5000);
    socket.once('message', (data) => {
      clearTimeout(timer);
      resolve(data.toString());
    });
  });
}

function waitForOpen(socket: WebSocket): Promise<void> {
  return new Promise((resolve, reject) => {
    socket.once('open', () => resolve());
    socket.once('error', reject);
  });
}

describe('serve', () => {
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;
  let handle: ServeHandle | undefined;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-serve-content-');
    outputDir = makeTempDir('ssg-serve-output-');
    templatesDir = makeTempDir('ssg-serve-templates-');

    writeFile(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );

    writeFile(
      path.join(contentDir, 'hello.md'),
      `---
title: Hello
---
Hello world.
`
    );
  });

  afterEach(async () => {
    if (handle) {
      await handle.close();
      handle = undefined;
    }
    fs.rmSync(contentDir, { recursive: true, force: true });
    fs.rmSync(outputDir, { recursive: true, force: true });
    fs.rmSync(templatesDir, { recursive: true, force: true });
  });

  it('builds the site up front and serves pages with a live-reload script injected', async () => {
    handle = await serve({ contentDir, outputDir, templatesDir, port: 0 });

    expect(fs.existsSync(path.join(outputDir, 'hello.html'))).toBe(true);

    const res = await fetch(`${handle.url}/hello.html`);
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain('Hello world.');
    expect(html).toContain('__livereload');
    expect(html).toContain('WebSocket');
  });

  it('serves the index page at the root path', async () => {
    handle = await serve({ contentDir, outputDir, templatesDir, port: 0 });

    const res = await fetch(`${handle.url}/`);
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain('hello.html');
  });

  it('returns 404 for unknown paths', async () => {
    handle = await serve({ contentDir, outputDir, templatesDir, port: 0 });

    const res = await fetch(`${handle.url}/does-not-exist.html`);
    expect(res.status).toBe(404);
  });

  it('rebuilds and pushes a reload message over WebSocket when a content file changes', async () => {
    handle = await serve({ contentDir, outputDir, templatesDir, port: 0, debounceMs: 20 });

    const socket = new WebSocket(`ws://localhost:${handle.port}/__livereload`);
    await waitForOpen(socket);

    const reloadPromise = waitForMessage(socket);

    fs.writeFileSync(
      path.join(contentDir, 'hello.md'),
      `---
title: Hello
---
Hello again, updated.
`
    );

    const message = await reloadPromise;
    expect(message).toBe('reload');

    const rebuiltHtml = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf8');
    expect(rebuiltHtml).toContain('Hello again, updated.');

    socket.close();
  });

  it('rebuilds when a template file changes', async () => {
    handle = await serve({ contentDir, outputDir, templatesDir, port: 0, debounceMs: 20 });

    const socket = new WebSocket(`ws://localhost:${handle.port}/__livereload`);
    await waitForOpen(socket);

    const reloadPromise = waitForMessage(socket);

    fs.writeFileSync(
      path.join(templatesDir, 'layouts', 'default.hbs'),
      '<!DOCTYPE html><html data-marker="updated"><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
    );

    await reloadPromise;

    const rebuiltHtml = fs.readFileSync(path.join(outputDir, 'hello.html'), 'utf8');
    expect(rebuiltHtml).toContain('data-marker="updated"');

    socket.close();
  });
});
