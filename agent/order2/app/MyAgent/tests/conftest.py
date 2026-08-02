"""テスト用の共通設定。

tools.py からのインポートを可能にするためにパスを設定する。
"""

import sys
import os

# 親ディレクトリ（MyAgent）をパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
