import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import WebSocket from 'ws';
import { startDevServer, type DevServer } from '../src/server';

describe('development server', () => {
  let root: string;
  let server: DevServer | undefined;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-server-'));
    await fs.mkdir(path.join(root, 'content'));
    await fs.mkdir(path.join(root, 'templates'));
    await fs.writeFile(path.join(root, 'content', 'hello.md'), '---\ntitle: Hello\n---\nFirst version');
  });

  afterEach(async () => {
    await server?.close();
    await fs.rm(root, { recursive: true, force: true });
  });

  it('serves dist HTML with the live-reload client injected', async () => {
    server = await startDevServer({
      contentDir: path.join(root, 'content'),
      templatesDir: path.join(root, 'templates'),
      outputDir: path.join(root, 'dist'),
      port: 0,
    });

    const response = await fetch(`http://localhost:${server.port}/hello.html`);
    const html = await response.text();

    expect(response.status).toBe(200);
    expect(response.headers.get('cache-control')).toBe('no-store');
    expect(html).toContain('First version');
    expect(html).toContain("new WebSocket(protocol+location.host+'/__ssg_reload')");
    expect(html.indexOf('new WebSocket')).toBeLessThan(html.indexOf('</body>'));
  });

  it('rebuilds changes and notifies connected browsers', async () => {
    server = await startDevServer({
      contentDir: path.join(root, 'content'),
      templatesDir: path.join(root, 'templates'),
      outputDir: path.join(root, 'dist'),
      port: 0,
    });
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

    await fs.writeFile(path.join(root, 'content', 'hello.md'), '---\ntitle: Hello\n---\nSecond version');
    await reloaded;

    const response = await fetch(`http://localhost:${server.port}/hello.html`);
    await expect(response.text()).resolves.toContain('Second version');
    socket.close();
  });

  it('does not serve paths outside dist', async () => {
    await fs.writeFile(path.join(root, 'secret.txt'), 'secret');
    server = await startDevServer({
      contentDir: path.join(root, 'content'),
      templatesDir: path.join(root, 'templates'),
      outputDir: path.join(root, 'dist'),
      port: 0,
    });

    const response = await fetch(`http://localhost:${server.port}/%2e%2e/secret.txt`);
    expect(response.status).toBe(404);
  });
});
