import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { WebSocket } from 'ws';
import { startDevelopmentServer } from './dev-server';

describe('startDevelopmentServer', () => {
  it('serves rebuilt pages with the live reload client', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-server-'));
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    const output = join(root, 'dist');
    await mkdir(content, { recursive: true });
    await writeFile(join(content, 'page.md'), '# Hello', 'utf8');
    const server = await startDevelopmentServer({ contentDir: content, templateDir: templates, outputDir: output, port: 0 });

    try {
      const response = await fetch(`http://localhost:${server.port}/page.html`);
      const html = await response.text();
      expect(response.status).toBe(200);
      expect(html).toContain('<h1>Hello</h1>');
      expect(html).toContain('new WebSocket');
    } finally {
      await server.close();
    }
  });

  it('rebuilds and signals connected browsers after content changes', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-server-'));
    const content = join(root, 'content');
    const output = join(root, 'dist');
    await mkdir(content, { recursive: true });
    const page = join(content, 'page.md');
    await writeFile(page, '# Before', 'utf8');
    const server = await startDevelopmentServer({ contentDir: content, outputDir: output, port: 0 });
    const socket = new WebSocket(`ws://localhost:${server.port}`);

    try {
      await new Promise<void>((resolveOpen, rejectOpen) => {
        socket.once('open', resolveOpen);
        socket.once('error', rejectOpen);
      });
      const reloaded = new Promise<void>((resolveReload, rejectReload) => {
        socket.once('message', (message) => message.toString() === 'reload' ? resolveReload() : rejectReload(new Error('Unexpected WebSocket message')));
        socket.once('error', rejectReload);
      });
      await writeFile(page, '# After', 'utf8');
      await reloaded;
      await expect(fetch(`http://localhost:${server.port}/page.html`).then((response) => response.text())).resolves.toContain('<h1>After</h1>');
    } finally {
      socket.close();
      await server.close();
    }
  });
});
