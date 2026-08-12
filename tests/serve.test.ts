import { mkdtempSync, writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { get } from 'node:http';
import { WebSocket } from 'ws';
import {
  DEFAULT_PORT,
  WS_PATH,
  RELOAD_MESSAGE,
  contentType,
  injectLiveReloadScript,
  liveReloadScript,
  resolveFile,
  startServe,
  type ServeHandle,
} from '../src/serve';
import { parseArgs } from '../src/cli';

function makeTempDir(): string {
  return mkdtempSync(path.join(tmpdir(), 'ssg-serve-test-'));
}

function writeFixture(root: string, files: Record<string, string>): void {
  for (const [rel, content] of Object.entries(files)) {
    const full = path.join(root, rel);
    mkdirSync(path.dirname(full), { recursive: true });
    writeFileSync(full, content, 'utf8');
  }
}

function fetchText(url: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    get(url, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        body += chunk;
      });
      res.on('end', () => resolve({ status: res.statusCode ?? 0, body }));
    }).on('error', reject);
  });
}

function waitFor(condition: () => boolean, timeoutMs: number, intervalMs = 25): Promise<void> {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = (): void => {
      if (condition()) {
        resolve();
        return;
      }
      if (Date.now() - start > timeoutMs) {
        reject(new Error('Timed out waiting for condition'));
        return;
      }
      setTimeout(tick, intervalMs);
    };
    tick();
  });
}

describe('contentType', () => {
  it('maps extensions to mime types', () => {
    expect(contentType('a.html')).toBe('text/html; charset=utf-8');
    expect(contentType('a.css')).toBe('text/css; charset=utf-8');
    expect(contentType('a.png')).toBe('image/png');
    expect(contentType('a.unknown')).toBe('application/octet-stream');
  });
});

describe('liveReloadScript', () => {
  it('injects a websocket-based reload script before the closing body tag', () => {
    const html = '<html><body><p>Hi</p></body></html>';
    const out = injectLiveReloadScript(html, DEFAULT_PORT);
    expect(out).toContain('__ssg_reload__');
    expect(out).toContain('WebSocket');
    expect(out).toContain('location.reload');
    expect(out).toContain('</script>');
    expect(out.indexOf('<script')).toBeLessThan(out.indexOf('</body>'));
  });

  it('appends the script when the document has no closing tags', () => {
    const out = injectLiveReloadScript('plain text', 4000);
    expect(out).toContain('__ssg_reload__');
    expect(out.startsWith('plain text')).toBe(true);
  });

  it('marks the script with a recognizable attribute', () => {
    expect(liveReloadScript(3000)).toContain('data-ssg-live-reload');
  });
});

describe('resolveFile', () => {
  it('resolves a file directly', async () => {
    const dir = makeTempDir();
    writeFixture(dir, { 'site/hello.html': 'x' });
    const resolved = await resolveFile(path.join(dir, 'site'), '/hello.html');
    expect(resolved).toBe(path.join(dir, 'site', 'hello.html'));
  });

  it('resolves extensionless paths to .html', async () => {
    const dir = makeTempDir();
    writeFixture(dir, { 'site/hello.html': 'x' });
    const resolved = await resolveFile(path.join(dir, 'site'), '/hello');
    expect(resolved).toBe(path.join(dir, 'site', 'hello.html'));
  });

  it('resolves the index for the root path', async () => {
    const dir = makeTempDir();
    writeFixture(dir, { 'site/index.html': 'x' });
    const resolved = await resolveFile(path.join(dir, 'site'), '/');
    expect(resolved).toBe(path.join(dir, 'site', 'index.html'));
  });

  it('returns null for missing files and path traversal', async () => {
    const dir = makeTempDir();
    writeFixture(dir, { 'site/index.html': 'x' });
    expect(await resolveFile(path.join(dir, 'site'), '/nope')).toBeNull();
    expect(await resolveFile(path.join(dir, 'site'), '/../secret.txt')).toBeNull();
  });
});

describe('parseArgs --port', () => {
  it('parses --port as a separate flag', () => {
    const parsed = parseArgs(['--port', '4321']);
    expect(parsed.ok).toBe(true);
    if (parsed.ok) {
      expect(parsed.options.port).toBe(4321);
    }
  });

  it('parses --port=value style flags', () => {
    const parsed = parseArgs(['--port=5000']);
    expect(parsed.ok).toBe(true);
    if (parsed.ok) {
      expect(parsed.options.port).toBe(5000);
    }
  });

  it('defaults the port when unspecified', () => {
    const parsed = parseArgs([]);
    expect(parsed.ok).toBe(true);
    if (parsed.ok) {
      expect(parsed.options.port).toBeUndefined();
    }
  });

  it('rejects invalid ports', () => {
    expect(parseArgs(['--port', 'abc']).ok).toBe(false);
    expect(parseArgs(['--port=99999']).ok).toBe(false);
    expect(parseArgs(['--port']).ok).toBe(false);
  });
});

describe('startServe', () => {
  jest.setTimeout(20000);

  let dir: string;
  let handle: ServeHandle | undefined;

  beforeEach(() => {
    dir = makeTempDir();
    writeFixture(dir, {
      'content/hello.md': '---\ntitle: Hello\n---\n# Hello World\n',
    });
  });

  afterEach(async () => {
    if (handle) {
      await handle.stop();
      handle = undefined;
    }
  });

  it('serves the built site with a live reload script injected', async () => {
    handle = await startServe({
      contentDir: path.join(dir, 'content'),
      outputDir: path.join(dir, 'dist'),
      templatesDir: path.join(dir, 'templates'),
      port: 0,
    });

    const address = handle.server.address();
    expect(address).not.toBeNull();
    const port = typeof address === 'object' && address !== null ? address.port : 0;

    const { status, body } = await fetchText(`http://127.0.0.1:${port}/hello.html`);
    expect(status).toBe(200);
    expect(body).toContain('<h1>Hello World</h1>');
    expect(body).toContain('data-ssg-live-reload');
    expect(body).toContain('__ssg_reload__');
    expect(body).toContain('location.reload');
  });

  it('serves index.html for the root path', async () => {
    handle = await startServe({
      contentDir: path.join(dir, 'content'),
      outputDir: path.join(dir, 'dist'),
      templatesDir: path.join(dir, 'templates'),
      port: 0,
    });

    const address = handle.server.address();
    const port = typeof address === 'object' && address !== null ? address.port : 0;

    const { status, body } = await fetchText(`http://127.0.0.1:${port}/`);
    expect(status).toBe(200);
    expect(body).toContain('href="hello.html"');
  });

  it('returns 404 for missing pages', async () => {
    handle = await startServe({
      contentDir: path.join(dir, 'content'),
      outputDir: path.join(dir, 'dist'),
      templatesDir: path.join(dir, 'templates'),
      port: 0,
    });

    const address = handle.server.address();
    const port = typeof address === 'object' && address !== null ? address.port : 0;

    const { status } = await fetchText(`http://127.0.0.1:${port}/missing.html`);
    expect(status).toBe(404);
  });

  it('rebuilds and broadcasts a reload message when content changes', async () => {
    handle = await startServe({
      contentDir: path.join(dir, 'content'),
      outputDir: path.join(dir, 'dist'),
      templatesDir: path.join(dir, 'templates'),
      port: 0,
    });

    const address = handle.server.address();
    const port = typeof address === 'object' && address !== null ? address.port : 0;

    const socket = new WebSocket(`ws://127.0.0.1:${port}${WS_PATH}`);
    const messages: string[] = [];
    socket.on('message', (data) => {
      messages.push(String(data));
    });

    await new Promise<void>((resolve, reject) => {
      socket.once('open', resolve);
      socket.once('error', reject);
    });

    writeFileSync(path.join(dir, 'content', 'hello.md'), '---\ntitle: Hello\n---\n# Updated\n', 'utf8');

    await waitFor(() => messages.includes(RELOAD_MESSAGE), 10000);

    const rebuilt = readFileSync(path.join(dir, 'dist', 'hello.html'), 'utf8');
    expect(rebuilt).toContain('<h1>Updated</h1>');

    socket.terminate();
  });
});

describe('ssg serve (end to end)', () => {
  jest.setTimeout(20000);

  let dir: string;
  let child: ChildProcess | undefined;

  beforeEach(() => {
    dir = makeTempDir();
    writeFixture(dir, {
      'content/hello.md': '---\ntitle: Hello\n---\n# Hello World\n',
    });
  });

  afterEach(() => {
    if (child) {
      child.kill('SIGTERM');
      child = undefined;
    }
  });

  it('starts a server on the requested port and injects the reload script', async () => {
    const cli = path.resolve(__dirname, '..', 'dist', 'cli.js');
    const port = 49876;

    child = spawn(process.execPath, [cli, 'serve', '--port', String(port)], { cwd: dir });

    const started = new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Server did not start in time')), 10000);
      child?.stdout?.on('data', (chunk: Buffer) => {
        if (chunk.toString().includes('Serving')) {
          clearTimeout(timeout);
          resolve();
        }
      });
      child?.on('error', reject);
    });

    await started;

    let { status, body } = { status: 0, body: '' };
    for (let i = 0; i < 50; i += 1) {
      try {
        const res = await fetchText(`http://127.0.0.1:${port}/hello.html`);
        if (res.status === 200) {
          status = res.status;
          body = res.body;
          break;
        }
      } catch {
        // retry
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    expect(status).toBe(200);
    expect(body).toContain('<h1>Hello World</h1>');
    expect(body).toContain('data-ssg-live-reload');
    expect(body).toContain('__ssg_reload__');
  });
});
