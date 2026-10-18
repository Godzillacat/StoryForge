interface Props {
  title: string
  value: string
  onChange: (value: string) => void
  disabled: boolean
  placeholder: string
}

export default function SceneTextView({
  title,
  value,
  onChange,
  disabled,
  placeholder,
}: Props) {
  const chars = value.replace(/\s/g, '').length
  return (
    <label className="block space-y-1">
      <span className="text-xs text-slate-500">
        {title} · {chars ? `${chars} 字` : '空'}
      </span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        rows={18}
        placeholder={placeholder}
        className="w-full resize-y rounded border border-slate-700 bg-slate-950 p-3 font-mono text-sm leading-7 text-slate-100 outline-none focus:border-indigo-500 disabled:opacity-60"
      />
    </label>
  )
}
