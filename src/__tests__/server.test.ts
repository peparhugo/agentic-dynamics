import http from 'http';
import fs from 'fs';
import path from 'path';
import os from 'os';
import WebSocket from 'ws';
import { startDevServer, DevServer } from '../server';

function setupContentDir(files: Record<string, string>): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-test-'));
  for (const [name, content] of Object.entries(files)) {
    fs.writeFileSync(path.join(dir, name), content, 'utf-8');
  }
  return dir;
}

function httpGet(url: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http
      .get(url, (res) => {
        let body = '';
        res.on('data', (chunk: Buffer) => {
          body += chunk.toString();
        });
        res.on('end', () =>
          resolve({ status: res.statusCode || 0, body }),
        );
      })
      .on('error', reject);
  });
}

function waitForSocketOpen(ws: WebSocket, timeout = 3000): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error('WebSocket connection timeout')),
      timeout,
    );
    ws.on('open', () => {
      clearTimeout(timer);
      resolve();
    });
    ws.on('error', (err: Error) => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

function waitForMessage(
  ws: WebSocket,
  timeout = 8000,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error('Timeout waiting for reload message')),
      timeout,
    );
    ws.on('message', (data: Buffer) => {
      clearTimeout(timer);
      resolve(data.toString());
    });
  });
}

describe('serve command', () => {
  let server: DevServer | null = null;
  let contentDir: string;
  let outputDir: string;

  afterEach(async () => {
    if (server) {
      try {
        await server.close();
      } catch {
        // ignore
      }
      server = null;
    }
    if (outputDir) {
      try {
        fs.rmSync(outputDir, { recursive: true, force: true });
      } catch {
        // ignore
      }
    }
    if (contentDir) {
      try {
        fs.rmSync(contentDir, { recursive: true, force: true });
      } catch {
        // ignore
      }
    }
  });

  async function startServer(
    contentFiles: Record<string, string>,
    extraOpts: Record<string, unknown> = {},
  ): Promise<DevServer> {
    contentDir = setupContentDir(contentFiles);
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-output-'));
    server = await startDevServer({
      content: contentDir,
      output: outputDir,
      templates: '/nonexistent/templates',
      port: 0,
      ...extraOpts,
    });
    return server;
  }

  test('serves index.html and injects live reload script', async () => {
    const server = await startServer({
      'hello.md': `---
title: Hello World
date: 2024-01-01
---
# Hello
`,
    });

    const { status, body } = await httpGet(
      `http://localhost:${server.port}/`,
    );
    expect(status).toBe(200);
    expect(body).toContain('Hello World');
    expect(body).toContain('new WebSocket');
    expect(body).toContain('location.reload');
  });

  test('serves page HTML and injects live reload script', async () => {
    const server = await startServer({
      'hello.md': `---
title: Hello World
date: 2024-01-01
---
# Hello
`,
    });

    const { status, body } = await httpGet(
      `http://localhost:${server.port}/hello.html`,
    );
    expect(status).toBe(200);
    expect(body).toContain('<title>Hello World</title>');
    expect(body).toContain('new WebSocket');
  });

  test('returns 404 for nonexistent file', async () => {
    const server = await startServer({
      'hello.md': `---
title: Hello
date: 2024-01-01
---
# Hello
`,
    });

    const { status } = await httpGet(
      `http://localhost:${server.port}/nonexistent.html`,
    );
    expect(status).toBe(404);
  });

  test('sends reload message on file change via WebSocket', async () => {
    const server = await startServer({
      'hello.md': `---
title: Hello
date: 2024-01-01
---
# Hello
`,
    });

    const ws = new WebSocket(`ws://localhost:${server.port}`);
    await waitForSocketOpen(ws);

    const reloadPromise = waitForMessage(ws, 5000);

    fs.writeFileSync(
      path.join(contentDir, 'hello.md'),
      `---
title: Updated Title
date: 2024-01-01
---
# Updated Content
`,
    );

    const message = await reloadPromise;
    expect(message).toBe('reload');

    const { body } = await httpGet(
      `http://localhost:${server.port}/hello.html`,
    );
    expect(body).toContain('Updated Title');

    ws.close();
  }, 10000);

  test('rebuilds on new file added', async () => {
    const server = await startServer({
      'hello.md': `---
title: Hello
date: 2024-01-01
---
# Hello
`,
    });

    const ws = new WebSocket(`ws://localhost:${server.port}`);
    await waitForSocketOpen(ws);

    const reloadPromise = waitForMessage(ws, 5000);

    fs.writeFileSync(
      path.join(contentDir, 'newpost.md'),
      `---
title: New Post
date: 2024-06-01
---
# New
`,
    );

    const message = await reloadPromise;
    expect(message).toBe('reload');

    const { body } = await httpGet(
      `http://localhost:${server.port}/`,
    );
    expect(body).toContain('New Post');

    ws.close();
  }, 10000);

  test('uses custom port from --port option', async () => {
    contentDir = setupContentDir({
      'hello.md': `---
title: Hello
date: 2024-01-01
---
# Hello
`,
    });
    outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-output-'));

    server = await startDevServer({
      content: contentDir,
      output: outputDir,
      templates: '/nonexistent/templates',
      port: 51235,
    });

    expect(server.port).toBe(51235);

    const { status, body } = await httpGet(
      `http://localhost:${server.port}/`,
    );
    expect(status).toBe(200);
    expect(body).toContain('Hello');
  });

  test('does not inject live reload script into non-HTML files', async () => {
    const server = await startServer({
      'hello.md': `---
title: Hello World
date: 2024-01-01
---
# Hello
`,
    });

    const { body } = await httpGet(
      `http://localhost:${server.port}/hello.html`,
    );
    expect(body).toContain('new WebSocket');

    const { status } = await httpGet(
      `http://localhost:${server.port}/nonexistent.css`,
    );
    expect(status).toBe(404);
  });

  test('handles empty content directory', async () => {
    const server = await startServer({});

    const { status, body } = await httpGet(
      `http://localhost:${server.port}/`,
    );
    expect(status).toBe(200);
    expect(body).toContain('new WebSocket');
  });

  test('serves root path as index.html', async () => {
    const server = await startServer({
      'hello.md': `---
title: Hello
date: 2024-01-01
---
# Hello
`,
    });

    const { status, body } = await httpGet(
      `http://localhost:${server.port}/`,
    );
    expect(status).toBe(200);
    expect(body).toContain('Hello');
    expect(body).toContain('<a href="hello.html">Hello</a>');
  });

  test('falls back to index.html on unknown path', async () => {
    const server = await startServer({
      'hello.md': `---
title: Hello
date: 2024-01-01
---
# Hello
`,
    });

    const { status, body } = await httpGet(
      `http://localhost:${server.port}/unknown/path`,
    );
    expect(status).toBe(200);
    expect(body).toContain('Hello');
    expect(body).toContain('new WebSocket');
  });

  test('sends reload on file deletion', async () => {
    const server = await startServer({
      'hello.md': `---
title: Hello
date: 2024-01-01
---
# Hello
`,
      'goodbye.md': `---
title: Goodbye
date: 2024-01-02
---
# Goodbye
`,
    });

    const ws = new WebSocket(`ws://localhost:${server.port}`);
    await waitForSocketOpen(ws);

    const reloadPromise = waitForMessage(ws, 5000);

    fs.unlinkSync(path.join(contentDir, 'goodbye.md'));

    const message = await reloadPromise;
    expect(message).toBe('reload');

    ws.close();
  }, 10000);
});
