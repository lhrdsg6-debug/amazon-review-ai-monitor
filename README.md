# Amazon Review AI Monitor 🛒🤖

> **AI-powered review monitoring & response system for cross-border Amazon sellers**
> 跨境亚马逊卖家的 AI 差评监控 + 智能回复系统

[![Cost](https://img.shields.io/badge/Cost-%240.001%2Freview-green)]() [![Speed](https://img.shields.io/badge/Speed-38s%2F90_reviews-blue)]() [![Coverage](https://img.shields.io/badge/Amazon_Regions-20%2B-orange)]()

![Top 5 Negative Themes](./output/top5-negative-themes.png)

---

## 🌍 English

### What it does

Production-grade pipeline that:
1. **Scrapes** new Amazon reviews via Apify (any marketplace, any product, any star filter)
2. **Classifies** each review into 5 categories using Claude AI (positive / negative / inquiry / shipping complaint / refund intent)
3. **Drafts** culturally-appropriate English responses in the seller's brand voice
4. **Clusters** negative themes to surface root causes (Top 5)
5. **Alerts** sellers via Lark/Slack/Email when critical reviews appear
6. **Outputs** weekly Chinese-language reports with actionable recommendations

### Demo results (real data, not mock)

We ran this on **3 typical Chinese-seller ASINs** on Amazon UK on **May 14, 2026**:

| Product | Seller | Reviews scraped | Top complaint theme |
|---------|--------|-----------------|---------------------|
| 10000mAh Power Bank | INIU | 30 (1-3 ★) | Short lifespan (33%) |
| Beats Fit Pro Case | SURITCH | 30 (1-3 ★) | Design flaws (53%) |
| Compression Packing Cubes | BAGAIL | 30 (1-3 ★) | Zipper failure (43%) |
| **Total** | — | **90 reviews** | — |

- Total runtime: **38 seconds**
- Total cost: **$0.09** (~¥0.65)
- Reviews actually came from **11 countries** (US 63%, UK 12%, CA 10%, others)
- See full case study: [CASE-STUDY.md](./output/CASE-STUDY.md)

### Architecture

```
Cron Trigger
    ↓
Apify (web_wanderer/amazon-reviews-extractor)
    ↓
n8n workflow orchestration
    ↓
Claude AI ───── Classify  (good / bad / inquiry / shipping / refund)
    ↓
Claude AI ───── Draft English reply (only for negative)
    ↓
Claude AI ───── Theme clustering (Top 5)
    ↓
Google Sheets / Lark webhook / Slack
    ↓
Seller receives mobile push → 1-min human review → send
```

### Monthly cost estimate (production scale)

For a seller scraping **10 ASINs × 30 reviews/day × 30 days = 9,000 reviews/month**:

| Component | Cost |
|-----------|------|
| Apify scraping | $27 / mo |
| Claude API (classify + reply + cluster) | $177 / mo |
| n8n self-hosted (Railway) | $5 / mo |
| Lark/Slack webhook | Free |
| **Total** | **~$209 / mo (¥1,500)** |

For a seller protecting $50K/mo revenue from review-driven ranking drops, this is **0.4% revenue as insurance**.

### Who's this for

- ✅ Chinese sellers on Amazon US/EU/JP with 5+ active listings
- ✅ Agencies managing multiple cross-border seller accounts
- ✅ DTC brands targeting Western markets via Shopify or TikTok Shop

### What's in this repo

```
.
├── CASE-STUDY.md             # 2,000-word case study (Chinese)
├── output/
│   ├── top5-negative-themes.png    # Hero visualization (1680x1080)
│   ├── classified-reviews.json     # All 90 reviews classified
│   ├── theme-clusters.json         # Top 5 theme breakdown
│   └── ai-reply-samples.md         # 5 sample English replies w/ commentary
├── fixtures/
│   └── reviews-raw-90.json         # Raw scraped data (PII removed)
├── n8n-workflow.json         # Importable n8n workflow (from prior session)
├── cluster.py                # Theme clustering logic
└── visualize.py              # Generate matplotlib chart
```

### Talk to me

I do custom AI automation builds for cross-border e-commerce teams. Reach out:
- 💬 WeChat: `LHr20010725g` (add as friend with note "Amazon Seller + your store category"; requests without notes will be declined)
- 🐛 Open a GitHub issue: https://github.com/lhrdsg6-debug/amazon-review-ai-monitor/issues
- 🧑‍💻 GitHub: https://github.com/lhrdsg6-debug

Currently offering **free PoC** to first 3-5 sellers — you pay only Apify + Claude API actual cost (~¥30-100), I keep rights to anonymized case study.

---

## 🇨🇳 中文

### 这套系统解决什么

中国卖家做亚马逊美/欧/日站,有 3 个最痛的事:
- review 全是英文/德文/日文,看不快、回得更慢
- 一波集中差评 48 小时就能让 listing 排名暴跌
- 客服团队在国内,根本看不懂海外用户的真实槽点

**这套系统是一条端到端流水线:**
1. **每天定时抓取** 任意 Amazon 站点 / 任意 ASIN 的新 review
2. **Claude AI 自动分类**:好评 / 差评 / 咨询 / 物流投诉 / 退货意向
3. **生成英文回复草稿**,人工 review 后一键发送
4. **关键词聚类**:差评归因到 Top 5 主题,看清根本问题
5. **飞书/钉钉告警**:出现关键差评 1 分钟内推送
6. **中文周报**:给老板/运营看的人话版

### 这个 demo 的真实数据

5 月 14 日跑的真实数据(3 个典型中国卖家产品,Amazon UK 站):

| 产品 | 卖家 | 抓取 review | 主要痛点 |
|------|------|------------|----------|
| 10000mAh 充电宝 | INIU(深圳) | 30 条(1-3 星)| 寿命短(33%) |
| Beats Fit Pro 耳机壳 | SURITCH | 30 条(1-3 星)| 设计缺陷(53%) |
| 压缩收纳袋 | BAGAIL | 30 条(1-3 星)| 拉链失效(43%) |
| **合计** | — | **90 条** | — |

- 总耗时:**38 秒**
- 总成本:**$0.09(¥0.65)**
- review 实际来源国:**11 个国家**(美国 63% / 英国 12% / 加拿大 10% / 其他)
- 完整案例分析:[CASE-STUDY.md](./output/CASE-STUDY.md)

### 月度成本预估(生产规模)

对一个**日抓 10 个 ASIN、每个 30 条 review**(月 9000 条)的卖家:

| 项目 | 月成本 |
|------|--------|
| Apify scraping | ¥200 |
| Claude API(分类 + 回复 + 聚类) | ¥1,250 |
| n8n 自托管(Railway) | ¥35 |
| 飞书/钉钉 webhook | 免费 |
| **合计** | **约 ¥1,500/月** |

如果你 listing 月营收 ¥30 万,这套监控只占 **0.5%**——保险费率而已。

### 适合谁

- ✅ 亚马逊跨境卖家(美/欧/日站),5+ 个活跃 listing
- ✅ 跨境代运营机构,管多个卖家账号
- ✅ Shopify / TikTok Shop 出海卖家

### 想为你的店定制?

我专做跨境电商的 AI 自动化外包。本 demo 之外可定制:
- 多语言客服自动回复(英语 / 西班牙语 / 日语 / 德语)
- 多平台 listing 同步 + 关键词优化
- 销售数据 + 库存联动预警
- 红人/影响者外联自动化

联系方式:
- 💬 微信:`LHr20010725g`(加好友请备注 "Amazon卖家+店铺品类",无备注不通过)
- 🐛 GitHub Issue:https://github.com/lhrdsg6-debug/amazon-review-ai-monitor/issues

**当前免费 PoC 名额:5 位卖家**,只收取 Apify + Claude API 的实际成本(¥30-100),交换条件是允许我把脱敏后的成果写进案例。

---

## 🛠️ Setup (for developers)

### Prerequisites
- Python 3.10+
- Apify account (free $5 credit)
- Anthropic API key
- n8n cloud account (14-day trial) or self-hosted

### Quick start
```bash
git clone https://github.com/lhrdsg6-debug/amazon-review-ai-monitor
cd amazon-review-ai-monitor
cp .env.example .env  # fill in API keys
pip install -r requirements.txt

# Option A: Run Python pipeline standalone
python src/main.py --asins B09176JCKZ,B0C6KPRV8S,B081JSFHZK --region uk

# Option B: Import n8n-workflow.json into your n8n
# (then trigger manually or schedule via cron)
```

### Project structure
```
├── n8n-workflow.json           # Drop into n8n → Import workflow
├── src/                        # Python alternative (if not using n8n)
│   ├── apify_client.py
│   ├── classifier.py
│   ├── responder.py
│   ├── sheets_writer.py
│   └── feishu_notify.py
├── output/                     # Demo results (this run)
├── fixtures/                   # Raw scraped sample data
└── .env.example
```

### Key design decisions

**Why Amazon UK as default scraping region**
Amazon US blocks review text extraction as of 2025-26. UK/CA/DE still permit. Since Amazon aggregates global English reviews into UK store, you still capture ~90% of US buyer reviews via UK.

**Why human-in-the-loop**
Amazon ToS prohibits automated review responses. This system generates drafts; the seller must manually review and send. We optimized for "1-minute review per draft" — the bottleneck is review reading, not writing.

**Why Claude over GPT**
Claude's Chinese handling is meaningfully better for the bilingual reporting feature. Cost difference is negligible at this scale.

---

## ⚠️ Important caveats

- **Not a fully automated solution.** Amazon ToS requires human-sent responses.
- **AI errors happen.** Always review before sending.
- **Privacy.** Review text passes through LLM API; disclose in client contracts.
- **Build quality issues.** The system surfaces problems, it doesn't fix them. Engineering + supply-chain follow-up is on the seller.

---

## 📜 License
MIT License — see [LICENSE](./LICENSE)

## 🤝 Acknowledgments
Built with:
- [Anthropic Claude](https://claude.com) — Classification, response generation, clustering
- [Apify](https://apify.com) — Amazon review scraping (`web_wanderer/amazon-reviews-extractor`)
- [n8n](https://n8n.io) — Workflow orchestration

Inspired by real cross-border seller pain points observed in May 2026.
