import { promises as fs } from 'fs';
import path from 'path';
import { generatePageHtml, generateIndexHtml } from './generator';
import { PageData } from './page';

const testDir = path.join(__dirname, '..', '__test_gen__');

async function cleanup(): Promise<void> {
  try {
    await fs.rm(testDir, { recursive: true, force: true });
  } catch (e) {
    // ignored
  }
}

describe('generator', () => {
  beforeEach(async () => {
    await cleanup();
  });

  afterEach(async () => {
    await cleanup();
  });

  describe('generatePageHtml', () => {
    it('should generate page HTML file', async () => {
      const page: PageData = {
        slug: 'test-post',
        title: 'Test Post',
        html: '<p>Content</p>'
      };

      await generatePageHtml(page, testDir);

      const filePath = path.join(testDir, 'test-post.html');
      const exists = await fs.stat(filePath).then(() => true).catch(() => false);
      expect(exists).toBe(true);
    });

    it('should generate page HTML file with templates', async () => {
      const templatesDir = path.join(testDir, 'templates');
      await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });

      const layoutContent = '<!DOCTYPE html><html><body>{{{body}}}</body></html>';
      await fs.writeFile(
        path.join(templatesDir, 'layouts', 'default.hbs'),
        layoutContent
      );

      const page: PageData = {
        slug: 'test-post',
        title: 'Test Post',
        layout: 'default',
        html: '<p>Content with template</p>'
      };

      await generatePageHtml(page, testDir, templatesDir);

      const filePath = path.join(testDir, 'test-post.html');
      const exists = await fs.stat(filePath).then(() => true).catch(() => false);
      expect(exists).toBe(true);

      const content = await fs.readFile(filePath, 'utf-8');
      expect(content).toContain('<!DOCTYPE html>');
      expect(content).toContain('<p>Content with template</p>');
    });

    it('should include title in page HTML', async () => {
      const page: PageData = {
        slug: 'test',
        title: 'My Page Title',
        html: '<p>Content</p>'
      };

      await generatePageHtml(page, testDir);

      const content = await fs.readFile(path.join(testDir, 'test.html'), 'utf-8');
      expect(content).toContain('My Page Title');
      expect(content).toContain('<h1>My Page Title</h1>');
    });

    it('should include page content in HTML', async () => {
      const page: PageData = {
        slug: 'test',
        title: 'Test',
        html: '<p>This is the page content</p>'
      };

      await generatePageHtml(page, testDir);

      const content = await fs.readFile(path.join(testDir, 'test.html'), 'utf-8');
      expect(content).toContain('This is the page content');
    });

    it('should include date if provided', async () => {
      const page: PageData = {
        slug: 'test',
        title: 'Test',
        date: '2024-01-15',
        html: '<p>Content</p>'
      };

      await generatePageHtml(page, testDir);

      const content = await fs.readFile(path.join(testDir, 'test.html'), 'utf-8');
      expect(content).toContain('2024-01-15');
    });

    it('should include tags if provided', async () => {
      const page: PageData = {
        slug: 'test',
        title: 'Test',
        tags: ['javascript', 'tutorial'],
        html: '<p>Content</p>'
      };

      await generatePageHtml(page, testDir);

      const content = await fs.readFile(path.join(testDir, 'test.html'), 'utf-8');
      expect(content).toContain('javascript');
      expect(content).toContain('tutorial');
      expect(content).toContain('class="tag"');
    });

    it('should include back link to index', async () => {
      const page: PageData = {
        slug: 'test',
        title: 'Test',
        html: '<p>Content</p>'
      };

      await generatePageHtml(page, testDir);

      const content = await fs.readFile(path.join(testDir, 'test.html'), 'utf-8');
      expect(content).toContain('index.html');
      expect(content).toContain('Back to all pages');
    });

    it('should escape HTML in title', async () => {
      const page: PageData = {
        slug: 'test',
        title: '<script>alert("xss")</script>',
        html: '<p>Content</p>'
      };

      await generatePageHtml(page, testDir);

      const content = await fs.readFile(path.join(testDir, 'test.html'), 'utf-8');
      expect(content).not.toContain('<script>');
      expect(content).toContain('&lt;script&gt;');
    });
  });

  describe('generateIndexHtml', () => {
    it('should generate index HTML file', async () => {
      const pages: PageData[] = [
        {
          slug: 'post1',
          title: 'Post 1',
          html: '<p>Content</p>'
        }
      ];

      await generateIndexHtml(pages, testDir);

      const filePath = path.join(testDir, 'index.html');
      const exists = await fs.stat(filePath).then(() => true).catch(() => false);
      expect(exists).toBe(true);
    });

    it('should list all pages in index', async () => {
      const pages: PageData[] = [
        { slug: 'post1', title: 'First Post', html: '<p>Content</p>' },
        { slug: 'post2', title: 'Second Post', html: '<p>Content</p>' }
      ];

      await generateIndexHtml(pages, testDir);

      const content = await fs.readFile(path.join(testDir, 'index.html'), 'utf-8');
      expect(content).toContain('First Post');
      expect(content).toContain('Second Post');
      expect(content).toContain('post1.html');
      expect(content).toContain('post2.html');
    });

    it('should show page count', async () => {
      const pages: PageData[] = [
        { slug: 'post1', title: 'Post 1', html: '<p>Content</p>' },
        { slug: 'post2', title: 'Post 2', html: '<p>Content</p>' }
      ];

      await generateIndexHtml(pages, testDir);

      const content = await fs.readFile(path.join(testDir, 'index.html'), 'utf-8');
      expect(content).toContain('Total: 2 pages');
    });

    it('should sort pages by date descending', async () => {
      const pages: PageData[] = [
        { slug: 'post1', title: 'First', date: '2024-01-10', html: '<p>1</p>' },
        { slug: 'post2', title: 'Third', date: '2024-01-20', html: '<p>3</p>' },
        { slug: 'post3', title: 'Second', date: '2024-01-15', html: '<p>2</p>' }
      ];

      await generateIndexHtml(pages, testDir);

      const content = await fs.readFile(path.join(testDir, 'index.html'), 'utf-8');
      const post2Index = content.indexOf('Third');
      const post3Index = content.indexOf('Second');
      const post1Index = content.indexOf('First');

      expect(post2Index).toBeLessThan(post3Index);
      expect(post3Index).toBeLessThan(post1Index);
    });

    it('should include dates in index', async () => {
      const pages: PageData[] = [
        { slug: 'post1', title: 'Post', date: '2024-01-15', html: '<p>Content</p>' }
      ];

      await generateIndexHtml(pages, testDir);

      const content = await fs.readFile(path.join(testDir, 'index.html'), 'utf-8');
      expect(content).toContain('2024-01-15');
    });

    it('should include tags in index', async () => {
      const pages: PageData[] = [
        {
          slug: 'post1',
          title: 'Post',
          tags: ['javascript', 'web'],
          html: '<p>Content</p>'
        }
      ];

      await generateIndexHtml(pages, testDir);

      const content = await fs.readFile(path.join(testDir, 'index.html'), 'utf-8');
      expect(content).toContain('javascript');
      expect(content).toContain('web');
    });

    it('should escape HTML in titles', async () => {
      const pages: PageData[] = [
        {
          slug: 'test',
          title: '<script>alert("xss")</script>',
          html: '<p>Content</p>'
        }
      ];

      await generateIndexHtml(pages, testDir);

      const content = await fs.readFile(path.join(testDir, 'index.html'), 'utf-8');
      expect(content).not.toContain('<script>');
      expect(content).toContain('&lt;script&gt;');
    });

    it('should handle empty pages array', async () => {
      await generateIndexHtml([], testDir);

      const content = await fs.readFile(path.join(testDir, 'index.html'), 'utf-8');
      expect(content).toContain('Total: 0 pages');
    });

    it('should handle single page correctly', async () => {
      const pages: PageData[] = [
        { slug: 'post', title: 'Post', html: '<p>Content</p>' }
      ];

      await generateIndexHtml(pages, testDir);

      const content = await fs.readFile(path.join(testDir, 'index.html'), 'utf-8');
      expect(content).toContain('Total: 1 page');
    });
  });
});
