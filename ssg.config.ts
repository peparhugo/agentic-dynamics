import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';

/**
 * Default SSG plugin configuration. Add your own plugins to this array to
 * extend the pipeline; hooks run in the order listed here.
 */
export default {
  plugins: [new MarkdownPlugin(), new TemplatePlugin()],
};
