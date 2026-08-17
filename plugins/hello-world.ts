import { Plugin, PluginContext } from '../src/plugin';
import { Page } from '../src/ssg';

export class HelloWorldPlugin implements Plugin {
  name = 'hello-world';

  onStart(context: PluginContext): void {
    context.helloWorld = 0;
  }

  onFile(page: Page, context: PluginContext): Page {
    const count = typeof context.helloWorld === 'number' ? context.helloWorld : 0;
    context.helloWorld = count + 1;
    return page;
  }

  onEnd(context: PluginContext): void {
    console.log(`hello-world plugin processed ${String(context.helloWorld)} page(s)`);
  }
}

export default HelloWorldPlugin;
