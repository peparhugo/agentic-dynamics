import { describe, it, expect } from 'vitest';
import { createMarkdown } from '../src/markdown';

describe('markdown rendering', () => {
  it('renders code blocks with highlighting', () => {
    const md = createMarkdown();
    const out = md.render('```js\nconsole.log(1)\n```');
    expect(out).toContain('hljs');
    expect(out).toContain('language-js');
  });
});
