/**
 * 学科包云端下载已下线；请在「设置」中上传 ZIP，由本地后端 /api/v1/specialty/import-local 安装。
 * 保留占位导出，避免旧引用崩溃。
 */
const path = require('path')
const { app } = require('electron')

function getPacksDir() {
  const root = process.env.LINSCIO_APP_DATA || path.join(app.getPath('userData'), 'data')
  return path.join(root, 'specialty-packs')
}

async function installSpecialtyPack() {
  throw new Error('云端学科包下载已关闭，请在「设置」中上传 ZIP 文件安装')
}

module.exports = { installSpecialtyPack, getPacksDir }
