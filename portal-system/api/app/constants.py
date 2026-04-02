"""
门户与主产品共用的常量。受控模块 code 必须与主产品 require_module() 一致。
"""
# 6 个受控模块预置：(code, name, bit_position, basic_enabled, pro_enabled, team_enabled, enterprise_enabled, beta_enabled)
CONTROLLED_MODULES_SEED = [
    ("schola", "Schola 论文辅助", 0, True, True, True, True, True),
    ("medcomm", "MedComm 科普创作", 1, True, True, True, True, True),
    ("qcc", "QCC 质量控制", 2, True, True, True, True, True),
    ("literature", "Literature 文献管理", 3, True, True, False, True, True),
    ("analyzer", "Data Analyzer 数据分析", 4, True, True, False, True, True),
    ("image_studio", "AI Image Studio", 5, True, True, False, True, True),
]
