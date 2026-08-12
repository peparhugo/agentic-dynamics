import { Plugin } from "./src/plugin";
import { createMarkdownPlugin } from "./src/plugins/markdown";
import { createTemplatePlugin } from "./src/plugins/template";
import { createDevServerPlugin } from "./src/plugins/dev-server";

const plugins: Plugin[] = [
  createMarkdownPlugin(),
  createTemplatePlugin(),
  createDevServerPlugin(),
];

export default { plugins };
