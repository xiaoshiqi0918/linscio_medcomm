# ComfyUI 工作流编排设计方案（医学科普 / LinScio MedComm 场景）

本文档从**编排视角**说明：如何选节点、如何配参数、如何选基底模型与 LoRA，以稳定产出**教育向医学插画、信息图、流程图**类画面。与《ComfyUI绘图集成方案.md》的关系：后者侧重 **MedComm 后端对接**；本文侧重 **ComfyUI 侧设计与调参**。

---

## 1. 设计原则

| 原则 | 说明 |
|------|------|
| **教育优先** | 清晰、可读、少惊悚；避免过度写实「创伤/手术」类视觉。 |
| **可控文字** | 科普图常需标签；完全依赖模型生成文字易乱码，重要文案建议后期矢量/排版叠加。 |
| **风格一致** | 同一专栏固定「基底模型 + 主 LoRA + 固定 seed 区间」便于系列图统一。 |
| **算力与延迟** | 本地部署在效果与 VRAM 间平衡；SD1.5 省显存，SDXL 细节与构图更好。 |
| **可 API 化** | 最终需能导出 **API Format**，且关键注入点（正/负向、KSampler、可选 Latent 尺寸）节点 ID 固定，便于程序覆盖。 |

---

## 2. 基底模型（Checkpoint）选择

### 2.1 路线对比

| 路线 | 显存参考 | 优势 | 劣势 | 科普场景适用 |
|------|----------|------|------|----------------|
| **SDXL Base（+ 可选 Refiner）** | 约 8–12GB+ | 构图稳、细节好、1024 原生 | 更重、更慢 | **首选**：插图、封面、复杂信息图 |
| **SD 1.5** | 约 4–8GB | 快、插件生态老、省显存 | 默认分辨率偏低，需放大 | 草图、简单扁平图、低配机器 |
| **SDXL Lightning / Turbo 系** | 与 SDXL 类似 | 步数少、快 | 细调空间略小 | 批量配图、预览稿 |
| **Flux.1（dev/schnell）** | 较高 | 提示遵从、光影好 | 工作流节点与 SD 不同，需单独 JSON | 高质量单张、需单独维护一套 API |

**推荐默认**：**SDXL Base 1.0**（或社区认可的 XL 融合模型），与仓库示例 `medcomm_t2i_sdxl.api.json` 一致；有 Refiner 时再增加第二阶段采样节点链。

### 2.2 选型检查清单

- [ ] 许可证允许商用（若 MedComm 商用分发）。  
- [ ] 偏「通用写实」还是「插画/动漫」——科普多选 **偏写实插画、3D 渲染风、扁平矢量风** 的融合模，少选纯二次元 unless 栏目定位是儿童向。  
- [ ] 是否与计划使用的 **LoRA** 同架构（XL 配 XL LoRA，1.5 配 1.5 LoRA）。

---

## 3. LoRA 策略

### 3.1 作用分工

| 类型 | 作用 | 典型触发 |
|------|------|----------|
| **风格 LoRA** | 统一笔触、色彩、扁平/矢量感 | 在正向提示中加触发词（若作者要求） |
| **题材 LoRA** | 强化「医疗 UI、解剖示意、信息图框」等 | 低权重起步，避免盖过主模 |
| **角色/ IP LoRA** | 固定吉祥物形象 | 科普栏目品牌化时使用；注意版权 |

### 3.2 堆叠与权重建议

- **单 LoRA**：`0.5 – 0.85` 先试；过强易「糊脸、糊字、风格过曝」。  
- **多 LoRA**：优先 **风格 1 个 + 题材 1 个**；总强度不宜「全满」，建议各 **0.3–0.6** 组合调试。  
- **在图中的位置**：`Load LoRA` 串在 **Checkpoint → Model** 之间，**CLIP 也要走 LoRA 链**（若该 LoRA 含 text encoder 训练）。Comfy 标准 `LoraLoader` 会输出 `MODEL` 与 `CLIP`，需同时接到后续 `CLIPTextEncode` 与 `KSampler` 的 model 源。

### 3.3 与 MedComm 风格的映射（概念）

MedComm 内置风格如 `medical_illustration`、`flat_design`、`data_viz` 等（见 `prompt_builder`），在 Comfy 侧建议：

- **medical_illustration / realistic**：XL 通用模 + 可选「medical illustration / educational」向 LoRA。  
- **flat_design / data_viz**：扁平/信息图 LoRA + 略低 CFG（6–7）减少立体伪阴影。  
- **cartoon / picture_book**：儿向插画 LoRA + 更亮饱和度（可在提示词里约束）。

---

## 4. 节点编排（标准文生图）

### 4.1 最小必选链（SDXL）

```
CheckpointLoaderSimple
    →（可选）LoraLoader × N
    → CLIPTextEncode（正）
    → CLIPTextEncode（负）
EmptyLatentImage
    → KSampler（model / positive / negative / latent）
    → VAEDecode
    → SaveImage
```

### 4.2 建议增加的节点

| 节点 | 用途 |
|------|------|
| **CLIP Set Last Layer**（部分工作流） | 调节 CLIP 截断层，微调提示敏感度（高级）。 |
| **SDXL 专用**：若使用官方两阶段文本编码 | 使用 `CLIPTextEncodeSDXL` 或工作流模板中带 `width/height/crop` 的编码节点（按你导出的 API 为准）。 |
| **Refiner**（可选） | Base 采完后 latent → Refiner Checkpoint + 第二次 KSampler（步数少、denoise 低）。 |
| **Upscale**（可选） | `Upscale Model` 或 latent upscale → 再 VAE Decode；注意显存与超时。 |

> 说明：若使用 **SDXL 双 CLIP 编码** 的完整模板，请以 ComfyUI 导出 API 为准；MedComm 当前客户端只注入**单个**正向节点与**单个**负向节点，复杂双编码需合并提示或扩展后端注入逻辑。

### 4.3 节点配置要点

| 节点 | 关键 inputs | 建议 |
|------|-------------|------|
| **EmptyLatentImage** | `width`, `height`, `batch_size` | 科普默认 **1024×1024**；横版信息图 **1280×720** 或 **1344×768**。 |
| **KSampler** | `steps`, `cfg`, `sampler_name`, `scheduler`, `denoise` | 见第 5 节。 |
| **CLIPTextEncode** | `text` | 正向写风格+主体；负向写安全+画质+「乱码文字」抑制。 |
| **VAEDecode** | `samples`, `vae` | 使用与 Checkpoint 匹配的 VAE；色偏大时可试 `VAE Loader` 替换。 |
| **SaveImage** | `filename_prefix` | 固定前缀便于和 MedComm 下载逻辑区分（如 `MedComm`）。 |

---

## 5. 参数配置矩阵

### 5.1 KSampler（文生图 denoise=1）

| 参数 | 保守起点 | 提质/创意 | 说明 |
|------|----------|-----------|------|
| **steps** | 24–28 | 32–40 | XL 28 步常已够用；过高收益递减。 |
| **cfg** | 6.5–7.5 | 5–6（更「软」） / 8–9（更「贴提示」） | 科普插画 **7±1** 较稳；过高易过度饱和与伪文字。 |
| **sampler_name** | `euler` / `dpmpp_2m` | `dpmpp_2m_sde_gpu`（需环境支持） | 先 euler 做基准再换。 |
| **scheduler** | `normal` / `sgm_uniform` | 与 sampler 文档推荐搭配 | 不一致时可能发灰或噪点异常。 |
| **seed** | 固定某值做 A/B | 随机 | 系列图可「基础 seed + 小增量」控制变化幅度。 |

### 5.2 Refiner 阶段（若启用）

| 参数 | 建议 |
|------|------|
| **steps** | 10–20 |
| **denoise** | **0.15–0.35**（仅细化，不重画） |
| **cfg** | 略低于 Base 或持平 |

### 5.3 分辨率与显存（经验值）

| 分辨率 | 适用 | 备注 |
|--------|------|------|
| 768×768 | SD1.5 常用 | 科普可用，细节略逊 XL。 |
| 1024×1024 | SDXL 默认 | 与 MedComm 默认一致。 |
| 1216×832 / 1344×768 | 横版信息图 | 注意 XL 对宽高多为 8 的倍数。 |
| 更高 | 海报 | 建议 **先生成再放大**，而非一步拉满 latent。 |

---

## 6. 正负向提示在编排中的分工

### 6.1 正向（建议结构）

1. **画质与用途**：`professional medical illustration, educational, clean composition`  
2. **风格**：与 `prompt_builder` 的 style 一致（扁平/矢量/3D 示意等）。  
3. **主体与构图**：场景描述由 MedComm 生成；Comfy 内可在模板里写极短的「默认画风」作为底，程序注入覆盖或拼接。  

### 6.2 负向（建议结构）

1. **安全与不适内容**：与产品 `SAFETY_NEGATIVE` 对齐（血腥、恐怖、隐私等）。  
2. **画质**：`low quality, blurry, jpeg artifacts, watermark`。  
3. **文字乱码**：`gibberish text, illegible labels`（完全避免乱字不现实，可降低概率）。  

程序侧：MedComm 已通过独立负向节点注入；编排时**预留足够长的 CLIP 负向节点**，避免后续追加负向词超长被截断。

---

## 7. 进阶编排（按需）

| 能力 | 节点思路 | 科普用途 |
|------|----------|----------|
| **ControlNet（Lineart / Softedge）** | 先验边缘 → 采样 | 流程图线稿上色、版式可控。 |
| **ControlNet（Depth）** | 深度图控制层次 | 示意图前后景分层。 |
| **IP-Adapter** | 参考图风格/构图 | 与参考插图风格对齐。 |
| **Regional / Attention** | 分区提示 | 左文右图布局（实现复杂，维护成本高）。 |

**建议**：主线先跑通「无 ControlNet + 好提示词 + 可选 LoRA」；版式强需求再上 ControlNet，并单独导出一份 API JSON。

---

## 8. 实施步骤（推荐顺序）

1. **选定 Checkpoint**（建议 SDXL Base 或已验证的 XL 融合模）。  
2. **搭建最小链**（第 4.1 节）→ 仅用提示词出图，固定 seed 调 **CFG / steps**。  
3. **加入 1 个风格 LoRA** → 扫权重曲线（如 0.4、0.6、0.8）。  
4. **固化负向** → 与产品安全词合并测试。  
5. **（可选）Refiner / 放大** → 单独记一份节点 ID 表，便于 API 注入。  
6. **导出 API Format** → 对齐 `COMFYUI_*_NODE_ID` 环境变量，接 MedComm。  

---

## 9. 与仓库文件的对应

| 文件 | 内容 |
|------|------|
| `medcomm_t2i_sdxl.api.json` | **最小 SDXL API 示例**（无 LoRA）；改 `ckpt_name` 即用。 |
| `ComfyUI绘图集成方案.md` | 后端 URL、环境变量、与 `comfy_client` 的对接。 |
| 本文 `ComfyUI工作流编排设计方案.md` | **节点、参数、模型与 LoRA 编排策略**。 |

---

## 10. 附录：含 LoRA 时的典型拓扑（文字说明）

在 `CheckpointLoaderSimple` 之后串联：

```
CheckpointLoaderSimple
  → LoraLoader #1 (model+clip 输出)
  → LoraLoader #2 (可选，接上一路 model+clip)
  → 后续 CLIPTextEncode ×2 使用「最后一级 LoRA 的 CLIP」
  → KSampler 的 model 使用「最后一级 LoRA 的 MODEL」
```

每个 `LoraLoader` 需配置：`lora_name`、`strength_model`、`strength_clip`（按 Comfy 版本字段名为准）。**strength_clip** 过大易导致提示词失真，宜 ≤ **strength_model** 或先锁 1.0 只调 model 强度试效果。

---

**文档维护**：更换模型体系（如全面切 Flux）时，需重写第 2、4 节并新增对应 API JSON 模板。
