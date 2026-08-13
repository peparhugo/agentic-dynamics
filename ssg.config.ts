import { createMarkdownPlugin, createTemplatePlugin, SSGConfig } from './src';
import { createLoggerPlugin } from './plugins/exampleLoggerPlugin';

/**
 * Example plugin config: `ssg build --config ssg.config.ts` runs this
 * project's build through the custom plugin pipeline instead of the
 * built-in default. Plugin order matters — the logger's `onFile` runs
 * before TemplatePlugin's, so it observes each page before it's rendered
 * and written to disk.
 */
const config: SSGConfig = {
  plugins: [createMarkdownPlugin(), createLoggerPlugin(), createTemplatePlugin()],
  contentDir: './content',
  outputDir: './dist-site',
  templatesDir: './templates',
};

export default config;
