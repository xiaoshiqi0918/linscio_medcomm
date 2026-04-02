"""
ACCEPTANCE_CRITERIA 的可执行实现
将文档中的验收标准转化为可调用的检查函数，返回结构化结果。

调用时机：
  · quality_check_node 之后、verify_medical_claims 之前
  · 导出前的最终检查（ExportGuard）
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"  # 阻断发布，必须修复
    WARNING = "warning"  # 提示，建议修复
    INFO = "info"  # 质量建议


@dataclass
class CheckResult:
    rule_name: str
    severity: Severity
    message: str
    location: str = ""  # 在内容中的定位（如"第2段"）


@dataclass
class AcceptanceReport:
    content_format: str
    passed: bool
    results: list[CheckResult] = field(default_factory=list)

    @property
    def errors(self):
        return [r for r in self.results if r.severity == Severity.ERROR]

    @property
    def warnings(self):
        return [r for r in self.results if r.severity == Severity.WARNING]

    def to_dict(self) -> dict:
        return {
            "content_format": self.content_format,
            "passed": self.passed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "results": [
                {
                    "rule": r.rule_name,
                    "severity": r.severity.value,
                    "message": r.message,
                    "location": r.location,
                }
                for r in self.results
            ],
        }


class AcceptanceChecker:
    """
    ACCEPTANCE_CRITERIA 可执行版本
    根据 content_format 自动路由到对应的检查规则集
    """

    def check(
        self,
        content: str,
        content_format: str,
        target_audience: str = "public",
        platform: str = "universal",
    ) -> AcceptanceReport:
        """
        执行验收检查
        content: 纯文本内容（非JSON格式的形式），或 JSON 字符串（图示类）
        """
        results: list[CheckResult] = []

        # 通用规则（所有形式都检查）
        results.extend(self._check_common(content))

        # 形式专属规则
        format_checkers = {
            "article": self._check_narrative,
            "debunk": self._check_narrative,
            "story": self._check_narrative,
            "qa_article": self._check_narrative,
            "research_read": self._check_narrative,
            "oral_script": self._check_script,
            "drama_script": self._check_script,
            "audio_script": self._check_script,
            "storyboard": self._check_storyboard,
            "comic_strip": self._check_visual_json,
            "card_series": self._check_visual_json,
            "picture_book": self._check_visual_json,
            "poster": self._check_visual_json,
            "long_image": self._check_visual_json,
            "patient_handbook": self._check_handbook,
            "quiz_article": self._check_quiz,
            "h5_outline": self._check_h5,
        }

        checker_fn = format_checkers.get(content_format)
        if checker_fn:
            results.extend(checker_fn(content, target_audience, platform))

        passed = not any(r.severity == Severity.ERROR for r in results)
        return AcceptanceReport(
            content_format=content_format,
            passed=passed,
            results=results,
        )

    # ── 通用规则 ──────────────────────────────────────────
    def _check_common(self, content: str) -> list[CheckResult]:
        results = []

        # 1. 具体剂量（HIGH）
        dosage_pattern = re.compile(
            r"\d+\s*(mg|ml|毫克|毫升|片|粒|滴|μg|mcg|IU|单位)"
            r"(?:\s*/\s*(?:次|天|日|kg|公斤))?",
            re.IGNORECASE,
        )
        if dosage_pattern.search(content):
            results.append(
                CheckResult(
                    rule_name="具体剂量",
                    severity=Severity.ERROR,
                    message="内容包含具体药物剂量，必须删除或改为'遵医嘱'",
                )
            )

        # 2. 绝对化表述（HIGH）
        absolute_terms = [
            "一定会",
            "必然导致",
            "百分之百",
            "绝对有效",
            "完全治愈",
            "永久有效",
            "从不发生",
            "只要……就能治愈",
        ]
        for term in absolute_terms:
            if term in content:
                results.append(
                    CheckResult(
                        rule_name="绝对化表述",
                        severity=Severity.ERROR,
                        message=f"包含绝对化表述：'{term}'，须改为概率性表述",
                    )
                )

        # 3. 开场套话（WARNING）
        opening = content[:80]
        cliches = [
            "随着医学的发展",
            "在当今社会",
            "众所周知",
            "大家都知道",
            "随着科技的进步",
            "在现代医学",
            "随着人们生活水平",
        ]
        for cliche in cliches:
            if cliche in opening:
                results.append(
                    CheckResult(
                        rule_name="开场套话",
                        severity=Severity.WARNING,
                        message=f"开场使用了套话：'{cliche}'，建议更换为有信息量的开场",
                        location="开头80字内",
                    )
                )

        # 4. 高风险比喻短语（WARNING）- 多学科比喻反例库 v1.0
        analogy_risk_phrases = [
            ("多放点水就好", "血压/降压相关：人体不能'放水'降压"),
            ("多放点水就行了", "血压/降压相关：人体不能'放水'降压"),
            ("支架放了就一劳永逸", "支架术后仍有再狭窄风险并需长期管理"),
            ("心衰休息一下就能恢复", "心衰是慢性进展性疾病"),
            ("心律不齐换个电池就好", "不同心律失常治疗策略不同"),
            ("少吃酸的就没事了", "胃酸并非由食物酸度直接决定"),
            ("肠镜像照镜子没痛苦", "过度轻描淡写检查体验会误导预期"),
            ("慢阻肺把锈刮掉就好了", "慢阻肺损伤不可逆"),
            ("哮喘发作用一下吸入剂就好", "忽略长期炎症控制治疗"),
            ("肺结节查到就赶紧手术切掉", "多数小结节良性，常规是随访评估"),
            ("脑梗通开就好了", "溶栓时间窗和不可逆损伤被忽略"),
            ("补充多巴胺就能完全控制", "帕金森病为进展性疾病"),
            ("换血就好了", "白血病：换血只能暂时改善，根治需化疗/移植"),
            ("贫血多吃补血食物就能好", "贫血病因多样，治疗路径不同"),
            ("透析洗完就跟正常人一样", "透析仅替代部分肾功能"),
            ("肾结石喝多点水就能冲出来", "较大结石通常不能靠多喝水排出"),
            ("胰岛素打了就能完全控制", "剂量和时机需个体化调整"),
            ("甲亢切掉就彻底好了", "可能转为需终身替代治疗"),
            ("类风湿吃消炎药一段时间就好了", "需长期免疫调节治疗"),
            ("红斑狼疮皮疹好了就是病好了", "狼疮可多器官受累"),
            ("肝癌切掉就治好了", "术后复发率高，仍需随访"),
            ("气胸把气抽出来就好了", "存在复发风险"),
            ("脑出血把积血抽出来就好了", "手术决策高度个体化"),
            ("前列腺增生喝中药就能缩小", "缺乏循证支持"),
            ("想开点就好了", "抑郁症：有神经生物学基础，需专业治疗"),
            ("精神分裂解开心结就好", "抗精神病药物是核心治疗"),
            ("焦虑药吃了就不用一直吃", "需足疗程并评估复发风险"),
            ("休息一下就能恢复", "心衰等慢性病：不能通过休息恢复"),
            ("少吃肥肉就会消", "脂肪肝：与碳水、代谢更密切"),
            ("宫颈癌疫苗打了就不会得", "并非全覆盖，仍需筛查"),
            ("多囊减肥就好了", "并非所有患者仅靠减重即可管理"),
            ("小孩发烧就是细菌感染", "儿童发热常见病毒感染"),
            ("补钙就能治好", "骨质疏松：核心是抗骨吸收/促骨形成药物"),
            ("椎间盘突出慢慢会吸收不用管", "出现神经功能异常不能等待"),
            ("耳聋戴助听器就跟正常人一样", "助听器无法完全恢复正常听觉"),
            ("鼻炎手术治好了就不会复发", "过敏体质并未被根治"),
            ("种植牙一辈子不用管", "需长期维护防种植体周围炎"),
            ("晒太阳就能治好", "牛皮癣：需专业光疗设备"),
            ("白癜风完全治不好", "过于绝对，规范治疗可复色"),
            ("化疗不如不做", "可能导致患者拒绝有效治疗"),
            ("靶向药没有副作用", "靶向治疗也有不良反应"),
            ("肿瘤标志物升高就是复发", "需结合影像与临床判断"),
            ("心肺复苏做了就能救活", "成功率受多因素影响"),
            ("ICU进去就出不来", "属于恐慌性误导"),
            ("中风后半身不遂康复没用", "忽略神经可塑性与康复获益"),
            ("中药没有副作用", "中药同样存在毒副作用"),
            ("乙肝携带者和乙肝患者是一回事", "两者状态与处理不同"),
            ("艾滋病患者活不过几年", "与现代ART事实不符"),
            ("CT核磁什么病都能查出来", "影像检查有边界"),
            ("核磁有辐射", "MRI无电离辐射"),
            ("血常规正常就是健康", "不能覆盖系统性疾病评估"),
            ("白细胞高就一定是细菌感染", "需综合判断"),
            ("肿瘤标志物正常就排除癌症", "灵敏度有限"),
            ("尿常规正常肾脏就没问题", "早期肾损伤可能漏检"),
            ("激光手术永久治好", "近视：眼底并发症风险仍存在"),
        ]
        hit_count = 0
        for phrase, reason in analogy_risk_phrases:
            if phrase in content:
                results.append(
                    CheckResult(
                        rule_name="比喻准确性",
                        severity=Severity.WARNING,
                        message=f"发现可能存在问题的比喻表述：\"{phrase}\"（{reason}）",
                    )
                )
                hit_count += 1
                if hit_count >= 5:
                    break  # 限制条数，避免刷屏

        # 5. 感谢阅读（WARNING）
        closing = content[-100:] if len(content) >= 100 else content
        closings = [
            "感谢阅读",
            "谢谢观看",
            "感谢您的关注",
            "欢迎关注我们",
            "感谢您的耐心阅读",
            "感谢大家的观看",
        ]
        for c in closings:
            if c in closing:
                results.append(
                    CheckResult(
                        rule_name="感谢阅读",
                        severity=Severity.WARNING,
                        message=f"结尾包含无意义收尾语：'{c}'，建议删除",
                        location="结尾100字内",
                    )
                )

        return results

    # ── 叙事文章类 ─────────────────────────────────────────
    def _check_narrative(
        self, content: str, audience: str, platform: str
    ) -> list[CheckResult]:
        results = []

        # 医学准确性：无来源声明（WARNING）
        unsourced = re.compile(
            r"据.*?研究[，,]|根据.*?指南[，,]|.*?统计(?:数据)?(?:显示|表明)"
        )
        matches = unsourced.findall(content)
        if matches:
            results.append(
                CheckResult(
                    rule_name="疑似无来源声明",
                    severity=Severity.WARNING,
                    message=f"发现 {len(matches)} 处疑似引用表述，请确认有 RAG 来源支撑",
                )
            )

        # 案例化名标注
        if any(
            kw in content for kw in ["医生", "患者", "阿姨", "叔叔", "先生", "女士"]
        ):
            if "化名" not in content:
                results.append(
                    CheckResult(
                        rule_name="案例化名",
                        severity=Severity.WARNING,
                        message="内容涉及具体人物，请确认已标注（化名）",
                    )
                )

        # 受众句长检查
        sentences = re.split(r"[。！？…]", content)
        long_sentences = []
        max_len = {
            "public": 25,
            "patient": 30,
            "student": 40,
            "professional": 50,
            "children": 15,
        }.get(audience, 30)
        for i, s in enumerate(sentences):
            s = s.strip()
            if len(s) > max_len:
                long_sentences.append((i + 1, len(s), s[:20]))
        if long_sentences:
            sample = long_sentences[0]
            results.append(
                CheckResult(
                    rule_name="句长超标",
                    severity=Severity.WARNING,
                    message=(
                        f"发现 {len(long_sentences)} 处句子超过受众上限（{max_len}字）。"
                        f"最长处约 {sample[1]} 字（第{sample[0]}句：{sample[2]}…）"
                    ),
                )
            )

        # 就医提示（INFO）
        medical_kw = ["就医", "看医生", "咨询医生", "请及时", "医院"]
        if not any(kw in content for kw in medical_kw):
            results.append(
                CheckResult(
                    rule_name="就医提示",
                    severity=Severity.INFO,
                    message="未检测到就医提示，建议在合适位置添加就医指引",
                )
            )

        return results

    # ── 脚本类 ─────────────────────────────────────────────
    def _check_script(
        self, content: str, audience: str, platform: str
    ) -> list[CheckResult]:
        results = []

        # 时间戳格式（ERROR）
        if re.search(r"\[?\d{2}:\d{2}", content):
            bad_ts = re.findall(r"\[\d{2}:\d{2}(?!-\d{2}:\d{2})", content)
            if bad_ts:
                results.append(
                    CheckResult(
                        rule_name="时间戳格式",
                        severity=Severity.ERROR,
                        message=f"发现 {len(bad_ts)} 处时间戳格式不正确，应为 [MM:SS-MM:SS]",
                    )
                )

        # 书面连接词（WARNING）
        formal_connectors = [
            "此外",
            "然而",
            "综上所述",
            "值得注意的是",
            "总而言之",
            "由此可见",
            "不难看出",
        ]
        found = [c for c in formal_connectors if c in content]
        if found:
            results.append(
                CheckResult(
                    rule_name="书面连接词",
                    severity=Severity.WARNING,
                    message=f"脚本中包含书面连接词：{found}，建议改为口语表达",
                )
            )

        # 口播句长（WARNING）
        lines = [
            l.strip()
            for l in content.split("\n")
            if l.strip() and not l.strip().startswith("[")
        ]
        long_lines = [l for l in lines if len(l) > 15]
        if long_lines:
            results.append(
                CheckResult(
                    rule_name="口播句长",
                    severity=Severity.WARNING,
                    message=f"发现 {len(long_lines)} 处单句超过 15 字，建议拆分",
                )
            )

        return results

    # ── 动画分镜类 ─────────────────────────────────────────
    def _check_storyboard(
        self, content: str, audience: str, platform: str
    ) -> list[CheckResult]:
        results = []

        # 中文 scene_desc（ERROR）
        scene_sections = re.findall(r"Scene:(.+?)(?:Action:|$)", content, re.DOTALL)
        for sec in scene_sections:
            if re.search(r"[\u4e00-\u9fff]", sec):
                results.append(
                    CheckResult(
                        rule_name="Scene中文",
                        severity=Severity.ERROR,
                        message="Scene 描述中包含中文，必须改为英文",
                    )
                )
                break

        # 旁白字数匹配（INFO）
        ts_matches = re.findall(r"\((\d+)s\)", content)
        narr_matches = re.findall(r"【旁白.*?】\s*(.+?)(?=\n|$)", content)
        for i, (ts, narr) in enumerate(zip(ts_matches, narr_matches)):
            expected = int(ts) * 3
            actual = len(narr)
            if actual > expected * 1.3:
                results.append(
                    CheckResult(
                        rule_name="旁白超时",
                        severity=Severity.WARNING,
                        message=(
                            f"第{i+1}帧旁白 {actual} 字，帧时长 {ts}s（约 {expected} 字），"
                            f"建议压缩约 {actual - expected} 字"
                        ),
                    )
                )

        return results

    # ── 图示类（JSON 输出）─────────────────────────────────
    def _check_visual_json(
        self, content: str, audience: str, platform: str
    ) -> list[CheckResult]:
        results = []

        # JSON 合法性（ERROR）
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            results.append(
                CheckResult(
                    rule_name="JSON格式",
                    severity=Severity.ERROR,
                    message=f"输出不是合法 JSON：{str(e)[:60]}",
                )
            )
            return results

        # illustration_desc / scene_desc 中文检测（ERROR）
        def check_image_fields(obj, path=""):
            issues = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in (
                        "illustration_desc",
                        "scene_desc",
                        "image_prompt",
                        "main_visual_desc",
                        "footer_image_prompt",
                        "visual_mood",
                        "background_desc",
                    ):
                        if isinstance(v, str) and re.search(r"[\u4e00-\u9fff]", v):
                            issues.append(f"字段 '{k}' 包含中文（路径：{path}.{k}）")
                        if isinstance(v, str) and len(v.split()) < 8:
                            issues.append(
                                f"字段 '{k}' 过短（{len(v.split())} 词，建议20词以上）"
                            )
                    else:
                        issues.extend(check_image_fields(v, f"{path}.{k}"))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    issues.extend(check_image_fields(item, f"{path}[{i}]"))
            return issues

        img_issues = check_image_fields(parsed)
        for issue in img_issues:
            results.append(
                CheckResult(
                    rule_name="图像描述",
                    severity=Severity.ERROR,
                    message=issue,
                )
            )

        # 字数检查（各形式专属）
        if isinstance(parsed, list):
            for i, item in enumerate(parsed):
                if isinstance(item, dict):
                    results.extend(self._check_visual_item(item, i))

        return results

    def _check_visual_item(self, item: dict, index: int) -> list[CheckResult]:
        """单个图示条目的字数检查"""
        results = []

        def char_count(text: str) -> int:
            return len(re.sub(r"\s", "", str(text)))

        # dialogue（条漫对白）
        if "dialogue" in item and item["dialogue"]:
            n = char_count(item["dialogue"])
            if n > 30:
                results.append(
                    CheckResult(
                        rule_name="对白字数",
                        severity=Severity.WARNING,
                        message=f"第{index+1}格对白 {n} 字，超过上限 30 字",
                        location=f"panel[{index}].dialogue",
                    )
                )

        # page_text（绘本页面文字）
        if "page_text" in item:
            n = char_count(item["page_text"])
            if n > 20:
                results.append(
                    CheckResult(
                        rule_name="绘本页面文字",
                        severity=Severity.WARNING,
                        message=f"第{index+1}页文字 {n} 字，超过上限 20 字",
                        location=f"page[{index}].page_text",
                    )
                )
            if n < 6:
                results.append(
                    CheckResult(
                        rule_name="绘本页面文字",
                        severity=Severity.INFO,
                        message=f"第{index+1}页文字 {n} 字，低于建议下限 6 字",
                        location=f"page[{index}].page_text",
                    )
                )

        # headline（卡片标题）
        if "headline" in item:
            n = char_count(item["headline"])
            if n > 15:
                results.append(
                    CheckResult(
                        rule_name="卡片标题",
                        severity=Severity.WARNING,
                        message=f"第{index+1}张卡片 headline {n} 字，超过上限 15 字",
                        location=f"card[{index}].headline",
                    )
                )

        return results

    # ── 患者手册类 ─────────────────────────────────────────
    def _check_handbook(
        self, content: str, audience: str, platform: str
    ) -> list[CheckResult]:
        results = []

        # 【注意】【医嘱】【警告】标注检查（INFO）
        if "注意" in content or "医嘱" in content or "警告" in content:
            wrong_format = re.findall(r"(?<!【)(注意|医嘱|警告)(?!】)", content)
            if wrong_format:
                results.append(
                    CheckResult(
                        rule_name="警示框格式",
                        severity=Severity.WARNING,
                        message=f"发现未用【】包裹的警示词：{set(wrong_format)}，格式应为【注意】【医嘱】【警告】",
                    )
                )

        # 行动建议可操作性（INFO）
        vague_advice = [
            "保持良好",
            "注意饮食",
            "适当运动",
            "规律作息",
            "保持健康",
            "积极配合",
        ]
        found_vague = [a for a in vague_advice if a in content]
        if found_vague:
            results.append(
                CheckResult(
                    rule_name="行动建议可操作性",
                    severity=Severity.INFO,
                    message=f"发现空泛建议：{found_vague}，建议改为具体可量化的行动",
                )
            )

        # 必须包含就医提示（ERROR）
        medical_kw = ["就医", "看医生", "咨询医生", "急诊", "就诊"]
        if not any(kw in content for kw in medical_kw):
            results.append(
                CheckResult(
                    rule_name="就医提示",
                    severity=Severity.ERROR,
                    message="患者手册缺少就医提示，必须包含在什么情况下需要就医",
                )
            )

        return results

    # ── 自测科普类 ─────────────────────────────────────────
    def _check_quiz(
        self, content: str, audience: str, platform: str
    ) -> list[CheckResult]:
        results = []

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            results.append(
                CheckResult(
                    rule_name="JSON格式",
                    severity=Severity.ERROR,
                    message="输出不是合法 JSON",
                )
            )
            return results

        if not isinstance(parsed, list):
            return results

        for i, item in enumerate(parsed):
            if not isinstance(item, dict):
                continue

            options = item.get("options", [])
            correct = item.get("correct_answer", "")
            valid_keys = [o[0] for o in options if o and o[0].isalpha()]
            if correct and valid_keys and correct not in valid_keys:
                results.append(
                    CheckResult(
                        rule_name="答案有效性",
                        severity=Severity.ERROR,
                        message=f"第{i+1}题 correct_answer='{correct}' 不在选项中",
                        location=f"question[{i}]",
                    )
                )

            exp = item.get("explanation", "")
            if len(exp) < 30:
                results.append(
                    CheckResult(
                        rule_name="解析字数",
                        severity=Severity.WARNING,
                        message=f"第{i+1}题 explanation 仅 {len(exp)} 字，建议80字以上",
                        location=f"question[{i}].explanation",
                    )
                )

        return results

    # ── H5 大纲类 ──────────────────────────────────────────
    def _check_h5(
        self, content: str, audience: str, platform: str
    ) -> list[CheckResult]:
        results = []

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            results.append(
                CheckResult(
                    rule_name="JSON格式",
                    severity=Severity.ERROR,
                    message="输出不是合法 JSON",
                )
            )
            return results

        pages = parsed.get("pages", [])
        for i, page in enumerate(pages):
            if not isinstance(page, dict):
                continue

            page_type = page.get("page_type", "")
            elements = page.get("elements", {})

            # quiz 类型必须有 feedback
            if page_type == "quiz":
                if not elements.get("feedback_correct") or not elements.get(
                    "feedback_wrong"
                ):
                    results.append(
                        CheckResult(
                            rule_name="测验反馈",
                            severity=Severity.ERROR,
                            message=f"第{i+1}页（quiz）缺少 feedback_correct 或 feedback_wrong",
                            location=f"pages[{i}]",
                        )
                    )

            # share 页必须有 share_reason
            if page_type == "share":
                share_reason = elements.get("share_reason", "")
                if not share_reason:
                    results.append(
                        CheckResult(
                            rule_name="分享理由",
                            severity=Severity.WARNING,
                            message=f"第{i+1}页（share）缺少 share_reason",
                            location=f"pages[{i}]",
                        )
                    )
                boring_share = ["欢迎关注", "关注我们", "关注公众号"]
                if any(bs in share_reason for bs in boring_share):
                    results.append(
                        CheckResult(
                            rule_name="分享文案质量",
                            severity=Severity.WARNING,
                            message=f"第{i+1}页 share_reason 缺少具体传播动机",
                            location=f"pages[{i}].elements.share_reason",
                        )
                    )

        return results
