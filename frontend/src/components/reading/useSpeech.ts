import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

/** 系统 TTS（D-17）：零依赖、离线、零成本。
 *
 * **按段落排队**，不拼成一整条 —— 单条长 utterance 在很多系统上会中途断掉，
 * 也没法可靠地暂停与继续。排队还能让界面知道「现在读到第几段」。
 *
 * **先探测有没有可用语音再决定按钮能不能点。** 探测不到就明说，不假装在读。
 *
 * 队列用**代际序号**而不是布尔开关：`cancel()` 会让被取消的那条 utterance
 * 照样触发 `onend`，它如果只看一个布尔值，就会接着念下一段 —— 换了章、离开
 * 了页面都还在念。每条 utterance 记住自己属于哪一代，代际变了就闭麦。
 */

export interface SpeechState {
  supported: boolean
  /** 有可用语音才算真的能读：某些环境 `speechSynthesis` 存在但一个语音都没有。 */
  ready: boolean
  speaking: boolean
  paused: boolean
  /** 正在读第几段（在 `chunks` 里的下标）；没在读时为 -1。 */
  index: number
}

export function useSpeech(chunks: string[]) {
  const [state, setState] = useState<SpeechState>({
    supported: typeof window !== 'undefined' && 'speechSynthesis' in window,
    ready: false,
    speaking: false,
    paused: false,
    index: -1,
  })
  // 队列在 ref 里：utterance 的回调是异步的，从 state 读会读到旧值。
  const chunksRef = useRef(chunks)
  // 在 layout effect 里同步，不在 render 中赋值 —— render 可能被丢弃，
  // 那样 ref 就会停在一份从没提交过的 chunks 上。
  useLayoutEffect(() => {
    chunksRef.current = chunks
  }, [chunks])
  // 代际：每次开念或停止都递增。旧代际的回调一律不再出声。
  const generationRef = useRef(0)

  useEffect(() => {
    if (!state.supported) return
    const synth = window.speechSynthesis
    const probe = () => {
      setState((current) => ({ ...current, ready: synth.getVoices().length > 0 }))
    }
    probe()
    // Chromium 系在页面刚加载时 `getVoices()` 常返回空，稍后才填好并触发这个事件。
    synth.addEventListener?.('voiceschanged', probe)
    return () => synth.removeEventListener?.('voiceschanged', probe)
  }, [state.supported])

  const stop = useCallback(() => {
    if (!state.supported) return
    // 先换代际再 cancel：cancel 触发的 onend 会看到新代际，不会再排下一段。
    generationRef.current += 1
    window.speechSynthesis.cancel()
    setState((current) => ({
      ...current,
      speaking: false,
      paused: false,
      index: -1,
    }))
  }, [state.supported])

  const speakFrom = useCallback(
    (start: number) => {
      if (!state.supported) return
      if (start < 0 || start >= chunksRef.current.length) return
      const synth = window.speechSynthesis
      // 同样先换代际，再 cancel 上一条 —— 顺序反了会让旧的 onend 抢跑。
      const generation = generationRef.current + 1
      generationRef.current = generation
      synth.cancel()

      const speakAt = (at: number) => {
        if (generationRef.current !== generation) return
        if (at >= chunksRef.current.length) {
          setState((current) => ({ ...current, speaking: false, paused: false, index: -1 }))
          return
        }
        const utterance = new SpeechSynthesisUtterance(chunksRef.current[at])
        utterance.lang = 'zh-CN'
        utterance.onend = () => {
          if (generationRef.current !== generation) return
          speakAt(at + 1)
        }
        utterance.onerror = () => {
          if (generationRef.current !== generation) return
          setState((current) => ({ ...current, speaking: false, paused: false, index: -1 }))
        }
        setState((current) => ({ ...current, speaking: true, paused: false, index: at }))
        synth.speak(utterance)
      }

      speakAt(start)
    },
    [state.supported],
  )

  const pause = useCallback(() => {
    if (!state.supported) return
    window.speechSynthesis.pause()
    setState((current) => ({ ...current, paused: true }))
  }, [state.supported])

  const resume = useCallback(() => {
    if (!state.supported) return
    window.speechSynthesis.resume()
    setState((current) => ({ ...current, paused: false }))
  }, [state.supported])

  // 离开页面时停下：不然切走还在念。换代际与 stop() 同理 —— 只 cancel
  // 不换代际，被取消那条的 onend 会接着念下一段。
  useEffect(() => {
    return () => {
      generationRef.current += 1
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  return { state, speakFrom, pause, resume, stop }
}
