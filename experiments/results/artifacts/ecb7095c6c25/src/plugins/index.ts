import { Plugin } from '../types';
import { MarkdownPlugin } from './markdown';
import { TemplatePlugin } from './template';
import { DevServerPlugin } from './devserver';

export const builtInPlugins: Plugin[] = [
  MarkdownPlugin,
  TemplatePlugin,
  DevServerPlugin,
];

export { MarkdownPlugin } from './markdown';
export { TemplatePlugin } from './template';
export { DevServerPlugin } from './devserver';
