import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import WebSocket from 'ws';
import { DevServer, startDevServer } from '../src/server';

function get(url: string): Promise<{ statusCode: number; body: string }> {
  return new Promise((resolve, reject) => {
    http.get(url, (response) => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', (chunk: string) => { body += chunk; });
      response.on('end', () => resolve({ statusCode: response.statusCode ?? 0, body }));
    }).on('error', reject);
  });
}

describe('development server', () => {
  let directory: string;
  let content: string;
  let output: string;
  let server: DevServer;

  beforeEach(async () => {
    directory = await mkdtemp(path.join(os.tmpdir(), 'ssg-server-'));
    content = path.join(directory, 'content');
    output = path.join(directory, 'dist');
    await mkdir(content);
    await writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello\n---\nOriginal');
    server = await startDevServer({ contentDir: content, outputDir: output, port: 0 });
  });

  afterEach(async () => {
    await server.close();
    await rm(directory, { recursive: true, force: true });
  });

  it('serves built HTML with the live reload client injected', async () => {
    const response = await get(`http://localhost:${server.port}/hello.html`);

    expect(response.statusCode).toBe(200);
    expect(response.body).toContain('<p>Original</p>');
    expect(response.body).toContain('/__ssg_reload');
    await expect(readFile(path.join(output, 'hello.html'), 'utf8')).resolves.not.toContain('/__ssg_reload');
  });

  it('rebuilds and notifies connected browsers when content changes', async () => {
    const socket = new WebSocket(`ws://localhost:${server.port}/__ssg_reload`);
    await new Promise<void>((resolve, reject) => {
      socket.once('open', resolve);
      socket.once('error', reject);
    });
    const reloaded = new Promise<void>((resolve) => socket.once('message', () => resolve()));

    await writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello\n---\nUpdated');
    await reloaded;

    await expect(readFile(path.join(output, 'hello.html'), 'utf8')).resolves.toContain('<p>Updated</p>');
    socket.close();
  });
});
