import { MarkdownPlugin } from './markdown.plugin';
import { PluginContext } from '../plugin';
import { PageData } from '../page';

describe('MarkdownPlugin', () => {
  const testContext: PluginContext = {
    contentDir: './content',
    outputDir: './dist'
  };

  describe('onFile hook', () => {
    it('should return page unchanged', async () => {
      const page: PageData = {
        slug: 'test',
        title: 'Test',
        html: '<p>Content</p>'
      };

      if (MarkdownPlugin.onFile) {
        const result = await MarkdownPlugin.onFile(page, testContext);
        expect(result).toEqual(page);
      }
    });

    it('should preserve all page properties', async () => {
      const page: PageData = {
        slug: 'test-post',
        title: 'Test Post',
        date: '2024-01-15',
        tags: ['markdown', 'test'],
        html: '<h1>Test</h1>',
        layout: 'default',
        template: 'post'
      };

      if (MarkdownPlugin.onFile) {
        const result = await MarkdownPlugin.onFile(page, testContext);
        expect(result.slug).toBe('test-post');
        expect(result.title).toBe('Test Post');
        expect(result.date).toBe('2024-01-15');
        expect(result.tags).toEqual(['markdown', 'test']);
        expect(result.html).toBe('<h1>Test</h1>');
        expect(result.layout).toBe('default');
        expect(result.template).toBe('post');
      }
    });
  });
});
