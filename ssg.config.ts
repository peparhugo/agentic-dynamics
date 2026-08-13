import { Plugin } from './src/plugin';
import { MarkdownPlugin } from './src/plugins/markdown-plugin';
import { TemplatePlugin } from './src/plugins/template-plugin';
import { DevServerPlugin } from './src/plugins/dev-server-plugin';

const plugins: Plugin[] = [
  new MarkdownPlugin(),
  new TemplatePlugin(),
  new DevServerPlugin({ port: 3000 }),
];

export default { plugins };
