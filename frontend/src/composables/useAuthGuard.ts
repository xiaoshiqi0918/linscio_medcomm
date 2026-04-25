import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { getAuthToken } from '@/api'
import { ElMessageBox } from 'element-plus'

export function useAuthGuard() {
  const router = useRouter()
  const isLoggedIn = computed(() => !!getAuthToken())

  async function requireAuth(actionLabel = '此操作'): Promise<boolean> {
    if (isLoggedIn.value) return true

    try {
      await ElMessageBox.confirm(
        `${actionLabel}需要登录账号后才能使用，是否前往登录？`,
        '请先登录',
        {
          confirmButtonText: '去登录',
          cancelButtonText: '取消',
          type: 'info',
        }
      )
      const redirect = router.currentRoute.value.fullPath
      router.push({ name: 'login', query: { redirect } })
    } catch {
      // user cancelled
    }
    return false
  }

  return { isLoggedIn, requireAuth }
}
