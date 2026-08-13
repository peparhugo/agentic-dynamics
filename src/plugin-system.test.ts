import fs from 'fs';
import path from 'path';
import { build } from './generator';
import { PluginManager } from './plugin';
import { MarkdownPlugin, TemplatePlugin, DevServerPlugin } from './plugins';
import { createPluginManager } from './plugin-loader';

const TEST_CONTENT_DIR = path.join(__dirname, '__test-plugins-content');
const TEST_OUTPUT_DIR = path.join(__dirname, '__test-plugins-output');
const TEST_TEMPLATES_DIR = path.join(__dirname, '__test-plugins-templates');

function setupTestDirs(): void {
  for (const dir of [TEST_CONTENT_DIR, TEST_OUTPUT_DIR, TEST_TEMPLATES_DIR]) {
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true });
    }
    fs.mkdirSync(dir, { recursive: true });
  }

  const layoutsDir = path.join(TEST_TEMPLATES_DIR, 'layouts');
  fs.mkdirSync(layoutsDir, { recursive: true });
}

function cleanupTestDirs(): void {
  for (const dir of [TEST_CONTENT_DIR, TEST_OUTPUT_DIR, TEST_TEMPLATES_DIR]) {
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true });
    }
  }
}

describe('Plugin System', () => {
  beforeEach(setupTestDirs);
  afterEach(cleanupTestDirs);

  it('should create a plugin manager and add plugins', () => {
    const manager = new PluginManager();
    const markdownPlugin = new MarkdownPlugin();
    const templatePlugin = new TemplatePlugin();

    manager.addPlugin(markdownPlugin);
    manager.addPlugin(templatePlugin);

    expect(manager.getPlugins()).toHaveLength(2);
    expect(manager.getPlugin('markdown-plugin')).toBe(markdownPlugin);
    expect(manager.getPlugin('template-plugin')).toBe(templatePlugin);
  });

  it('should build with plugins', async () => {
    const content = `---
title: Plugin Test
---
# Hello World

This is a test.`;

    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'test.md'), content);

    const manager = createPluginManager([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await build(TEST_CONTENT_DIR, TEST_OUTPUT_DIR, '__nonexistent__', manager);

    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'test.html'))).toBe(true);
    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'index.html'))).toBe(true);

    const html = fs.readFileSync(path.join(TEST_OUTPUT_DIR, 'test.html'), 'utf-8');
    expect(html).toContain('Plugin Test');
    expect(html).toContain('Hello World');
  });

  it('should build with plugin manager from config', async () => {
    const content = `---
title: Config Test
---
# Test Content`;

    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'test.md'), content);

    const plugins = [
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ];
    const manager = createPluginManager(plugins);

    await build(TEST_CONTENT_DIR, TEST_OUTPUT_DIR, '__nonexistent__', manager);

    const html = fs.readFileSync(path.join(TEST_OUTPUT_DIR, 'test.html'), 'utf-8');
    expect(html).toContain('Config Test');
    expect(html).toContain('<h1>Test Content</h1>');
  });

  it('should handle multiple pages with plugins', async () => {
    const page1 = `---
title: Page One
date: 2023-01-01
---
# First Page`;

    const page2 = `---
title: Page Two
date: 2023-01-02
---
# Second Page`;

    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page1.md'), page1);
    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'page2.md'), page2);

    const manager = createPluginManager([
      new MarkdownPlugin(),
      new TemplatePlugin(),
    ]);

    await build(TEST_CONTENT_DIR, TEST_OUTPUT_DIR, '__nonexistent__', manager);

    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'page1.html'))).toBe(true);
    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'page2.html'))).toBe(true);

    const page1Html = fs.readFileSync(path.join(TEST_OUTPUT_DIR, 'page1.html'), 'utf-8');
    expect(page1Html).toContain('Page One');

    const page2Html = fs.readFileSync(path.join(TEST_OUTPUT_DIR, 'page2.html'), 'utf-8');
    expect(page2Html).toContain('Page Two');
  });

  it('should maintain backward compatibility without plugins', async () => {
    const content = `---
title: Backward Compat
---
# Test`;

    fs.writeFileSync(path.join(TEST_CONTENT_DIR, 'test.md'), content);

    await build(TEST_CONTENT_DIR, TEST_OUTPUT_DIR, '__nonexistent__');

    expect(fs.existsSync(path.join(TEST_OUTPUT_DIR, 'test.html'))).toBe(true);
    const html = fs.readFileSync(path.join(TEST_OUTPUT_DIR, 'test.html'), 'utf-8');
    expect(html).toContain('Backward Compat');
  });
});
