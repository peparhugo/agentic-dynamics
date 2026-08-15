import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/generator';

describe('buildSite', () => {
  it('writes pages and an index using supplied directories', async () => {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ssg-'));
    const content = path.join(root, 'content');
    const output = path.join(root, 'output');
    await fs.mkdir(path.join(content, 'notes'), { recursive: true });
    await fs.writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello & goodbye\ntags: [one, two]\n---\n\n**Welcome**');
    await fs.writeFile(path.join(content, 'notes', 'second.md'), '# Second');

    await buildSite({ contentDir: content, outputDir: output });

    const page = await fs.readFile(path.join(output, 'hello.html'), 'utf8');
    const nested = await fs.readFile(path.join(output, 'notes', 'second.html'), 'utf8');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');
    expect(page).toContain('<title>Hello &amp; goodbye</title>');
    expect(page).toContain('<strong>Welcome</strong>');
    expect(page).toContain('one, two');
    expect(nested).toContain('<h1>second</h1>');
    expect(index).toContain('hello.html');
    expect(index).toContain('notes/second.html');
  });
});
