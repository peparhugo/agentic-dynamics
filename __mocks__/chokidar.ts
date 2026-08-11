function createWatcher() {
  return {
    on: jest.fn().mockReturnThis(),
    close: jest.fn(),
  };
}

export function watch() {
  return createWatcher();
}
