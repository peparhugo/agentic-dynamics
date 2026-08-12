import { promises as fs } from 'fs';
import * as http from 'http';
import * as os from 'os';
import * as path from 'path';
import WebSocket from 'ws';

import { parseArgs, printHelp } from '../src/cli';
import {
  injectReloadScript,
  RELOAD_PATH,
  startDevServer,
  type DevServer,
} from '../src/serve';
import { build } from '../src/ssg';

const FIXTURES = path.join(__dirname, 'fixtures');
const CONTENT_DIR = path.join(FIXTURES, 'content');

let tempRoot: string;
let contentDir: string;
let templateDir: string;
let outputDir: string;

function fetchText(port: number, route: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port, path: route }, (res) => {
      const chunks: Buffer[] = [];
      res.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
      res.on('end', () => {
        resolve(Buffer.concat(chunks).toString('utf8'));
      });
    });
    req.on('error', reject);
  });
}

function fetchStatus(port: number, route: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port, path: route }, (res) => {
      res.resume();
      res.on('end', () => resolve(res.statusCode ?? 0));
    });
    req.on('error', reject);
  });
}

function connectWs(port: number): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}${RELOAD_PATH}`);
    ws.once('open', () => resolve(ws));
    ws.once('error', reject);
  });
}

function waitForMessage(ws: WebSocket, timeoutMs: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      ws.off('message', onMessage);
      reject(new Error('Timed out waiting for reload message'));
    }, timeoutMs);
    const onMessage = (data: WebSocket.RawData): void => {
      clearTimeout(timer);
      resolve(data.toString());
    };
    ws.once('message', onMessage);
  });
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

beforeAll(async () => {
  tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-serve-test-'));
  contentDir = path.join(tempRoot, 'content');
  templateDir = path.join(tempRoot, 'templates');
  outputDir = path.join(tempRoot, 'dist');
  await fs.mkdir(contentDir, { recursive: true });
  await fs.mkdir(templateDir, { recursive: true });
  await fs.cp(CONTENT_DIR, contentDir, { recursive: true });
  await fs.writeFile(
    path.join(contentDir, 'extra.md'),
    '---\ntitle: Extra\n---\n\n# Extra\n\nBody text.\n'
  );
});

afterAll(async () => {
  await fs.rm(tempRoot, { recursive: true, force: true });
});

describe('injectReloadScript', () => {
  it('injects the reload script before the closing body tag', () => {
    const html = '<html><head></head><body><p>Hi</p></body></html>';
    const out = injectReloadScript(html);
    expect(out).toContain('ssg-live-reload');
    expect(out).toContain(RELOAD_PATH);
    const body = out.indexOf('</body>');
    const script = out.indexOf('ssg-live-reload');
    expect(script).toBeGreaterThan(-1);
    expect(script).toBeLessThan(body);
  });

  it('appends the script when there is no closing body tag', () => {
    const out = injectReloadScript('<p>No body</p>');
    expect(out).toContain('ssg-live-reload');
    expect(out).toContain('<p>No body</p>');
  });

  it('does not inject the script twice', () => {
    const once = injectReloadScript('<html><body></body></html>');
    const twice = injectReloadScript(once);
    expect(twice).toBe(once);
  });

  it('does not modify non-HTML content markers', () => {
    const out = injectReloadScript('<!DOCTYPE html><html></html>');
    expect(out).toContain('<!DOCTYPE html>');
  });
});

describe('parseArgs serve', () => {
  it('uses defaults for serve', () => {
    expect(parseArgs(['serve'])).toEqual({
      command: 'serve',
      contentDir: 'content',
      outputDir: 'dist',
      templateDir: 'templates',
      port: 3000,
    });
  });

  it('honors --port, --content, --output, and --templates', () => {
    expect(parseArgs(['serve', '--port', '8080', '--content', 'posts', '--output', 'public', '--templates', 'theme'])).toEqual({
      command: 'serve',
      contentDir: 'posts',
      outputDir: 'public',
      templateDir: 'theme',
      port: 8080,
    });
  });

  it('returns help for serve --help', () => {
    expect(parseArgs(['serve', '--help'])).toBe('help');
  });

  it('returns invalid for bad ports or missing values', () => {
    expect(parseArgs(['serve', '--port', 'abc'])).toBe('invalid');
    expect(parseArgs(['serve', '--port', '0'])).toBe('invalid');
    expect(parseArgs(['serve', '--port', '70000'])).toBe('invalid');
    expect(parseArgs(['serve', '--port'])).toBe('invalid');
    expect(parseArgs(['serve', '--output'])).toBe('invalid');
  });

  it('printHelp mentions the serve command', () => {
    const spy = jest.spyOn(console, 'log').mockImplementation(() => undefined);
    printHelp();
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('ssg serve'));
    spy.mockRestore();
  });
});

describe('startDevServer', () => {
  let server: DevServer;
  let port: number;

  afterEach(async () => {
    if (server) {
      await server.close();
      server = undefined as unknown as DevServer;
    }
  });

  it('builds and serves HTML with the reload script injected', async () => {
    server = await startDevServer({
      command: 'serve',
      contentDir,
      outputDir,
      templateDir,
      port: 0,
    });
    port = server.port;
    expect(port).toBeGreaterThan(0);

    const index = await fetchText(port, '/');
    expect(index).toContain('Index');
    expect(index).toContain('fixture-one.html');
    expect(index).toContain('ssg-live-reload');

    const page = await fetchText(port, '/fixture-one.html');
    expect(page).toContain('<h1>Fixture One</h1>');
    expect(page).toContain('ssg-live-reload');

    expect(await fetchStatus(port, '/missing.html')).toBe(404);
  });

  it('rebuilds and broadcasts reload when a watched file changes', async () => {
    server = await startDevServer({
      command: 'serve',
      contentDir,
      outputDir,
      templateDir,
      port: 0,
    });
    port = server.port;

    const ws = await connectWs(port);
    const pageFile = path.join(contentDir, 'extra.md');
    await fs.writeFile(
      pageFile,
      '---\ntitle: Extra Updated\n---\n\n# Extra Updated\n\nChanged body.\n'
    );

    const message = await waitForMessage(ws, 10000);
    expect(message).toBe('reload');
    ws.close();

    const served = await fetchText(port, '/extra.html');
    expect(served).toContain('<h1>Extra Updated</h1>');
    expect(served).toContain('Changed body.');
  });

  it('serves the output built by the regular build command', async () => {
    const standaloneDir = path.join(tempRoot, 'standalone-dist');
    await build({ contentDir, outputDir: standaloneDir, templateDir });
    const pages = await build({ contentDir, outputDir: standaloneDir, templateDir });
    expect(pages.length).toBeGreaterThan(0);

    server = await startDevServer({
      command: 'serve',
      contentDir,
      outputDir: standaloneDir,
      templateDir,
      port: 0,
    });
    port = server.port;

    const page = await fetchText(port, '/fixture-two.html');
    expect(page).toContain('<h1>Fixture Two</h1>');
    expect(await fetchStatus(port, '/nope.txt')).toBe(404);
  });
});
