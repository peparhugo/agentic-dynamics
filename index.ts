export { buildSite } from './src/generator';
export type { BuildOptions, Page } from './src/generator';
export { startDevServer } from './src/server';
export type { DevServer, ServeOptions } from './src/server';
export type { Plugin, BuildContext, SSGConfig } from './src/plugin';
export { loadPlugins } from './src/plugin';
export { MarkdownPlugin } from './plugins/markdown';
export { TemplatePlugin } from './plugins/template';
export { DevServerPlugin } from './plugins/dev-server';
