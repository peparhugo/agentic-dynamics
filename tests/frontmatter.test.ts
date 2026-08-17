import { extractFrontmatter } from '../src/frontmatter';

describe('extractFrontmatter', () => {
  it('parses title, date and tags, and strips the block from the body', () => {
    const source = `---
title: Hello World
date: 2024-01-02
tags:
  - one
  - two
---
# Body
`;
    const { frontmatter, content } = extractFrontmatter(source);

    expect(frontmatter.title).toBe('Hello World');
    expect(frontmatter.date).toBe('2024-01-02');
    expect(frontmatter.tags).toEqual(['one', 'two']);
    expect(content).toBe('# Body\n');
    expect(content).not.toContain('---');
  });

  it('handles inline array tags', () => {
    const { frontmatter } = extractFrontmatter(`---
title: T
tags: [a, b, c]
---
Body`);
    expect(frontmatter.tags).toEqual(['a', 'b', 'c']);
  });

  it('handles comma-separated string tags', () => {
    const { frontmatter } = extractFrontmatter(`---
title: T
tags: one, two, three
---
Body`);
    expect(frontmatter.tags).toEqual(['one', 'two', 'three']);
  });

  it('returns empty frontmatter and full content when no block is present', () => {
    const { frontmatter, content } = extractFrontmatter('# Just a body');

    expect(frontmatter.title).toBe('');
    expect(frontmatter.date).toBeUndefined();
    expect(frontmatter.tags).toEqual([]);
    expect(content).toBe('# Just a body');
  });

  it('ignores a --- that is not at the very start of the file', () => {
    const source = 'leading text\n---\ntitle: Nope\n---\n# Body';
    const { frontmatter, content } = extractFrontmatter(source);

    expect(frontmatter.title).toBe('');
    expect(content).toBe(source);
  });
});
