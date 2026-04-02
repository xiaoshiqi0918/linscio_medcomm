/**
 * medcomm-image:// 协议注册
 * 安全访问应用数据目录下的图像文件
 */
const { protocol, net } = require('electron')
const path = require('path')

let appDataRoot = ''

function setAppDataRoot(root) {
  appDataRoot = root
}

function register() {
  protocol.handle('medcomm-image', (request) => {
    const url = request.url.replace(/^medcomm-image:\/\//, '').split('?')[0]
    const decoded = decodeURIComponent(url)
    if (decoded.includes('..') || decoded.startsWith('/')) {
      return new Response('Forbidden', { status: 403 })
    }
    const absolutePath = path.join(appDataRoot, decoded)
    return net.fetch(`file://${absolutePath}`)
  })
}

module.exports = {
  register,
  setAppDataRoot,
}
