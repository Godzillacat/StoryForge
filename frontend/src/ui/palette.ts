/**
 * 全站唯一的一组颜色常量。
 *
 * 页面与组件只能引用这里的值（经 Tailwind 令牌类使用），不得写裸十六进制。
 * `contrast.test.ts` 守着浅色底上的对比度，改任何一格都会先变红。
 */
export const PALETTE = {
  paper: '#F4F1EA',
  surface: '#FBF9F5',
  sunken: '#ECE7DC',
  ink: '#23201C',
  ink2: '#4E4941',
  muted: '#6E6A61',
  faint: '#8D8679',
  line: '#E3DDD0',
  lineStrong: '#CFC7B6',
  accent: '#2F5D4E',
  accentInk: '#24483C',
  accentSoft: '#E6EFE9',
  warn: '#8A5C16',
  warnSoft: '#F6ECD8',
  danger: '#9B3B32',
} as const

export type PaletteKey = keyof typeof PALETTE
