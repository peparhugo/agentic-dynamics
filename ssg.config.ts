import { MarkdownPlugin } from './src/plugins/markdown';
import { TemplatePlugin } from './src/plugins/template';
import { DevServerPlugin } from './src/plugins/dev-server';
import { Plugin } from './src/plugin';

export interface SsgConfig {
  plugins: Plugin[];
}

const config: SsgConfig = {
  plugins: [
    new MarkdownPlugin(),
    new TemplatePlugin(),
  ],
};

export default config;
