import { generatePageHTML, generateIndexHTML } from '../generator';
import { ParsedPage } from '../parser';

describe('generator', () => {
  describe('generatePageHTML', () => {
    it('should generate valid HTML for a page', () => {
      const page: ParsedPage = {
        slug: 'test-page',
        frontmatter: {
          title: 'Test Page',
          date: '2024-01-15',
          tags: ['test', 'example'],
        },
        html: '<p>This is test content</p>',
      };

      const result = generatePageHTML(page);

      expect(result).toContain('<!DOCTYPE html>');
      expect(result).toContain('<title>Test Page</title>');
      expect(result).toContain('<h1>Test Page</h1>');
      expect(result).toContain('Published: 1/15/2024');
      expect(result).toContain('<span class="tag">test</span>');
      expect(result).toContain('<span class="tag">example</span>');
      expect(result).toContain('<p>This is test content</p>');
      expect(result).toContain('<a href="index.html">← Back to index</a>');
    });

    it('should handle pages without date', () => {
      const page: ParsedPage = {
        slug: 'no-date',
        frontmatter: {
          title: 'No Date Post',
        },
        html: '<p>Content</p>',
      };

      const result = generatePageHTML(page);

      expect(result).toContain('<title>No Date Post</title>');
      expect(result).not.toContain('Published:');
      expect(result).toContain('<p>Content</p>');
    });

    it('should handle pages without tags', () => {
      const page: ParsedPage = {
        slug: 'no-tags',
        frontmatter: {
          title: 'No Tags',
          tags: [],
        },
        html: '<p>Content</p>',
      };

      const result = generatePageHTML(page);

      expect(result).not.toContain('class="tag"');
    });

    it('should escape HTML in title', () => {
      const page: ParsedPage = {
        slug: 'xss-test',
        frontmatter: {
          title: '<script>alert("xss")</script>',
        },
        html: '<p>Content</p>',
      };

      const result = generatePageHTML(page);

      expect(result).not.toContain('<script>');
      expect(result).toContain('&lt;script&gt;');
    });

    it('should escape HTML in tags', () => {
      const page: ParsedPage = {
        slug: 'tag-escape',
        frontmatter: {
          title: 'Test',
          tags: ['<bad>', '"quote"'],
        },
        html: '<p>Content</p>',
      };

      const result = generatePageHTML(page);

      expect(result).toContain('&lt;bad&gt;');
      expect(result).toContain('&quot;quote&quot;');
    });
  });

  describe('generateIndexHTML', () => {
    it('should generate index with multiple pages', () => {
      const pages: ParsedPage[] = [
        {
          slug: 'first',
          frontmatter: { title: 'First Post', date: '2024-01-15' },
          html: '<p>First</p>',
        },
        {
          slug: 'second',
          frontmatter: { title: 'Second Post', date: '2024-01-10' },
          html: '<p>Second</p>',
        },
      ];

      const result = generateIndexHTML(pages);

      expect(result).toContain('<!DOCTYPE html>');
      expect(result).toContain('<title>Site Index</title>');
      expect(result).toContain('<h1>Site Index</h1>');
      expect(result).toContain('2 pages found');
      expect(result).toContain('<a href="first.html">First Post</a>');
      expect(result).toContain('<a href="second.html">Second Post</a>');
    });

    it('should sort pages by date in descending order', () => {
      const pages: ParsedPage[] = [
        {
          slug: 'old',
          frontmatter: { title: 'Old Post', date: '2024-01-01' },
          html: '<p>Old</p>',
        },
        {
          slug: 'new',
          frontmatter: { title: 'New Post', date: '2024-01-31' },
          html: '<p>New</p>',
        },
      ];

      const result = generateIndexHTML(pages);

      const newIndex = result.indexOf('New Post');
      const oldIndex = result.indexOf('Old Post');
      expect(newIndex).toBeLessThan(oldIndex);
    });

    it('should handle pages without dates', () => {
      const pages: ParsedPage[] = [
        {
          slug: 'with-date',
          frontmatter: { title: 'With Date', date: '2024-01-15' },
          html: '<p>Content</p>',
        },
        {
          slug: 'no-date',
          frontmatter: { title: 'No Date' },
          html: '<p>Content</p>',
        },
      ];

      const result = generateIndexHTML(pages);

      expect(result).toContain('With Date');
      expect(result).toContain('No Date');
      expect(result).toContain('No date');
    });

    it('should display correct page count', () => {
      const pages: ParsedPage[] = [
        {
          slug: 'one',
          frontmatter: { title: 'One' },
          html: '<p>One</p>',
        },
      ];

      const result = generateIndexHTML(pages);
      expect(result).toContain('1 page found');

      const pages2: ParsedPage[] = Array(5)
        .fill(null)
        .map((_, i) => ({
          slug: `page-${i}`,
          frontmatter: { title: `Page ${i}` },
          html: '<p>Content</p>',
        }));

      const result2 = generateIndexHTML(pages2);
      expect(result2).toContain('5 pages found');
    });

    it('should escape HTML in page titles', () => {
      const pages: ParsedPage[] = [
        {
          slug: 'xss',
          frontmatter: { title: '<img src=x onerror=alert(1)>' },
          html: '<p>Content</p>',
        },
      ];

      const result = generateIndexHTML(pages);

      expect(result).not.toContain('<img src=');
      expect(result).toContain('&lt;img');
    });
  });
});
