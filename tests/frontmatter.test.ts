import { parseFrontmatter } from '../src/frontmatter';

describe('parseFrontmatter', () => {
  it('parses YAML-style key: value frontmatter', () => {
    const raw = `---
title: Hello World
date: 2024-01-15
tags: [intro, news]
---
# Body

Some content.`;
    const { data, content } = parseFrontmatter(raw);
    expect(data.title).toBe('Hello World');
    expect(data.date).toBe('2024-01-15');
    expect(data.tags).toEqual(['intro', 'news']);
    expect(content.trim()).toBe('# Body\n\nSome content.');
  });

  it('supports comma-separated tags without brackets', () => {
    const raw = `---
title: Post
tags: a, b, c
---
Body text`;
    const { data } = parseFrontmatter(raw);
    expect(data.tags).toEqual(['a', 'b', 'c']);
  });

  it('supports quoted string values', () => {
    const raw = `---
title: "Quoted Title"
---
Body`;
    const { data } = parseFrontmatter(raw);
    expect(data.title).toBe('Quoted Title');
  });

  it('returns empty data and full content when there is no frontmatter', () => {
    const raw = `# Just Markdown\n\nNo frontmatter here.`;
    const { data, content } = parseFrontmatter(raw);
    expect(data).toEqual({});
    expect(content).toBe(raw);
  });

  it('merges JSON frontmatter handled by gray-matter with the YAML block', () => {
    const raw = `---
title: From YAML
---
Body`;
    const { data } = parseFrontmatter(raw);
    expect(data.title).toBe('From YAML');
  });
});
