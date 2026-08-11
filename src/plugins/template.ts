import { generateSite, GenerateStats } from '../generator';
import { Plugin, PluginContext } from '../plugin';

export class TemplatePlugin implements Plugin {
  name = 'template';

  afterBuild(context: PluginContext): void {
    const genStats: GenerateStats = { built: 0, skipped: 0 };
    const hasCache = context.cache && context.cache.isPopulated();

    generateSite(
      context.pages,
      context.options.output,
      context.options.templates,
      context.cache,
      genStats
    );

    if (context.stats && hasCache) {
      context.stats.pagesBuilt = genStats.built;
      context.stats.pagesSkipped = genStats.skipped;
    } else if (context.stats) {
      context.stats.pagesBuilt = genStats.built;
      context.stats.pagesSkipped = 0;
    }
  }
}
