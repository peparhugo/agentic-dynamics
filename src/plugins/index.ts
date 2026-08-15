/**
 * Built-in plugins shipped with the SSG. These are the standard features
 * (Markdown rendering, template rendering and the live-reload dev server)
 * exposed through the plugin system.
 */

export {
  DEV_SERVER_PLUGIN_NAME,
  DevServerPlugin,
  DEFAULT_PORT,
  RELOAD_PATH,
  REBUILD_DELAY_MS,
  injectLiveReloadScript,
} from './dev-server';
export type { DevServer, ServeOptions } from './dev-server';
export { MARKDOWN_PLUGIN_NAME, MarkdownPlugin } from './markdown';
export { TEMPLATE_PLUGIN_NAME, TemplatePlugin } from './template';
