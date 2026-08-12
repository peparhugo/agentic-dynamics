import type { Plugin } from './src/plugin';
import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/templates';
import { DevServerPlugin } from './plugins/dev-server';

export interface SSGConfig {
  plugins: Plugin[];
}

const config: SSGConfig = {
  plugins: [new MarkdownPlugin(), new TemplatePlugin(), new DevServerPlugin()],
};

export default config;
