# LoRA 训练图素材标准（林策 linca / 沈砚 shenyan）

> 用途：攒 LoRA 训练图时的对照检查表。符合全部标准再进训练中心。
> 教训来源：shenyan_v1 水印入模、lince_v2 箭囊入模、两版服装颜色锁不死——都是素材筛选不严。

---

## 一、通用硬标准（三禁一清，底线）

| 项 | 标准 | 原因 |
|---|---|---|
| 数量 | 20~30 张（不少于 15） | 少了锁不住，多了易过拟合 |
| 分辨率 | ≥1080P，面部清晰 | 模糊帧会把脸教"虚" |
| 禁水印 | 任何平台水印/角标（先检查右下角） | 水印会被原样学进模型 |
| 禁武器/多余道具 | 不带武器、箭囊、无关手持物 | 会被学成角色的一部分 |
| 禁服装混色混款 | 同一角色服装颜色款式必须统一 | 混色=颜色永远锁不死 |
| 脸部状态 | 表情自然；删闭眼/半闭眼/怪相帧 | 怪相会被学成常态 |

## 二、配比要求（决定"锁什么"）

- **人脸特写 30%**（正脸为主，锁定五官）
- **半身/全身 50%**（带完整服装，锁服装）
- **多视角**：正脸 50% / 45°侧脸 30% / 正侧 20%（全正脸→转头就崩）
- **多背景 ≥5 种**（街市/室内/纯色/庭院/夜景）——**最重要的一条**：
  服装必须与背景解耦，否则模型以为"衣服长在场景里"，换场景就漂移

## 三、林策（linca）专属

- 服装：**深灰冲锋衣 + 迷彩登山包**，每张都要齐（缺一件=脏数据）
- 场景：古代背景 50% + 现代/中性背景 50%（目标：任何场景都穿现代装）
- 头发：现代短发，**束发/发髻图一律删除**
- 空手为主；手电可留 2~3 张当道具锚点，其余手持物全删

## 四、沈砚（shenyan）专属

- 服装：**青色长袍 + 红腰带**，白袍/黄袍/铠甲图一律删除
- 特征件：发冠 + 山羊须 + 折扇，尽量每张都有
- 场景：古风为主（府门/庭院/街市/夜景灯笼）
- 表情：沉稳/微笑/深沉为主，删瞪眼张嘴夸张帧

## 五、caption 规范（训练中心自动写）

统一格式：`触发词, 角色英文描述, cinematic photo`
**不写场景词**——场景让模型当变量学，不当特征学。

## 六、攒图快捷路径

用杂具小栈锁脸生成批量抽卡（提示词写死服装），抽出的图天然"脸对+服装对"，
再按本标准逐项筛。验收双图（写服装/不写服装）都合格才算训练成功。

---

## 附：验收标准（训完怎么算合格）

- **必过项**：写不写服装提示词，两张验收图都是同一张脸（锁脸合格）
- **目标项**：不写服装时，服装仍正确不漂移（服装锁定——v3 的根治目标）
- 不达标处理：按本标准补图/换图重训，不凑合入库

---

## 附：角色描述速查（训练中心「角色外貌/服装描述」框直接粘贴）

**林策（触发词 linca，注意别写成 linca）**
```
a 25 years old Chinese young man, short black hair, dark grey modern outdoor jacket, camo hiking backpack
```

**沈砚（触发词 shenyan）**
```
a middle-aged Song dynasty scholar with goatee and hairpin crown, teal hanfu robe with red waist sash, holding a folding fan
```

> 提醒：林策框里出现 scholar/goatee/teal robe 就是拿错沈砚的了——两栏别混。

---

## 附：抽片攒图②·提示词清单（锁脸抽片直接逐段粘贴）

> 用法：「🎰 抽片攒图」②的「服装+背景描述」框逐段粘贴；每段抽 3~4 张，
> 景别自然变化，想手动控制就在描述开头加 close-up, / medium shot, / full body shot,
> （特写:中景:全身 ≈ 3:5:2）。每张过目：脸走样/服装变色/多道具当场删。

### 林策 v4（共 26 张 + 基准脸 1 = 27 张）

第 1 段｜特写肖像（4 张）
```
close-up portrait, wearing a dark grey modern outdoor jacket and camo hiking backpack, plain studio grey background, soft frontal lighting
```
第 2 段｜汴京街市·古（4 张）
```
wearing a dark grey modern outdoor jacket and camo hiking backpack, standing in a Song dynasty street market at dusk, wooden shops, red lanterns
```
第 3 段｜城门府门·古（4 张）
```
wearing a dark grey modern outdoor jacket and camo hiking backpack, standing before an ancient Chinese city gate with wooden gatehouse, dusk
```
第 4 段｜现代都市（4 张）
```
wearing a dark grey modern outdoor jacket and camo hiking backpack, standing in a modern Chinese city street, glass skyscrapers, daylight
```
第 5 段｜纯色影棚（4 张）
```
wearing a dark grey modern outdoor jacket and camo hiking backpack, in a clean photography studio with plain warm beige backdrop, soft studio lighting
```
第 6 段｜夜景灯笼·古（3 张）
```
wearing a dark grey modern outdoor jacket and camo hiking backpack, night street market in Bianjing, red lanterns bokeh
```
第 7 段｜庭院园林·古（3 张）
```
wearing a dark grey modern outdoor jacket and camo hiking backpack, standing in an ancient Chinese courtyard garden, stone pavement, potted plants
```

> 送训参数：角色名 林策，触发词 **linca**（沿用！分镜提示词全用这个词），
> 描述框用上方「角色描述速查」林策那段。

### 沈砚 v4（共 22 张 + 基准脸 1 = 23 张，全青袍无水印）

第 1 段｜特写肖像（4 张）
```
close-up portrait, wearing a (teal hanfu robe:1.4) with red waist sash, hairpin crown, goatee, plain studio grey background, soft frontal lighting
```
第 2 段｜府门石阶（4 张）
```
wearing a (teal hanfu robe:1.4) with red waist sash, holding a folding fan, standing before an ancient Chinese mansion gate, stone steps, red lanterns
```
第 3 段｜庭院园林（4 张）
```
wearing a (teal hanfu robe:1.4) with red waist sash, holding a folding fan, standing in a courtyard with Taihu rocks and bamboo
```
第 4 段｜汴京街市（4 张）
```
wearing a (teal hanfu robe:1.4) with red waist sash, holding a folding fan, dusk street market in Bianjing, wooden shops, red lanterns
```
第 5 段｜夜景灯笼（3 张）
```
wearing a (teal hanfu robe:1.4) with red waist sash, holding a folding fan, night market, red lanterns bokeh
```
第 6 段｜书房烛影（3 张）
```
wearing a (teal hanfu robe:1.4) with red waist sash, holding a folding fan, in a study room with bamboo scrolls, candlelight
```

> 送训参数：角色名 谋士-沈砚，触发词 **shenyan**，
> 描述框用上方「角色描述速查」沈砚那段（带发冠+红腰带版）。
