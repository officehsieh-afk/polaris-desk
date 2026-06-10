"""訂閱過濾（specs/002 / FR-NC-006）。

Phase 1 為單一全域設定（單人情境，PRD OQ-3 暫緩多帳號）。
規則順序見 data-model.md：alert 恆放行 → 類型開關 → watchlist。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polaris.notifications.model import Notification, NotificationType


class Subscription(BaseModel):
    """使用者的追蹤清單與類型開關。

    - ``tickers``：None = 全收（預設、不漏報）；空集合 = 全擋（除 alert）。
    - ``muted_types``：被關閉的通知類型。
    """

    model_config = ConfigDict(frozen=True)

    tickers: frozenset[str] | None = Field(default=None)
    muted_types: frozenset[NotificationType] = Field(default_factory=frozenset)

    def allows(self, notification: Notification) -> bool:
        # 1. 安全攸關通知不可被靜音。
        if notification.severity == "alert":
            return True
        # 2. 類型開關。
        if notification.type in self.muted_types:
            return False
        # 3. watchlist；ticker=None 的系統級通知不受此過濾。
        if (
            self.tickers is not None
            and notification.ticker is not None
            and notification.ticker not in self.tickers
        ):
            return False
        return True


__all__ = ["Subscription"]
