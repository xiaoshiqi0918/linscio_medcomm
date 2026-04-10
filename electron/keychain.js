/**
 * Keychain 安全存储 - MedComm v3 规范
 * "LinScio MedComm"        / access_token  → 软件 access_token（64 位 hex，激活后下发）
 * "LinScio MedComm"        / user@email.com → 门户 token（兼容）
 * "LinScio MedComm - Keys" / openai         → OpenAI API Key
 * "LinScio MedComm - Keys" / dashscope      → 绘图 LLM / 通义万相 API Key
 * "LinScio MedComm - Keys" / siliconflow    → 硅基流动 API Key
 * "LinScio MedComm - Keys" / deepseek       → DeepSeek API Key
 * "LinScio MedComm - Keys" / zhipu          → 智谱 API Key
 * "LinScio MedComm - Keys" / moonshot       → 月之暗面 API Key
 * "LinScio MedComm - Keys" / google_ai      → Google AI API Key
 * "LinScio MedComm - Keys" / baidu          → 文心图像 API Key
 * "LinScio MedComm - Keys" / baidu_secret   → 文心图像 Secret Key
 * "LinScio MedComm - Keys" / openrouter     → OpenRouter API Key
 * "LinScio MedComm - Keys" / qiniu_maas     → 七牛 MaaS API Key
 * "LinScio MedComm - Keys" / pollinations   → Pollinations API Key
 * "LinScio MedComm - Keys" / comfy_cloud    → Comfy Cloud API Key（platform.comfy.org）
 * "LinScio MedComm - Keys" / deepl          → DeepL 翻译 API Key
 * "LinScio MedComm - Keys" / google_translate → Google Cloud Translation API Key
 * "LinScio MedComm - Keys" / azure_translate  → Azure Translator API Key
 * "LinScio MedComm - Keys" / azure_translate_region → Azure Translator Region
 * 若 keytar 不可用则降级为内存缓存（仅当前会话）
 */
const SERVICE_PORTAL = 'LinScio MedComm'
const SERVICE_KEYS = 'LinScio MedComm - Keys'
const LEGACY_SERVICE = 'com.linscio.medcomm'
const fs = require('fs')
const path = require('path')
const os = require('os')

const LEGACY_TO_ACCOUNT = {
  OPENAI_API_KEY: 'openai',
  ANTHROPIC_API_KEY: 'anthropic',
  USER_TOKEN: 'user@email.com',
  AUTH_TOKEN: 'user@email.com',
}

const ACCOUNT_TO_ENV = {
  openai: 'OPENAI_API_KEY',
  dashscope: 'DASHSCOPE_API_KEY',
  siliconflow: 'SILICONFLOW_API_KEY',
  deepseek: 'DEEPSEEK_API_KEY',
  zhipu: 'ZHIPU_API_KEY',
  moonshot: 'MOONSHOT_API_KEY',
  google_ai: 'GOOGLE_API_KEY',
  baidu: 'BAIDU_API_KEY',
  baidu_secret: 'BAIDU_SECRET_KEY',
  openrouter: 'OPENROUTER_API_KEY',
  qiniu_maas: 'QINIU_MAAS_API_KEY',
  anthropic: 'ANTHROPIC_API_KEY',
  pollinations: 'POLLINATIONS_API_KEY',
  comfy_cloud: 'COMFY_CLOUD_API_KEY',
  deepl: 'DEEPL_API_KEY',
  google_translate: 'GOOGLE_TRANSLATE_API_KEY',
  azure_translate: 'AZURE_TRANSLATE_KEY',
  azure_translate_region: 'AZURE_TRANSLATE_REGION',
}

const ENV_TO_ACCOUNT = Object.fromEntries(
  Object.entries(ACCOUNT_TO_ENV).map(([k, v]) => [v, k])
)

let keytar = null
const memoryFallback = new Map() // { service: { account: value } }
const FALLBACK_STORE_PATH = path.join(os.homedir(), '.linscio-medcomm-keys.json')

try {
  keytar = require('keytar')
} catch (e) {
  console.warn('[MedComm] keytar not available, using memory fallback')
}

function loadFallbackStore() {
  try {
    if (!fs.existsSync(FALLBACK_STORE_PATH)) return {}
    const raw = fs.readFileSync(FALLBACK_STORE_PATH, 'utf-8')
    return JSON.parse(raw || '{}') || {}
  } catch {
    return {}
  }
}

function saveFallbackStore(store) {
  try {
    fs.writeFileSync(FALLBACK_STORE_PATH, JSON.stringify(store, null, 2), { mode: 0o600 })
  } catch (e) {
    console.warn('[MedComm] fallback store write failed:', e.message)
  }
}

function normalizeAccount(account) {
  if (ENV_TO_ACCOUNT[account]) return ENV_TO_ACCOUNT[account]
  return account
}

function getServiceForAccount(account) {
  const a = normalizeAccount(account)
  if (a === 'access_token' || a === 'user@email.com') return SERVICE_PORTAL
  if (ACCOUNT_TO_ENV[a]) return SERVICE_KEYS
  return SERVICE_KEYS
}

async function getPassword(account) {
  const a = normalizeAccount(account)
  const service = getServiceForAccount(account)
  if (keytar) {
    try {
      let val = await keytar.getPassword(service, a)
      if (!val && ACCOUNT_TO_ENV[a]) {
        const legacyKey = ACCOUNT_TO_ENV[a]
        val = await keytar.getPassword(LEGACY_SERVICE, legacyKey)
        if (val) await setPassword(a, val)
      }
      if (val) return val
    } catch (e) {
      console.warn('[MedComm] keytar get failed:', e.message)
    }
  }
  const key = `${service}:${a}`
  if (memoryFallback.has(key)) return memoryFallback.get(key) || null
  const store = loadFallbackStore()
  const v = store[key] || null
  if (v) memoryFallback.set(key, v)
  return v
}

async function setPassword(account, password) {
  const a = normalizeAccount(account)
  const service = getServiceForAccount(account)
  if (keytar) {
    try {
      await keytar.setPassword(service, a, password)
      memoryFallback.set(`${service}:${a}`, password)
      return true
    } catch (e) {
      console.warn('[MedComm] keytar set failed:', e.message)
    }
  }
  const key = `${service}:${a}`
  memoryFallback.set(key, password)
  const store = loadFallbackStore()
  store[key] = password
  saveFallbackStore(store)
  return true
}

async function deletePassword(account) {
  const a = normalizeAccount(account)
  const service = getServiceForAccount(account)
  if (keytar) {
    try {
      return await keytar.deletePassword(service, a)
    } catch (e) {
      console.warn('[MedComm] keytar delete failed:', e.message)
    }
  }
  const key = `${service}:${a}`
  memoryFallback.delete(key)
  const store = loadFallbackStore()
  delete store[key]
  saveFallbackStore(store)
  return true
}

async function migrateFromLegacy() {
  if (!keytar) return
  try {
    for (const [legacy, account] of Object.entries(LEGACY_TO_ACCOUNT)) {
      const val = await keytar.getPassword(LEGACY_SERVICE, legacy)
      if (val) {
        await setPassword(account, val)
        await keytar.deletePassword(LEGACY_SERVICE, legacy)
      }
    }
  } catch (e) {
    console.warn('[MedComm] legacy keychain migration skipped:', e.message)
  }
}

/** 获取所有 API Keys，按 env 变量名注入到 Python 子进程 */
async function getApiKeysForBackend() {
  await migrateFromLegacy()
  const env = {}
  for (const [account, envKey] of Object.entries(ACCOUNT_TO_ENV)) {
    const val = await getPassword(account)
    if (val) env[envKey] = val
  }
  const portalToken = await getPassword('user@email.com')
  if (portalToken) {
    env.USER_TOKEN = portalToken
    env.AUTH_TOKEN = portalToken
  }
  return env
}

module.exports = {
  getPassword,
  setPassword,
  deletePassword,
  getApiKeysForBackend,
  ACCOUNT_TO_ENV,
  SERVICE_PORTAL,
  SERVICE_KEYS,
}
