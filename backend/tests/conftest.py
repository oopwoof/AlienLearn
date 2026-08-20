"""让测试能以顶层模块名导入 backend 下的代码（backend 内部互相 import 就是顶层名）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
