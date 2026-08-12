import { MarkdownPlugin } from './src/plugins/markdown-plugin';
import { TemplatePlugin } from './src/plugins/template-plugin';
import { ExamplePlugin } from './plugins/example-plugin';
import type { Plugin } from './src/plugin';

const plugins: Plugin[] = [
  new MarkdownPlugin(),
  new TemplatePlugin(),
  new ExamplePlugin(),
];

export default { plugins };
