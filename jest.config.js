module.exports = {
  testEnvironment: 'node',
  roots: ['<rootDir>/tests/js'],
  testMatch: ['**/*.test.js'],
  verbose: true,
  collectCoverageFrom: [
    'vibe/cli/web_ui/static/js/**/*.js',
    '!**/node_modules/**',
  ],
};
