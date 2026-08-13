import { promises as fs } from 'node:fs';
import { get } from 'node:http';
import os from 'node:os';
import path from 'node:path';
import WebSocket from 'ws';
import { startDevServer, type DevServer } from '../src';

function fetch(port: number, pathname: string): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    get(`http://localhost:${port}${pathname}`, (response) => {
      const chunks: Buffer[] = [];
      response.on('data', (chunk: Buffer) => chunks.push(chunk));
      response.on('end', () => resolve({
        status: response.statusCode ?? 0,
        body: Buffer.concat(chunks).toString('utf8')
      }));
    }).on('error', reject);
  });
}

describe('startDevServer', () => {
  let root: string;
  let server: DevServer | undefined;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-server-'));
  });

  afterEach(async () => {
    await server?.close();
    await fs.rm(root, { recursive: true, force: true });
  });

  test('builds and serves dist pages with a live-reload client', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Served page');

    server = await startDevServer({ contentDir, outputDir, port: 0 });
    const response = await fetch(server.port, '/page.html');
    const builtHtml = await fs.readFile(path.join(outputDir, 'page.html'), 'utf8');

    expect(response.status).toBe(200);
    expect(response.body).toContain('<h1>Served page</h1>');
    expect(response.body).toContain('new WebSocket(`ws://${location.host}`)');
    expect(response.body).toContain("event.data === 'reload'");
    expect(builtHtml).not.toContain('new WebSocket');
  });

  test('rebuilds changed content and notifies WebSocket clients', async () => {
    const contentDir = path.join(root, 'content');
    const outputDir = path.join(root, 'dist');
    const templatesDir = path.join(root, 'templates');
    await fs.mkdir(contentDir);
    await fs.mkdir(templatesDir);
    const contentFile = path.join(contentDir, 'page.md');
    await fs.writeFile(contentFile, '# Before');

    server = await startDevServer({ contentDir, outputDir, templatesDir, port: 0 });
    const socket = new WebSocket(`ws://localhost:${server.port}`);
    await new Promise<void>((resolve, reject) => {
      socket.once('open', resolve);
      socket.once('error', reject);
    });
    const reload = new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Timed out waiting for reload')), 5000);
      socket.once('message', (data) => {
        clearTimeout(timeout);
        if (data.toString() === 'reload') resolve();
        else reject(new Error(`Unexpected message: ${data.toString()}`));
      });
    });

    await fs.writeFile(contentFile, '# After');
    await reload;

    await expect(fs.readFile(path.join(outputDir, 'page.html'), 'utf8')).resolves.toContain('<h1>After</h1>');
    socket.close();
  });

  test('returns 404 for missing files and blocks traversal', async () => {
    const contentDir = path.join(root, 'content');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'page.md'), 'Page');
    server = await startDevServer({ contentDir, outputDir: path.join(root, 'dist'), port: 0 });

    await expect(fetch(server.port, '/missing.html')).resolves.toMatchObject({ status: 404 });
    await expect(fetch(server.port, '/..%2Fcontent%2Fpage.md')).resolves.toMatchObject({ status: 400 });
  });
});
