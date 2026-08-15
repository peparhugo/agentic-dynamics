import { Plugin, PluginManager, PluginContext } from './plugin';
import { PageData } from './page';

describe('PluginManager', () => {
  let pluginManager: PluginManager;
  const testContext: PluginContext = {
    contentDir: './content',
    outputDir: './dist'
  };

  beforeEach(() => {
    pluginManager = new PluginManager();
  });

  describe('plugin registration', () => {
    it('should register a plugin', () => {
      const testPlugin: Plugin = { name: 'test' };
      pluginManager.register(testPlugin);
      expect(pluginManager).toBeDefined();
    });

    it('should register multiple plugins', () => {
      const plugin1: Plugin = { name: 'test1' };
      const plugin2: Plugin = { name: 'test2' };
      pluginManager.register(plugin1);
      pluginManager.register(plugin2);
      expect(pluginManager).toBeDefined();
    });
  });

  describe('onStart hook', () => {
    it('should call onStart hook on all plugins', async () => {
      const calls: string[] = [];
      const plugin1: Plugin = {
        name: 'plugin1',
        onStart: async () => {
          calls.push('plugin1');
        }
      };
      const plugin2: Plugin = {
        name: 'plugin2',
        onStart: async () => {
          calls.push('plugin2');
        }
      };

      pluginManager.register(plugin1);
      pluginManager.register(plugin2);
      await pluginManager.runOnStart(testContext);

      expect(calls).toEqual(['plugin1', 'plugin2']);
    });

    it('should skip plugins without onStart hook', async () => {
      const calls: string[] = [];
      const plugin1: Plugin = {
        name: 'plugin1',
        onStart: async () => {
          calls.push('plugin1');
        }
      };
      const plugin2: Plugin = { name: 'plugin2' };

      pluginManager.register(plugin1);
      pluginManager.register(plugin2);
      await pluginManager.runOnStart(testContext);

      expect(calls).toEqual(['plugin1']);
    });
  });

  describe('beforeBuild hook', () => {
    it('should call beforeBuild hook on all plugins', async () => {
      const calls: string[] = [];
      const plugin1: Plugin = {
        name: 'plugin1',
        beforeBuild: async () => {
          calls.push('plugin1');
        }
      };
      const plugin2: Plugin = {
        name: 'plugin2',
        beforeBuild: async () => {
          calls.push('plugin2');
        }
      };

      pluginManager.register(plugin1);
      pluginManager.register(plugin2);
      await pluginManager.runBeforeBuild(testContext);

      expect(calls).toEqual(['plugin1', 'plugin2']);
    });
  });

  describe('onFile hook', () => {
    it('should process page through onFile hooks in order', async () => {
      const page: PageData = {
        slug: 'test',
        title: 'Test',
        html: '<p>Original</p>'
      };

      const plugin1: Plugin = {
        name: 'plugin1',
        onFile: async (p) => ({
          ...p,
          html: p.html + '<!-- Plugin 1 -->'
        })
      };

      const plugin2: Plugin = {
        name: 'plugin2',
        onFile: async (p) => ({
          ...p,
          html: p.html + '<!-- Plugin 2 -->'
        })
      };

      pluginManager.register(plugin1);
      pluginManager.register(plugin2);
      const result = await pluginManager.runOnFile(page, testContext);

      expect(result.html).toContain('Original');
      expect(result.html).toContain('Plugin 1');
      expect(result.html).toContain('Plugin 2');
      expect(result.html.indexOf('Plugin 1')).toBeLessThan(result.html.indexOf('Plugin 2'));
    });

    it('should pass page data through plugin chain', async () => {
      const page: PageData = {
        slug: 'test',
        title: 'Original Title',
        html: '<p>Content</p>'
      };

      const plugin1: Plugin = {
        name: 'plugin1',
        onFile: async (p) => ({
          ...p,
          title: p.title + ' - Modified by Plugin 1'
        })
      };

      pluginManager.register(plugin1);
      const result = await pluginManager.runOnFile(page, testContext);

      expect(result.title).toBe('Original Title - Modified by Plugin 1');
    });

    it('should handle plugins without onFile hook', async () => {
      const page: PageData = {
        slug: 'test',
        title: 'Test',
        html: '<p>Content</p>'
      };

      const plugin1: Plugin = {
        name: 'plugin1',
        onFile: async (p) => ({
          ...p,
          html: p.html + '<!-- Modified -->'
        })
      };

      const plugin2: Plugin = { name: 'plugin2' };

      pluginManager.register(plugin1);
      pluginManager.register(plugin2);
      const result = await pluginManager.runOnFile(page, testContext);

      expect(result.html).toContain('Modified');
    });
  });

  describe('afterBuild hook', () => {
    it('should call afterBuild hook with all pages', async () => {
      const pages: PageData[] = [
        { slug: 'page1', title: 'Page 1', html: '<p>1</p>' },
        { slug: 'page2', title: 'Page 2', html: '<p>2</p>' }
      ];

      let receivedPages: PageData[] | null = null;
      const plugin: Plugin = {
        name: 'test',
        afterBuild: async (p) => {
          receivedPages = p;
        }
      };

      pluginManager.register(plugin);
      await pluginManager.runAfterBuild(pages, testContext);

      expect(receivedPages).toEqual(pages);
    });

    it('should call afterBuild on all plugins', async () => {
      const pages: PageData[] = [];
      const calls: string[] = [];

      const plugin1: Plugin = {
        name: 'plugin1',
        afterBuild: async () => {
          calls.push('plugin1');
        }
      };

      const plugin2: Plugin = {
        name: 'plugin2',
        afterBuild: async () => {
          calls.push('plugin2');
        }
      };

      pluginManager.register(plugin1);
      pluginManager.register(plugin2);
      await pluginManager.runAfterBuild(pages, testContext);

      expect(calls).toEqual(['plugin1', 'plugin2']);
    });
  });

  describe('onEnd hook', () => {
    it('should call onEnd hook on all plugins', async () => {
      const calls: string[] = [];
      const plugin1: Plugin = {
        name: 'plugin1',
        onEnd: async () => {
          calls.push('plugin1');
        }
      };

      const plugin2: Plugin = {
        name: 'plugin2',
        onEnd: async () => {
          calls.push('plugin2');
        }
      };

      pluginManager.register(plugin1);
      pluginManager.register(plugin2);
      await pluginManager.runOnEnd(testContext);

      expect(calls).toEqual(['plugin1', 'plugin2']);
    });
  });

  describe('full lifecycle', () => {
    it('should execute hooks in correct order', async () => {
      const order: string[] = [];

      const plugin: Plugin = {
        name: 'test',
        onStart: async () => {
          order.push('onStart');
        },
        beforeBuild: async () => {
          order.push('beforeBuild');
        },
        afterBuild: async () => {
          order.push('afterBuild');
        },
        onEnd: async () => {
          order.push('onEnd');
        }
      };

      pluginManager.register(plugin);
      await pluginManager.runOnStart(testContext);
      await pluginManager.runBeforeBuild(testContext);
      await pluginManager.runAfterBuild([], testContext);
      await pluginManager.runOnEnd(testContext);

      expect(order).toEqual(['onStart', 'beforeBuild', 'afterBuild', 'onEnd']);
    });
  });
});
