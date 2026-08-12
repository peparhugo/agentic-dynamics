import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src';

function fixture(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-templates-'));
}

describe('templates', () => {
  test('renders the default template and layout with partials', () => {
    const root = fixture();
    fs.mkdirSync(path.join(root, 'content'));
    fs.mkdirSync(path.join(root, 'templates', 'layouts'), { recursive: true });
    fs.mkdirSync(path.join(root, 'templates', 'partials'));
    fs.writeFileSync(path.join(root, 'content', 'hello.md'), '---\ntitle: Hello\n---\n# Welcome');
    fs.writeFileSync(path.join(root, 'templates', 'default.hbs'), '{{> header}}<main>{{{body}}}</main>');
    fs.writeFileSync(path.join(root, 'templates', 'layouts', 'default.hbs'), '<html><body>{{{body}}}</body></html>');
    fs.writeFileSync(path.join(root, 'templates', 'partials', 'header.hbs'), '<header>{{title}}</header>');

    buildSite({ contentDir: path.join(root, 'content'), outputDir: path.join(root, 'out'), templatesDir: path.join(root, 'templates') });

    expect(fs.readFileSync(path.join(root, 'out', 'hello.html'), 'utf8'))
      .toContain('<html><body><header>Hello</header><main><h1>Welcome</h1>\n</main></body></html>');
  });

  test('uses a frontmatter template and escapes normal values', () => {
    const root = fixture();
    fs.mkdirSync(path.join(root, 'content'));
    fs.mkdirSync(path.join(root, 'templates'));
    fs.writeFileSync(path.join(root, 'content', 'page.md'), '---\ntitle: "<Unsafe>"\ntemplate: article\n---\nText');
    fs.writeFileSync(path.join(root, 'templates', 'article.hbs'), '<h1>{{title}}</h1><div>{{{body}}}</div>');

    buildSite({ contentDir: path.join(root, 'content'), outputDir: path.join(root, 'out'), templatesDir: path.join(root, 'templates') });

    expect(fs.readFileSync(path.join(root, 'out', 'page.html'), 'utf8'))
      .toBe('<h1>&lt;Unsafe&gt;</h1><div><p>Text</p>\n</div>');
  });

  test('keeps markdown-only output when no template exists', () => {
    const root = fixture();
    fs.mkdirSync(path.join(root, 'content'));
    fs.writeFileSync(path.join(root, 'content', 'page.md'), '# Text');
    buildSite({ contentDir: path.join(root, 'content'), outputDir: path.join(root, 'out'), templatesDir: path.join(root, 'templates') });
    expect(fs.readFileSync(path.join(root, 'out', 'page.html'), 'utf8')).toBe('<h1>Text</h1>\n');
  });
});
