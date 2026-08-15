import * as http from 'http';
import { promises as fs } from 'fs';
import * as os from 'os';
import * as path from 'path';
import WebSocket from 'ws';
import { startDevServer, injectReloadScript, reloadClientScript } from '../src/serve';
import { DevServer } from '../src/serve';

const LIVERELOAD_PATH = '/__ssg_livereload';

async function makeSite(): Promise<{
  root: string;
  contentDir: string;
  outputDir: string;
  templatesDir: string;
}> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-serve-test-'));
  const contentDir = path.join(root, 'content');
  const outputDir = path.join(root, 'dist');
  const templatesDir = path.join(root, 'templates');
  await fs.mkdir(contentDir, { recursive: true });
  await fs.writeFile(
    path.join(contentDir, 'hello.md'),
    ['---', 'title: Hello', 'date: 2024-01-01', '---', '# Hello', 'World'].join('\n'),
    'utf8'
  );
  return { root, contentDir, outputDir, templatesDir };
}

function get(url: string): Promise<string> {
  return new Promise((resolve, reject) => {
    http
      .get(url, (res) => {
        let data = '';
        res.on('data', (chunk) => {
          data += chunk;
        });
        res.on('end', () => resolve(data));
      })
      .on('error', reject);
  });
}

function status(url: string): Promise<number> {
  return new Promise((resolve, reject) => {
    http
      .get(url, (res) => {
        res.resume();
        res.on('end', () => resolve(res.statusCode ?? 0));
      })
      .on('error', reject);
  });
}

async function waitFor(
  predicate: () => Promise<boolean> | boolean,
  timeoutMs = 8000
): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await predicate()) {
      return;
    }
    await new Promise((r) => setTimeout(r, 50));
  }
  throw new Error('waitFor timed out');
}

async function startDev(
  overrides: Partial<{ contentDir: string; outputDir: string; templatesDir: string }> = {}
): Promise<{ dev: DevServer; site: Awaited<ReturnType<typeof makeSite>> }> {
  const site = await makeSite();
  const dev = await startDevServer({
    contentDir: overrides.contentDir ?? site.contentDir,
    outputDir: overrides.outputDir ?? site.outputDir,
    templatesDir: overrides.templatesDir ?? site.templatesDir,
    port: 0,
  });
  return { dev, site };
}

describe('injectReloadScript', () => {
  it('injects the client script before </body>', () => {
    const html = '<html><body><h1>Hi</h1></body></html>';
    const injected = injectReloadScript(html);
    expect(injected.indexOf(reloadClientScript())).toBeLessThan(
      injected.indexOf('</body>')
    );
    expect(injected).toContain(LIVERELOAD_PATH);
    expect(injected).toContain('</body>');
  });

  it('appends the script when there is no </body>', () => {
    const injected = injectReloadScript('<p>no body tag</p>');
    expect(injected).toContain(LIVERELOAD_PATH);
    expect(injected).toContain('<p>no body tag</p>');
  });

  it('injects only the client script content, never a duplicate </body>', () => {
    const html = '<html><body><h1>Hi</h1></body></html>';
    const injected = injectReloadScript(html);
    expect(injected.match(/<\/body>/g)).toHaveLength(1);
    expect(injected.match(/<\/script>/g)).toHaveLength(1);
  });
});

describe('startDevServer', () => {
  it('serves the initial build and injects the live-reload script', async () => {
    const { dev } = await startDev();
    try {
      const index = await get(`http://localhost:${dev.port}/`);
      expect(index).toContain('<h1>Index</h1>');
      expect(index).toContain('href="hello.html"');
      expect(index).toContain(LIVERELOAD_PATH);

      const page = await get(`http://localhost:${dev.port}/hello.html`);
      expect(page).toContain('<h1>Hello</h1>');
      expect(page).toContain('World');
      expect(page).toContain(LIVERELOAD_PATH);
    } finally {
      await dev.close();
    }
  });

  it('serves from the output directory even when it differs from ./dist', async () => {
    const site = await makeSite();
    const dev = await startDevServer({
      contentDir: site.contentDir,
      outputDir: path.join(site.root, 'public'),
      templatesDir: site.templatesDir,
      port: 0,
    });
    try {
      const page = await get(`http://localhost:${dev.port}/hello.html`);
      expect(page).toContain('World');
    } finally {
      await dev.close();
    }
  });

  it('rebuilds and serves new content when a file changes', async () => {
    const { dev, site } = await startDev();
    try {
      await fs.writeFile(path.join(site.contentDir, 'new.md'), '# New Page', 'utf8');
      await waitFor(async () => {
        try {
          const html = await get(`http://localhost:${dev.port}/new.html`);
          return html.includes('<h1>New Page</h1>');
        } catch {
          return false;
        }
      });
    } finally {
      await dev.close();
    }
  });

  it('rebuilds pages when a template changes', async () => {
    const { dev, site } = await startDev();
    try {
      const templatesDir = path.join(site.root, 'templates');
      await fs.mkdir(templatesDir, { recursive: true });
      await fs.writeFile(
        path.join(templatesDir, 'default.hbs'),
        'TEMPLATED {{title}}',
        'utf8'
      );
      await waitFor(async () => {
        const page = await get(`http://localhost:${dev.port}/hello.html`);
        return page.includes('TEMPLATED Hello');
      });
    } finally {
      await dev.close();
    }
  });

  it('reloads the index after a content change', async () => {
    const { dev, site } = await startDev();
    try {
      await fs.writeFile(
        path.join(site.contentDir, 'second.md'),
        ['---', 'title: Second', '---', '# Second'].join('\n'),
        'utf8'
      );
      await waitFor(async () => {
        const index = await get(`http://localhost:${dev.port}/`);
        return index.includes('href="second.html"');
      });
    } finally {
      await dev.close();
    }
  });

  it('broadcasts a reload message over WebSocket after a rebuild', async () => {
    const { dev, site } = await startDev();
    const ws = new WebSocket(`ws://localhost:${dev.port}${LIVERELOAD_PATH}`);
    try {
      const messages: string[] = [];
      ws.on('message', (data) => messages.push(data.toString()));
      await new Promise<void>((resolve, reject) => {
        ws.once('open', resolve);
        ws.once('error', reject);
      });

      await fs.writeFile(
        path.join(site.contentDir, 'hello.md'),
        ['---', 'title: Hello Updated', '---', '# Hello Updated'].join('\n'),
        'utf8'
      );

      await waitFor(() => messages.includes('reload'));
      expect(messages).toContain('reload');
    } finally {
      ws.close();
      await dev.close();
    }
  });

  it('returns 404 for unknown paths and guards against traversal', async () => {
    const { dev, site } = await startDev();
    try {
      expect(await status(`http://localhost:${dev.port}/nope.html`)).toBe(404);

      const traversalStatus = await new Promise<number>((resolve, reject) => {
        const req = http.request(
          {
            host: 'localhost',
            port: dev.port,
            path: '/../package.json',
          },
          (res) => {
            res.resume();
            res.on('end', () => resolve(res.statusCode ?? 0));
          }
        );
        req.on('error', reject);
        req.end();
      });
      expect(traversalStatus).toBe(403);

      const escaped = await new Promise<number>((resolve, reject) => {
        const req = http.request(
          {
            host: 'localhost',
            port: dev.port,
            path: `/%2e%2e/${path.basename(site.root)}/package.json`,
          },
          (res) => {
            res.resume();
            res.on('end', () => resolve(res.statusCode ?? 0));
          }
        );
        req.on('error', reject);
        req.end();
      });
      expect(escaped).toBe(403);
    } finally {
      await dev.close();
    }
  });

  it('stops accepting connections after close', async () => {
    const { dev } = await startDev();
    const port = dev.port;
    await dev.close();
    await expect(status(`http://localhost:${port}/`)).rejects.toThrow();
  });
});
