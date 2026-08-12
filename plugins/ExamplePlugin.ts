import type { Page, Plugin, PluginContext } from '../src/types';

export default class ExamplePlugin implements Plugin {
  readonly name = 'example';

  onStart(ctx: PluginContext): void {
    ctx.output.started = true;
  }

  beforeBuild(_ctx: PluginContext): void {}

  afterBuild(_ctx: PluginContext): void {}

  onFile(_page: Page, _ctx: PluginContext): void {}

  onEnd(ctx: PluginContext): void {
    ctx.output.ended = true;
  }
}
