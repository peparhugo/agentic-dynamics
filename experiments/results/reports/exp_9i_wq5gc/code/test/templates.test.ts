import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describe, it, expect } from 'vitest';
import { buildSite } from '../src/builder';

function tmpdir(prefix: string) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe('template rendering', () => {
  it('applies layout and partials with body content', async () => {
    const src = tmpdir('ssg-src-');
    const tpl = tmpdir('ssg-tpl-');
    const out = tmpdir('ssg-out-');

    // Source markdown
    fs.mkdirSync(src, { recursive: true });
    fs.writeFileSync(path.join(src, 'index.md'), `---\ntitle: Home\n---\n# Welcome\n\nContent here.`);

    // Templates: layout and partial
    const layoutsDir = path.join(tpl, 'layouts');
    const partialsDir = path.join(tpl, 'partials');
    fs.mkdirSync(layoutsDir, { recursive: true });
    fs.mkdirSync(partialsDir, { recursive: true });
    fs.writeFileSync(path.join(partialsDir, 'header.hbs'), `<header><h1>{{page.title}}</h1></header>`);
    fs.writeFileSync(
      path.join(layoutsDir, 'default.hbs'),
      `<!doctype html><html><body>{{> header}}<main>{{{body}}}</main></body></html>`
    );

    await buildSite({ srcDir: src, templatesDir: tpl, outDir: out, includeDrafts: false, cleanOutDir: true });

    const html = fs.readFileSync(path.join(out, 'index.html'), 'utf8');
    expect(html).toContain('<header><h1>Home</h1></header>');
    expect(html).toContain('<main>');
    expect(html).toContain('<h1>Welcome</h1>'); // markdown rendered
  });
});
