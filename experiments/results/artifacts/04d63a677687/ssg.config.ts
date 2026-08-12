import { MarkdownPlugin } from './src/plugins/markdown';
import { TemplatePlugin } from './src/plugins/template';
import { DevServerPlugin } from './src/plugins/devserver';

export default {
  plugins: [
    new MarkdownPlugin(),
    new TemplatePlugin(),
    new DevServerPlugin(),
  ],
};
