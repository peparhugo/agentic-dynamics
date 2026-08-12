import http, { IncomingMessage } from 'http';
import net, { AddressInfo } from 'net';
import { readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { WebSocket } from 'ws';
import { parseArgs } from '../src/cli';
import { DEFAULT_PORT, DevServer, injectLiveReload, liveReloadScript, startDevServer } from '../src/serve';
import { createFixture, cleanupFixture, Fixture } from './helpers';

jest.setTimeout(20000);

function waitForReload(ws: WebSocket, trigger: () => void): Promise<string> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('timed out waiting for reload')), 15000);
    const interval = setInterval(() => {
      try {
        trigger();
      } catch {
        // ignore transient write errors while retrying
      }
    }, 300);
    const finish = (value: string): void => {
      clearTimeout(timer);
      clearInterval(interval);
      resolve(value);
    };
    ws.on('message', (data) => finish(String(data)));
  });
}

function get(url: string): Promise<string> {
  return new Promise((resolve, reject) => {
    http
      .get(url, (res: IncomingMessage) => {
        let body = '';
        res.on('data', (chunk) => {
          body += chunk;
        });
        res.on('end', () => resolve(body));
      })
      .on('error', reject);
  });
}

describe('parseArgs serve', () => {
  it('defaults the port to 3000', () => {
    const parsed = parseArgs(['serve']);
    expect(parsed).toEqual({
      command: 'serve',
      options: { content: './content', output: './dist', templates: './templates', port: 3000 },
    });
  });

  it('accepts a --port flag', () => {
    const parsed = parseArgs(['serve', '--port', '4000']);
    expect(parsed).toEqual({
      command: 'serve',
      options: { content: './content', output: './dist', templates: './templates', port: 4000 },
    });
  });

  it('accepts --port=8080 syntax', () => {
    const parsed = parseArgs(['serve', '--port=8080']);
    expect(parsed?.command).toBe('serve');
    expect((parsed?.options as { port: number }).port).toBe(8080);
  });

  it('accepts content/output/templates flags alongside --port', () => {
    const parsed = parseArgs(['serve', '--content', 'src', '--output', 'public', '--templates', 'themes', '--port', '9000']);
    expect(parsed).toEqual({
      command: 'serve',
      options: { content: 'src', output: 'public', templates: 'themes', port: 9000 },
    });
  });

  it('rejects an invalid port', () => {
    expect(parseArgs(['serve', '--port', 'abc'])).toBeNull();
    expect(parseArgs(['serve', '--port', '-1'])).toBeNull();
  });

  it('does not accept --port for the build command', () => {
    expect(parseArgs(['build', '--port', '3000'])).toBeNull();
  });
});

describe('injectLiveReload', () => {
  it('injects the live reload script before </body>', () => {
    const html = '<html><body><h1>Hi</h1></body></html>';
    const result = injectLiveReload(html);
    expect(result).toContain('new WebSocket');
    expect(result.indexOf('new WebSocket')).toBeLessThan(result.indexOf('</body>'));
    expect(result.endsWith('</html>')).toBe(true);
  });

  it('appends the script when there is no </body>', () => {
    const html = '<p>plain</p>';
    const result = injectLiveReload(html);
    expect(result).toContain('new WebSocket');
  });

  it('produces a script that reloads on websocket messages', () => {
    const script = liveReloadScript();
    expect(script).toContain('new WebSocket');
    expect(script).toContain('location.reload');
    expect(script).toContain('location.host');
  });
});

describe('dev server', () => {
  let fixture: Fixture;
  let dev: DevServer;

  afterEach(async () => {
    if (dev) {
      await dev.close();
      dev = undefined as unknown as DevServer;
    }
    cleanupFixture(fixture);
  });

  function serve(overrides: Partial<{ port: number; templates: string }> = {}): Promise<DevServer> {
    const templates = overrides.templates ?? fixture.templatesDir;
    dev = startDevServer({
      content: fixture.contentDir,
      output: fixture.outputDir,
      templates,
      port: overrides.port ?? 0,
    });
    return new Promise((resolve) => {
      dev.server.on('listening', () => resolve(dev));
    });
  }

  function portOf(server: DevServer): number {
    return (server.server.address() as AddressInfo).port;
  }

  it('serves built pages with the live reload script injected', async () => {
    fixture = createFixture({ 'hello.md': '---\ntitle: Hello\n---\n\nHi there.' });
    const server = await serve();

    const html = await get(`http://localhost:${portOf(server)}/hello.html`);
    expect(html).toContain('<title>Hello</title>');
    expect(html).toContain('new WebSocket');

    const index = await get(`http://localhost:${portOf(server)}/`);
    expect(index).toContain('href="hello.html"');
    expect(index).toContain('new WebSocket');
  });

  it('rebuilds and notifies clients when a content file changes', async () => {
    fixture = createFixture({ 'a.md': '# A' });
    const server = await serve();
    const port = portOf(server);

    const ws = new WebSocket(`ws://localhost:${port}`);
    await new Promise<void>((resolve, reject) => {
      ws.on('open', () => resolve());
      ws.on('error', reject);
    });

    await server.ready();

    const message = waitForReload(ws, () => {
      writeFileSync(join(fixture.contentDir, 'a.md'), `# A changed ${Date.now()}`);
    });

    await expect(message).resolves.toBe('reload');
    const html = await get(`http://localhost:${port}/a.html`);
    expect(html).toContain('A changed');

    const closed = new Promise<void>((resolve) => ws.on('close', () => resolve()));
    ws.close();
    await closed;
  });

  it('rebuilds and notifies clients when a template changes', async () => {
    fixture = createFixture({ 'post.md': '---\ntitle: Post\n---\n\nBody.' }, { 'default.hbs': '<div>OLD</div>{{{content}}}' });
    const server = await serve();
    const port = portOf(server);

    const ws = new WebSocket(`ws://localhost:${port}`);
    await new Promise<void>((resolve, reject) => {
      ws.on('open', () => resolve());
      ws.on('error', reject);
    });

    await server.ready();

    const message = waitForReload(ws, () => {
      writeFileSync(join(fixture.templatesDir, 'default.hbs'), `<div>NEW</div>{{{content}}} ${Date.now()}`);
    });

    await expect(message).resolves.toBe('reload');
    const html = await get(`http://localhost:${port}/post.html`);
    expect(html).toContain('NEW');

    const closed = new Promise<void>((resolve) => ws.on('close', () => resolve()));
    ws.close();
    await closed;
  });

  it('returns 404 for unknown paths and 403 for path traversal', async () => {
    fixture = createFixture({ 'a.md': '# A' });
    const server = await serve();
    const port = portOf(server);

    const status = (path: string): Promise<number> =>
      new Promise((resolve, reject) => {
        http
          .get(`http://localhost:${port}${path}`, (res) => {
            res.resume();
            resolve(res.statusCode ?? 0);
          })
          .on('error', reject);
      });

    const rawStatus = (path: string): Promise<number> =>
      new Promise((resolve, reject) => {
        const socket = net.createConnection({ port }, () => {
          socket.write(`GET ${path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n`);
        });
        let data = '';
        socket.on('data', (chunk) => {
          data += chunk.toString();
        });
        socket.on('end', () => {
          const match = data.match(/^HTTP\/1\.1 (\d+)/);
          resolve(match ? Number(match[1]) : 0);
        });
        socket.on('error', reject);
      });

    await expect(status('/missing.html')).resolves.toBe(404);
    await expect(rawStatus('/%2e%2e/secret')).resolves.toBe(403);
  });

  it('exposes a DEFAULT_PORT of 3000', () => {
    expect(DEFAULT_PORT).toBe(3000);
  });

  it('leaves the raw source files untouched and writes the build output', async () => {
    fixture = createFixture({ 'page.md': '# Page' });
    const server = await serve();
    const port = portOf(server);

    const html = await get(`http://localhost:${port}/page.html`);
    expect(html).toContain('<h1>Page</h1>');
    expect(readFileSync(join(fixture.outputDir, 'page.html'), 'utf8')).toContain('<h1>Page</h1>');
    expect(server.address()).toContain(`localhost:${port}`);
  });
});
