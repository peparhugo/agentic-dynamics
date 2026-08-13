import { promises as fs } from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { WebSocket } from 'ws';
import { DevServer, startDevServer } from '../src/server';

function request(port: number, pathname: string): Promise<{ status: number; body: string; type: string }> {
  return new Promise((resolve, reject) => {
    http.get({ hostname: 'localhost', port, path: pathname }, (response) => {
      const chunks: Buffer[] = [];
      response.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
      response.on('end', () => resolve({
        status: response.statusCode ?? 0,
        body: Buffer.concat(chunks).toString('utf8'),
        type: String(response.headers['content-type']),
      }));
    }).on('error', reject);
  });
}

describe('development server', () => {
  let root: string;
  let contentDir: string;
  let outputDir: string;
  let templatesDir: string;
  let server: DevServer | undefined;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-server-'));
    contentDir = path.join(root, 'content');
    outputDir = path.join(root, 'dist');
    templatesDir = path.join(root, 'templates');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'page.md'), '# First');
  });

  afterEach(async () => {
    await server?.close();
    await fs.rm(root, { recursive: true, force: true });
  });

  it('serves dist HTML with the live reload client injected', async () => {
    server = await startDevServer({ contentDir, outputDir, templatesDir, port: 0 });

    const page = await request(server.port, '/page.html');
    const missing = await request(server.port, '/missing.html');

    expect(page.status).toBe(200);
    expect(page.type).toBe('text/html; charset=utf-8');
    expect(page.body).toContain('<h1>First</h1>');
    expect(page.body).toContain("event.data === 'reload'");
    expect(missing.status).toBe(404);
  });

  it('rebuilds changed content and notifies WebSocket clients', async () => {
    server = await startDevServer({ contentDir, outputDir, templatesDir, port: 0 });
    const socket = new WebSocket(`ws://localhost:${server.port}`);
    await new Promise<void>((resolve, reject) => {
      socket.once('open', resolve);
      socket.once('error', reject);
    });
    const reload = new Promise<void>((resolve, reject) => {
      socket.once('message', (message) => message.toString() === 'reload' ? resolve() : reject(new Error('Unexpected message')));
      socket.once('error', reject);
    });

    await fs.writeFile(path.join(contentDir, 'page.md'), '# Updated');
    await reload;

    const page = await request(server.port, '/page.html');
    expect(page.body).toContain('<h1>Updated</h1>');
    socket.close();
  });
});
