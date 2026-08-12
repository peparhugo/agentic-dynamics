import type { Plugin } from '../../../src/plugin';
import { MarkdownPlugin } from '../../../src/plugins/markdown';
import { TemplatePlugin } from '../../../src/plugins/templates';
import { DevServerPlugin } from '../../../src/plugins/dev-server';

const config: { plugins: Plugin[] } = {
  plugins: [new MarkdownPlugin(), new TemplatePlugin(), new DevServerPlugin()],
};

export default config;
