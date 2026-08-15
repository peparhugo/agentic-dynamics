import { DevServerPlugin } from './plugins/DevServerPlugin';
import { MarkdownPlugin } from './plugins/MarkdownPlugin';
import { TemplatePlugin } from './plugins/TemplatePlugin';

export default {
  plugins: [MarkdownPlugin, TemplatePlugin, DevServerPlugin()],
};
