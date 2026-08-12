import fs from 'fs';
import os from 'os';
import path from 'path';
import {
  build,
  buildWithStats,
  CACHE_FILE,
  loadCache,
} from '../src/ssg';
import { parseArgs, run } from '../src/cli';

function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'ssg-inc-'));
}

interface Fixture {
  content: string;
  output: string;
  templates: string;
}

function makeFixture(files: Record<string, string>): Fixture {
  const fixture = {
    content: makeTempDir(),
    output: makeTempDir(),
    templates: makeTempDir(),
  };
  for (const [rel, source] of Object.entries(files)) {
    const target = rel.startsWith('tpl/') ? path.join(fixture.templates, rel.slice(4)) : path.join(fixture.content, rel);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, source);
  }
  return fixture;
}

function cleanup(fixture: Fixture): void {
  fs.rmSync(fixture.content, { recursive: true, force: true });
  fs.rmSync(fixture.output, { recursive: true, force: true });
  fs.rmSync(fixture.templates, { recursive: true, force: true });
}

function readHtml(fixture: Fixture, file: string): string {
  return fs.readFileSync(path.join(fixture.output, file), 'utf8');
}

describe('incremental build', () => {
  it('skips every page on a second build when nothing changed', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\n-->\n# A body',
      'b.md': '<!--\ntitle: B\n-->\n# B body',
    });
    try {
      const first = buildWithStats(fixture.content, fixture.output, fixture.templates);
      expect(first.stats.pagesBuilt).toBe(2);
      expect(first.stats.pagesSkipped).toBe(0);

      const second = buildWithStats(fixture.content, fixture.output, fixture.templates, {
        incremental: true,
      });
      expect(second.stats.pagesBuilt).toBe(0);
      expect(second.stats.pagesSkipped).toBe(2);
      expect(second.stats.pages).toBe(2);
      expect(second.stats.timeSavedMs).toBeGreaterThanOrEqual(0);

      expect(readHtml(fixture, 'a.html')).toContain('<title>A</title>');
      expect(readHtml(fixture, 'b.html')).toContain('<title>B</title>');
      expect(readHtml(fixture, 'index.html')).toContain('<a href="a.html">A</a>');
      expect(readHtml(fixture, 'index.html')).toContain('<a href="b.html">B</a>');
    } finally {
      cleanup(fixture);
    }
  });

  it('rebuilds only the page whose source changed', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\n-->\n# A body',
      'b.md': '<!--\ntitle: B\n-->\n# B body',
    });
    try {
      build(fixture.content, fixture.output, fixture.templates);

      fs.writeFileSync(path.join(fixture.content, 'a.md'), '<!--\ntitle: A2\n-->\n# A2 body');

      const result = buildWithStats(fixture.content, fixture.output, fixture.templates, {
        incremental: true,
      });
      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(1);

      expect(readHtml(fixture, 'a.html')).toContain('<title>A2</title>');
      expect(readHtml(fixture, 'a.html')).toContain('<h1>A2 body</h1>');
      expect(readHtml(fixture, 'b.html')).toContain('<title>B</title>');
      expect(readHtml(fixture, 'b.html')).not.toContain('A2');
    } finally {
      cleanup(fixture);
    }
  });

  it('rebuilds all pages when a shared template changes', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\n-->\n# A body',
      'b.md': '<!--\ntitle: B\n-->\n# B body',
      'tpl/default.hbs': 'OLD {{title}}\n{{{html}}}',
    });
    try {
      build(fixture.content, fixture.output, fixture.templates);
      expect(readHtml(fixture, 'a.html')).toContain('OLD A');

      fs.writeFileSync(path.join(fixture.templates, 'default.hbs'), 'NEW {{title}}\n{{{html}}}');

      const result = buildWithStats(fixture.content, fixture.output, fixture.templates, {
        incremental: true,
      });
      expect(result.stats.pagesBuilt).toBe(2);
      expect(result.stats.pagesSkipped).toBe(0);

      expect(readHtml(fixture, 'a.html')).toContain('NEW A');
      expect(readHtml(fixture, 'b.html')).toContain('NEW B');
      expect(readHtml(fixture, 'a.html')).not.toContain('OLD A');
    } finally {
      cleanup(fixture);
    }
  });

  it('rebuilds a page when its frontmatter names a changed template', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\ntemplate: one\n-->\n# A body',
      'b.md': '<!--\ntitle: B\ntemplate: two\n-->\n# B body',
      'tpl/one.hbs': 'ONE {{title}}',
      'tpl/two.hbs': 'TWO {{title}}',
    });
    try {
      build(fixture.content, fixture.output, fixture.templates);

      fs.writeFileSync(path.join(fixture.templates, 'two.hbs'), 'TWO-V2 {{title}}');

      const result = buildWithStats(fixture.content, fixture.output, fixture.templates, {
        incremental: true,
      });
      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(1);

      expect(readHtml(fixture, 'a.html')).toContain('ONE A');
      expect(readHtml(fixture, 'b.html')).toContain('TWO-V2 B');
    } finally {
      cleanup(fixture);
    }
  });

  it('rebuilds only the newly added page', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\n-->\n# A body',
    });
    try {
      build(fixture.content, fixture.output, fixture.templates);

      fs.writeFileSync(path.join(fixture.content, 'c.md'), '<!--\ntitle: C\n-->\n# C body');

      const result = buildWithStats(fixture.content, fixture.output, fixture.templates, {
        incremental: true,
      });
      expect(result.stats.pagesBuilt).toBe(1);
      expect(result.stats.pagesSkipped).toBe(1);
      expect(readHtml(fixture, 'c.html')).toContain('<title>C</title>');
      expect(readHtml(fixture, 'index.html')).toContain('<a href="c.html">C</a>');
    } finally {
      cleanup(fixture);
    }
  });

  it('cleans stale cache entries for removed pages', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\n-->\n# A body',
      'b.md': '<!--\ntitle: B\n-->\n# B body',
    });
    try {
      build(fixture.content, fixture.output, fixture.templates);

      fs.rmSync(path.join(fixture.content, 'b.md'));

      buildWithStats(fixture.content, fixture.output, fixture.templates, { incremental: true });

      const cache = loadCache(path.join(fixture.output, CACHE_FILE));
      expect(cache).not.toBeNull();
      expect(Object.keys(cache?.entries ?? {})).toEqual(['a']);
    } finally {
      cleanup(fixture);
    }
  });

  it('creates the cache manifest in the output directory', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\n-->\n# A body',
    });
    try {
      build(fixture.content, fixture.output, fixture.templates);
      const cachePath = path.join(fixture.output, CACHE_FILE);
      expect(fs.existsSync(cachePath)).toBe(true);
      const cache = loadCache(cachePath);
      expect(cache?.version).toBe(1);
      expect(cache?.entries.a.sourceHash).toBeTruthy();
      expect(cache?.entries.a.templateHash).toBeTruthy();
      expect(typeof cache?.entries.a.html).toBe('string');
    } finally {
      cleanup(fixture);
    }
  });

  it('does a full build when the cache is missing', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\n-->\n# A body',
      'b.md': '<!--\ntitle: B\n-->\n# B body',
    });
    try {
      build(fixture.content, fixture.output, fixture.templates);
      const firstInc = buildWithStats(fixture.content, fixture.output, fixture.templates, {
        incremental: true,
      });
      expect(firstInc.stats.pagesSkipped).toBe(2);

      fs.rmSync(path.join(fixture.output, CACHE_FILE));

      const second = buildWithStats(fixture.content, fixture.output, fixture.templates, {
        incremental: true,
      });
      expect(second.stats.pagesBuilt).toBe(2);
      expect(second.stats.pagesSkipped).toBe(0);
    } finally {
      cleanup(fixture);
    }
  });

  it('does a full build when --clean is requested', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\n-->\n# A body',
      'b.md': '<!--\ntitle: B\n-->\n# B body',
    });
    try {
      build(fixture.content, fixture.output, fixture.templates);
      const firstInc = buildWithStats(fixture.content, fixture.output, fixture.templates, {
        incremental: true,
      });
      expect(firstInc.stats.pagesSkipped).toBe(2);

      const result = buildWithStats(fixture.content, fixture.output, fixture.templates, {
        incremental: true,
        clean: true,
      });
      expect(result.stats.pagesBuilt).toBe(2);
      expect(result.stats.pagesSkipped).toBe(0);
    } finally {
      cleanup(fixture);
    }
  });

  it('restores cached HTML output when output files were removed', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\n-->\n# A body',
      'b.md': '<!--\ntitle: B\n-->\n# B body',
    });
    try {
      build(fixture.content, fixture.output, fixture.templates);

      fs.rmSync(path.join(fixture.output, 'a.html'));
      fs.rmSync(path.join(fixture.output, 'b.html'));
      fs.rmSync(path.join(fixture.output, 'index.html'));

      const result = buildWithStats(fixture.content, fixture.output, fixture.templates, {
        incremental: true,
      });
      expect(result.stats.pagesSkipped).toBeGreaterThanOrEqual(2);

      expect(readHtml(fixture, 'a.html')).toContain('<title>A</title>');
      expect(readHtml(fixture, 'b.html')).toContain('<title>B</title>');
      expect(readHtml(fixture, 'index.html')).toContain('<a href="a.html">A</a>');
    } finally {
      cleanup(fixture);
    }
  });

  it('caches parsed frontmatter so unchanged pages are not re-parsed', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\ntags: [one, two]\n-->\n# A body',
    });
    try {
      build(fixture.content, fixture.output, fixture.templates);

      const result = buildWithStats(fixture.content, fixture.output, fixture.templates, {
        incremental: true,
      });
      expect(result.stats.pagesSkipped).toBe(1);
      expect(result.pages[0].title).toBe('A');
      expect(result.pages[0].tags).toEqual(['one', 'two']);
    } finally {
      cleanup(fixture);
    }
  });

  it('a full build and an incremental build produce identical output', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\ndate: 2024-05-10\ntags: [news]\n-->\n# A body',
      'tpl/default.hbs': 'TPL {{title}}\n{{{html}}}',
    });
    try {
      build(fixture.content, fixture.output, fixture.templates);
      const fullHtml = readHtml(fixture, 'a.html');

      fs.mkdirSync(fixture.output, { recursive: true });
      fs.rmSync(path.join(fixture.output, 'a.html'));

      buildWithStats(fixture.content, fixture.output, fixture.templates, { incremental: true });
      expect(readHtml(fixture, 'a.html')).toBe(fullHtml);
    } finally {
      cleanup(fixture);
    }
  });

  it('reports build stats through the CLI with --incremental', () => {
    const fixture = makeFixture({
      'a.md': '<!--\ntitle: A\n-->\n# A body',
    });
    try {
      run(['build', '--content', fixture.content, '--output', fixture.output, '--templates', fixture.templates]);
      const message = run([
        'build',
        '--content',
        fixture.content,
        '--output',
        fixture.output,
        '--templates',
        fixture.templates,
        '--incremental',
      ]);
      expect(message).toContain('Built 1 page(s)');
      expect(message).toContain('1 skipped');
      expect(message).toContain('0 built');
    } finally {
      cleanup(fixture);
    }
  });
});

describe('parseArgs for incremental options', () => {
  it('parses --incremental and --clean flags', () => {
    const options = parseArgs(['build', '--incremental', '--clean']);
    expect(options.incremental).toBe(true);
    expect(options.clean).toBe(true);
  });

  it('defaults to full builds when the flags are absent', () => {
    const options = parseArgs(['build']);
    expect(options.incremental).toBe(false);
    expect(options.clean).toBe(false);
  });
});
