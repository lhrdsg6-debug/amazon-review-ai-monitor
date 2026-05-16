"""生成可视化:Top 5 差评主题横向条形图(中文)"""
import json
import matplotlib.pyplot as plt
import matplotlib
from matplotlib import font_manager
import numpy as np
import os

# 字体处理(系统可能没中文字体,fallback 用英文标签)
matplotlib.rcParams['axes.unicode_minus'] = False

# 检测中文字体
chinese_font = None
for f in ['Noto Sans CJK SC', 'Source Han Sans SC', 'PingFang SC', 'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'AR PL UMing CN', 'SimHei', 'Microsoft YaHei']:
    fonts = [f.name for f in font_manager.fontManager.ttflist]
    if any(f in fn or fn in f for fn in fonts):
        chinese_font = f
        break

# 试着用 wqy
try:
    matplotlib.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
    chinese_font = 'WenQuanYi'
except:
    pass

print(f"Using font: {matplotlib.rcParams['font.sans-serif']}")

clusters = json.load(open('/home/claude/amazon-review-monitor/output/theme-clusters.json'))['themes_ranked']

# 中英双标签(防中文字体加载失败)
theme_labels_cn = [
    "设计缺陷\n使用体验反人类",
    "虚假宣传\n实物与listing不符",
    "制造质量差\n拉链/卡扣/接缝失效",
    "产品寿命短\n几周-几个月就坏",
    "安全风险\n财产/人身损失"
]
theme_labels_en = [
    "Design Flaws\nPoor UX",
    "False Advertising\nMismatch w/ Listing",
    "Build Quality\nZipper/Clip/Seam Fail",
    "Short Lifespan\nBroken in Weeks-Months",
    "Safety Risk\nProperty/Personal Loss"
]
percentages = [c['percentage'] for c in clusters]
counts = [c['count'] for c in clusters]

# 各产品在该主题下的占比堆叠
asins = ['B09176JCKZ', 'B0C6KPRV8S', 'B081JSFHZK']
asin_labels = ['INIU 电池\nPower Bank', 'SURITCH 耳机壳\nBeats Case', 'BAGAIL 收纳袋\nPacking Cubes']
asin_data = np.array([[c['by_asin'][a] for c in clusters] for a in asins])

# 配色:差评主题用红橙色系
colors_asin = ['#E63946', '#F77F00', '#FCBF49']  # 红、橙、黄

# 创建图
fig, ax = plt.subplots(figsize=(14, 9), dpi=100)
fig.patch.set_facecolor('white')

y_pos = np.arange(len(theme_labels_cn))[::-1]  # 倒序让最大的在上面

# 堆叠条形图
left = np.zeros(len(theme_labels_cn))
bars = []
for i, asin in enumerate(asins):
    values = asin_data[i]
    bar = ax.barh(y_pos, values, left=left, color=colors_asin[i], 
                  edgecolor='white', linewidth=1.5, label=asin_labels[i],
                  height=0.65)
    bars.append(bar)
    left += values

# 数值标签(总数在最右边)
for i, (count, pct) in enumerate(zip(counts, percentages)):
    ax.text(count + 0.7, y_pos[i], f'{count} 条 / {pct}%', 
            va='center', fontsize=13, fontweight='bold', color='#2D3436')

# 每段堆叠的小标签(>=3 条才标)
left = np.zeros(len(theme_labels_cn))
for i, asin in enumerate(asins):
    values = asin_data[i]
    for j, v in enumerate(values):
        if v >= 3:
            ax.text(left[j] + v/2, y_pos[j], str(int(v)),
                   va='center', ha='center', fontsize=11, color='white',
                   fontweight='bold')
    left += values

# Y 轴标签(双语)
y_labels = [f"#{i+1}  {cn}\n{en}" for i, (cn, en) in enumerate(zip(theme_labels_cn, theme_labels_en))]
ax.set_yticks(y_pos)
ax.set_yticklabels(y_labels, fontsize=11)

# 标题
fig.suptitle('Top 5 差评原因聚类  |  Top 5 Negative Review Themes',
             fontsize=18, fontweight='bold', y=0.97, color='#1D3557')
ax.set_title('基于 3 个亚马逊中国卖家产品 · 90 条 1-3 星 review · 抓取耗时 38s · 成本 $0.09',
             fontsize=11, color='#636e72', pad=15)

# X 轴
ax.set_xlabel('Review 数量(总样本 90 条)| Number of Reviews (n=90)',
              fontsize=12, color='#2D3436')
ax.set_xlim(0, max(counts) + 8)
ax.grid(True, axis='x', alpha=0.3, linestyle='--')
ax.set_axisbelow(True)

# 图例
legend = ax.legend(loc='lower right', frameon=True, fontsize=11,
                   title='产品 / Product', title_fontsize=12,
                   facecolor='#F8F9FA', edgecolor='#DEE2E6')

# 去掉顶部和右侧边框
for spine in ['top', 'right']:
    ax.spines[spine].set_visible(False)
ax.spines['left'].set_color('#DEE2E6')
ax.spines['bottom'].set_color('#DEE2E6')

# 底部 footer
fig.text(0.5, 0.02,
         'Data: Apify (web_wanderer/amazon-reviews-extractor) · '
         'Classification: Anthropic Claude · '
         'Pipeline: n8n + Apify + Claude API',
         ha='center', fontsize=9, color='#95a5a6', style='italic')

plt.tight_layout(rect=[0, 0.04, 1, 0.95])
plt.savefig('/home/claude/amazon-review-monitor/output/top5-negative-themes.png',
            dpi=120, bbox_inches='tight', facecolor='white')
print("✅ Saved: output/top5-negative-themes.png")
print(f"Image dimensions: ~{int(14*120)}x{int(9*120)} px")
