import { MarkdownPlugin } from './plugins/markdown';
import { TemplatePlugin } from './plugins/template';
import { DevServerPlugin } from './plugins/dev-server';
import type { SsgConfig } from './src/config';

/**
 * Example plugin configuration, wiring up the built-in plugins explicitly.
 * Pass `--config ssg.config.ts` to `ssg build`/`ssg serve` to use it, or
 * swap in your own plugins from `./plugins/`.
 */
const config: SsgConfig = {
  plugins: [new MarkdownPlugin(), new TemplatePlugin(), new DevServerPlugin()],
};

export default config;
