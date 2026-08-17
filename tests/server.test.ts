import http from 'http';
import { promises as fs } from 'fs';
import os from 'os';
import path from 'path';
import { WebSocket } from 'ws';
import { serveSite, injectReloadScript } from '../src/server';

async function makeTempDir(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
}

function fetch(port: number, pathname = '/'): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http
      .get({ host: 'localhost', port, path: pathname }, (res) => {
        let data = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => {
          data += chunk;
        });
        res.on('end', () => resolve({ status: res.statusCode ?? 0, body: data }));
      })
      .on('error', reject);
  });
}

async function waitFor(predicate: () => Promise<boolean>, timeoutMs = 5000): Promise<void> {
  const start = Date.now();
  for (;;) {
    if (await predicate()) {
      return;
    }
    if (Date.now() - start > timeoutMs) {
      throw new Error('condition not met before timeout');
    }
    await new Promise((r) => setTimeout(r, 50));
  }
}

describe('injectReloadScript', () => {
  it('injects the websocket client before the closing body tag', () => {
    const html = '<html><head></head><body><p>hi</p></body></html>';
    const out = injectReloadScript(html);
    expect(out).toContain('new WebSocket');
    expect(out).toContain('</body>');
    expect(out.indexOf('new WebSocket')).toBeLessThan(out.indexOf('</body>'));
  });

  it('appends the client when there is no body tag', () => {
    const out = injectReloadScript('<p>hi</p>');
    expect(out).toContain('new WebSocket');
  });
});

describe('serveSite', () => {
  it('serves the built site and injects the reload script', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    const templates = await makeTempDir();

    await fs.writeFile(path.join(content, 'hello.md'), '# Hello\n');

    const dev = await serveSite({ content, output, templates, port: 0 });

    try {
      const res = await fetch(dev.port, '/');
      expect(res.status).toBe(200);
      expect(res.body).toContain('Hello');
      expect(res.body).toContain('new WebSocket');
    } finally {
      await dev.close();
    }
  });

  it('rebuilds and notifies connected websocket clients on change', async () => {
    const content = await makeTempDir();
    const output = await makeTempDir();
    const templates = await makeTempDir();

    await fs.writeFile(path.join(content, 'one.md'), '# One\n');

    const dev = await serveSite({ content, output, templates, port: 0 });

    try {
      const messages: string[] = [];
      const ws = new WebSocket(`ws://localhost:${dev.port}`);
      await new Promise<void>((resolve, reject) => {
        ws.on('open', () => resolve());
        ws.on('error', reject);
      });
      ws.on('message', (data) => messages.push(data.toString()));

      await fs.writeFile(path.join(content, 'two.md'), '# Two\n');

      await waitFor(async () => messages.includes('reload'));
      await waitFor(async () => {
        const res = await fetch(dev.port, '/');
        return res.body.includes('Two');
      });

      ws.terminate();
    } finally {
      await dev.close();
    }
  });
});
