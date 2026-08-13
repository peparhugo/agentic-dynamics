import { promises as fs } from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { WebSocket } from 'ws';
import { startDevServer, type DevServer } from '../src/server';

function request(port: number, pathname = '/'): Promise<{ body: string; status: number | undefined }> {
  return new Promise((resolve, reject) => {
    http.get({ hostname: 'localhost', port, path: pathname }, (response) => {
      const chunks: Buffer[] = [];
      response.on('data', (chunk: Buffer) => chunks.push(chunk));
      response.on('end', () => resolve({ body: Buffer.concat(chunks).toString(), status: response.statusCode }));
    }).on('error', reject);
  });
}

function nextMessage(socket: WebSocket): Promise<string> {
  return new Promise((resolve, reject) => {
    socket.once('message', (data) => resolve(data.toString()));
    socket.once('error', reject);
  });
}

describe('development server', () => {
  let root: string;
  let contentDir: string;
  let templatesDir: string;
  let outputDir: string;
  let server: DevServer | undefined;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-server-'));
    contentDir = path.join(root, 'content');
    templatesDir = path.join(root, 'templates');
    outputDir = path.join(root, 'dist');
    await fs.mkdir(contentDir);
    await fs.mkdir(templatesDir);
    await fs.writeFile(path.join(contentDir, 'page.md'), '# First');
  });

  afterEach(async () => {
    await server?.close();
    await fs.rm(root, { recursive: true, force: true });
  });

  it('serves generated pages and injects the live reload client', async () => {
    server = await startDevServer({ contentDir, templatesDir, outputDir, port: 0 });

    const response = await request(server.port, '/page.html');

    expect(response.status).toBe(200);
    expect(response.body).toContain('<h1>First</h1>');
    expect(response.body).toContain("new WebSocket('ws://'+location.host+'/__ssg_reload')");
    expect(await fs.readFile(path.join(outputDir, 'page.html'), 'utf8')).not.toContain('__ssg_reload');
  });

  it('rebuilds changed content and signals connected browsers', async () => {
    server = await startDevServer({ contentDir, templatesDir, outputDir, port: 0 });
    const socket = new WebSocket(`ws://localhost:${server.port}/__ssg_reload`);
    await new Promise<void>((resolve, reject) => {
      socket.once('open', resolve);
      socket.once('error', reject);
    });
    const message = nextMessage(socket);

    await fs.writeFile(path.join(contentDir, 'page.md'), '# Updated');

    await expect(message).resolves.toBe('reload');
    expect((await request(server.port, '/page.html')).body).toContain('<h1>Updated</h1>');
    socket.close();
  });

  it('watches template changes and prevents paths outside the output directory', async () => {
    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<main>{{{content}}}</main>');
    server = await startDevServer({ contentDir, templatesDir, outputDir, port: 0 });
    const socket = new WebSocket(`ws://localhost:${server.port}/__ssg_reload`);
    await new Promise<void>((resolve, reject) => {
      socket.once('open', resolve);
      socket.once('error', reject);
    });
    const message = nextMessage(socket);

    await fs.writeFile(path.join(templatesDir, 'default.hbs'), '<article>{{{content}}}</article>');

    await expect(message).resolves.toBe('reload');
    expect((await request(server.port, '/page.html')).body).toContain('<article><h1>First</h1>');
    expect((await request(server.port, '/../package.json')).status).toBe(404);
    socket.close();
  });
});
