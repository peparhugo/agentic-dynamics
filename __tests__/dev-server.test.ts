import { spawn, spawnSync, ChildProcess } from 'child_process';
import fs from 'fs';
import http from 'http';
import os from 'os';
import path from 'path';
import WebSocket from 'ws';
import {
  LiveReloadDevServer,
  injectLiveReload,
  liveReloadScript,
  startDevServer,
} from '../src/dev-server';
import { parseArgs, printHelp } from '../src/cli';

const REPO_ROOT = path.resolve(__dirname, '..');
const CLI_JS = path.join(REPO_ROOT, 'dist', 'cli.js');

function makeTempDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeContent(dir: string, files: Record<string, string>): void {
  fs.mkdirSync(dir, { recursive: true });
  for (const [name, content] of Object.entries(files)) {
    const filePath = path.join(dir, name);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content);
  }
}

const NO_KEEP_ALIVE = { agent: false } as http.RequestOptions;

function fetchText(url: string): Promise<string> {
  return new Promise((resolve, reject) => {
    http
      .get(url, NO_KEEP_ALIVE, (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => {
          body += chunk;
        });
        res.on('end', () => resolve(body));
      })
      .on('error', reject);
  });
}

function fetchStatus(url: string): Promise<number> {
  return new Promise((resolve, reject) => {
    http
      .get(url, NO_KEEP_ALIVE, (res) => {
        res.resume();
        res.on('end', () => resolve(res.statusCode ?? 0));
      })
      .on('error', reject);
  });
}

function waitFor(predicate: () => boolean, timeoutMs = 8000): Promise<void> {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      if (predicate()) {
        resolve();
        return;
      }
      if (Date.now() - start > timeoutMs) {
        reject(new Error('Timed out waiting for condition'));
        return;
      }
      setTimeout(check, 50);
    };
    check();
  });
}

async function waitForWsMessage(ws: WebSocket, timeoutMs = 8000): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      ws.removeAllListeners();
      reject(new Error('Timed out waiting for WebSocket message'));
    }, timeoutMs);
    ws.once('message', (data) => {
      clearTimeout(timer);
      resolve(data.toString());
    });
  });
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function buildFixture(): Promise<{ tmp: string; contentDir: string; outputDir: string }> {
  const tmp = makeTempDir('ssg-dev-');
  const contentDir = path.join(tmp, 'content');
  const outputDir = path.join(tmp, 'dist');
  writeContent(contentDir, {
    'home.md': '---\ntitle: Home\n---\n\n# Home page',
    'about.md': '---\ntitle: About\n---\n\n# About page',
  });
  return { tmp, contentDir, outputDir };
}

describe('parseArgs serve', () => {
  it('defaults the port to 3000', () => {
    const opts = parseArgs(['serve']);
    expect(opts.command).toBe('serve');
    expect(opts.port).toBe(3000);
  });

  it('parses --port', () => {
    const opts = parseArgs(['serve', '--port', '8080']);
    expect(opts.port).toBe(8080);
  });

  it('falls back to the default port for an invalid --port', () => {
    expect(parseArgs(['serve', '--port', 'abc']).port).toBe(3000);
    expect(parseArgs(['serve', '--port', '-1']).port).toBe(3000);
  });

  it('combines serve options with content, output and templates', () => {
    const opts = parseArgs(['serve', '--content', 'posts', '--output', 'public', '--port', '4000']);
    expect(opts.command).toBe('serve');
    expect(opts.contentDir).toBe('posts');
    expect(opts.outputDir).toBe('public');
    expect(opts.port).toBe(4000);
  });

  it('mentions serve and --port in help', () => {
    const spy = jest.spyOn(console, 'log').mockImplementation(() => undefined);
    printHelp();
    const output = (spy.mock.calls[0] as string[]).join('\n');
    spy.mockRestore();
    expect(output).toContain('npx ssg serve');
    expect(output).toContain('--port');
  });
});

describe('liveReloadScript / injectLiveReload', () => {
  it('creates a script that opens a WebSocket and reloads on message', () => {
    const script = liveReloadScript('ws://localhost:3000/__ssg_live_reload');
    expect(script).toContain('new WebSocket("ws://localhost:3000/__ssg_live_reload")');
    expect(script).toContain('window.location.reload()');
    expect(script).toContain('"reload"');
  });

  it('injects the script before the closing body tag', () => {
    const html = '<!DOCTYPE html><html><body><p>Hi</p></body></html>';
    const injected = injectLiveReload(html, 'ws://localhost:3000/__ssg_live_reload');
    expect(injected).toContain('<p>Hi</p>');
    expect(injected).toContain('ssg-live-reload');
    expect(injected.indexOf('ssg-live-reload')).toBeLessThan(injected.indexOf('</body>'));
  });

  it('appends the script when there is no body tag', () => {
    const injected = injectLiveReload('<html><p>Hi</p></html>', 'ws://localhost:3000/x');
    expect(injected).toContain('ssg-live-reload');
  });

  it('does not inject the script twice', () => {
    const once = injectLiveReload('<html><body></body></html>', 'ws://localhost:3000/x');
    const twice = injectLiveReload(once, 'ws://localhost:3000/x');
    expect(twice.match(/ssg-live-reload/g)).toHaveLength(1);
  });
});

describe('startDevServer serving', () => {
  it('serves built HTML from the output directory', async () => {
    const { contentDir, outputDir } = await buildFixture();
    const devServer = await startDevServer({ contentDir, outputDir, port: 0 });
    try {
      const base = `http://localhost:${devServer.port}`;
      const html = await fetchText(`${base}/about.html`);
      expect(html).toContain('<title>About</title>');
      expect(html).toContain('<h1>About</h1>');
    } finally {
      await devServer.close();
    }
  });

  it('serves index.html for the root path', async () => {
    const { contentDir, outputDir } = await buildFixture();
    const devServer = await startDevServer({ contentDir, outputDir, port: 0 });
    try {
      const html = await fetchText(`http://localhost:${devServer.port}/`);
      expect(html).toContain('<a href="about.html">About</a>');
      expect(html).toContain('<a href="home.html">Home</a>');
    } finally {
      await devServer.close();
    }
  });

  it('injects the live reload script into served HTML pages', async () => {
    const { contentDir, outputDir } = await buildFixture();
    const devServer = await startDevServer({ contentDir, outputDir, port: 0 });
    try {
      const html = await fetchText(`http://localhost:${devServer.port}/home.html`);
      expect(html).toContain('ssg-live-reload');
      expect(html).toContain(`ws://localhost:${devServer.port}/__ssg_live_reload`);
    } finally {
      await devServer.close();
    }
  });

  it('returns 404 for missing files', async () => {
    const { contentDir, outputDir } = await buildFixture();
    const devServer = await startDevServer({ contentDir, outputDir, port: 0 });
    try {
      const status = await fetchStatus(`http://localhost:${devServer.port}/nope.html`);
      expect(status).toBe(404);
    } finally {
      await devServer.close();
    }
  });

  it('does not inject the script into non-HTML files', async () => {
    const { contentDir, outputDir } = await buildFixture();
    const devServer = await startDevServer({ contentDir, outputDir, port: 0 });
    try {
      fs.writeFileSync(path.join(outputDir, 'styles.css'), 'body { color: red; }');
      const css = await fetchText(`http://localhost:${devServer.port}/styles.css`);
      expect(css).toContain('body { color: red; }');
      expect(css).not.toContain('ssg-live-reload');
    } finally {
      await devServer.close();
    }
  });
});

describe('live reload rebuild', () => {
  it('rebuilds and broadcasts reload when content changes', async () => {
    const { contentDir, outputDir } = await buildFixture();
    const devServer = await startDevServer({ contentDir, outputDir, port: 0 });
    try {
      const ws = new WebSocket(
        `ws://localhost:${devServer.port}/__ssg_live_reload`,
        { headers: { Origin: `http://localhost:${devServer.port}` } }
      );
      await new Promise<void>((resolve, reject) => {
        ws.once('open', resolve);
        ws.once('error', reject);
      });

      fs.writeFileSync(path.join(contentDir, 'home.md'), '---\ntitle: Home Updated\n---\n\n# Home page v2');
      const message = await waitForWsMessage(ws);
      expect(JSON.parse(message)).toEqual({ type: 'reload' });

      await waitFor(() =>
        fs.readFileSync(path.join(outputDir, 'home.html'), 'utf8').includes('Home Updated')
      );
      ws.close();
    } finally {
      await devServer.close();
    }
  });

  it('serves rebuilt content after a change', async () => {
    const { contentDir, outputDir } = await buildFixture();
    const devServer = await startDevServer({ contentDir, outputDir, port: 0 });
    try {
      fs.writeFileSync(path.join(contentDir, 'about.md'), '---\ntitle: About v2\n---\n\n# About page v2');
      await waitFor(() =>
        fs.readFileSync(path.join(outputDir, 'about.html'), 'utf8').includes('About v2')
      );
      const html = await fetchText(`http://localhost:${devServer.port}/about.html`);
      expect(html).toContain('About v2');
    } finally {
      await devServer.close();
    }
  });

  it('keeps serving when a rebuild fails and recovers on the next change', async () => {
    const tmp = makeTempDir('ssg-dev-fail-');
    const contentDir = path.join(tmp, 'content');
    const outputDir = path.join(tmp, 'dist');
    const tplDir = path.join(tmp, 'templates');
    writeContent(tplDir, { 'default.hbs': '<main>{{{contentHtml}}}</main>' });
    writeContent(contentDir, { 'a.md': '---\ntitle: A\n---\n\n# A v1' });
    const devServer = await startDevServer({
      contentDir,
      outputDir,
      templateDir: tplDir,
      port: 0,
    });
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => undefined);
    try {
      fs.writeFileSync(
        path.join(contentDir, 'a.md'),
        '---\ntitle: A\ntemplate: missing\n---\n\n# A v2'
      );
      await delay(500);

      const html = await fetchText(`http://localhost:${devServer.port}/a.html`);
      expect(html).toContain('<h1>A v1</h1>');
      expect(html).not.toContain('A v2');

      fs.writeFileSync(path.join(contentDir, 'a.md'), '---\ntitle: A\n---\n\n# A v3');
      await waitFor(() =>
        fs.readFileSync(path.join(outputDir, 'a.html'), 'utf8').includes('<h1>A v3</h1>')
      );
      const updated = await fetchText(`http://localhost:${devServer.port}/a.html`);
      expect(updated).toContain('<h1>A v3</h1>');
    } finally {
      errorSpy.mockRestore();
      await devServer.close();
    }
  });
});

describe('serve CLI binary', () => {
  function ensureBuilt(): void {
    if (!fs.existsSync(CLI_JS)) {
      const result = spawnSync('npx', ['tsc'], { cwd: REPO_ROOT, encoding: 'utf8' });
      if (result.status !== 0) {
        throw new Error(`Failed to build TypeScript: ${result.stderr}`);
      }
    }
  }

  beforeAll(() => {
    ensureBuilt();
  });

  it('starts a live-reload server and serves the site', async () => {
    const { contentDir, outputDir } = await buildFixture();

    const child: ChildProcess = spawn(
      process.execPath,
      [CLI_JS, 'serve', '--content', contentDir, '--output', outputDir, '--port', '0'],
      { cwd: REPO_ROOT }
    );
    let stdout = '';
    let stderr = '';
    child.stdout?.on('data', (chunk: string) => {
      stdout += chunk;
    });
    child.stderr?.on('data', (chunk: string) => {
      stderr += chunk;
    });

    try {
      await waitFor(() => stdout.includes('Serving') && /localhost:\d+/.test(stdout));
      expect(stderr).toBe('');
      const port = Number(stdout.match(/localhost:(\d+)/)?.[1]);
      expect(Number.isInteger(port) && port > 0).toBe(true);

      const html = await fetchText(`http://localhost:${port}/home.html`);
      expect(html).toContain('Home page');
      expect(html).toContain('ssg-live-reload');
    } finally {
      child.kill('SIGTERM');
      await delay(300);
    }
  });

  it('fails with a non-zero exit code for a missing content directory', () => {
    const tmp = makeTempDir('ssg-serve-missing-');
    const result = spawnSync(
      process.execPath,
      [CLI_JS, 'serve', '--content', path.join(tmp, 'nope')],
      { cwd: REPO_ROOT, encoding: 'utf8' }
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain('Serve failed');
  });
});
