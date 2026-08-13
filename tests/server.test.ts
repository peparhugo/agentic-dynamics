import { promises as fs } from 'node:fs';
import { get } from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { WebSocket } from 'ws';
import { startDevelopmentServer } from '../src/server.js';

function request(url: string): Promise<{ statusCode?: number; body: string }> {
  return new Promise((resolve, reject) => {
    get(url, (response) => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => { body += chunk; });
      response.on('end', () => resolve({ statusCode: response.statusCode, body }));
    }).on('error', reject);
  });
}

describe('development server', () => {
  let directory: string;

  beforeEach(async () => {
    directory = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-server-'));
  });

  afterEach(async () => {
    await fs.rm(directory, { recursive: true, force: true });
  });

  it('serves built pages with the live-reload client and broadcasts after rebuilds', async () => {
    const content = path.join(directory, 'content');
    const templates = path.join(directory, 'templates');
    await fs.mkdir(content);
    await fs.mkdir(templates);
    await fs.writeFile(path.join(content, 'page.md'), '---\ntitle: Before\n---\nText');
    const developmentServer = await startDevelopmentServer({ contentDir: content, templatesDir: templates, outputDir: path.join(directory, 'dist'), port: 0 });
    const socket = new WebSocket(`ws://localhost:${developmentServer.port}`);

    try {
      await new Promise<void>((resolve) => socket.once('open', resolve));
      await expect(request(`http://localhost:${developmentServer.port}/page.html`)).resolves.toMatchObject({
        statusCode: 200,
        body: expect.stringContaining('new WebSocket'),
      });
      const reloaded = new Promise<void>((resolve) => socket.once('message', (message) => {
        if (message.toString() === 'reload') resolve();
      }));
      await fs.writeFile(path.join(content, 'page.md'), '---\ntitle: After\n---\nText');
      await reloaded;
      await expect(request(`http://localhost:${developmentServer.port}/page.html`)).resolves.toMatchObject({ body: expect.stringContaining('After') });
    } finally {
      socket.close();
      await developmentServer.close();
    }
  });
});
