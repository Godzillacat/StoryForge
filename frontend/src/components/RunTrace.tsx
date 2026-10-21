import { costLabel, durationLabel, tokensLabel } from '../lib/format'
import type { RunView } from '../api/client'

export default function RunTrace({ run }: { run: RunView }) {
  const estimated = run.usage_source !== 'provider'
  return (
    <div className="space-y-3 rounded border border-slate-800 p-4 text-sm">
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-slate-400">
        <span>模型：{run.model || '未指定'}</span>
        <span>
          {tokensLabel(run.prompt_tokens, run.completion_tokens)}
          {estimated && <span className="ml-1 text-amber-400">（估算）</span>}
        </span>
        <span>{costLabel(run.cost_estimate)}</span>
        <span>{durationLabel(run.duration_ms)}</span>
        <span>状态：{run.status}</span>
      </div>

      {estimated && run.status !== 'error' && (
        <p className="text-xs text-amber-400/80">
          服务商没有返回用量，这两个 token 数是本地估算的，费用也按它算出来。
        </p>
      )}

      {Object.keys(run.trimmed ?? {}).length > 0 && (
        <div className="rounded bg-amber-950/40 p-2 text-amber-300">
          这次砍掉了：
          {Object.entries(run.trimmed).map(([slot, action]) => (
            <span key={slot} className="ml-2">
              {slot}（{action}）
            </span>
          ))}
        </div>
      )}

      {run.error && (
        <div className="rounded bg-red-950/40 p-2 text-red-300">
          {run.error.kind}：{run.error.message}
        </div>
      )}

      {run.parse_error && (
        <div className="rounded bg-amber-950/40 p-2 text-amber-300">未结构化：{run.parse_error}</div>
      )}

      <details open>
        <summary className="cursor-pointer text-slate-300">渲染后的完整提示词</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-900 p-3 text-xs">{run.rendered_prompt}</pre>
      </details>

      <details>
        <summary className="cursor-pointer text-slate-300">实际发出的参数</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-900 p-3 text-xs">
          {JSON.stringify(run.params ?? {}, null, 2)}
        </pre>
      </details>

      <details>
        <summary className="cursor-pointer text-slate-300">原始返回</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-900 p-3 text-xs">{run.raw_output}</pre>
      </details>

      <details>
        <summary className="cursor-pointer text-slate-300">解析结果</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-900 p-3 text-xs">
          {run.structured ? JSON.stringify(run.parsed_json, null, 2) : '未结构化'}
        </pre>
      </details>
    </div>
  )
}
