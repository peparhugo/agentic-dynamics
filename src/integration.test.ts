import { promises as fs } from 'fs';
import path from 'path';
import { build } from './build';
import { PluginManager } from './plugin';
import { MarkdownPlugin } from './plugins/markdown.plugin';
import { TemplatePlugin } from './plugins/template.plugin';

const testDir = path.join(__dirname, '..', '__test_integration__');
const contentDir = path.join(testDir, 'content');
const outputDir = path.join(testDir, 'dist');
const templateDir = path.join(testDir, 'templates');

async function cleanup(): Promise<void> {
  try {
    await fs.rm(testDir, { recursive: true, force: true });
  } catch (e) {
    // ignored
  }
}

async function setupTestContent(): Promise<void> {
  await fs.mkdir(contentDir, { recursive: true });
  await fs.mkdir(path.join(templateDir, 'layouts'), { recursive: true });

  const markdownContent = `---
title: Test Post
date: 2024-01-15
tags: [test, markdown]
layout: default
---

# Hello World

This is a test post.`;

  await fs.writeFile(path.join(contentDir, 'test.md'), markdownContent);

  const layoutContent = `<!DOCTYPE html>
<html>
<head>
  <title>{{title}}</title>
</head>
<body>
  {{{body}}}
</body>
</html>`;

  await fs.writeFile(path.join(templateDir, 'layouts', 'default.hbs'), layoutContent);
}

describe('Integration: Plugin System', () => {
  beforeEach(async () => {
    await cleanup();
    await setupTestContent();
  });

  afterEach(async () => {
    await cleanup();
  });

  describe('End-to-end build', () => {
    it('should build site with markdown and template plugins', async () => {
      await build(contentDir, outputDir, templateDir);

      const indexPath = path.join(outputDir, 'index.html');
      const testPagePath = path.join(outputDir, 'test.html');

      const indexExists = await fs.stat(indexPath).then(() => true).catch(() => false);
      const testPageExists = await fs.stat(testPagePath).then(() => true).catch(() => false);

      expect(indexExists).toBe(true);
      expect(testPageExists).toBe(true);

      const testPageContent = await fs.readFile(testPagePath, 'utf-8');
      expect(testPageContent).toContain('Test Post');
      expect(testPageContent).toContain('Hello World');
    });

    it('should maintain backward compatibility without plugins', async () => {
      await build(contentDir, outputDir, templateDir, false);

      const testPagePath = path.join(outputDir, 'test.html');
      const testPageExists = await fs.stat(testPagePath).then(() => true).catch(() => false);

      expect(testPageExists).toBe(true);

      const content = await fs.readFile(testPagePath, 'utf-8');
      expect(content).toContain('Test Post');
    });

    it('should generate index.html with all pages', async () => {
      await build(contentDir, outputDir, templateDir);

      const indexPath = path.join(outputDir, 'index.html');
      const content = await fs.readFile(indexPath, 'utf-8');

      expect(content).toContain('Test Post');
      expect(content).toContain('test.html');
      expect(content).toContain('Total: 1 page');
    });
  });

  describe('Plugin lifecycle', () => {
    it('should execute plugin hooks in correct sequence', async () => {
      const callStack: string[] = [];

      const trackingPlugin: any = {
        name: 'tracking',
        onStart: async () => callStack.push('onStart'),
        beforeBuild: async () => callStack.push('beforeBuild'),
        onFile: async (page: any) => {
          callStack.push('onFile');
          return page;
        },
        afterBuild: async () => callStack.push('afterBuild'),
        onEnd: async () => callStack.push('onEnd')
      };

      const manager = new PluginManager();
      manager.register(trackingPlugin);

      const context = { contentDir, outputDir, templateDir };

      await manager.runOnStart(context);
      await manager.runBeforeBuild(context);
      const page = await manager.runOnFile({ slug: 'test', title: 'Test', html: '<p>Test</p>' }, context);
      await manager.runAfterBuild([page], context);
      await manager.runOnEnd(context);

      expect(callStack).toEqual(['onStart', 'beforeBuild', 'onFile', 'afterBuild', 'onEnd']);
    });

    it('should allow plugins to modify page data', async () => {
      const modifyingPlugin = {
        name: 'modifier',
        onFile: async (page: any) => ({
          ...page,
          html: page.html + '<!-- Modified -->'
        })
      };

      const manager = new PluginManager();
      manager.register(modifyingPlugin);

      const page = { slug: 'test', title: 'Test', html: '<p>Original</p>' };
      const context = { contentDir, outputDir };

      const result = await manager.runOnFile(page, context);

      expect(result.html).toBe('<p>Original</p><!-- Modified -->');
      expect(result.title).toBe('Test');
    });
  });
});
