import { Plugin, PluginContext } from '../src/plugin';
import { Page } from '../src/types';

export interface ExampleOptions {
  enabled?: boolean;
  banner?: string;
}

export class ExamplePlugin implements Plugin {
  name = 'example';

  constructor(private options: ExampleOptions = {}) {}

  onStart(ctx: PluginContext): void {
    if (!this.options.enabled) return;
    console.log('[ssg] example plugin started');
  }

  beforeBuild(ctx: PluginContext): void {
    if (!this.options.enabled) return;
    console.log('[ssg] example plugin: beforeBuild');
  }

  onFile(page: Page, _ctx: PluginContext): Page | void {
    if (!this.options.enabled) return;
    return { ...page };
  }

  afterBuild(ctx: PluginContext): void {
    if (!this.options.enabled) return;
    console.log('[ssg] example plugin: afterBuild');
  }

  onEnd(ctx: PluginContext): void {
    if (!this.options.enabled) return;
    console.log('[ssg] example plugin: onEnd');
  }
}

export default ExamplePlugin;
