import { serve, ServerInstance } from '../src/serve';
import fs from 'fs';
import path from 'path';
import http from 'http';
import WebSocket from 'ws';

const testBase = path.join(__dirname, 'serve-integration');
const contentDir = path.join(testBase, 'content');
const outputDir = path.join(testBase, 'dist');
const templatesDir = path.join(testBase, 'templates');

function httpGet(url: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let body = '';
      res.on('data', (chunk: Buffer) => { body += chunk.toString(); });
      res.on('end', () => resolve({ status: res.statusCode || 0, body }));
    }).on('error', reject);
  });
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function createContentFile(name: string, body: string) {
  fs.writeFileSync(path.join(contentDir, name), body, 'utf-8');
}

describe('serve', () => {
  let instance: ServerInstance | null = null;
  let baseUrl: string = '';

  beforeEach(() => {
    if (fs.existsSync(testBase)) {
      fs.rmSync(testBase, { recursive: true, force: true });
    }
    fs.mkdirSync(contentDir, { recursive: true });
  });

  afterEach(async () => {
    if (instance) {
      try {
        await instance.close();
      } catch {
        // ignore
      }
      instance = null;
    }
    try {
      if (fs.existsSync(testBase)) {
        fs.rmSync(testBase, { recursive: true, force: true });
      }
    } catch {
      // ignore
    }
  }, 15000);

  async function startServer(opts?: { port?: number; templatesDir?: string }) {
    const port = opts?.port || 0;
    instance = serve({
      contentDir,
      outputDir,
      templatesDir: opts?.templatesDir,
      port,
    });
    await instance.ready;
    const addr = instance.server.address();
    if (addr && typeof addr === 'object') {
      baseUrl = `http://localhost:${addr.port}`;
    }
  }

  it('serves HTML files from the output directory', async () => {
    createContentFile('hello.md', `---
title: Hello World
---
# Hello

Content here.`);

    await startServer();

    const { status, body } = await httpGet(`${baseUrl}/hello.html`);
    expect(status).toBe(200);
    expect(body).toContain('<title>Hello World</title>');
    expect(body).toContain('<h1>Hello</h1>');
    expect(body).toContain('Content here.');
  });

  it('serves index.html at /', async () => {
    createContentFile('post.md', `---
title: Test Post
---
Post content`);

    await startServer();

    const { status, body } = await httpGet(`${baseUrl}/`);
    expect(status).toBe(200);
    expect(body).toContain('<title>Index</title>');
    expect(body).toContain('All Pages');
  });

  it('injects live-reload script into HTML responses', async () => {
    createContentFile('page.md', `---
title: Injected Page
---
Some content`);

    await startServer();

    const { body } = await httpGet(`${baseUrl}/page.html`);
    expect(body).toContain("new WebSocket('ws://'+location.host+'/__ssg_livereload')");
    expect(body).toContain("location.reload()");
  });

  it('does not inject script into non-HTML responses', async () => {
    createContentFile('page.md', `---
title: Page
---
Content`);

    await startServer();

    const cssContent = 'body { color: red; }';
    fs.writeFileSync(path.join(outputDir, 'styles.css'), cssContent, 'utf-8');

    const { body } = await httpGet(`${baseUrl}/styles.css`);
    expect(body).toBe(cssContent);
    expect(body).not.toContain('__ssg_livereload');
  });

  it('returns 404 for missing files', async () => {
    createContentFile('page.md', `---
title: Page
---
Content`);

    await startServer();

    const { status } = await httpGet(`${baseUrl}/nonexistent.html`);
    expect(status).toBe(404);
  });

  it('returns 404 for missing directory index', async () => {
    createContentFile('page.md', `---
title: Page
---
Content`);

    await startServer();

    const { status } = await httpGet(`${baseUrl}/nope/`);
    expect(status).toBe(404);
  });

  it('WebSocket connection is established', async () => {
    createContentFile('page.md', `---
title: Page
---
Content`);

    await startServer();

    const addr = instance!.server.address();
    const port = typeof addr === 'object' && addr ? addr.port : 0;

    const ws = new WebSocket(`ws://localhost:${port}/__ssg_livereload`);
    await new Promise<void>((resolve, reject) => {
      ws.on('open', resolve);
      ws.on('error', reject);
      setTimeout(() => reject(new Error('WebSocket connection timeout')), 3000);
    });

    expect(ws.readyState).toBe(WebSocket.OPEN);
    ws.close();
  });

  it('sends reload message on content file change', async () => {
    createContentFile('alpha.md', `---
title: Alpha
---
Alpha content`);

    await startServer();

    const addr = instance!.server.address();
    const port = typeof addr === 'object' && addr ? addr.port : 0;

    const ws = new WebSocket(`ws://localhost:${port}/__ssg_livereload`);

    await new Promise<void>((resolve, reject) => {
      ws.on('open', resolve);
      ws.on('error', reject);
      setTimeout(() => reject(new Error('WebSocket connection timeout')), 3000);
    });

    const messagePromise = new Promise<string>((resolve, reject) => {
      ws.on('message', (data) => resolve(data.toString()));
      ws.on('error', reject);
      setTimeout(() => reject(new Error('No reload message received')), 15000);
    });

    createContentFile('beta.md', `---
title: Beta
---
Beta content`);

    const msg = await messagePromise;
    expect(msg).toBe('reload');

    ws.close();
  }, 20000);

  it('rebuilds dist on content change', async () => {
    createContentFile('first.md', `---
title: First
---
First content`);

    await startServer();

    const firstPath = path.join(outputDir, 'first.html');
    expect(fs.existsSync(firstPath)).toBe(true);

    const secondPath = path.join(outputDir, 'second.html');
    expect(fs.existsSync(secondPath)).toBe(false);

    createContentFile('second.md', `---
title: Second
---
Second content`);

    let exists = false;
    for (let i = 0; i < 20; i++) {
      await wait(500);
      if (fs.existsSync(secondPath)) {
        exists = true;
        break;
      }
    }

    expect(exists).toBe(true);
    const html = fs.readFileSync(secondPath, 'utf-8');
    expect(html).toContain('Second');
  }, 30000);

  it('serves on the specified port', async () => {
    createContentFile('page.md', `---
title: Custom Port
---
Content`);

    await startServer({ port: 0 });

    const addr = instance!.server.address();
    const port = typeof addr === 'object' && addr ? addr.port : 0;
    expect(port).toBeGreaterThan(0);

    const { status, body } = await httpGet(`http://localhost:${port}/page.html`);
    expect(status).toBe(200);
    expect(body).toContain('Custom Port');
  });

  it('serves with templates directory', async () => {
    createContentFile('tpl.md', `---
title: Templated
---
Content`);

    fs.mkdirSync(templatesDir, { recursive: true });

    await startServer({ templatesDir });

    const { status, body } = await httpGet(`${baseUrl}/tpl.html`);
    expect(status).toBe(200);
    expect(body).toContain('Templated');
  });

  it('injects live-reload script into index.html', async () => {
    createContentFile('page.md', `---
title: Index Test
---
Content`);

    await startServer();

    const { body } = await httpGet(`${baseUrl}/`);
    expect(body).toContain("new WebSocket('ws://'+location.host+'/__ssg_livereload')");
  });
});
