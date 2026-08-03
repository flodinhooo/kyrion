export function csrfHeader(): Record<string, string> {
  const token = document.cookie.split("; ").find((item) => item.startsWith("kyrion_csrf="))?.split("=")[1];
  return token ? { "X-Kyrion-CSRF": decodeURIComponent(token) } : {};
}
