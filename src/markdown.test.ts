import { parseMarkdown } from './markdown';

describe('parseMarkdown', () => {
  it('merges manually parsed YAML frontmatter and renders markdown', () => {
    const page = parseMarkdown('---\ntitle: Hello world\ndate: 2026-08-15\ntags: [typescript, static]\n---\n# Welcome\n\nText', 'fallback');
    expect(page.metadata).toMatchObject({ title: 'Hello world', date: '2026-08-15', tags: ['typescript', 'static'] });
    expect(page.html).toContain('<h1>Welcome</h1>');
    expect(page.html).toContain('<p>Text</p>');
  });

  it('uses the fallback title when frontmatter omits one', () => {
    expect(parseMarkdown('A paragraph', 'Untitled').metadata).toMatchObject({ title: 'Untitled', tags: [] });
  });
});
