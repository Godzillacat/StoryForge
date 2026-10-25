/** @type {import('tailwindcss').Config} */
// 颜色值必须与 `src/ui/palette.ts` 完全一致 —— `src/ui/palette.test.ts` 会逐个断言。
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: '#F4F1EA',
        surface: '#FBF9F5',
        sunken: '#ECE7DC',
        ink: '#23201C',
        'ink-2': '#4E4941',
        muted: '#6E6A61',
        faint: '#8D8679',
        line: '#E3DDD0',
        'line-strong': '#CFC7B6',
        accent: '#2F5D4E',
        'accent-ink': '#24483C',
        'accent-soft': '#E6EFE9',
        warn: '#8A5C16',
        'warn-soft': '#F6ECD8',
        danger: '#9B3B32',
      },
      fontFamily: {
        ui: ['"Microsoft YaHei UI"', '"Segoe UI"', 'system-ui', 'sans-serif'],
        serif: ['STSong', '"Songti SC"', 'SimSun', 'Georgia', 'serif'],
      },
      borderRadius: {
        tag: '4px',
        control: '6px',
        card: '8px',
        overlay: '10px',
      },
      boxShadow: {
        overlay: '0 10px 30px rgba(35,32,28,.10), 0 1px 2px rgba(35,32,28,.06)',
      },
    },
  },
  plugins: [],
}
