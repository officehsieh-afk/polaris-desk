"""Polaris Desk — 台股法遵與投研 Agent-Augmented Research Workflow。

保持輕量：不要在這裡 import 需要重相依（langgraph / google 套件）的子模組，
以免 `import polaris` 在尚未安裝完整相依時就掛掉。
"""

__version__ = "0.1.0"
