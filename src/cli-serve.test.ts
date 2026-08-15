import { ServeOptions } from './serve';

const startDevServer = jest.fn();

jest.mock('./serve', () => ({
  startDevServer: (...args: unknown[]) => startDevServer(...args),
}));

describe('ssg serve CLI', () => {
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.resetModules();
    startDevServer.mockReset();
    startDevServer.mockResolvedValue({
      url: 'http://localhost:4000',
      port: 4000,
      close: jest.fn().mockResolvedValue(undefined),
    });
    logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    logSpy.mockRestore();
  });

  it('starts the dev server with parsed options, including a custom --port', async () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { run } = require('./cli');

    run(['node', 'ssg', 'serve', '--content', './my-content', '--output', './my-dist', '--port', '4000']);

    await new Promise((resolve) => setImmediate(resolve));

    expect(startDevServer).toHaveBeenCalledWith(
      expect.objectContaining({
        contentDir: './my-content',
        outputDir: './my-dist',
        port: 4000,
      } as Partial<ServeOptions>)
    );
    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('http://localhost:4000'));
  });

  it('defaults to port 3000 when --port is not provided', async () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { run } = require('./cli');

    run(['node', 'ssg', 'serve']);

    await new Promise((resolve) => setImmediate(resolve));

    expect(startDevServer).toHaveBeenCalledWith(expect.objectContaining({ port: 3000 }));
  });
});
