import { promises as fs } from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { WebSocket } from 'ws';
import { type DevelopmentServer, startDevelopmentServer } from '../src/server';

function get(port: number, pathname: string): Promise<{ body: string; status: number | undefined }> {
  return new Promise((resolve, reject) => {
    http.get({ hostname: 'localhost', port, path: pathname }, (response) => {
      const chunks: Buffer[] = [];
      response.on('data', (chunk: Buffer) => chunks.push(chunk));
      response.on('end', () => resolve({ body: Buffer.concat(chunks).toString(), status: response.statusCode }));
    }).on('error', reject);
  });
}

describe('development server', () => {
  let root: string;
  let content: string;
  let output: string;
  let templates: string;
  let server: DevelopmentServer | undefined;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-server-'));
    content = path.join(root, 'content');
    output = path.join(root, 'dist');
    templates = path.join(root, 'templates');
    await fs.mkdir(content);
    await fs.mkdir(templates);
  });

  afterEach(async () => {
    await server?.close();
    await fs.rm(root, { recursive: true, force: true });
  });

  it('serves generated pages and reloads browsers after changes', async () => {
    const source = path.join(content, 'hello.md');
    await fs.writeFile(source, '# First version');
    server = await startDevelopmentServer({ content, output, templates, port: 0 });

    const initial = await get(server.port, '/hello.html');
    expect(initial.status).toBe(200);
    expect(initial.body).toContain('<h1>First version</h1>');
    expect(initial.body).toContain("new WebSocket(protocol + '//' + location.host + '/__ssg_reload')");

    const socket = new WebSocket(`ws://localhost:${server.port}/__ssg_reload`);
    await new Promise<void>((resolve, reject) => {
      socket.once('open', resolve);
      socket.once('error', reject);
    });
    const reloaded = new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Timed out waiting for reload')), 5000);
      socket.once('message', (message) => {
        clearTimeout(timeout);
        expect(message.toString()).toBe('reload');
        resolve();
      });
    });

    await fs.writeFile(source, '# Second version');
    await reloaded;
    expect((await get(server.port, '/hello.html')).body).toContain('<h1>Second version</h1>');
    socket.close();
  });

  it('returns 404 for files outside the output directory', async () => {
    await fs.writeFile(path.join(content, 'hello.md'), 'Hello');
    await fs.writeFile(path.join(root, 'secret.txt'), 'secret');
    server = await startDevelopmentServer({ content, output, templates, port: 0 });

    const response = await get(server.port, '/..%2fsecret.txt');
    expect(response.status).toBe(404);
    expect(response.body).not.toContain('secret');
  });
});
