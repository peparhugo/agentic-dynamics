import { parseMarkdown } from '../src/parser';

describe('parseMarkdown', () => {
  it('parses YAML frontmatter and markdown content', () => {
    const result = parseMarkdown(`---\ntitle: Hello\ndate: 2026-01-02\ntags:\n  - typescript\n  - static sites\n---\n\n# Welcome`);

    expect(result.data).toEqual({
      title: 'Hello', date: '2026-01-02', tags: ['typescript', 'static sites'],
    });
    expect(result.content).toContain('# Welcome');
    expect(result.content).not.toContain('title: Hello');
  });

  it('supports documents without frontmatter', () => {
    expect(parseMarkdown('# Plain').data).toEqual({});
  });
});
