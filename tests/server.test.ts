import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { get } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import WebSocket from 'ws';
import { DevelopmentServer, serveSite } from '../src/server';

function request(port: number, path: string): Promise<string> {
  return new Promise((resolve, reject) => {
    get(`http://localhost:${port}${path}`, (response) => {
      const chunks: Buffer[] = [];
      response.on('data', (chunk: Buffer) => chunks.push(chunk));
      response.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    }).on('error', reject);
  });
}

describe('development server', () => {
  let directory: string;
  let developmentServer: DevelopmentServer;

  beforeEach(async () => { directory = await mkdtemp(join(tmpdir(), 'ssg-server-')); });
  afterEach(async () => {
    await developmentServer?.close();
    await rm(directory, { recursive: true, force: true });
  });

  it('serves rebuilt pages with live-reload support and notifies connected browsers', async () => {
    const content = join(directory, 'content');
    const templates = join(directory, 'templates');
    const output = join(directory, 'dist');
    await mkdir(content, { recursive: true });
    await mkdir(templates, { recursive: true });
    await writeFile(join(content, 'page.md'), '---\ntitle: First\n---\nBody');
    developmentServer = await serveSite({ contentDir: content, templateDir: templates, outputDir: output, port: 0 });

    expect(await request(developmentServer.port, '/page.html')).toContain('new WebSocket');

    const client = new WebSocket(`ws://localhost:${developmentServer.port}`);
    await new Promise<void>((resolve, reject) => {
      client.once('open', resolve);
      client.once('error', reject);
    });
    const reloaded = new Promise<void>((resolve) => client.once('message', () => resolve()));
    await writeFile(join(content, 'page.md'), '---\ntitle: Second\n---\nUpdated');
    await reloaded;
    client.close();

    expect(await request(developmentServer.port, '/page.html')).toContain('<h1>Second</h1>');
  });
});
