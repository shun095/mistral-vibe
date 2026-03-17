module.exports = {
  testEnvironment: 'node',
  roots: ['<rootDir>/tests/js'],
  testMatch: ['**/*.test.js'],
  verbose: true,
  transform: {
    '^.+\\.jsx?$': 'babel-jest',
  },
  collectCoverageFrom: [
    'vibe/cli/web_ui/static/js/**/*.js',
    '!**/node_modules/**',
  ],
};
