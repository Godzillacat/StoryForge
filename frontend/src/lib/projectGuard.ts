/**
 * 切换项目前的守卫：页面可以登记一个「还能不能走」的判断（例如写作台有未保存的修改）。
 * 项目选择器在真正切换前问一次；没人登记就放行。
 *
 * 为什么需要：切项目的入口从各页收进了外壳，原来写作台自己的未保存确认会因此消失，
 * 而它保护的是作者刚敲进去的字。
 */
type Guard = () => boolean

let guard: Guard | null = null

export function setProjectGuard(next: Guard | null): void {
  guard = next
}

export function runProjectGuard(): boolean {
  return guard ? guard() : true
}
