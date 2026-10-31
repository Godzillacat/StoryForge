/** 拼接类名：丢掉假值，压缩空白。不引第三方库。 */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts
    .filter(Boolean)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
}
