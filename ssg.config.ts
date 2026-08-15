import { markdownPlugin } from './plugins/markdown-plugin';
import { templatePlugin } from './plugins/template-plugin';
import { SSGConfig } from './src/config';

const config: SSGConfig = {
  plugins: [markdownPlugin(), templatePlugin()],
};

export default config;
