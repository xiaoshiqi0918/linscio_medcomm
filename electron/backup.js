/**
 * 数据备份：DB + images/ + uploads/ → .linscio-backup zip
 * 策略：每小时(仅DB) / 每日(完整) / 迁移前(自动) / 手动
 */
const AdmZip = require('adm-zip')
const fs = require('fs')
const path = require('path')

let appDataRoot = ''
let lastHourlyBackup = 0
let lastDailyBackup = 0

function setAppDataRoot(root) {
  appDataRoot = root
}

function getBackupsDir() {
  return path.join(appDataRoot, 'backups')
}

function ensureBackupsDir() {
  const dir = getBackupsDir()
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  return dir
}

/** 仅备份 DB */
function backupDbOnly() {
  ensureBackupsDir()
  const dbPath = path.join(appDataRoot, 'medcomm.db')
  if (!fs.existsSync(dbPath)) return { ok: false, error: 'DB not found' }
  const stamp = Math.floor(Date.now() / 1000)
  const dest = path.join(getBackupsDir(), `db_${stamp}.linscio-backup`)
  fs.copyFileSync(dbPath, dest)
  lastHourlyBackup = Date.now()
  return { ok: true, path: dest }
}

/** 完整备份：DB + images/ + uploads/ → zip */
function backupFull() {
  ensureBackupsDir()
  const stamp = Math.floor(Date.now() / 1000)
  const zipPath = path.join(getBackupsDir(), `full_${stamp}.linscio-backup`)
  const zip = new AdmZip()

  const dbPath = path.join(appDataRoot, 'medcomm.db')
  if (fs.existsSync(dbPath)) zip.addLocalFile(dbPath, '', 'medcomm.db')

  const imagesDir = path.join(appDataRoot, 'images')
  if (fs.existsSync(imagesDir)) zip.addLocalFolder(imagesDir, 'images')

  const uploadsDir = path.join(appDataRoot, 'uploads')
  if (fs.existsSync(uploadsDir)) zip.addLocalFolder(uploadsDir, 'uploads')

  zip.writeZip(zipPath)
  lastDailyBackup = Date.now()
  return { ok: true, path: zipPath }
}

/** 迁移前备份（由 migration 调用） */
function backupBeforeMigration() {
  const dbPath = path.join(appDataRoot, 'medcomm.db')
  if (!fs.existsSync(dbPath)) return null
  ensureBackupsDir()
  const stamp = Math.floor(Date.now() / 1000)
  const dest = path.join(getBackupsDir(), `pre_migration_${stamp}.linscio-backup`)
  fs.copyFileSync(dbPath, dest)
  return dest
}

/** 定时策略：每小时仅 DB，每日完整 */
function runScheduledBackup() {
  const now = Date.now()
  const oneHour = 60 * 60 * 1000
  const oneDay = 24 * oneHour

  if (now - lastHourlyBackup >= oneHour) backupDbOnly()
  if (now - lastDailyBackup >= oneDay) backupFull()
}

/** 从 zip 恢复；strategy: 'overwrite' | 'missing_only' | 'cancel' */
function restoreFromZip(zipPath, strategy = 'overwrite') {
  if (strategy === 'cancel') return { ok: false, cancelled: true }

  try {
    const zip = new AdmZip(zipPath)
    const entries = zip.getEntries()

    for (const entry of entries) {
      const destPath = path.join(appDataRoot, entry.entryName)
      if (entry.isDirectory) {
        fs.mkdirSync(destPath, { recursive: true })
        continue
      }
      if (strategy === 'missing_only' && fs.existsSync(destPath)) continue
      fs.mkdirSync(path.dirname(destPath), { recursive: true })
      zip.extractEntryTo(entry, appDataRoot, true, strategy === 'overwrite')
    }
    return { ok: true }
  } catch (e) {
    return { ok: false, error: e.message }
  }
}

module.exports = {
  setAppDataRoot,
  backupDbOnly,
  backupFull,
  backupBeforeMigration,
  runScheduledBackup,
  restoreFromZip,
  getBackupsDir,
}
