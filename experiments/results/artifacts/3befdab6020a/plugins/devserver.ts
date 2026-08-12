import { Plugin, BuildContext } from '../src/plugin';
import { createServer } from '../src/server';

export const DevServerPlugin: Plugin = {
  name: 'devserver',

  async onStart(context: BuildContext): Promise<void> {
    const server = createServer({
      content: context.contentDir,
      output: context.outputDir,
      templates: context.templatesDir,
      port: context.port || 3000,
    });

    await new Promise<void>((resolve, reject) => {
      server.on('error', reject);
      server.listen(context.port || 3000, () => {
        console.log(`Dev server running at http://localhost:${context.port || 3000}`);
        resolve();
      });
    });

    context.server = server;
  },
};
