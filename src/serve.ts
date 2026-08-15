import fs from 'fs';
import { generate } from './generator.js';
import { BuildContext, PluginManager } from './plugin.js';
import { MarkdownPlugin } from './plugins/markdown-plugin.js';
import { TemplatePlugin } from './plugins/template-plugin.js';
import { DevServerPlugin } from './plugins/dev-server-plugin.js';

export interface ServeOptions {
  contentDir: string;
  outputDir: string;
  port?: number;
  templatesDir?: string;
  layoutsDir?: string;
  partialsDir?: string;
}

export interface ServeResult {
  close: () => Promise<void>;
}

export async function serve(options: ServeOptions, test?: boolean): Promise<ServeResult> {
  const port = options.port || 3000;
  const { contentDir, outputDir } = options;
  const templatesDir = options.templatesDir || './templates';
  const layoutsDir = options.layoutsDir || './templates/layouts';
  const partialsDir = options.partialsDir || './templates/partials';

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const rebuildSite = async () => {
    await generate({
      contentDir,
      outputDir,
      templatesDir,
      layoutsDir,
      partialsDir
    });
  };

  const devServerPlugin = new DevServerPlugin({
    port,
    onRebuild: rebuildSite,
    test
  });

  const pluginManager = new PluginManager();
  pluginManager.addPlugin(devServerPlugin);

  const context: BuildContext = {
    contentDir,
    outputDir,
    templatesDir,
    layoutsDir,
    partialsDir,
    pages: []
  };

  await pluginManager.callHook('onStart', context);

  return {
    close: async () => {
      await pluginManager.callHook('onEnd', context);
    }
  };
}
