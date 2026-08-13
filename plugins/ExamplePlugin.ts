import type { Plugin, PluginContext } from '../src/plugin';

export class ExamplePlugin implements Plugin {
  readonly name = 'example';

  beforeBuild(ctx: PluginContext): void {
    ctx.log ??= [];
    (ctx.log as string[]).push('example:beforeBuild');
  }

  afterBuild(ctx: PluginContext): void {
    ctx.log ??= [];
    (ctx.log as string[]).push('example:afterBuild');
  }
}
