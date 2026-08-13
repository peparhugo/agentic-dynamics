import { build } from '../src/build';

jest.mock('../src/build');

import { createProgram } from '../src/cli';

const mockedBuild = build as jest.MockedFunction<typeof build>;

describe('cli', () => {
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    mockedBuild.mockReset();
    mockedBuild.mockReturnValue({ pages: [], outputDir: '/resolved/dist' });
    logSpy = jest.spyOn(console, 'log').mockImplementation(() => undefined);
  });

  afterEach(() => {
    logSpy.mockRestore();
  });

  it('defaults to ./content and ./dist when no options are given', () => {
    createProgram().parse(['node', 'ssg', 'build']);

    expect(mockedBuild).toHaveBeenCalledWith({ contentDir: './content', outputDir: './dist' });
  });

  it('passes through custom --content and --output options', () => {
    createProgram().parse([
      'node',
      'ssg',
      'build',
      '--content',
      './my-content',
      '--output',
      './public',
    ]);

    expect(mockedBuild).toHaveBeenCalledWith({
      contentDir: './my-content',
      outputDir: './public',
    });
  });

  it('logs a summary after a successful build', () => {
    mockedBuild.mockReturnValue({ pages: [{} as any, {} as any], outputDir: '/resolved/dist' });

    createProgram().parse(['node', 'ssg', 'build']);

    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining('Built 2 page(s)'));
  });
});
