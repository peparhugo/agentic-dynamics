import { generateSite } from '../generator';
import { Plugin, PluginContext } from '../plugin';

export class TemplatePlugin implements Plugin {
  name = 'template';

  afterBuild(context: PluginContext): void {
    generateSite(
      context.pages,
      context.options.output,
      context.options.templates
    );
  }
}
