import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite, SitePage } from '../src';

function fixture(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-incremental-'));
}

describe('incremental builds', () => {
  test('builds only changed pages and reuses cached rendered output', () => {
    const root = fixture();
    const content = path.join(root, 'content');
    const output = path.join(root, 'out');
    const templates = path.join(root, 'templates');
    fs.mkdirSync(content);
    fs.mkdirSync(templates);
    fs.writeFileSync(path.join(content, 'one.md'), '---\ntitle: One\n---\nFirst');
    fs.writeFileSync(path.join(content, 'two.md'), '---\ntitle: Two\n---\nSecond');
    fs.writeFileSync(path.join(templates, 'default.hbs'), '<h1>{{title}}</h1>{{{body}}}');
    const calls: string[] = [];
    const plugin = { onFile: (page: SitePage) => calls.push(page.source) };
    buildSite({ contentDir: content, outputDir: output, templatesDir: templates, plugins: [plugin] });
    calls.length = 0;

    fs.writeFileSync(path.join(content, 'two.md'), '---\ntitle: Updated\n---\nChanged');
    let stats;
    buildSite({ contentDir: content, outputDir: output, templatesDir: templates, plugins: [plugin], incremental: true, onStats: (value) => { stats = value; } });

    expect(calls).toEqual(['two.md']);
    expect(stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 1 });
    expect(fs.readFileSync(path.join(output, 'one.html'), 'utf8')).toContain('First');
    expect(fs.readFileSync(path.join(output, 'two.html'), 'utf8')).toContain('Changed');
    expect(fs.existsSync(path.join(output, '.ssg-cache.json'))).toBe(true);
  });

  test('invalidates every page when a template changes and cleans deleted pages', () => {
    const root = fixture();
    const content = path.join(root, 'content');
    const output = path.join(root, 'out');
    const templates = path.join(root, 'templates');
    fs.mkdirSync(content);
    fs.mkdirSync(templates);
    fs.writeFileSync(path.join(content, 'page.md'), '# Page');
    fs.writeFileSync(path.join(content, 'other.md'), '# Other');
    fs.writeFileSync(path.join(templates, 'default.hbs'), '<main>{{{body}}}</main>');
    buildSite({ contentDir: content, outputDir: output, templatesDir: templates });
    fs.unlinkSync(path.join(content, 'other.md'));
    fs.writeFileSync(path.join(templates, 'default.hbs'), '<article>{{{body}}}</article>');
    let stats;
    buildSite({ contentDir: content, outputDir: output, templatesDir: templates, incremental: true, onStats: (value) => { stats = value; } });

    expect(stats).toMatchObject({ pagesBuilt: 1, pagesSkipped: 0 });
    expect(fs.readFileSync(path.join(output, 'page.html'), 'utf8')).toContain('<article>');
    expect(fs.existsSync(path.join(output, 'other.html'))).toBe(false);
  });
});
