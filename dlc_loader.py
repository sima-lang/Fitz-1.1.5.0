"""
dlc_loader.py — Загрузчик DLC.
Ищет плагины внутри папки dlc/ и во внешней папке на рабочем столе.
"""
import os
import sys
import importlib
import traceback

# Пути для поиска DLC
DLC_DIRS = [
    "dlc",
]

def load_dlcs():
    handlers = []

    for dlc_dir in DLC_DIRS:
        if not os.path.isdir(dlc_dir):
            continue

        # Добавляем родительскую папку в sys.path, чтобы работали относительные импорты
        parent_dir = os.path.dirname(os.path.abspath(dlc_dir))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        # Если это папка с самим DLC (а не контейнер)
        init_file = os.path.join(dlc_dir, "__init__.py")
        if os.path.exists(init_file):
            module_name = os.path.basename(dlc_dir)
            try:
                # Пытаемся импортировать как пакет
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                module = importlib.import_module(module_name)
                
                dlc_title = getattr(module, "DLC_NAME", module_name)
                
                if hasattr(module, "register"):
                    result = module.register()
                    if result:
                        handlers.extend(result)
                        print(f"😈 DLC загружен: {dlc_title}")
                elif hasattr(module, "handle"):
                    handlers.append(module.handle)
                    print(f"😈 DLC загружен: {dlc_title}")
            except Exception as e:
                print(f"⚠️ DLC {dlc_dir} не загружен: {e}")
                traceback.print_exc()
            continue

        # Если это контейнер с несколькими DLC (как папка dlc/)
        for name in sorted(os.listdir(dlc_dir)):
            path = os.path.join(dlc_dir, name)
            if not os.path.isdir(path) or name.startswith("_"):
                continue
            init_file = os.path.join(path, "__init__.py")
            if not os.path.exists(init_file):
                continue
            try:
                if name in sys.modules:
                    del sys.modules[name]
                
                module = importlib.import_module(name)
                
                dlc_title = getattr(module, "DLC_NAME", name)
                if hasattr(module, "register"):
                    result = module.register()
                    if result:
                        handlers.extend(result)
                        print(f"😈 DLC загружен: {dlc_title}")
                elif hasattr(module, "handle"):
                    handlers.append(module.handle)
                    print(f"😈 DLC загружен: {dlc_title}")
            except Exception as e:
                print(f"⚠️ DLC '{name}' не загружен: {e}")
                traceback.print_exc()

    return handlers