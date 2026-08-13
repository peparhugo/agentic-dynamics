import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { startDevServer } from '../src/server.js';

describe('startDevServer', () => {
  it('serves generated HTML with the live reload client', async () => {
    const root = await mkdtemp(join(tmpdir(), 'ssg-'));
    const content = join(root, 'content');
    const output = join(root, 'site');
    await mkdir(content);
    await writeFile(join(content, 'hello.md'), '# Hello');
    const server = await startDevServer({ contentDir: content, outputDir: output, port: 0 });

    try {
      const response = await fetch(`http://localhost:${server.port}/hello.html`);
      const html = await response.text();
      expect(response.status).toBe(200);
      expect(html).toContain('<h1>Hello</h1>');
      expect(html).toContain('/__ssg_live_reload');
    } finally {
      await server.close();
    }
  });
});
