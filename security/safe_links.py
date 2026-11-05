"""
safe_links.py — Проверка ссылок на безопасность (кроссплатформенный).
• Проверяет сокращатели (bit.ly, clck.ru).
• Проверяет опасные расширения (.exe, .bat).
• Проверяет доступность (HTTP-код).
• SSRF-защита: блокирует внутренние/локальные IP-адреса.
"""
import ipaddress
import socket
from urllib.parse import urlparse

from core.logger import get_logger

_log = get_logger("safe_links")

try:
    import requests
except Exception:
    requests = None

# ===== SSRF-ЗАЩИТА: блокируемые сети =====
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("10.0.0.0/8"),         # private
    ipaddress.ip_network("172.16.0.0/12"),      # private
    ipaddress.ip_network("192.168.0.0/16"),     # private
    ipaddress.ip_network("169.254.0.0/16"),     # link-local / AWS IMDS
    ipaddress.ip_network("0.0.0.0/8"),          # "this" network
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
]

_BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]", "0"}


def _is_internal_url(url: str) -> bool:
    """Возвращает True, если URL ведёт во внутреннюю/закрытую сеть."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            # Не можем определить хост — блокируем для безопасности
            return True
        if hostname.lower() in _BLOCKED_HOSTNAMES:
            return True
        # Разрешаем DNS и проверяем IP
        resolved_ip = socket.gethostbyname(hostname)
        addr = ipaddress.ip_address(resolved_ip)
        return any(addr in net for net in _BLOCKED_NETWORKS)
    except Exception as e:
        _log.warning("SSRF-проверка не выполнена для %s: %s", url, e)
        return True


class SafeLinks:
    def __init__(self, config=None):
        self.config = config
        self.dangerous_extensions = [
            ".exe", ".bat", ".cmd", ".vbs", ".scr", ".msi", ".jar",
        ]
        self.suspicious_domains = [
            "bit.ly", "tinyurl.com", "clck.ru", "is.gd", "goo.gl",
            "rb.gy", "mzl.la", "adf.ly", "shorte.st",
        ]

    def check_url(self, url: str) -> str:
        if not url:
            return "❌ Пустая ссылка"
        if not url.startswith("http"):
            url = "https://" + url

        # SSRF-защита: блокируем внутренние адреса
        if _is_internal_url(url):
            return "⛔ Доступ к локальным/внутренним адресам запрещён (SSRF-защита)."

        results = []

        # 1. Сокращатели
        for domain in self.suspicious_domains:
            if domain in url.lower():
                results.append(f"⚠️ Сокращатель ссылок: {domain}")

        # 2. Опасные расширения
        for ext in self.dangerous_extensions:
            if ext in url.lower():
                results.append(f"⚠️ Опасное расширение: {ext}")

        # 3. Доступность
        if requests is not None:
            try:
                r = requests.get(url, timeout=5, allow_redirects=True)
                final_url = r.url

                # Проверяем расширение после редиректа
                for ext in self.dangerous_extensions:
                    if ext in final_url.lower():
                        results.append(f"⚠️ Опасное расширение после редиректа: {ext}")

                # Проверяем, не увёл ли редирект на внутренний адрес
                if _is_internal_url(final_url):
                    results.append("⛔ Редирект ведёт на внутренний адрес (SSRF).")

                if r.status_code == 200:
                    results.append(f"✅ Ссылка доступна (код {r.status_code})")
                else:
                    results.append(f"⚠️ Ссылка недоступна (код {r.status_code})")
            except Exception as e:
                results.append(f"⚠️ Не удалось проверить доступность: {e}")

        return "\n".join(results) if results else "✅ Ссылка безопасна"

    def is_safe_url(self, url: str) -> tuple:
        """Быстрая проверка — безопасно ли."""
        if not url:
            return False, "Пустая ссылка"
        if not url.startswith("http"):
            url = "https://" + url

        # SSRF-защита
        if _is_internal_url(url):
            return False, "Доступ к локальным адресам запрещён (SSRF-защита)"

        for domain in self.suspicious_domains:
            if domain in url.lower():
                return False, f"Сокращатель ссылок: {domain}"

        for ext in self.dangerous_extensions:
            if ext in url.lower():
                return False, f"Опасное расширение: {ext}"

        return True, "Ссылка безопасна"


# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====
_safe_links = None


def get_safe_links(config=None) -> SafeLinks:
    global _safe_links
    if _safe_links is None:
        _safe_links = SafeLinks(config)
    return _safe_links