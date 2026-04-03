const path = require('path')

/**
 * Replace app.asar with app.asar.unpacked for paths that need
 * real filesystem access (spawn cwd, script paths, etc.)
 */
function resolveUnpacked(p) {
  return p.replace(/app\.asar(?![.])/g, 'app.asar.unpacked')
}

function getBackendDir() {
  return resolveUnpacked(path.join(__dirname, '..', 'backend'))
}

module.exports = { resolveUnpacked, getBackendDir }
