import fs from 'fs';
import http from 'http';
import os from 'os';
import path from 'path';

import WebSocket from 'ws';

import { injectLiveReloadScript, RELOAD_PATH, startDevServer } from '../serve';
import type { DevServer } from '../serve';

const SAMPLE_MD = `---
title: Hello
date: 2026-05-01
tags: demo
---

# Hello page

Some <b>body</b> content.
`;

function writeTree(root: string, files: Record<string, string>): void {
  for (const [rel, contents] of Object.entries(files)) {
    const full = path.join(root, rel);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, contents);
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitFor(
  condition: () => boolean,
  timeoutMs = 4000,
  intervalMs = 50,
): Promise<void> {
  const start = Date.now();
  for (;;) {
    if (condition()) return;
    if (Date.now() - start > timeoutMs) {
      throw new Error('Timed out waiting for condition');
    }
    // eslint-disable-next-line no-await-in-loop
    await delay(intervalMs);
  }
}

function httpGet(
  port: number,
  requestPath: string,
): Promise<{ status: number; body: string; headers: http.IncomingHttpHeaders }> {
  return new Promise((resolve, reject) => {
    const req = http.get(
      {
        hostname: '127.0.0.1',
        port,
        path: requestPath,
        agent: false,
        headers: { Connection: 'close' },
      },
      (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        body += chunk;
      });
      res.on('end', () => {
        resolve({ status: res.statusCode ?? 0, body, headers: res.headers });
      });
      res.on('error', reject);
    });
    req.on('error', reject);
  });
}

interface TestServer {
  dev: DevServer;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
}

async function startServer(
  overrides: Partial<{ templatesDir: string }> = {},
): Promise<TestServer> {
  const contentDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-content-'));
  const outputDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-dist-'));
  const templatesDir = overrides.templatesDir ?? path.join(outputDir, 'missing-templates');

  fs.writeFileSync(path.join(contentDir, 'hello.md'), SAMPLE_MD);

  const dev = await startDevServer({
    contentDir,
    outputDir,
    templatesDir,
    port: 0,
  });

  return { dev, contentDir, outputDir, templatesDir };
}

async function stopServer(test: TestServer): Promise<void> {
  await test.dev.close();
  fs.rmSync(test.contentDir, { recursive: true, force: true });
  fs.rmSync(test.outputDir, { recursive: true, force: true });
  if (fs.existsSync(test.templatesDir)) {
    fs.rmSync(test.templatesDir, { recursive: true, force: true });
  }
}

describe('injectLiveReloadScript', () => {
  it('injects the reload script before the closing body tag', () => {
    const html = '<html><head></head><body><p>hi</p></body></html>';
    const out = injectLiveReloadScript(html);

    expect(out).toContain('WebSocket');
    expect(out).toContain(RELOAD_PATH);
    expect(out.indexOf('WebSocket')).toBeLessThan(out.indexOf('</body>'));
    expect(out).toContain('location.reload()');
    expect(out.endsWith('</html>')).toBe(true);
  });

  it('appends the script when there is no closing body tag', () => {
    const out = injectLiveReloadScript('<p>hi</p>');
    expect(out).toContain('WebSocket');
    expect(out).toContain(RELOAD_PATH);
  });
});

describe('startDevServer', () => {
  it('serves built pages from the output directory with the reload script', async () => {
    const server = await startServer();
    try {
      const res = await httpGet(server.dev.port, '/hello.html');
      expect(res.status).toBe(200);
      expect(res.body).toContain('<h1>Hello</h1>');
      expect(res.body).toContain('WebSocket');
      expect(res.body).toContain(RELOAD_PATH);
    } finally {
      await stopServer(server);
    }
  });

  it('serves index.html at the root', async () => {
    const server = await startServer();
    try {
      const res = await httpGet(server.dev.port, '/');
      expect(res.status).toBe(200);
      expect(res.body).toContain('href="hello.html"');
      expect(res.body).toContain('WebSocket');
    } finally {
      await stopServer(server);
    }
  });

  it('serves static assets with a matching content type', async () => {
    const server = await startServer();
    try {
      fs.writeFileSync(path.join(server.outputDir, 'style.css'), 'body { color: red; }');
      const res = await httpGet(server.dev.port, '/style.css');
      expect(res.status).toBe(200);
      expect(res.body).toContain('color: red');
      expect(res.headers['content-type']).toContain('text/css');
    } finally {
      await stopServer(server);
    }
  });

  it('returns 404 for missing files', async () => {
    const server = await startServer();
    try {
      const res = await httpGet(server.dev.port, '/missing.html');
      expect(res.status).toBe(404);
    } finally {
      await stopServer(server);
    }
  });

  it('blocks path traversal outside the output directory', async () => {
    const server = await startServer();
    try {
      const res = await httpGet(server.dev.port, '/../package.json');
      expect(res.status).toBe(403);
    } finally {
      await stopServer(server);
    }
  });

  it('rebuilds the site when a content file changes', async () => {
    const server = await startServer();
    try {
      expect(fs.existsSync(path.join(server.outputDir, 'hello.html'))).toBe(true);
      expect(fs.existsSync(path.join(server.outputDir, 'second.html'))).toBe(false);

      await delay(200);
      fs.writeFileSync(
        path.join(server.contentDir, 'second.md'),
        '---\ntitle: Second\n---\n# Two',
      );

      await waitFor(() => fs.existsSync(path.join(server.outputDir, 'second.html')));
      const html = fs.readFileSync(path.join(server.outputDir, 'second.html'), 'utf8');
      expect(html).toContain('Second');
    } finally {
      await stopServer(server);
    }
  });

  it('rebuilds the site when a template file changes', async () => {
    const templatesDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-tpl-'));
    writeTree(templatesDir, {
      'default.hbs': '<article>{{title}}</article>',
      'layouts/default.hbs': '<html><body>{{{body}}}</body></html>',
    });

    const server = await startServer({ templatesDir });
    try {
      const initial = fs.readFileSync(path.join(server.outputDir, 'hello.html'), 'utf8');
      expect(initial).toContain('<article>Hello</article>');

      await delay(200);
      fs.writeFileSync(
        path.join(templatesDir, 'default.hbs'),
        '<article>{{title}}!</article>',
      );

      await waitFor(() =>
        fs
          .readFileSync(path.join(server.outputDir, 'hello.html'), 'utf8')
          .includes('<article>Hello!</article>'),
      );
    } finally {
      await stopServer(server);
      fs.rmSync(templatesDir, { recursive: true, force: true });
    }
  });

  it('sends a reload message to connected clients when files change', async () => {
    const server = await startServer();
    const messages: string[] = [];
    const fakeClient = {
      readyState: WebSocket.OPEN,
      send: (data: string) => {
        messages.push(data);
      },
    } as unknown as WebSocket;

    server.dev.wss.clients.add(fakeClient);
    try {
      await delay(200);
      fs.writeFileSync(path.join(server.contentDir, 'third.md'), '# Third');

      await waitFor(() =>
        messages.some((message) => message.includes('reload')),
      );
      await waitFor(() =>
        fs.existsSync(path.join(server.outputDir, 'third.html')),
      );
    } finally {
      server.dev.wss.clients.delete(fakeClient);
      await stopServer(server);
    }
  });

  it('closes the server and watcher cleanly', async () => {
    const server = await startServer();
    try {
      await server.dev.close();
      expect(server.dev.server.listening).toBe(false);
      await expect(
        httpGet(server.dev.port, '/hello.html'),
      ).rejects.toBeDefined();
    } finally {
      await stopServer(server);
    }
  });
});
