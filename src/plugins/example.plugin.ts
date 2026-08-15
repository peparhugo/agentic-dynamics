import { Plugin, PluginContext } from '../plugin';
import { PageData } from '../page';

export const ExamplePlugin: Plugin = {
  name: 'example',

  onStart: async (context: PluginContext): Promise<void> => {
    console.log(`[Example Plugin] Starting build with content dir: ${context.contentDir}`);
  },

  beforeBuild: async (context: PluginContext): Promise<void> => {
    console.log('[Example Plugin] Running before build');
  },

  onFile: async (page: PageData, context: PluginContext): Promise<PageData> => {
    console.log(`[Example Plugin] Processing file: ${page.slug}`);
    return page;
  },

  afterBuild: async (pages: PageData[], context: PluginContext): Promise<void> => {
    console.log(`[Example Plugin] Build complete! Generated ${pages.length} pages`);
  },

  onEnd: async (context: PluginContext): Promise<void> => {
    console.log('[Example Plugin] Build process finished');
  }
};
