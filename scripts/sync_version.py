import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.version import __version__
pkg = Path(__file__).parent.parent / "package.json"
data = json.loads(pkg.read_text())
data["version"] = __version__
pkg.write_text(json.dumps(data, indent=2, ensure_ascii=False))
print(f"✅ package.json обновлён до {__version__}")
