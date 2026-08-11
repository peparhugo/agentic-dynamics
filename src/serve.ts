import { SSGEngine } from './ssg';
import { DevServerPlugin, DevServerOptions, ServeInstance } from './plugins/dev-server-plugin';

export { ServeInstance };

export interface ServeOptions extends DevServerOptions {}

export function serve(options: ServeOptions): ServeInstance {
  const { contentDir, outputDir, templateDir } = options;

  const engine = new SSGEngine({ contentDir, outputDir, templateDir });
  engine.build();

  const devServer = new DevServerPlugin();
  devServer.setEngine(engine);
  return devServer.start(options);
}
