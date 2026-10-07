const Path = require('path')
module.exports = { configureWebpack: { resolve: { alias: {
  '@Comp': Path.resolve(__dirname + '/src/components'),
} } } }
