import http from 'http';
import fs from 'fs';
import path from 'path';
import os from 'os';
import WebSocket from 'ws';
import { serve, ServeInstance } from '../src/serve';

function makeTempDir(prefix: string): string {
  const dir = path.join(os.tmpdir(), `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function cleanup(dir: string) {
  if (fs.existsSync(dir)) {
    fs.rmSync(dir, { recursive: true });
  }
}

function closeServer(instance: ServeInstance) {
  return new Promise<void>((resolve) => {
    instance.watcher.close().then(() => {
      instance.wss.clients.forEach((client) => client.terminate());
      instance.wss.close(() => {
        instance.server.close(() => {
          // wait for ws server to fully close
          setTimeout(resolve, 50);
        });
      });
    });
  });
}

function waitForServer(port: number, timeout = 3000): Promise<void> {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    function tryConnect() {
      const req = http.get(`http://localhost:${port}/`, (res) => {
        res.resume();
        resolve();
      });
      req.on('error', () => {
        if (Date.now() - start > timeout) {
          reject(new Error('Server did not start within timeout'));
        } else {
          setTimeout(tryConnect, 50);
        }
      });
      req.end();
    }
    tryConnect();
  });
}

function httpGet(url: string): Promise<{ status: number; body: string; headers: http.IncomingHttpHeaders }> {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let body = '';
      res.on('data', (chunk) => (body += chunk));
      res.on('end', () => resolve({ status: res.statusCode || 0, body, headers: res.headers }));
    }).on('error', reject);
  });
}

function getRandomPort(): number {
  return 10000 + Math.floor(Math.random() * 50000);
}

describe('SSG dev server', () => {
  let contentDir: string;
  let outputDir: string;
  let instance: ServeInstance | null;
  let port: number;

  beforeEach(() => {
    contentDir = makeTempDir('ssg-serve-content');
    outputDir = makeTempDir('ssg-serve-output');
    port = getRandomPort();
    instance = null;
  });

  afterEach(async () => {
    if (instance) {
      await closeServer(instance);
    }
    cleanup(contentDir);
    cleanup(outputDir);
  });

  test('serves HTML files from output directory', async () => {
    fs.writeFileSync(path.join(contentDir, 'test.md'), `---
title: Hello
---
Test page content.`);

    instance = serve({ contentDir, outputDir, port });
    await waitForServer(port);

    const res = await httpGet(`http://localhost:${port}/test.html`);
    expect(res.status).toBe(200);
    expect(res.body).toContain('<title>Hello</title>');
    expect(res.body).toContain('Test page content.');
  });

  test('serves index.html at root path', async () => {
    fs.writeFileSync(path.join(contentDir, 'test.md'), `---
title: Hello
---
Test page content.`);

    instance = serve({ contentDir, outputDir, port });
    await waitForServer(port);

    const res = await httpGet(`http://localhost:${port}/`);
    expect(res.status).toBe(200);
    expect(res.body).toContain('Hello');
    expect(res.body).toContain('Pages');
  });

  test('injects live reload script into HTML', async () => {
    fs.writeFileSync(path.join(contentDir, 'test.md'), `---
title: Hello
---
Test content.`);

    instance = serve({ contentDir, outputDir, port });
    await waitForServer(port);

    const res = await httpGet(`http://localhost:${port}/test.html`);
    expect(res.status).toBe(200);
    expect(res.body).toContain('WebSocket');
    expect(res.body).toContain("ws://'+location.host");
  });

  test('returns 404 for non-existent files', async () => {
    fs.writeFileSync(path.join(contentDir, 'test.md'), `---
title: Hello
---
Test content.`);

    instance = serve({ contentDir, outputDir, port });
    await waitForServer(port);

    const res = await httpGet(`http://localhost:${port}/nonexistent.html`);
    expect(res.status).toBe(404);
  });

  test('uses custom port via --port option', async () => {
    const customPort = getRandomPort();
    fs.writeFileSync(path.join(contentDir, 'test.md'), `---
title: Hello
---
Test content.`);

    instance = serve({ contentDir, outputDir, port: customPort });
    await waitForServer(customPort);

    const res = await httpGet(`http://localhost:${customPort}/test.html`);
    expect(res.status).toBe(200);
    expect(res.body).toContain('Hello');
  });

  test('rebuilds on file change', async () => {
    fs.writeFileSync(path.join(contentDir, 'test.md'), `---
title: Before
---
Original content.`);

    instance = serve({ contentDir, outputDir, port });
    await waitForServer(port);

    const res1 = await httpGet(`http://localhost:${port}/test.html`);
    expect(res1.body).toContain('Original content.');

    // Modify the file
    fs.writeFileSync(path.join(contentDir, 'test.md'), `---
title: After
---
Updated content.`);

    // Wait for rebuild
    const start = Date.now();
    let updated = false;
    while (Date.now() - start < 5000) {
      const res = await httpGet(`http://localhost:${port}/test.html`);
      if (res.body.includes('Updated content.')) {
        updated = true;
        break;
      }
      await new Promise((r) => setTimeout(r, 200));
    }
    expect(updated).toBe(true);
  });

  test('handles missing content directory gracefully', async () => {
    const nonexistent = path.join(os.tmpdir(), 'ssg-nonexistent-' + Date.now());

    instance = serve({ contentDir: nonexistent, outputDir, port });
    await waitForServer(port);

    const res = await httpGet(`http://localhost:${port}/`);
    expect(res.status).toBe(200);

    cleanup(nonexistent);
  });

  test('serves HTML content type correctly', async () => {
    fs.writeFileSync(path.join(contentDir, 'test.md'), `---
title: Hello
---
Test.`);

    instance = serve({ contentDir, outputDir, port });
    await waitForServer(port);

    const res = await httpGet(`http://localhost:${port}/test.html`);

    // Handle both cases - sometimes content-type includes charset, sometimes not
    const contentType = (res.headers['content-type'] || '').toLowerCase();
    expect(contentType).toContain('text/html');
  });

  test('WebSocket sends reload message on rebuild', async () => {
    fs.writeFileSync(path.join(contentDir, 'test.md'), `---
title: Before
---
Original content.`);

    instance = serve({ contentDir, outputDir, port });
    await waitForServer(port);

    // Connect WebSocket client
    const ws = new WebSocket(`ws://localhost:${port}`);

    const messagePromise = new Promise<string>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('No reload message received')), 5000);
      ws.on('message', (data) => {
        clearTimeout(timeout);
        resolve(data.toString());
      });
      ws.on('error', (err) => {
        clearTimeout(timeout);
        reject(err);
      });
    });

    await new Promise<void>((resolve) => {
      ws.on('open', resolve);
    });

    // Modify file to trigger rebuild
    fs.writeFileSync(path.join(contentDir, 'test.md'), `---
title: After
---
Updated content.`);

    const msg = await messagePromise;
    expect(msg).toBe('reload');

    ws.close();
  });
});
