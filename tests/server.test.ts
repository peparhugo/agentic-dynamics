import { promises as fs } from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { WebSocket } from 'ws';
import { DevServer, serveSite } from '../src/server';

function request(port: number, pathname: string): Promise<{ body: Buffer; contentType?: string; status?: number }> {
  return new Promise((resolve, reject) => {
    http.get({ hostname: 'localhost', port, path: pathname }, (response) => {
      const chunks: Buffer[] = [];
      response.on('data', (chunk: Buffer) => chunks.push(chunk));
      response.on('end', () => resolve({
        body: Buffer.concat(chunks),
        contentType: response.headers['content-type'],
        status: response.statusCode
      }));
    }).on('error', reject);
  });
}

function openSocket(port: number): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(`ws://localhost:${port}/__ssg_live_reload`);
    socket.once('open', () => resolve(socket));
    socket.once('error', reject);
  });
}

function nextMessage(socket: WebSocket): Promise<string> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Timed out waiting for live reload')), 5000);
    socket.once('message', (data) => {
      clearTimeout(timeout);
      resolve(data.toString());
    });
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
    await fs.mkdir(templatesDir);
    await fs.writeFile(path.join(contentDir, 'hello.md'), '# First');
  });

  afterEach(async () => {
    await server?.close();
    await fs.rm(root, { recursive: true, force: true });
  });

  it('serves dist pages with live reload without modifying built HTML', async () => {
    server = await serveSite({ contentDir, outputDir, templatesDir, port: 0 });

    const response = await request(server.port, '/hello.html');
    const served = response.body.toString('utf8');
    const built = await fs.readFile(path.join(outputDir, 'hello.html'), 'utf8');

    expect(response.status).toBe(200);
    expect(response.contentType).toBe('text/html; charset=utf-8');
    expect(served).toContain('/__ssg_live_reload');
    expect(served.indexOf('/__ssg_live_reload')).toBeLessThan(served.indexOf('</body>'));
    expect(built).not.toContain('/__ssg_live_reload');
    await expect(request(server.port, '/../package.json')).resolves.toMatchObject({ status: 404 });
  });

  it('rebuilds changed content and broadcasts reload', async () => {
    server = await serveSite({ contentDir, outputDir, templatesDir, port: 0 });
    const socket = await openSocket(server.port);
    const message = nextMessage(socket);

    await fs.writeFile(path.join(contentDir, 'hello.md'), '# Updated');

    await expect(message).resolves.toBe('reload');
    await expect(fs.readFile(path.join(outputDir, 'hello.html'), 'utf8')).resolves.toContain('<h1>Updated</h1>');
    socket.close();
  });
});
