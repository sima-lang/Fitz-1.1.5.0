"""
ui/theme.py — Цветовые схемы и применение тем.
"""

THEMES = {
    "cyberpunk": {
        "accent": "#00d4ff",
        "bg": "#0a0a0f",
        "chat_bg": "#0d0d1a",
        "bubble_fitz": "#1a1a2e",
        "bubble_user": "#0078d4",
        "border": "#2a2a4e",
        "text": "#e0e0e0",
    },
    "matrix": {
        "accent": "#00ff41",
        "bg": "#050505",
        "chat_bg": "#0a0f0a",
        "bubble_fitz": "#0f1a0f",
        "bubble_user": "#005500",
        "border": "#1a3a1a",
        "text": "#00ff41",
    },
    "strict": {
        "accent": "#cccccc",
        "bg": "#1a1a1a",
        "chat_bg": "#222222",
        "bubble_fitz": "#2a2a2a",
        "bubble_user": "#444444",
        "border": "#444444",
        "text": "#ffffff",
    },
    "night": {
        "accent": "#5555aa",
        "bg": "#050510",
        "chat_bg": "#080812",
        "bubble_fitz": "#12121a",
        "bubble_user": "#333366",
        "border": "#1a1a2e",
        "text": "#a0a0c0",
    },
}

def get_theme(name: str, accent_override: str = None) -> dict:
    """Возвращает словарь цветов для темы."""
    theme = THEMES.get(name, THEMES["cyberpunk"]).copy()
    if accent_override:
        theme["accent"] = accent_override
    return theme