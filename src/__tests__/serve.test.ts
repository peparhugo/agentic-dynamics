import fs from 'fs/promises';
import http from 'http';
import os from 'os';
import path from 'path';
import { WebSocket } from 'ws';
import {
  DevServer,
  injectLiveReloadScript,
  liveReloadClientScript,
  startDevServer,
} from '../serve';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-serve-'));
}

async function write(filePath: string, content: string): Promise<void> {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, content, 'utf-8');
}

async function get(url: string): Promise<{ status: number; text: string }> {
  const res = await fetch(url);
  const text = await res.text();
  return { status: res.status, text };
}

function waitForRebuild(server: DevServer): Promise<void> {
  return new Promise((resolve) => {
    server.onRebuild(() => resolve());
  });
}

interface Fixture {
  root: string;
  contentDir: string;
  outputDir: string;
  templateDir: string;
}

async function makeFixture(): Promise<Fixture> {
  const root = await makeTempDir();
  const contentDir = path.join(root, 'content');
  const outputDir = path.join(root, 'dist');
  const templateDir = path.join(root, 'templates');

  await write(
    path.join(contentDir, 'hello.md'),
    `---
title: Hello World
---
# Hello
Welcome **everyone**.
`
  );
  await write(
    path.join(templateDir, 'default.hbs'),
    '<article><h1>{{title}}</h1>{{{body}}}</article>'
  );
  await write(
    path.join(templateDir, 'layouts', 'default.hbs'),
    '<!DOCTYPE html><html><body><main>{{{body}}}</main></body></html>'
  );

  return { root, contentDir, outputDir, templateDir };
}

describe('injectLiveReloadScript', () => {
  it('injects the client script before the closing body tag', () => {
    const html = '<!DOCTYPE html><html><body><p>hi</p></body></html>';
    const result = injectLiveReloadScript(html);
    expect(result).toContain('/__ssg_ws');
    expect(result).toContain('location.reload()');
    expect(result.indexOf('<p>hi</p>')).toBeLessThan(
      result.indexOf('<script>')
    );
    expect(result.indexOf('<script>')).toBeLessThan(
      result.indexOf('</body>')
    );
  });

  it('appends the script when there is no body tag', () => {
    const result = injectLiveReloadScript('<html><p>raw</p></html>');
    expect(result.endsWith('</script>')).toBe(true);
    expect(result).toContain('/__ssg_ws');
  });

  it('builds a client that reloads on a reload message', () => {
    const script = liveReloadClientScript();
    expect(script).toContain('/__ssg_ws');
    expect(script).toContain('new WebSocket');
    expect(script).toContain("message.type === 'reload'");
  });
});

describe('startDevServer', () => {
  let server: DevServer | undefined;

  afterEach(async () => {
    if (server) {
      await server.close();
      server = undefined;
    }
  });

  async function start(): Promise<DevServer> {
    const fixture = await makeFixture();
    server = await startDevServer({
      contentDir: fixture.contentDir,
      outputDir: fixture.outputDir,
      templateDir: fixture.templateDir,
      port: 0,
      host: '127.0.0.1',
    });
    (server as DevServer & { fixture: Fixture }).fixture = fixture;
    return server;
  }

  it('builds the site and serves it from the output directory', async () => {
    const devServer = await start();
    const fixture = (devServer as DevServer & { fixture: Fixture }).fixture;
    const base = `http://127.0.0.1:${devServer.port}`;

    const index = await get(`${base}/`);
    expect(index.status).toBe(200);
    expect(index.text).toContain('Hello World');
    expect(index.text).toContain('href="hello.html"');

    const page = await get(`${base}/hello.html`);
    expect(page.status).toBe(200);
    expect(page.text).toContain('<h1>Hello World</h1>');
    expect(page.text).toContain('<strong>everyone</strong>');
    expect(page.text).toContain('/__ssg_ws');

    expect(
      await fs.stat(path.join(fixture.outputDir, 'index.html'))
    ).toBeTruthy();
  });

  it('returns 404 for missing files', async () => {
    const devServer = await start();
    const res = await get(`http://127.0.0.1:${devServer.port}/nope.html`);
    expect(res.status).toBe(404);
  });

  it('rebuilds and serves fresh content after a markdown change', async () => {
    const devServer = await start();
    const fixture = (devServer as DevServer & { fixture: Fixture }).fixture;
    const base = `http://127.0.0.1:${devServer.port}`;

    const before = await get(`${base}/hello.html`);
    expect(before.text).toContain('Welcome');

    const rebuilt = waitForRebuild(devServer);
    await write(
      path.join(fixture.contentDir, 'hello.md'),
      `---
title: Hello Updated
---
# Hello
Fresh **content** here.
`
    );
    await rebuilt;

    const after = await get(`${base}/hello.html`);
    expect(after.text).toContain('Hello Updated');
    expect(after.text).toContain('<strong>content</strong>');
    expect(after.text).not.toContain('everyone');
  });

  it('rebuilds when a template file changes', async () => {
    const devServer = await start();
    const fixture = (devServer as DevServer & { fixture: Fixture }).fixture;
    const base = `http://127.0.0.1:${devServer.port}`;

    const before = await get(`${base}/hello.html`);
    expect(before.text).toContain('<article>');

    const rebuilt = waitForRebuild(devServer);
    await write(
      path.join(fixture.templateDir, 'default.hbs'),
      '<section class="new"><h1>{{title}}</h1>{{{body}}}</section>'
    );
    await rebuilt;

    const after = await get(`${base}/hello.html`);
    expect(after.text).toContain('<section class="new">');
    expect(after.text).not.toContain('<article>');
  });

  it('broadcasts a reload message to connected websocket clients', async () => {
    const devServer = await start();
    const fixture = (devServer as DevServer & { fixture: Fixture }).fixture;

    const ws = new WebSocket(`ws://127.0.0.1:${devServer.port}/__ssg_ws`);
    await new Promise<void>((resolve, reject) => {
      ws.on('open', () => resolve());
      ws.on('error', reject);
    });

    const received = new Promise<string>((resolve) => {
      ws.on('message', (data) => resolve(String(data)));
    });

    await write(
      path.join(fixture.contentDir, 'hello.md'),
      '---\ntitle: Reloaded\n---\n# Reloaded\nBoom.\n'
    );

    const message = await received;
    expect(JSON.parse(message).type).toBe('reload');
    ws.close();
  });

  it('honors a custom port', async () => {
    const fixture = await makeFixture();
    server = await startDevServer({
      contentDir: fixture.contentDir,
      outputDir: fixture.outputDir,
      templateDir: fixture.templateDir,
      port: 0,
      host: '127.0.0.1',
    });
    expect(server.port).toBeGreaterThan(0);

    const res = await get(`http://127.0.0.1:${server.port}/hello.html`);
    expect(res.status).toBe(200);
  });

  it('does not leak output directory changes into rebuilds', async () => {
    const devServer = await start();
    const fixture = (devServer as DevServer & { fixture: Fixture }).fixture;
    const base = `http://127.0.0.1:${devServer.port}`;

    const before = await get(`${base}/hello.html`);
    expect(before.text).toContain('Welcome');

    let rebuilt = false;
    devServer.onRebuild(() => {
      rebuilt = true;
    });

    const pageBefore = await get(`${base}/hello.html`);
    expect(pageBefore.text).toContain('/__ssg_ws');

    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(rebuilt).toBe(false);

    const after = await get(`${base}/hello.html`);
    expect(after.text).toContain('Welcome');
  });
});

describe('serve HTTP edge cases', () => {
  it('blocks path traversal outside the output directory', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templateDir = path.join(root, 'templates');
    await write(path.join(contentDir, 'a.md'), '---\ntitle: A\n---\nBody');
    await write(path.join(templateDir, 'default.hbs'), '{{title}}');

    const devServer = await startDevServer({
      contentDir,
      outputDir,
      templateDir,
      port: 0,
      host: '127.0.0.1',
    });

    try {
      const res = await get(
        `http://127.0.0.1:${devServer.port}/..%2fsecret.html`
      );
      expect(res.status).toBe(403);
    } finally {
      await devServer.close();
    }
  });

  it('serves css assets with the right content type', async () => {
    const root = await makeTempDir();
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templateDir = path.join(root, 'templates');
    await write(path.join(contentDir, 'a.md'), '---\ntitle: A\n---\nBody');
    await write(path.join(templateDir, 'default.hbs'), '{{title}}');

    const devServer = await startDevServer({
      contentDir,
      outputDir,
      templateDir,
      port: 0,
      host: '127.0.0.1',
    });

    await write(path.join(outputDir, 'style.css'), 'body { color: red; }');

    try {
      const res: http.IncomingMessage = await new Promise((resolve, reject) => {
        http.get(`http://127.0.0.1:${devServer.port}/style.css`, (response) =>
          resolve(response)
        );
      });
      expect(res.statusCode).toBe(200);
      expect(res.headers['content-type']).toContain('text/css');
      const body = await new Promise<string>((resolve) => {
        let data = '';
        res.on('data', (chunk: Buffer) => {
          data += chunk.toString();
        });
        res.on('end', () => resolve(data));
      });
      expect(body).toContain('color: red');
    } finally {
      await devServer.close();
    }
  });
});
