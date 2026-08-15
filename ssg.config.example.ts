import { SSGConfig } from './src/config';
import { MarkdownPlugin } from './src/plugins/markdown.plugin';
import { TemplatePlugin } from './src/plugins/template.plugin';

const config: SSGConfig = {
  contentDir: './content',
  outputDir: './dist',
  templateDir: './templates',
  plugins: [
    MarkdownPlugin,
    TemplatePlugin,
  ]
};

export default config;
