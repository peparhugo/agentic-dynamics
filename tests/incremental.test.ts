import fs from 'fs';
import path from 'path';
import os from 'os';
import { build } from '../src/build';
import { setPlugins } from '../src/plugin';
import { builtInPlugins } from '../src/plugins';
import { BuildStats } from '../src/types';

function createTempRoot(): string {
  const dir = path.join(os.tmpdir(), `ssg-incr-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function setupTempProject(root: string): { contentDir: string; outputDir: string; templatesDir: string } {
  const contentDir = path.join(root, 'content');
  const outputDir = path.join(root, 'output');
  const templatesDir = path.join(root, 'templates');
  fs.mkdirSync(contentDir, { recursive: true });
  fs.mkdirSync(outputDir, { recursive: true });
  fs.mkdirSync(templatesDir, { recursive: true });
  return { contentDir, outputDir, templatesDir };
}

function setupMinimalTemplates(templatesDir: string): void {
  const layoutsDir = path.join(templatesDir, 'layouts');
  const partialsDir = path.join(templatesDir, 'partials');
  fs.mkdirSync(layoutsDir, { recursive: true });
  fs.mkdirSync(partialsDir, { recursive: true });

  fs.writeFileSync(
    path.join(layoutsDir, 'default.hbs'),
    '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>'
  );
  fs.writeFileSync(
    path.join(templatesDir, 'page.hbs'),
    '<article><h1>{{title}}</h1><div>{{{content}}}</div></article>'
  );
  fs.writeFileSync(
    path.join(templatesDir, 'index.hbs'),
    '<h1>Index</h1><ul>{{#each pages}}<li><a href="{{slug}}.html">{{title}}</a></li>{{/each}}</ul>'
  );
}

function writePage(contentDir: string, filename: string, title: string, body: string, extra?: string): void {
  const extraYaml = extra ? `\n${extra}` : '';
  fs.writeFileSync(
    path.join(contentDir, filename),
    `---\ntitle: ${title}${extraYaml}\n---\n${body}`
  );
}

function readOutput(outputDir: string, filename: string): string {
  return fs.readFileSync(path.join(outputDir, filename), 'utf-8');
}

function cachePath(contentDir: string): string {
  return path.resolve(contentDir, '..', '.ssg-cache.json');
}

beforeEach(() => {
  setPlugins([...builtInPlugins]);
});

describe('incremental builds', () => {
  test('first build with --incremental builds all pages and creates cache', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');
      writePage(contentDir, 'b.md', 'Page B', '# Hello B');

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(2);
      expect(stats.pagesSkipped).toBe(0);
      expect(stats.totalPages).toBe(2);
      expect(fs.existsSync(cachePath(contentDir))).toBe(true);

      const cache = JSON.parse(fs.readFileSync(cachePath(contentDir), 'utf-8'));
      expect(cache.pages).toBeDefined();
      expect(Object.keys(cache.pages).length).toBe(2);
      expect(typeof cache.templateHash).toBe('string');
      expect(cache.templateHash.length).toBeGreaterThan(0);
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('second build with --incremental skips all unchanged pages', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');
      writePage(contentDir, 'b.md', 'Page B', '# Hello B');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(0);
      expect(stats.pagesSkipped).toBe(2);
      expect(stats.totalPages).toBe(2);
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('modifying one content file rebuilds only that page', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');
      writePage(contentDir, 'b.md', 'Page B', '# Hello B');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      writePage(contentDir, 'a.md', 'Page A Modified', '# Hello Modified A');

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(1);
      expect(stats.pagesSkipped).toBe(1);
      expect(stats.totalPages).toBe(2);

      const htmlA = readOutput(outputDir, 'a.html');
      expect(htmlA).toContain('Page A Modified');
      expect(htmlA).toContain('Hello Modified A');

      const htmlB = readOutput(outputDir, 'b.html');
      expect(htmlB).toContain('Page B');
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('modifying a template rebuilds all pages', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');
      writePage(contentDir, 'b.md', 'Page B', '# Hello B');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      fs.writeFileSync(
        path.join(templatesDir, 'page.hbs'),
        '<div class="new-wrapper"><h1>{{title}}</h1><div>{{{content}}}</div></div>'
      );

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(2);
      expect(stats.pagesSkipped).toBe(0);
      expect(stats.totalPages).toBe(2);

      const htmlA = readOutput(outputDir, 'a.html');
      expect(htmlA).toContain('new-wrapper');
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('--clean flag forces full rebuild and clears cache', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');

      build({ contentDir, outputDir, templatesDir, incremental: true });
      expect(fs.existsSync(cachePath(contentDir))).toBe(true);

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true, clean: true });

      expect(stats.pagesBuilt).toBe(1);
      expect(stats.pagesSkipped).toBe(0);
      expect(stats.totalPages).toBe(1);
      expect(fs.existsSync(cachePath(contentDir))).toBe(false);
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('build without --incremental does not create cache', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');

      build({ contentDir, outputDir, templatesDir });

      expect(fs.existsSync(cachePath(contentDir))).toBe(false);
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('cached pages produce correct output files', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');

      build({ contentDir, outputDir, templatesDir, incremental: true });
      const firstOutput = readOutput(outputDir, 'a.html');

      fs.rmSync(outputDir, { recursive: true, force: true });
      fs.mkdirSync(outputDir, { recursive: true });

      build({ contentDir, outputDir, templatesDir, incremental: true });
      const secondOutput = readOutput(outputDir, 'a.html');

      expect(secondOutput).toBe(firstOutput);
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('adding a new page builds it while skipping existing cached pages', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      writePage(contentDir, 'b.md', 'Page B', '# Hello B');

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(1);
      expect(stats.pagesSkipped).toBe(1);
      expect(stats.totalPages).toBe(2);
      expect(fs.existsSync(path.join(outputDir, 'b.html'))).toBe(true);
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('removing a page does not cause errors', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');
      writePage(contentDir, 'b.md', 'Page B', '# Hello B');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      fs.unlinkSync(path.join(contentDir, 'b.md'));

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(0);
      expect(stats.pagesSkipped).toBe(1);
      expect(stats.totalPages).toBe(1);
      expect(fs.existsSync(path.join(outputDir, 'a.html'))).toBe(true);
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('cache file has valid structure', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      const cache = JSON.parse(fs.readFileSync(cachePath(contentDir), 'utf-8'));
      expect(typeof cache.templateHash).toBe('string');

      const pageKeys = Object.keys(cache.pages);
      expect(pageKeys.length).toBe(1);

      const entry = cache.pages[pageKeys[0]];
      expect(typeof entry.contentHash).toBe('string');
      expect(typeof entry.templateHash).toBe('string');
      expect(typeof entry.html).toBe('string');
      expect(entry.contentHash.length).toBe(64);
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('modifying frontmatter triggers rebuild', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');
      writePage(contentDir, 'b.md', 'Page B', '# Hello B');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      writePage(contentDir, 'b.md', 'Page B Updated', '# Hello B');

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(1);
      expect(stats.pagesSkipped).toBe(1);

      const htmlB = readOutput(outputDir, 'b.html');
      expect(htmlB).toContain('Page B Updated');
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('modifying a layout rebuilds all pages', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');
      writePage(contentDir, 'b.md', 'Page B', '# Hello B');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      fs.writeFileSync(
        path.join(templatesDir, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html><head><title>WRAPPED: {{title}}</title></head><body>{{{body}}}</body></html>'
      );

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(2);
      expect(stats.pagesSkipped).toBe(0);

      const htmlA = readOutput(outputDir, 'a.html');
      expect(htmlA).toContain('WRAPPED: Page A');
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('modifying a partial rebuilds all pages', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);

      fs.writeFileSync(
        path.join(templatesDir, 'partials', 'nav.hbs'),
        '<nav>Custom Nav</nav>'
      );
      fs.writeFileSync(
        path.join(templatesDir, 'layouts', 'default.hbs'),
        '<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{> nav}}{{{body}}}</body></html>'
      );

      writePage(contentDir, 'a.md', 'Page A', '# Hello A');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(readOutput(outputDir, 'a.html')).toContain('Custom Nav');

      fs.writeFileSync(
        path.join(templatesDir, 'partials', 'nav.hbs'),
        '<nav>Updated Nav</nav>'
      );

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(1);
      expect(stats.pagesSkipped).toBe(0);

      expect(readOutput(outputDir, 'a.html')).toContain('Updated Nav');
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('corrupted cache file is treated as clean build', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');
      writePage(contentDir, 'b.md', 'Page B', '# Hello B');

      build({ contentDir, outputDir, templatesDir, incremental: true });
      fs.writeFileSync(cachePath(contentDir), 'not-valid-json');

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(2);
      expect(stats.totalPages).toBe(2);
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('build with custom templatesDir uses correct cache', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(fs.existsSync(cachePath(contentDir))).toBe(true);

      const cache = JSON.parse(fs.readFileSync(cachePath(contentDir), 'utf-8'));
      expect(Object.keys(cache.pages).length).toBe(1);
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('index is always regenerated', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');

      build({ contentDir, outputDir, templatesDir, incremental: true });
      const firstIndex = readOutput(outputDir, 'index.html');

      build({ contentDir, outputDir, templatesDir, incremental: true });
      const secondIndex = readOutput(outputDir, 'index.html');

      expect(secondIndex).toBe(firstIndex);
      expect(secondIndex).toContain('Page A');
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('build stats are correct for mixed scenario', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Hello A');
      writePage(contentDir, 'b.md', 'Page B', '# Hello B');
      writePage(contentDir, 'c.md', 'Page C', '# Hello C');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      writePage(contentDir, 'b.md', 'Page B Modified', '# Hello B Mod');

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(1);
      expect(stats.pagesSkipped).toBe(2);
      expect(stats.totalPages).toBe(3);
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });

  test('content hash changes when body content changes', () => {
    const root = createTempRoot();
    try {
      const { contentDir, outputDir, templatesDir } = setupTempProject(root);
      setupMinimalTemplates(templatesDir);
      writePage(contentDir, 'a.md', 'Page A', '# Original Body');

      build({ contentDir, outputDir, templatesDir, incremental: true });

      writePage(contentDir, 'a.md', 'Page A', '# New Body Content');

      const stats = build({ contentDir, outputDir, templatesDir, incremental: true });

      expect(stats.pagesBuilt).toBe(1);
      expect(stats.pagesSkipped).toBe(0);
      expect(readOutput(outputDir, 'a.html')).toContain('New Body Content');
    } finally {
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });
});
