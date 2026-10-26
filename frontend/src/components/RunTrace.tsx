import { costLabel, durationLabel, tokensLabel } from '../lib/format'
import type { RunView } from '../api/client'
import { Card } from '../ui/Card'

export default function RunTrace({ run }: { run: RunView }) {
  const estimated = run.usage_source !== 'provider'
  return (
    <Card className="space-y-3 text-[13.5px]">
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-muted">
        <span>模型：{run.model || '未指定'}</span>
        <span>
          {tokensLabel(run.prompt_tokens, run.completion_tokens)}
          {estimated && <span className="ml-1 text-warn">（估算）</span>}
        </span>
        <span>{costLabel(run.cost_estimate)}</span>
        <span>{durationLabel(run.duration_ms)}</span>
        <span>状态：{run.status}</span>
      </div>

      {estimated && run.status !== 'error' && (
        <p className="text-[11.5px] text-warn">
          服务商没有返回用量，这两个 token 数是本地估算的，费用也按它算出来。
        </p>
      )}

      {Object.keys(run.trimmed ?? {}).length > 0 && (
        <div className="rounded-control bg-warn-soft p-2 text-warn">
          这次砍掉了：
          {Object.entries(run.trimmed).map(([slot, action]) => (
            <span key={slot} className="ml-2">
              {slot}（{action}）
            </span>
          ))}
        </div>
      )}

      {run.error && (
        <div className="border-l-2 border-danger py-1 pl-2 text-danger">
          {run.error.kind}：{run.error.message}
        </div>
      )}

      {run.parse_error && (
        <div className="rounded-control bg-warn-soft p-2 text-warn">未结构化：{run.parse_error}</div>
      )}

      <details open>
        <summary className="cursor-pointer text-ink-2">渲染后的完整提示词</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded-control bg-sunken p-3 text-[11.5px]">{run.rendered_prompt}</pre>
      </details>

      <details>
        <summary className="cursor-pointer text-ink-2">实际发出的参数</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded-control bg-sunken p-3 text-[11.5px]">
          {JSON.stringify(run.params ?? {}, null, 2)}
        </pre>
      </details>

      <details>
        <summary className="cursor-pointer text-ink-2">原始返回</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded-control bg-sunken p-3 text-[11.5px]">{run.raw_output}</pre>
      </details>

      <details>
        <summary className="cursor-pointer text-ink-2">解析结果</summary>
        <pre className="mt-2 whitespace-pre-wrap rounded-control bg-sunken p-3 text-[11.5px]">
          {run.structured ? JSON.stringify(run.parsed_json, null, 2) : '未结构化'}
        </pre>
      </details>
    </Card>
  )
}
