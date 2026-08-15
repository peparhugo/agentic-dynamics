import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { PluginContext } from '../src/plugin';
import { markdownPlugin } from './markdown-plugin';

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function makeCtx(contentDir: string): PluginContext {
  return { contentDir, outputDir: contentDir, templatesDir: contentDir, config: {} };
}

describe('markdownPlugin', () => {
  let contentDir: string;

  beforeEach(() => {
    contentDir = makeTmpDir('ssg-md-plugin-');
  });

  afterEach(() => {
    fs.rmSync(contentDir, { recursive: true, force: true });
  });

  it('parses frontmatter and renders markdown into the page', () => {
    const filePath = path.join(contentDir, 'hello.md');
    fs.writeFileSync(filePath, '---\ntitle: Hello\ndate: 2026-01-01\ntags: [a, b]\n---\n\n# Hi there\n');

    const stub = {
      slug: 'hello',
      title: '',
      date: null,
      tags: [],
      html: '',
      sourcePath: filePath,
      outputPath: 'hello.html',
      template: '',
      layout: '',
    };

    const result = markdownPlugin().onFile!(stub, makeCtx(contentDir));

    expect(result).toMatchObject({
      title: 'Hello',
      date: '2026-01-01',
      tags: ['a', 'b'],
    });
    expect(result?.html).toContain('<h1>Hi there</h1>');
  });

  it('falls back to a title derived from the slug when frontmatter has no title', () => {
    const filePath = path.join(contentDir, 'my-cool-post.md');
    fs.writeFileSync(filePath, 'No frontmatter here.');

    const stub = {
      slug: 'my-cool-post',
      title: '',
      date: null,
      tags: [],
      html: '',
      sourcePath: filePath,
      outputPath: 'my-cool-post.html',
      template: '',
      layout: '',
    };

    const result = markdownPlugin().onFile!(stub, makeCtx(contentDir));

    expect(result?.title).toBe('My Cool Post');
    expect(result?.template).toBe('page');
    expect(result?.layout).toBe('default');
  });
});
