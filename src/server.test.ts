import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { get } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { startDevServer } from './server';

describe('startDevServer', () => {
  let root: string;

  beforeEach(async () => { root = await mkdtemp(join(tmpdir(), 'ssg-server-')); });
  afterEach(async () => { await rm(root, { recursive: true, force: true }); });

  it('serves generated pages with the live reload client', async () => {
    const content = join(root, 'content');
    const templates = join(root, 'templates');
    await mkdir(content, { recursive: true });
    await mkdir(templates, { recursive: true });
    await writeFile(join(content, 'welcome.md'), '# Welcome');
    const server = await startDevServer({ contentDirectory: content, templatesDirectory: templates, outputDirectory: join(root, 'dist'), port: 0 });

    const page = await new Promise<string>((resolvePage, reject) => {
      get(`http://localhost:${server.port}/welcome.html`, (response) => {
        const chunks: Buffer[] = [];
        response.on('data', (chunk: Buffer) => chunks.push(chunk));
        response.on('end', () => resolvePage(Buffer.concat(chunks).toString('utf8')));
      }).on('error', reject);
    });

    expect(page).toContain('<h1>Welcome</h1>');
    expect(page).toContain('new WebSocket');
    await server.close();
  });
});
