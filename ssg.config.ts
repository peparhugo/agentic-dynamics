import MarkdownPlugin from './plugins/markdown';
import TemplatePlugin from './plugins/template';

/** The default pipeline preserves the generator's existing markdown and template behavior. */
export default {
  plugins: [MarkdownPlugin, TemplatePlugin],
};
