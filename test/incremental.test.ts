import fs from 'fs';
import os from 'os';
import path from 'path';

import { buildSite } from '../src/site';
import { CACHE_FILENAME, loadManifest } from '../src/cache';

function tmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function writeFile(root: string, relative: string, content: string): string {
  const full = path.join(root, relative);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, content);
  return full;
}

function setupProject() {
  const root = tmpDir('ssg-inc-');
  const contentDir = path.join(root, 'content');
  const templatesDir = path.join(root, 'templates');
  const outputDir = path.join(root, 'dist');

  writeFile(
    templatesDir,
    path.join('layouts', 'default.hbs'),
    '<html><head><title>{{title}}</title></head><body><main>{{{body}}}</main></body></html>'
  );
  writeFile(
    templatesDir,
    path.join('layouts', 'post.hbs'),
    '<html><head><title>{{title}}</title></head><body><article>{{{body}}}</article></body></html>'
  );
  writeFile(templatesDir, path.join('partials', 'header.hbs'), '<header>Header</header>');

  writeFile(
    contentDir,
    'hello.md',
    `---
title: Hello World
date: 2024-01-15
tags: [intro]
---
# Welcome

This is **bold**.
`
  );
  writeFile(
    contentDir,
    'about.md',
    `---
title: About
template: post
---
# About Us

We build things.
`
  );

  return { root, contentDir, templatesDir, outputDir };
}

function cleanup(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

describe('incremental builds', () => {
  let project: ReturnType<typeof setupProject>;

  beforeEach(() => {
    project = setupProject();
  });

  afterEach(() => {
    cleanup(project.root);
  });

  it('writes a .ssg-cache.json manifest after a full build', () => {
    buildSite({ contentDir: project.contentDir, outputDir: project.outputDir, templatesDir: project.templatesDir });

    expect(fs.existsSync(path.join(project.outputDir, CACHE_FILENAME))).toBe(true);
    const manifest = loadManifest(path.join(project.outputDir, CACHE_FILENAME));
    expect(Object.keys(manifest.pages)).toHaveLength(2);
  });

  it('skips every page when nothing changed between incremental builds', () => {
    buildSite({ contentDir: project.contentDir, outputDir: project.outputDir, templatesDir: project.templatesDir });

    const result = buildSite({
      contentDir: project.contentDir,
      outputDir: project.outputDir,
      templatesDir: project.templatesDir,
      incremental: true,
    });

    expect(result.stats?.pagesSkipped).toBe(2);
    expect(result.stats?.pagesBuilt).toBe(0);
    expect(result.posts).toHaveLength(2);
  });

  it('rebuilds only the page whose source changed', () => {
    buildSite({ contentDir: project.contentDir, outputDir: project.outputDir, templatesDir: project.templatesDir });

    writeFile(
      project.contentDir,
      'hello.md',
      `---
title: Hello World (updated)
date: 2024-01-15
tags: [intro]
---
# Welcome

Changed content.
`
    );

    const result = buildSite({
      contentDir: project.contentDir,
      outputDir: project.outputDir,
      templatesDir: project.templatesDir,
      incremental: true,
    });

    expect(result.stats?.pagesBuilt).toBe(1);
    expect(result.stats?.pagesSkipped).toBe(1);

    const hello = fs.readFileSync(path.join(project.outputDir, 'hello.html'), 'utf-8');
    expect(hello).toContain('Hello World (updated)');
    expect(hello).toContain('Changed content.');

    const about = fs.readFileSync(path.join(project.outputDir, 'about.html'), 'utf-8');
    expect(about).toContain('We build things.');
  });

  it('rebuilds only pages using a changed template', () => {
    buildSite({ contentDir: project.contentDir, outputDir: project.outputDir, templatesDir: project.templatesDir });

    // Only the "post" layout changes; hello.md uses the default layout.
    writeFile(
      project.templatesDir,
      path.join('layouts', 'post.hbs'),
      '<html><body><section class="v2">{{{body}}}</section></body></html>'
    );

    const result = buildSite({
      contentDir: project.contentDir,
      outputDir: project.outputDir,
      templatesDir: project.templatesDir,
      incremental: true,
    });

    expect(result.stats?.pagesBuilt).toBe(1);
    expect(result.stats?.pagesSkipped).toBe(1);

    const about = fs.readFileSync(path.join(project.outputDir, 'about.html'), 'utf-8');
    expect(about).toContain('class="v2"');
  });

  it('treats a missing cache as a clean build', () => {
    const result = buildSite({
      contentDir: project.contentDir,
      outputDir: project.outputDir,
      templatesDir: project.templatesDir,
      incremental: true,
    });

    expect(result.stats?.pagesBuilt).toBe(2);
    expect(result.stats?.pagesSkipped).toBe(0);
  });

  it('forces a full rebuild with the clean flag', () => {
    buildSite({ contentDir: project.contentDir, outputDir: project.outputDir, templatesDir: project.templatesDir });
    buildSite({
      contentDir: project.contentDir,
      outputDir: project.outputDir,
      templatesDir: project.templatesDir,
      incremental: true,
    });

    const result = buildSite({
      contentDir: project.contentDir,
      outputDir: project.outputDir,
      templatesDir: project.templatesDir,
      incremental: true,
      clean: true,
    });

    expect(result.stats?.pagesBuilt).toBe(2);
    expect(result.stats?.pagesSkipped).toBe(0);
  });

  it('caches parsed frontmatter in the manifest', () => {
    buildSite({ contentDir: project.contentDir, outputDir: project.outputDir, templatesDir: project.templatesDir });

    const manifest = loadManifest(path.join(project.outputDir, CACHE_FILENAME));
    const hello = manifest.pages['hello'];
    expect(hello.title).toBe('Hello World');
    expect(hello.tags).toEqual(['intro']);
    expect(hello.html).toContain('<h1>Welcome</h1>');
    expect(hello.rendered).toContain('<main>');
  });

  it('still writes every output file when all pages are skipped', () => {
    buildSite({ contentDir: project.contentDir, outputDir: project.outputDir, templatesDir: project.templatesDir });

    const result = buildSite({
      contentDir: project.contentDir,
      outputDir: project.outputDir,
      templatesDir: project.templatesDir,
      incremental: true,
    });

    expect(result.stats?.pagesSkipped).toBe(2);
    expect(result.filesWritten).toHaveLength(3); // index + hello + about
    expect(fs.existsSync(path.join(project.outputDir, 'index.html'))).toBe(true);
    expect(fs.existsSync(path.join(project.outputDir, 'hello.html'))).toBe(true);
    expect(fs.existsSync(path.join(project.outputDir, 'about.html'))).toBe(true);
  });

  it('rebuilds a newly added page and skips the rest', () => {
    buildSite({ contentDir: project.contentDir, outputDir: project.outputDir, templatesDir: project.templatesDir });

    writeFile(
      project.contentDir,
      'new.md',
      `---
title: New Page
---
Fresh content.
`
    );

    const result = buildSite({
      contentDir: project.contentDir,
      outputDir: project.outputDir,
      templatesDir: project.templatesDir,
      incremental: true,
    });

    expect(result.stats?.pagesBuilt).toBe(1);
    expect(result.stats?.pagesSkipped).toBe(2);
    expect(fs.existsSync(path.join(project.outputDir, 'new.html'))).toBe(true);
  });
});
