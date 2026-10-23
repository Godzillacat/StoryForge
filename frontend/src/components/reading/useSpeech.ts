import { useCallback, useEffect, useRef, useState } from 'react'

/** 系统 TTS（D-17）：零依赖、离线、零成本。
 *
 * **按段落排队**，不拼成一整条 —— 单条长 utterance 在很多系统上会中途断掉，
 * 也没法可靠地暂停与继续。排队还能让界面知道「现在读到第几段」。
 *
 * **先探测有没有可用语音再决定按钮能不能点。** 探测不到就明说，不假装在读。
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
  chunksRef.current = chunks
  const indexRef = useRef(-1)
  const stoppedRef = useRef(true)

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
    stoppedRef.current = true
    indexRef.current = -1
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
      const list = chunksRef.current
      if (start < 0 || start >= list.length) return
      const synth = window.speechSynthesis
      synth.cancel()
      stoppedRef.current = false
      indexRef.current = start

      const speakAt = (at: number) => {
        if (stoppedRef.current || at >= chunksRef.current.length) {
          if (!stoppedRef.current) {
            setState((current) => ({ ...current, speaking: false, paused: false, index: -1 }))
          }
          return
        }
        const utterance = new SpeechSynthesisUtterance(chunksRef.current[at])
        utterance.lang = 'zh-CN'
        utterance.onend = () => {
          if (stoppedRef.current) return
          indexRef.current = at + 1
          speakAt(at + 1)
        }
        utterance.onerror = () => {
          if (stoppedRef.current) return
          setState((current) => ({ ...current, speaking: false, paused: false, index: -1 }))
        }
        indexRef.current = at
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

  // 离开页面时停下：不然切走还在念。
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  return { state, speakFrom, pause, resume, stop }
}
