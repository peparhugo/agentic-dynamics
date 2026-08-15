import { promises as fs } from 'fs';
import path from 'path';
import { TemplatePlugin } from './template.plugin';
import { PluginContext } from '../plugin';
import { PageData } from '../page';

const testDir = path.join(__dirname, '..', '..', '__test_template_plugin__');

async function cleanup(): Promise<void> {
  try {
    await fs.rm(testDir, { recursive: true, force: true });
  } catch (e) {
    // ignored
  }
}

describe('TemplatePlugin', () => {
  beforeEach(async () => {
    await cleanup();
  });

  afterEach(async () => {
    await cleanup();
  });

  describe('onFile hook', () => {
    it('should return page unchanged if no templateDir', async () => {
      const context: PluginContext = {
        contentDir: './content',
        outputDir: './dist'
      };

      const page: PageData = {
        slug: 'test',
        title: 'Test',
        html: '<p>Content</p>'
      };

      if (TemplatePlugin.onFile) {
        const result = await TemplatePlugin.onFile(page, context);
        expect(result).toEqual(page);
      }
    });

    it('should apply template if specified', async () => {
      const templatesDir = path.join(testDir, 'templates');
      await fs.mkdir(path.join(templatesDir, 'layouts'), { recursive: true });

      const layoutContent = '<!DOCTYPE html><html><body>{{{body}}}</body></html>';
      await fs.writeFile(
        path.join(templatesDir, 'layouts', 'default.hbs'),
        layoutContent
      );

      const context: PluginContext = {
        contentDir: './content',
        outputDir: './dist',
        templateDir: templatesDir
      };

      const page: PageData = {
        slug: 'test',
        title: 'Test',
        layout: 'default',
        html: '<p>Content</p>'
      };

      if (TemplatePlugin.onFile) {
        const result = await TemplatePlugin.onFile(page, context);
        expect(result.html).toContain('<!DOCTYPE html>');
        expect(result.html).toContain('<p>Content</p>');
      }
    });
  });

  describe('beforeBuild hook', () => {
    it('should load partials if templateDir is provided', async () => {
      const templatesDir = path.join(testDir, 'templates');
      await fs.mkdir(path.join(templatesDir, 'partials'), { recursive: true });

      const partialContent = '<div>Partial</div>';
      await fs.writeFile(
        path.join(templatesDir, 'partials', 'header.hbs'),
        partialContent
      );

      const context: PluginContext = {
        contentDir: './content',
        outputDir: './dist',
        templateDir: templatesDir
      };

      if (TemplatePlugin.beforeBuild) {
        await expect(TemplatePlugin.beforeBuild(context)).resolves.not.toThrow();
      }
    });

    it('should not throw if no templateDir', async () => {
      const context: PluginContext = {
        contentDir: './content',
        outputDir: './dist'
      };

      if (TemplatePlugin.beforeBuild) {
        await expect(TemplatePlugin.beforeBuild(context)).resolves.not.toThrow();
      }
    });
  });
});
