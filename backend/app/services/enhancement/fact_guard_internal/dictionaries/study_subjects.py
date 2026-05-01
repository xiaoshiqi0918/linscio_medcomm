"""
研究对象层级词典（P0-1 / 决策 S1-S6）

层级设计（layer1 / layer2 / 词条）：
  HUMAN
    HUMAN_GENERAL    - 人 / 受试者 / 志愿者（决策 S5：不拆）
    HUMAN_PATIENTS   - 患者 / 病人（决策 S4：仅泛指，不细分病种）
    HUMAN_CHILDREN   - 儿童 / 婴儿 / 新生儿
    HUMAN_PREGNANT   - 孕妇 / 妊娠期女性
    HUMAN_ELDERLY    - 老年人

  ANIMAL
    ANIMAL_RODENT    - 小鼠 / 大鼠 / 仓鼠
    ANIMAL_PRIMATE   - 猴 / 灵长类
    ANIMAL_OTHER     - 兔 / 犬 / 猪 / 斑马鱼

  IN_VITRO          - 细胞系 / 离体 / 体外

  IN_VIVO_AMBIGUOUS - "in vivo" / "在体内"（决策 S2，同段消解到具体类）

不收录英文 "subject"（决策 S3：含义太泛，漏判优于误判）。
"""
from __future__ import annotations


# {layer1: {layer2: [terms]}}
SUBJECT_TERMS: dict[str, dict[str, list[str]]] = {
    "HUMAN": {
        "HUMAN_GENERAL": [
            "人体", "人类", "成人", "成年人",
            "受试者", "志愿者", "参与者", "被试",  # S5: 不拆，都归 GENERAL
            "健康人", "健康成人", "健康受试者", "健康志愿者",
        ],
        "HUMAN_PATIENTS": [
            "患者", "病人", "病患",  # S4: 仅泛指，不收"高血压患者"等组合
        ],
        "HUMAN_CHILDREN": [
            "儿童", "小儿", "婴儿", "新生儿", "幼儿", "学龄儿童", "青少年",
        ],
        "HUMAN_PREGNANT": [
            "孕妇", "妊娠期妇女", "孕期女性", "妊娠女性",
        ],
        "HUMAN_ELDERLY": [
            "老年人", "老年患者", "高龄患者", "老年群体",
        ],
    },
    "ANIMAL": {
        "ANIMAL_RODENT": [
            "小鼠", "大鼠", "仓鼠", "豚鼠", "鼠类",
            "mouse", "mice", "rat", "rats",
        ],
        "ANIMAL_PRIMATE": [
            "猴", "猴子", "猕猴", "恒河猴", "灵长类",
            "monkey", "monkeys",
        ],
        "ANIMAL_OTHER": [
            "兔", "兔子", "家兔", "犬", "狗", "比格犬",
            "猪", "小型猪", "斑马鱼", "果蝇", "线虫",
        ],
    },
    "IN_VITRO": {
        "IN_VITRO_CELL": [
            "细胞系", "细胞株", "原代细胞", "类器官", "球状体",
            "in vitro", "离体", "体外", "体外实验", "体外研究",
            "细胞培养", "细胞实验",
        ],
    },
    "IN_VIVO_AMBIGUOUS": {
        "IN_VIVO_AMBIGUOUS": [
            # S2: "in vivo" 严格说就是"在体内"，可以指动物也可以指人体
            # 同段中如果有明确 ANIMAL 或 HUMAN 词，本类被消解
            "in vivo", "在体内", "体内实验", "活体实验", "活体研究",
        ],
    },
}


def _build_term_to_layer2() -> dict[str, str]:
    """词 → layer2 的反查表，启动报错检测冲突（决策 S6）。"""
    mapping: dict[str, str] = {}
    for _layer1, layer2_dict in SUBJECT_TERMS.items():
        for layer2, terms in layer2_dict.items():
            for term in terms:
                key = term.lower() if _is_ascii(term) else term
                if key in mapping:
                    raise ValueError(
                        f"研究对象词典冲突：'{term}' 同时出现在 "
                        f"{mapping[key]} 和 {layer2} 中，请修正词典。"
                    )
                mapping[key] = layer2
    return mapping


def _build_term_to_layer1() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for layer1, layer2_dict in SUBJECT_TERMS.items():
        for _layer2, terms in layer2_dict.items():
            for term in terms:
                key = term.lower() if _is_ascii(term) else term
                mapping[key] = layer1
    return mapping


def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


# 启动时立即构建，发现冲突直接 raise（fail-fast）
TERM_TO_LAYER2: dict[str, str] = _build_term_to_layer2()
TERM_TO_LAYER1: dict[str, str] = _build_term_to_layer1()


# 所有可能的术语（按长度倒序，正则匹配时长 token 优先）
ALL_SUBJECT_TERMS: list[str] = sorted(
    {term for layer2_dict in SUBJECT_TERMS.values()
          for terms in layer2_dict.values()
          for term in terms},
    key=lambda x: -len(x),
)


__all__ = [
    "SUBJECT_TERMS",
    "TERM_TO_LAYER1",
    "TERM_TO_LAYER2",
    "ALL_SUBJECT_TERMS",
]
