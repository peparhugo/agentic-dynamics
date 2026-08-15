import { SSGConfig } from './src/config';
import { markdownPlugin } from './plugins/markdown-plugin';
import { templatePlugin } from './plugins/template-plugin';

/**
 * Default plugin pipeline for this SSG. The dev server plugin is not listed
 * here - `startDevServer` appends it on top of this pipeline itself, since
 * it only applies to `ssg serve`, never to a plain `ssg build`.
 */
const config: SSGConfig = {
  plugins: [markdownPlugin(), templatePlugin()],
};

export default config;
