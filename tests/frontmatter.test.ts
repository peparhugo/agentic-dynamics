import { parseFrontmatter } from '../src/frontmatter';

describe('parseFrontmatter', () => {
  it('parses title, date, and bracketed tags from a YAML frontmatter block', () => {
    const raw = `---
title: My First Post
date: 2024-01-15
tags: [typescript, ssg, testing]
---
# Hello

This is the body.
`;

    const { data, content } = parseFrontmatter(raw);

    expect(data.title).toBe('My First Post');
    expect(data.date).toBe('2024-01-15');
    expect(data.tags).toEqual(['typescript', 'ssg', 'testing']);
    expect(content.trim()).toBe('# Hello\n\nThis is the body.'.trim());
  });

  it('parses comma-separated tags without brackets', () => {
    const raw = `---
title: Second Post
tags: foo, bar
---
Body text.
`;

    const { data } = parseFrontmatter(raw);
    expect(data.tags).toEqual(['foo', 'bar']);
  });

  it('strips quotes around scalar values', () => {
    const raw = `---
title: "Quoted Title"
date: '2024-02-01'
---
Body.
`;

    const { data } = parseFrontmatter(raw);
    expect(data.title).toBe('Quoted Title');
    expect(data.date).toBe('2024-02-01');
  });

  it('returns empty data and full content when there is no frontmatter block', () => {
    const raw = '# Just Markdown\n\nNo frontmatter here.\n';
    const { data, content } = parseFrontmatter(raw);

    expect(data.title).toBeUndefined();
    expect(content).toBe(raw);
  });

  it('handles an empty tags list', () => {
    const raw = `---
title: No Tags
tags: []
---
Body.
`;
    const { data } = parseFrontmatter(raw);
    expect(data.tags).toEqual([]);
  });
});
