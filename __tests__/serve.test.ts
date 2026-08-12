import fs from 'fs';
import http from 'http';
import os from 'os';
import path from 'path';
import { AddressInfo } from 'net';
import WebSocket from 'ws';
import {
  serve,
  ServeHandle,
  LIVERELOAD_PATH,
  DEFAULT_PORT,
  injectLiveReload,
  hasLiveReload,
  REBUILD_DELAY_MS,
} from '../src/serve';
import { parseArgs, printHelp } from '../src/cli';

interface TempDir {
  dir: string;
  cleanup: () => void;
}

function makeTempDir(): TempDir {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-serve-'));
  return { dir, cleanup: () => fs.rmSync(dir, { recursive: true, force: true }) };
}

function writeMarkdown(dir: string, relPath: string, content: string): void {
  const full = path.join(dir, relPath);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content, 'utf8');
}

async function startServer(
  contentDir: string,
  outputDir: string,
  templatesDir?: string
): Promise<{ handle: ServeHandle; port: number }> {
  const handle = serve({ contentDir, outputDir, templatesDir, port: 0 });
  await new Promise<void>((resolve) => handle.server.once('listening', resolve));
  const port = (handle.server.address() as AddressInfo).port;
  return { handle, port };
}

function fetchText(port: number, pathname: string): Promise<string> {
  return new Promise((resolve, reject) => {
    http
      .get({ hostname: 'localhost', port, path: pathname }, (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => resolve(data));
      })
      .on('error', reject);
  });
}

function fetchStatus(port: number, pathname: string): Promise<number> {
  return new Promise((resolve, reject) => {
    http
      .get({ hostname: 'localhost', port, path: pathname }, (res) => {
        res.resume();
        res.on('end', () => resolve(res.statusCode || 0));
      })
      .on('error', reject);
  });
}

async function waitFor(
  fn: () => boolean | Promise<boolean>,
  timeoutMs: number = 5000
): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await fn()) return;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error('waitFor timed out');
}

function nextWsMessage(ws: WebSocket): Promise<string> {
  return new Promise((resolve, reject) => {
    ws.on('message', (data) => resolve(String(data)));
    ws.on('error', reject);
  });
}

function openLiveReloadSocket(port: number): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://localhost:${port}${LIVERELOAD_PATH}`);
    ws.on('open', () => resolve(ws));
    ws.on('error', reject);
  });
}

describe('parseArgs for serve', () => {
  it('treats serve as a command', () => {
    const { command } = parseArgs(['serve']);
    expect(command).toBe('serve');
  });

  it('parses the --port option', () => {
    const { options } = parseArgs(['serve', '--port', '4321']);
    expect(options.port).toBe(4321);
  });

  it('parses the shorthand -p port option', () => {
    const { options } = parseArgs(['serve', '-p', '8080']);
    expect(options.port).toBe(8080);
  });

  it('leaves port unset when not provided', () => {
    const { options } = parseArgs(['serve']);
    expect(options.port).toBeUndefined();
  });

  it('throws when a port value is missing', () => {
    expect(() => parseArgs(['serve', '--port'])).toThrow(/missing value/);
  });

  it('throws on an invalid port value', () => {
    expect(() => parseArgs(['serve', '--port', 'abc'])).toThrow(/invalid port/);
    expect(() => parseArgs(['serve', '--port', '-1'])).toThrow(/invalid port/);
    expect(() => parseArgs(['serve', '--port', '70000'])).toThrow(/invalid port/);
  });

  it('exports the default port', () => {
    expect(DEFAULT_PORT).toBe(3000);
  });

  it('prints serve in the help text', () => {
    const spy = jest.spyOn(console, 'log').mockImplementation(() => {});
    expect(() => printHelp()).not.toThrow();
    expect(spy).toHaveBeenCalled();
    const output = spy.mock.calls.map((c) => c.join(' ')).join('\n');
    expect(output).toContain('serve');
    expect(output).toContain('--port');
    spy.mockRestore();
  });
});

describe('injectLiveReload', () => {
  it('injects the script before </body>', () => {
    const html = '<html><body><p>Hi</p></body></html>';
    const out = injectLiveReload(html);
    expect(out).toContain('<p>Hi</p>');
    expect(out.indexOf('__livereload')).toBeLessThan(out.indexOf('</body>'));
  });

  it('injects before </html> when there is no </body>', () => {
    const html = '<html><p>Hi</p></html>';
    const out = injectLiveReload(html);
    expect(out.indexOf('__livereload')).toBeLessThan(out.indexOf('</html>'));
  });

  it('does not inject twice', () => {
    const once = injectLiveReload('<html><body></body></html>');
    expect(hasLiveReload(once)).toBe(true);
    const twice = injectLiveReload(once);
    const count = (twice.match(/id="__livereload"/g) || []).length;
    expect(count).toBe(1);
  });

  it('appends the script when there is no body or html tag', () => {
    const html = '<p>Hi</p>';
    expect(injectLiveReload(html)).toContain('__livereload');
  });
});

describe('serve dev server', () => {
  it('builds and serves the site with the live-reload script injected', async () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeMarkdown(contentDir, 'one.md', '---\ntitle: First\n---\nHello **world**.');
    const { handle, port } = await startServer(contentDir, outDir);
    try {
      const index = await fetchText(port, '/');
      expect(index).toContain('Hello');
      expect(index).toContain('First');
      expect(index).toContain('id="__livereload"');
      expect(index).toContain(LIVERELOAD_PATH);

      const page = await fetchText(port, '/first.html');
      expect(page).toContain('<strong>world</strong>');
      expect(page).toContain('id="__livereload"');
    } finally {
      await handle.close();
      cleanup();
    }
  });

  it('serves an injected page only once after rebuild', async () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeMarkdown(contentDir, 'one.md', '---\ntitle: First\n---\nHello.');
    const { handle, port } = await startServer(contentDir, outDir);
    try {
      const first = await fetchText(port, '/');
      const second = await fetchText(port, '/');
      expect((first.match(/id="__livereload"/g) || []).length).toBe(1);
      expect(second).toBe(first);
    } finally {
      await handle.close();
      cleanup();
    }
  });

  it('returns a 404 for missing files', async () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeMarkdown(contentDir, 'one.md', '# Hello');
    const { handle, port } = await startServer(contentDir, outDir);
    try {
      expect(await fetchStatus(port, '/nope.html')).toBe(404);
    } finally {
      await handle.close();
      cleanup();
    }
  });

  it('rebuilds and broadcasts reload when content changes', async () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeMarkdown(contentDir, 'one.md', '---\ntitle: One\n---\nFirst body.');
    const { handle, port } = await startServer(contentDir, outDir);
    const ws = await openLiveReloadSocket(port);
    try {
      const reloadPromise = nextWsMessage(ws);
      writeMarkdown(contentDir, 'two.md', '---\ntitle: Two\n---\nSecond body.');
      await reloadPromise;

      await waitFor(async () => {
        const index = await fetchText(port, '/');
        return index.includes('Second body.');
      });

      const page = await fetchText(port, '/two.html');
      expect(page).toContain('Second body.');
    } finally {
      ws.close();
      await handle.close();
      cleanup();
    }
  });

  it('rebuilds and broadcasts reload when a template changes', async () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    const templatesDir = path.join(dir, 'templates');
    writeMarkdown(contentDir, 'one.md', '---\ntitle: One\ntemplate: page\n---\nBody.');
    writeMarkdown(templatesDir, 'page.hbs', 'PAGE OLD: {{title}}');
    const { handle, port } = await startServer(contentDir, outDir, templatesDir);
    const ws = await openLiveReloadSocket(port);
    try {
      const reloadPromise = nextWsMessage(ws);
      writeMarkdown(templatesDir, 'page.hbs', 'PAGE NEW: {{title}}');
      await reloadPromise;

      await waitFor(async () => {
        const page = await fetchText(port, '/one.html');
        return page.includes('PAGE NEW: One');
      });
    } finally {
      ws.close();
      await handle.close();
      cleanup();
    }
  });

  it('serves after a debounced burst of changes', async () => {
    const { dir, cleanup } = makeTempDir();
    const contentDir = path.join(dir, 'content');
    const outDir = path.join(dir, 'dist');
    writeMarkdown(contentDir, 'one.md', '---\ntitle: One\n---\nA.');
    const { handle, port } = await startServer(contentDir, outDir);
    try {
      for (let i = 0; i < 5; i++) {
        writeMarkdown(contentDir, 'one.md', `---\ntitle: One\n---\nUpdate ${i}.`);
        await new Promise((resolve) => setTimeout(resolve, REBUILD_DELAY_MS / 2));
      }
      await waitFor(async () => {
        const page = await fetchText(port, '/one.html');
        return page.includes('Update 4.');
      });
    } finally {
      await handle.close();
      cleanup();
    }
  });
});
