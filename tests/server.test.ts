import { promises as fs } from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { startDevServer, type DevServer } from '../src/server';

interface TestWebSocket {
  close(): void;
  once(event: 'open' | 'close', listener: () => void): this;
  once(event: 'error', listener: (error: Error) => void): this;
  once(event: 'message', listener: (data: Buffer) => void): this;
}

const WebSocket = require('ws') as new(url: string) => TestWebSocket;

function request(port: number, pathname: string): Promise<{ body: string; status: number | undefined }> {
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
  let server: DevServer | undefined;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-server-'));
  });

  afterEach(async () => {
    await server?.close();
    server = undefined;
    await fs.rm(root, { recursive: true, force: true });
  });

  test('builds and serves HTML with the live reload client', async () => {
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'page.md'), 'Hello');

    server = await startDevServer({ contentDir: content, outputDir: output, port: 0 });
    const page = await request(server.port, '/page.html');
    const missing = await request(server.port, '/missing.html');

    expect(page.status).toBe(200);
    expect(page.body).toContain('<p>Hello</p>');
    expect(page.body).toContain('new WebSocket');
    expect(page.body).toContain("event.data === 'reload'");
    expect(missing.status).toBe(404);
  });

  test('rebuilds changed content and broadcasts reload', async () => {
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await fs.mkdir(content);
    await fs.writeFile(path.join(content, 'page.md'), 'Before');
    server = await startDevServer({ contentDir: content, outputDir: output, port: 0 });

    const socket = new WebSocket(`ws://localhost:${server.port}`);
    await new Promise<void>((resolve, reject) => {
      socket.once('open', resolve);
      socket.once('error', reject);
    });
    const reloaded = new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Timed out waiting for reload')), 5000);
      socket.once('message', (data) => {
        clearTimeout(timeout);
        expect(data.toString()).toBe('reload');
        resolve();
      });
    });

    await fs.writeFile(path.join(content, 'page.md'), 'After');
    await reloaded;
    expect((await request(server.port, '/page.html')).body).toContain('<p>After</p>');
    socket.close();
    await new Promise<void>((resolve) => socket.once('close', () => resolve()));
  });
});
