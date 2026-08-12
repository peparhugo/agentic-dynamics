import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSite } from '../src/ssg';

async function temporaryDirectory(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), 'ssg-test-'));
}

describe('buildSite', () => {
  it('builds Markdown pages with frontmatter and an index', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const output = path.join(root, 'dist');
    await fs.mkdir(path.join(content, 'notes'), { recursive: true });
    await fs.writeFile(path.join(content, 'notes', 'hello.md'), `---
title: Hello World
date: 2026-01-02
  - TypeScript
  - static-sites
---

## Welcome

This is **important**.
`);

    const pages = await buildSite({ contentDir: content, outputDir: output });
    const page = await fs.readFile(path.join(output, 'notes', 'hello.html'), 'utf8');
    const index = await fs.readFile(path.join(output, 'index.html'), 'utf8');

    expect(pages).toHaveLength(1);
    expect(page).toContain('<title>Hello World</title>');
    expect(page).toContain('<h2>Welcome</h2>');
    expect(page).toContain('<strong>important</strong>');
    expect(page).toContain('<li>TypeScript</li>');
    expect(index).toContain('href="notes/hello.html"');
    expect(index).toContain('Hello World');
  });

  it('uses the filename as title and supports comma-separated tags', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    await fs.mkdir(content, { recursive: true });
    await fs.writeFile(path.join(content, 'about.markdown'), '---\ntags: one, two\n---\nAbout us');

    await buildSite({ contentDir: content, outputDir: path.join(root, 'output') });
    const page = await fs.readFile(path.join(root, 'output', 'about.html'), 'utf8');
    expect(page).toContain('<title>about</title>');
    expect(page).toContain('<li>one</li>');
    expect(page).toContain('<li>two</li>');
  });

  it('renders a default Handlebars template, layout, and partial', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    await fs.mkdir(content, { recursive: true });
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(path.join(templates, 'partials'), { recursive: true });
    await fs.writeFile(path.join(content, 'hello.md'), '---\ntitle: Hello\n---\n<p>Markdown</p>');
    await fs.writeFile(path.join(templates, 'default.hbs'), '{{> header}}<section>{{{body}}}</section>');
    await fs.writeFile(path.join(templates, 'layouts', 'default.hbs'), '<html><body>{{{body}}}</body></html>');
    await fs.writeFile(path.join(templates, 'partials', 'header.hbs'), '<header>{{title}}</header>');

    await buildSite({ contentDir: content, outputDir: path.join(root, 'dist'), templatesDir: templates });
    const page = await fs.readFile(path.join(root, 'dist', 'hello.html'), 'utf8');
    expect(page).toBe('<html><body><header>Hello</header><section><p>Markdown</p></section></body></html>');
  });

  it('selects a page template and layout from frontmatter', async () => {
    const root = await temporaryDirectory();
    const content = path.join(root, 'content');
    const templates = path.join(root, 'templates');
    await fs.mkdir(path.join(templates, 'layouts'), { recursive: true });
    await fs.mkdir(content, { recursive: true });
    await fs.writeFile(path.join(content, 'custom.md'), '---\ntitle: Custom\ntemplate: post.hbs\nlayout: bare\n---\nText');
    await fs.writeFile(path.join(templates, 'post.hbs'), '<h1>{{title}}</h1>{{{content}}}');
    await fs.writeFile(path.join(templates, 'layouts', 'bare.ejs'), '<main><%- body %></main>');

    await buildSite({ contentDir: content, outputDir: path.join(root, 'dist'), templatesDir: templates });
    const page = await fs.readFile(path.join(root, 'dist', 'custom.html'), 'utf8');
    expect(page).toBe('<main><h1>Custom</h1><p>Text</p>\n</main>');
  });
});
