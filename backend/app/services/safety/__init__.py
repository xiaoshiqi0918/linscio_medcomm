"""
合规风险扫描（P0-3）。

公共接口：
  - ActionLevel：风险级别枚举
  - RiskRule / RiskMatch / RiskScanReport：数据结构
  - scan_risk_words(text)：主扫描入口

详见 docs/AIGC治理可执行方案_v1.1.md 附录 A.9 / A.10。
"""
from app.services.safety.risk_scanner import (
    RiskMatch,
    RiskScanReport,
    scan_risk_words,
)
from app.services.safety.risk_words_dict import (
    ActionLevel,
    RiskRule,
)

__all__ = [
    "ActionLevel",
    "RiskRule",
    "RiskMatch",
    "RiskScanReport",
    "scan_risk_words",
]
