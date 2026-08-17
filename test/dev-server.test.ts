import * as fs from 'fs';
import * as http from 'http';
import * as os from 'os';
import * as path from 'path';
import WebSocket from 'ws';
import { DevServer, injectLiveReloadScript } from '../src/dev-server';
import { parseArgs } from '../src/cli';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-'));
}

function get(port: number, url: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    http
      .get({ host: 'localhost', port, path: url, headers: { Connection: 'close' } }, (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => resolve({ status: res.statusCode ?? 0, body }));
      })
      .on('error', reject);
  });
}

function waitFor(condition: () => boolean, timeoutMs = 5000): Promise<void> {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const timer = setInterval(() => {
      if (condition()) {
        clearInterval(timer);
        resolve();
      } else if (Date.now() - start > timeoutMs) {
        clearInterval(timer);
        reject(new Error('Timed out waiting for condition'));
      }
    }, 20);
  });
}

describe('injectLiveReloadScript', () => {
  it('injects the reload script before </body>', () => {
    const html = '<html><body><h1>Hi</h1></body></html>';
    const result = injectLiveReloadScript(html);
    expect(result).toContain('WebSocket');
    expect(result).toContain('location.host');
    expect(result).toContain('location.reload()');
    expect(result.indexOf('WebSocket')).toBeLessThan(result.indexOf('</body>'));
    expect(result).toContain('<h1>Hi</h1>');
  });

  it('appends the script when no </body> is present', () => {
    const html = '<h1>Fragment</h1>';
    const result = injectLiveReloadScript(html);
    expect(result).toContain('<h1>Fragment</h1>');
    expect(result).toContain('WebSocket');
    expect(result.endsWith('</script>')).toBe(true);
  });
});

describe('parseArgs serve', () => {
  it('parses the serve command with a default port of 3000', () => {
    const args = parseArgs(['node', 'ssg', 'serve']);
    expect(args.command).toBe('serve');
    expect(args.port).toBe(3000);
  });

  it('parses --port', () => {
    const args = parseArgs(['node', 'ssg', 'serve', '--port', '4321']);
    expect(args.port).toBe(4321);
  });

  it('parses --port=8080', () => {
    const args = parseArgs(['node', 'ssg', 'serve', '--port=8080']);
    expect(args.port).toBe(8080);
  });
});

describe('DevServer', () => {
  it('serves built HTML with an injected live-reload script', async () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    fs.writeFileSync(path.join(contentDir, 'hello.md'), '---\ntitle: Hello\n---\n# Hello\n');

    const server = new DevServer({ contentDir, outputDir, port: 0 });
    const port = await server.start();
    try {
      const index = await get(port, '/');
      expect(index.status).toBe(200);
      expect(index.body).toContain('hello.html');
      expect(index.body).toContain('Hello');
      expect(index.body).toContain('WebSocket');

      const page = await get(port, '/hello.html');
      expect(page.status).toBe(200);
      expect(page.body).toContain('<h1>Hello</h1>');
      expect(page.body).toContain('WebSocket');
    } finally {
      await server.close();
    }
  });

  it('rebuilds and notifies WebSocket clients on file change', async () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    const file = path.join(contentDir, 'post.md');
    fs.writeFileSync(file, '---\ntitle: Before\n---\n# Before\n');

    const server = new DevServer({ contentDir, outputDir, port: 0 });
    const port = await server.start();

    const messages: string[] = [];
    const ws = new WebSocket(`ws://localhost:${port}`);
    await new Promise<void>((resolve, reject) => {
      ws.once('open', () => resolve());
      ws.once('error', reject);
    });
    ws.on('message', (data) => messages.push(String(data)));

    const before = await get(port, '/post.html');
    expect(before.body).toContain('Before');

    fs.writeFileSync(file, '---\ntitle: After\n---\n# After\n');

    await waitFor(() => messages.includes('reload'));
    await waitFor(() => fs.readFileSync(path.join(outputDir, 'post.html'), 'utf8').includes('After'));

    ws.terminate();
    await server.close();
  });

  it('serves 404 for missing files', async () => {
    const contentDir = makeTempDir();
    const outputDir = makeTempDir();
    const server = new DevServer({ contentDir, outputDir, port: 0 });
    const port = await server.start();
    try {
      const res = await get(port, '/nope.html');
      expect(res.status).toBe(404);
    } finally {
      await server.close();
    }
  });
});
