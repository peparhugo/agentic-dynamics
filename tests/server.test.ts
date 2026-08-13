import { promises as fs } from 'node:fs';
import { get } from 'node:http';
import os from 'node:os';
import path from 'node:path';
import WebSocket from 'ws';
import { serveSite, type DevServer } from '../src/server';

function request(port: number, pathname = '/'): Promise<{ status: number | undefined; body: string }> {
  return new Promise((resolve, reject) => {
    get(`http://localhost:${port}${pathname}`, (response) => {
      const chunks: Buffer[] = [];
      response.on('data', (chunk: Buffer) => chunks.push(chunk));
      response.on('end', () => resolve({
        status: response.statusCode,
        body: Buffer.concat(chunks).toString('utf8'),
      }));
    }).on('error', reject);
  });
}

describe('development server', () => {
  let temporaryDirectory: string;
  let server: DevServer | undefined;

  beforeEach(async () => {
    temporaryDirectory = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-server-'));
  });

  afterEach(async () => {
    await server?.close();
    await fs.rm(temporaryDirectory, { recursive: true, force: true });
    jest.restoreAllMocks();
  });

  it('serves dist HTML with the live reload client injected', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'dist');
    await fs.mkdir(contentDir);
    await fs.writeFile(path.join(contentDir, 'page.md'), '# Page');

    server = await serveSite({ contentDir, outputDir, port: 0 });
    const response = await request(server.port, '/page.html');
    const generated = await fs.readFile(path.join(outputDir, 'page.html'), 'utf8');

    expect(response.status).toBe(200);
    expect(response.body).toContain('<h1>Page</h1>');
    expect(response.body).toContain("new WebSocket(protocol + '//' + location.host)");
    expect(generated).not.toContain('new WebSocket');
    await expect(request(server.port, '/../package.json')).resolves.toEqual(expect.objectContaining({ status: 404 }));
  });

  it('rebuilds changed content and tells connected browsers to reload', async () => {
    const contentDir = path.join(temporaryDirectory, 'content');
    const outputDir = path.join(temporaryDirectory, 'dist');
    await fs.mkdir(contentDir);
    const page = path.join(contentDir, 'page.md');
    await fs.writeFile(page, '# Before');
    jest.spyOn(console, 'log').mockImplementation();
    server = await serveSite({ contentDir, outputDir, port: 0 });

    const socket = new WebSocket(`ws://localhost:${server.port}`);
    await new Promise<void>((resolve, reject) => {
      socket.once('open', resolve);
      socket.once('error', reject);
    });
    const reload = new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Timed out waiting for reload')), 5000);
      socket.once('message', (message) => {
        clearTimeout(timeout);
        if (message.toString() === 'reload') resolve();
        else reject(new Error(`Unexpected message: ${message.toString()}`));
      });
    });

    await fs.writeFile(page, '# After');
    await reload;
    await expect(request(server.port, '/page.html')).resolves.toEqual(expect.objectContaining({
      body: expect.stringContaining('<h1>After</h1>'),
    }));
    socket.close();
  });
});
