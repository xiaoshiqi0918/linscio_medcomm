/**
 * 轮询保护：按间隔轮询直到完成/失败/超时
 */
export interface PollingGuardOptions<T, S> {
  pollFn: () => Promise<S>
  interval: number
  timeout: number
  isDone: (s: S) => boolean
  isFailed: (s: S) => boolean
  onDone?: (s: S) => void
  onFailed?: (s: S) => void
  onTimeout?: () => void
}

export async function usePollingGuard<T, S>(options: PollingGuardOptions<T, S>): Promise<S | null> {
  const { pollFn, interval, timeout, isDone, isFailed, onDone, onFailed, onTimeout } = options
  const start = Date.now()

  const poll = async (): Promise<S | null> => {
    const elapsed = Date.now() - start
    if (elapsed >= timeout) {
      onTimeout?.()
      return null
    }

    const s = await pollFn()

    if (isDone(s)) {
      onDone?.(s)
      return s
    }
    if (isFailed(s)) {
      onFailed?.(s)
      return s
    }

    await new Promise((r) => setTimeout(r, interval))
    return poll()
  }

  return poll()
}
