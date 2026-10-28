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
  return (
    <label className="block space-y-1">
      <span className="text-[11.5px] text-muted">{title}</span>
      {/* 正文按书页排：衬线、17px、行距 1.9，**不做首行缩进**（`text-indent` 在
          textarea 里只缩第一行；写全角空格会污染 Markdown 与导出）—— 缩进只出现
          在阅读器与 EPUB 传统模板里。也**去掉 resize-y**：拖动会破坏行宽与
          diff 的视觉对齐。
          段间距在 `<textarea>` 里做不到（没有逐段的盒模型），行距 1.9 已给出
          段落之间的呼吸；这一点与首行缩进同属 textarea 的限制。 */}
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        rows={18}
        placeholder={placeholder}
        className="w-full rounded-card border border-line-strong bg-surface p-4 font-serif text-[17px] leading-[1.9] text-ink outline-none transition-colors duration-[120ms] placeholder:text-faint focus:border-accent focus:shadow-[0_0_0_3px_var(--accent-soft)] disabled:opacity-60"
      />
    </label>
  )
}
