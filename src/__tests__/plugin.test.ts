import { PluginPipeline, runHook } from '../plugin';
import type { Page } from '../types';
import type { Plugin, PluginContext } from '../plugin';

function makeContext(): PluginContext {
  return { options: { contentDir: 'content', outputDir: 'dist' }, pages: [], outputs: {} };
}

function makePage(slug: string): Page {
  return {
    slug,
    sourcePath: `${slug}.md`,
    outputName: `${slug}.html`,
    title: slug,
    tags: [],
    html: '',
    content: '',
    raw: '',
    data: { title: slug },
  };
}

describe('runHook', () => {
  it('runs a hook across every plugin in registration order', () => {
    const events: string[] = [];
    const first: Plugin = { name: 'first', onStart: () => events.push('first') };
    const second: Plugin = { name: 'second', onStart: () => events.push('second') };
    const third: Plugin = { name: 'third', onStart: () => events.push('third') };

    runHook([first, second, third], 'onStart', makeContext());

    expect(events).toEqual(['first', 'second', 'third']);
  });

  it('ignores plugins that do not implement the hook', () => {
    const events: string[] = [];
    const withStart: Plugin = { name: 'a', onStart: () => events.push('a') };
    const without: Plugin = { name: 'b', afterBuild: () => events.push('b') };

    runHook([withStart, without], 'onStart', makeContext());

    expect(events).toEqual(['a']);
  });

  it('passes the page argument to onFile hooks', () => {
    const seen: string[] = [];
    const plugin: Plugin = {
      name: 'p',
      onFile: (page) => {
        seen.push(page.slug);
      },
    };

    runHook([plugin], 'onFile', makePage('x'), makeContext());

    expect(seen).toEqual(['x']);
  });
});

describe('PluginPipeline', () => {
  it('runs every lifecycle hook in order', () => {
    const order: string[] = [];
    const plugin: Plugin = {
      name: 'p',
      onStart: () => order.push('onStart'),
      beforeBuild: () => order.push('beforeBuild'),
      afterBuild: () => order.push('afterBuild'),
      onFile: () => order.push('onFile'),
      onEnd: () => order.push('onEnd'),
    };

    const pipeline = new PluginPipeline([plugin]);
    const context = makeContext();

    pipeline.onStart(context);
    pipeline.beforeBuild(context);
    pipeline.onFile(makePage('x'), context);
    pipeline.afterBuild(context);
    pipeline.onEnd(context);

    expect(order).toEqual(['onStart', 'beforeBuild', 'onFile', 'afterBuild', 'onEnd']);
  });

  it('runs each hook across all plugins before the next hook', () => {
    const events: string[] = [];
    const make = (name: string): Plugin => ({
      name,
      beforeBuild: () => events.push(`${name}:beforeBuild`),
      afterBuild: () => events.push(`${name}:afterBuild`),
    });

    const pipeline = new PluginPipeline([make('a'), make('b')]);
    const context = makeContext();

    pipeline.beforeBuild(context);
    pipeline.afterBuild(context);

    expect(events).toEqual([
      'a:beforeBuild',
      'b:beforeBuild',
      'a:afterBuild',
      'b:afterBuild',
    ]);
  });

  it('exposes the registered plugins', () => {
    const plugins: Plugin[] = [{ name: 'a' }, { name: 'b' }];
    expect(new PluginPipeline(plugins).plugins).toEqual(plugins);
  });
});
