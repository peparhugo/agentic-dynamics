import http from 'http';
import fs from 'fs';
import path from 'path';
import net from 'net';
import { serve } from '../src/serve';

function createTempDir(prefix: string): string {
  const dir = path.resolve(__dirname, '..', `${prefix}-${Date.now()}`);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function cleanupDir(dir: string): void {
  if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true });
}

function get(url: string, port: number): Promise<{ status: number; body: string; headers: http.IncomingHttpHeaders }> {
  return new Promise((resolve, reject) => {
    http.get(`http://localhost:${port}${url}`, (res) => {
      const chunks: Buffer[] = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        resolve({
          status: res.statusCode || 0,
          body: Buffer.concat(chunks).toString(),
          headers: res.headers,
        });
      });
    }).on('error', reject);
  });
}

function setupFixtures(): { content: string; output: string; templates: string } {
  const content = createTempDir('serve-content');
  const output = createTempDir('serve-output');
  const templates = createTempDir('serve-templates');

  fs.mkdirSync(path.join(templates, 'layouts'), { recursive: true });
  fs.mkdirSync(path.join(templates, 'partials'), { recursive: true });

  fs.writeFileSync(
    path.join(templates, 'layouts', 'default.hbs'),
    '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{> nav}}{{{body}}}</body></html>'
  );
  fs.writeFileSync(
    path.join(templates, 'partials', 'nav.hbs'),
    '<nav><a href="index.html">Home</a></nav>'
  );
  fs.writeFileSync(
    path.join(templates, 'index.hbs'),
    '<h1>My Site</h1><ul>{{#each pages}}<li><a href="{{slug}}.html">{{title}}</a></li>{{/each}}</ul>'
  );
  fs.writeFileSync(
    path.join(templates, 'page.hbs'),
    '<article><h1>{{title}}</h1><div>{{{content}}}</div></article>'
  );

  fs.writeFileSync(
    path.join(content, 'hello.md'),
    '---\ntitle: Hello World\ndate: 2025-01-01\n---\n# Hello'
  );
  fs.writeFileSync(
    path.join(content, 'about.md'),
    '---\ntitle: About\n---\n## About Us'
  );

  return { content, output, templates };
}

async function waitForServer(port: number, timeoutMs: number = 5000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      await get('/', port);
      return;
    } catch {
      await new Promise(r => setTimeout(r, 100));
    }
  }
  throw new Error('Server did not start in time');
}

function closeServer(srv: http.Server): Promise<void> {
  return new Promise((resolve) => {
    const timeout = setTimeout(() => resolve(), 2000);
    srv.closeAllConnections?.();
    srv.close(() => {
      clearTimeout(timeout);
      resolve();
    });
  });
}

describe('serve', () => {
  const dirs: { content: string; output: string; templates: string }[] = [];
  const servers: http.Server[] = [];

  afterEach(async () => {
    for (const s of servers.splice(0)) {
      await closeServer(s);
    }
    for (const d of dirs.splice(0)) {
      cleanupDir(d.content);
      cleanupDir(d.output);
      cleanupDir(d.templates);
    }
  });

  test('serves index.html at /', async () => {
    const fixtures = setupFixtures();
    dirs.push(fixtures);
    const port = 1024 + Math.floor(Math.random() * 30000);
    const srv = serve({
      contentDir: fixtures.content,
      outputDir: fixtures.output,
      templatesDir: fixtures.templates,
      port,
    });
    servers.push(srv);
    await waitForServer(port);

    const res = await get('/', port);
    expect(res.status).toBe(200);
    expect(res.body).toContain('<h1>My Site</h1>');
    expect(res.body).toContain('Hello World');
    expect(res.body).toContain('About');
  });

  test('serves individual page html', async () => {
    const fixtures = setupFixtures();
    dirs.push(fixtures);
    const port = 1024 + Math.floor(Math.random() * 30000);
    const srv = serve({
      contentDir: fixtures.content,
      outputDir: fixtures.output,
      templatesDir: fixtures.templates,
      port,
    });
    servers.push(srv);
    await waitForServer(port);

    const res = await get('/hello.html', port);
    expect(res.status).toBe(200);
    expect(res.body).toContain('<h1>Hello World</h1>');
    expect(res.body).toContain('<h1>Hello</h1>');
  });

  test('injects livereload script into html pages', async () => {
    const fixtures = setupFixtures();
    dirs.push(fixtures);
    const port = 1024 + Math.floor(Math.random() * 30000);
    const srv = serve({
      contentDir: fixtures.content,
      outputDir: fixtures.output,
      templatesDir: fixtures.templates,
      port,
    });
    servers.push(srv);
    await waitForServer(port);

    const res = await get('/', port);
    expect(res.body).toContain('__livereload');
    expect(res.body).toContain(`ws://localhost:${port}/__livereload`);
    expect(res.body).toContain('window.location.reload()');

    const res2 = await get('/about.html', port);
    expect(res2.body).toContain('__livereload');
    expect(res2.body).toContain(`ws://localhost:${port}/__livereload`);
  });

  test('returns 404 for missing files', async () => {
    const fixtures = setupFixtures();
    dirs.push(fixtures);
    const port = 1024 + Math.floor(Math.random() * 30000);
    const srv = serve({
      contentDir: fixtures.content,
      outputDir: fixtures.output,
      templatesDir: fixtures.templates,
      port,
    });
    servers.push(srv);
    await waitForServer(port);

    const res = await get('/nonexistent.html', port);
    expect(res.status).toBe(404);
  });

  test('returns 403 for paths outside output directory', async () => {
    const fixtures = setupFixtures();
    dirs.push(fixtures);
    const port = 1024 + Math.floor(Math.random() * 30000);
    const srv = serve({
      contentDir: fixtures.content,
      outputDir: fixtures.output,
      templatesDir: fixtures.templates,
      port,
    });
    servers.push(srv);
    await waitForServer(port);

    // Test the security check directly: verify that a path that resolves outside
    // the output directory is rejected. Use a raw net socket to avoid Node URL
    // normalization of '..' segments.
    const result = await new Promise<number>((resolve, reject) => {
      const socket = net.createConnection({ port, host: 'localhost' }, () => {
        socket.write('GET /../../etc/passwd HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n');
      });
      socket.setEncoding('utf-8');
      let data = '';
      socket.on('data', (chunk) => { data += chunk; });
      socket.on('end', () => {
        const statusLine = data.split('\r\n')[0] || '';
        const status = parseInt(statusLine.split(' ')[1], 10) || 0;
        resolve(status);
      });
      socket.on('error', reject);
    });
    expect(result).toBe(403);
  });

  test('serves css files without livereload injection', async () => {
    const fixtures = setupFixtures();
    dirs.push(fixtures);
    const port = 1024 + Math.floor(Math.random() * 30000);
    const srv = serve({
      contentDir: fixtures.content,
      outputDir: fixtures.output,
      templatesDir: fixtures.templates,
      port,
    });
    servers.push(srv);
    await waitForServer(port);

    fs.writeFileSync(path.join(fixtures.output, 'styles.css'), 'body { color: red; }');

    const res = await get('/styles.css', port);
    expect(res.status).toBe(200);
    expect(res.body).toBe('body { color: red; }');
    expect(res.body).not.toContain('__livereload');
    expect(res.headers['content-type']).toContain('text/css');
  });

  test('respects custom --port option', async () => {
    const fixtures = setupFixtures();
    dirs.push(fixtures);
    const customPort = 1024 + Math.floor(Math.random() * 30000);
    const srv = serve({
      contentDir: fixtures.content,
      outputDir: fixtures.output,
      templatesDir: fixtures.templates,
      port: customPort,
    });
    servers.push(srv);
    await waitForServer(customPort);

    const res = await get('/', customPort);
    expect(res.status).toBe(200);
  });
});
