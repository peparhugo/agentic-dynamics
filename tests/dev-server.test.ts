import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { WebSocket } from 'ws';
import { startDevServer, injectLiveReloadScript, WS_PATH } from '../src/dev-server';
import type { DevServerInstance } from '../src/dev-server';

async function waitFor(condition: () => boolean | Promise<boolean>, timeout = 5000): Promise<void> {
  const start = Date.now();
  while (!(await condition())) {
    if (Date.now() - start > timeout) {
      throw new Error('Timed out waiting for condition');
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
}

describe('injectLiveReloadScript', () => {
  it('injects the script before the closing body tag', () => {
    const html = '<!DOCTYPE html>\n<html>\n<body>\n<p>hi</p>\n</body>\n</html>';
    const injected = injectLiveReloadScript(html);
    expect(injected).toContain('<script>');
    expect(injected).toContain(WS_PATH);
    expect(injected).toContain('location.reload()');
    expect(injected.indexOf('<script>')).toBeGreaterThan(injected.indexOf('</p>'));
    expect(injected.indexOf('<script>')).toBeLessThan(injected.indexOf('</body>'));
  });

  it('injects before the closing html tag when there is no body', () => {
    const html = '<html><head><title>x</title></head><p>y</p></html>';
    const injected = injectLiveReloadScript(html);
    expect(injected.indexOf('<script>')).toBeLessThan(injected.indexOf('</html>'));
  });

  it('appends the script when there are no closing tags', () => {
    const injected = injectLiveReloadScript('<p>bare</p>');
    expect(injected.startsWith('<p>bare</p>')).toBe(true);
    expect(injected).toContain('<script>');
  });

  it('injects exactly one script per call', () => {
    const injected = injectLiveReloadScript('<html><body>x</body></html>');
    expect(injected.match(/new WebSocket\(/g) ?? []).toHaveLength(1);
  });
});

describe('startDevServer', () => {
  let tmp: string;
  let instance: DevServerInstance | undefined;

  beforeEach(() => {
    tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-dev-'));
  });

  afterEach(async () => {
    if (instance) {
      await instance.close();
    }
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  function writeContent(relPath: string, content: string): string {
    const full = path.join(tmp, 'content', relPath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content, 'utf8');
    return full;
  }

  async function start(opts: Partial<{ port: number; rebuildDelay: number }> = {}): Promise<DevServerInstance> {
    instance = await startDevServer({
      contentDir: path.join(tmp, 'content'),
      outputDir: path.join(tmp, 'dist'),
      templatesDir: path.join(tmp, 'templates'),
      siteTitle: 'Dev Site',
      host: '127.0.0.1',
      port: opts.port ?? 0,
      rebuildDelay: opts.rebuildDelay ?? 10,
    });
    return instance;
  }

  function baseUrl(server: DevServerInstance): string {
    return `http://127.0.0.1:${server.port}`;
  }

  function wsUrl(server: DevServerInstance): string {
    return `ws://127.0.0.1:${server.port}${WS_PATH}`;
  }

  function connect(server: DevServerInstance): Promise<WebSocket> {
    const socket = new WebSocket(wsUrl(server));
    return new Promise((resolve, reject) => {
      socket.on('open', () => resolve(socket));
      socket.on('error', reject);
    });
  }

  it('builds the site and serves pages with the live-reload script injected', async () => {
    writeContent('hello.md', '---\ntitle: Hello\ndate: 2024-01-01\n---\n\n# Hi there\n\nWelcome!');
    const server = await start();

    const indexRes = await fetch(`${baseUrl(server)}/`);
    expect(indexRes.status).toBe(200);
    const index = await indexRes.text();
    expect(index).toContain('<a href="hello.html">Hello</a>');
    expect(index).toContain('<script>');
    expect(index).toContain(WS_PATH);

    const pageRes = await fetch(`${baseUrl(server)}/hello.html`);
    expect(pageRes.status).toBe(200);
    const page = await pageRes.text();
    expect(page).toContain('<h1>Hi there</h1>');
    expect(page).toContain('<title>Hello</title>');
    expect(page).toContain(WS_PATH);
  });

  it('rebuilds on a content change and broadcasts a reload message', async () => {
    writeContent('post.md', '# Version one');
    const server = await start();

    let first = await (await fetch(`${baseUrl(server)}/post.html`)).text();
    expect(first).toContain('Version one');

    const messages: string[] = [];
    const socket = await connect(server);
    socket.on('message', (data) => {
      messages.push(data.toString());
    });

    writeContent('post.md', '# Version two');

    await waitFor(() => messages.includes('reload'));

    let updated = '';
    await waitFor(() => {
      return (async () => {
        updated = await (await fetch(`${baseUrl(server)}/post.html`)).text();
        return updated.includes('Version two');
      })();
    });
    expect(updated).toContain('Version two');
    expect(updated).not.toContain('Version one');
    socket.close();
  });

  it('rebuilds when a template changes', async () => {
    writeContent('page.md', '---\ntitle: Tpl Page\n---\n\n# Body');
    const templatesDir = path.join(tmp, 'templates');
    fs.mkdirSync(templatesDir, { recursive: true });
    fs.writeFileSync(path.join(templatesDir, 'default.hbs'), '<main class="first">\n{{{html}}}\n</main>');

    const server = await start();

    const messages: string[] = [];
    const socket = await connect(server);
    socket.on('message', (data) => {
      messages.push(data.toString());
    });

    let page = await (await fetch(`${baseUrl(server)}/page.html`)).text();
    expect(page).toContain('class="first"');

    fs.writeFileSync(path.join(templatesDir, 'default.hbs'), '<main class="second">\n{{{html}}}\n</main>');

    await waitFor(() => messages.includes('reload'));
    await waitFor(() => {
      return (async () => {
        page = await (await fetch(`${baseUrl(server)}/page.html`)).text();
        return page.includes('class="second"');
      })();
    });
    expect(page).not.toContain('class="first"');
    socket.close();
  });

  it('serves static assets and returns 404 for missing files', async () => {
    writeContent('page.md', '# Body');
    const server = await start();

    fs.writeFileSync(path.join(tmp, 'dist', 'style.css'), 'body { color: red; }');
    const cssRes = await fetch(`${baseUrl(server)}/style.css`);
    expect(cssRes.status).toBe(200);
    expect(await cssRes.text()).toContain('color: red');

    const missing = await fetch(`${baseUrl(server)}/nope.txt`);
    expect(missing.status).toBe(404);
  });

  it('honours an explicit port', async () => {
    writeContent('page.md', '# Body');
    const server = await start({ port: 0 });
    const chosen = server.port;
    await server.close();
    instance = undefined;

    instance = await startDevServer({
      contentDir: path.join(tmp, 'content'),
      outputDir: path.join(tmp, 'dist'),
      templatesDir: path.join(tmp, 'templates'),
      siteTitle: 'Dev Site',
      host: '127.0.0.1',
      port: chosen,
      rebuildDelay: 10,
    });

    expect(instance.port).toBe(chosen);
    const res = await fetch(`${baseUrl(instance)}/page.html`);
    expect(res.status).toBe(200);
  });

  it('close stops the server and releases the port', async () => {
    writeContent('page.md', '# Body');
    const server = await start();
    const port = server.port;

    await server.close();

    await expect(fetch(`http://127.0.0.1:${port}/`)).rejects.toThrow();
  });
});
