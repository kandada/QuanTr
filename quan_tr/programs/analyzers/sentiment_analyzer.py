# quan_tr/programs/analyzers/sentiment_analyzer.py
"""
情绪分析模块
用于分析股票相关的文本情绪，包括新闻、社交媒体、分析师报告等
支持中文和英文文本的情绪分析
"""

import os
import sys
import json
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import Counter
import pandas as pd
import numpy as np

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from quan_tr.config import config


class SentimentAnalyzer:
    """情绪分析器"""

    def __init__(self):
        """初始化情绪分析器"""
        self.config = config
        self.logger = self._setup_logger()

        # 加载情感词典
        self.positive_words = self._load_positive_words()
        self.negative_words = self._load_negative_words()
        self.intensifiers = self._load_intensifiers()
        self.negations = self._load_negations()

        self.logger.info("✅ 情绪分析器初始化成功")

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            log_file = self.config.base_dir / "logs" / "sentiment_analyzer.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _load_positive_words(self) -> set:
        """加载正面情感词典"""
        # 中文正面词
        chinese_positive = {
            "上涨",
            "增长",
            "利好",
            "优势",
            "突破",
            "强劲",
            "优秀",
            "良好",
            "稳定",
            "积极",
            "提升",
            "改善",
            "成功",
            "创新",
            "领先",
            "高效",
            "优质",
            "增值",
            "盈利",
            "收益",
            "买入",
            "推荐",
            "看好",
            "乐观",
            "信心",
            "扩张",
            "发展",
            "机遇",
            "潜力",
            "价值",
            "反弹",
            "回升",
            "升温",
            "火爆",
            "热捧",
            "追捧",
            "青睐",
            "看好",
            "增持",
            "重仓",
            "超预期",
            "历史新高",
            "业绩大增",
            "快速增长",
            "市场份额提升",
            "技术领先",
            "buy",
            "strong buy",
            "outperform",
            "overweight",
            "bullish",
            "positive",
            "growth",
            "profit",
            "gain",
            "rise",
            "surge",
            "rally",
            "boom",
            "breakthrough",
            "innovation",
            "leader",
            "advantage",
            "opportunity",
            "potential",
            "upgrade",
        }
        return chinese_positive

    def _load_negative_words(self) -> set:
        """加载负面情感词典"""
        # 中文负面词
        chinese_negative = {
            "下跌",
            "下降",
            "利空",
            "劣势",
            "跌破",
            "疲软",
            "糟糕",
            "恶化",
            "波动",
            "消极",
            "下滑",
            "衰退",
            "失败",
            "落后",
            "低效",
            "劣质",
            "贬值",
            "亏损",
            "损失",
            "债务",
            "卖出",
            "减持",
            "看空",
            "悲观",
            "担忧",
            "收缩",
            "风险",
            "危机",
            "泡沫",
            "高估",
            "暴跌",
            "重挫",
            "跳水",
            "崩盘",
            "恐慌",
            "逃离",
            "抛售",
            "清仓",
            "避雷",
            "谨慎",
            "不及预期",
            "历史新低",
            "业绩下滑",
            "增长放缓",
            "市场份额下降",
            "技术落后",
            "sell",
            "strong sell",
            "underperform",
            "underweight",
            "bearish",
            "negative",
            "decline",
            "loss",
            "fall",
            "drop",
            "crash",
            "slump",
            "recession",
            "risk",
            "debt",
            "bankruptcy",
            "crisis",
            "bubble",
            "overvalued",
            "downgrade",
            "warning",
        }
        return chinese_negative

    def _load_intensifiers(self) -> Dict[str, float]:
        """加载程度副词"""
        return {
            "非常": 1.5,
            "十分": 1.4,
            "特别": 1.4,
            "极其": 1.5,
            "极为": 1.5,
            "很": 1.3,
            "相当": 1.3,
            "显著": 1.3,
            "明显": 1.2,
            "比较": 1.1,
            "稍微": 0.8,
            "略": 0.8,
            "有点": 0.7,
            "略微": 0.8,
            "轻微": 0.7,
            "very": 1.5,
            "extremely": 1.5,
            "highly": 1.4,
            "quite": 1.2,
            "pretty": 1.2,
            "rather": 1.1,
            "somewhat": 0.8,
            "slightly": 0.7,
            "a bit": 0.7,
        }

    def _load_negations(self) -> set:
        """加载否定词"""
        return {
            "不",
            "没",
            "无",
            "未",
            "别",
            "勿",
            "否",
            "非",
            "莫",
            "弗",
            "没有",
            "不是",
            "不会",
            "不能",
            "不要",
            "不必",
            "未必",
            "难以",
            "not",
            "no",
            "never",
            "none",
            "nobody",
            "nothing",
            "neither",
            "nowhere",
            "don't",
            "doesn't",
            "didn't",
            "won't",
            "wouldn't",
            "can't",
            "cannot",
        }

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        分析单条文本的情绪

        Args:
            text: 待分析的文本

        Returns:
            情绪分析结果
        """
        if not text or not isinstance(text, str):
            return {
                "sentiment_score": 0,
                "sentiment_label": "neutral",
                "positive_words": [],
                "negative_words": [],
                "confidence": 0,
            }

        text = text.lower()

        # 分词（简单空格和标点分割）
        words = re.findall(r"\b\w+\b", text)

        positive_found = []
        negative_found = []

        i = 0
        while i < len(words):
            word = words[i]

            # 检查程度副词
            intensity = 1.0
            if i > 0 and words[i - 1] in self.intensifiers:
                intensity = self.intensifiers[words[i - 1]]

            # 检查否定词
            negation = False
            if i > 0 and words[i - 1] in self.negations:
                negation = True
            if i > 1 and words[i - 2] in self.negations:
                negation = True

            # 检查情感词
            if word in self.positive_words or any(
                pw in text for pw in self.positive_words if len(pw) > 2
            ):
                if negation:
                    negative_found.append((word, intensity))
                else:
                    positive_found.append((word, intensity))

            if word in self.negative_words or any(
                nw in text for nw in self.negative_words if len(nw) > 2
            ):
                if negation:
                    positive_found.append((word, intensity))
                else:
                    negative_found.append((word, intensity))

            i += 1

        # 计算情绪得分
        positive_score = sum(intensity for _, intensity in positive_found)
        negative_score = sum(intensity for _, intensity in negative_found)

        # 标准化得分到 -1 到 1
        total_words = len(words) if words else 1
        sentiment_score = (positive_score - negative_score) / max(total_words * 0.1, 1)
        sentiment_score = max(-1, min(1, sentiment_score))  # 限制在 -1 到 1

        # 确定情绪标签
        if sentiment_score > 0.2:
            sentiment_label = "positive"
        elif sentiment_score < -0.2:
            sentiment_label = "negative"
        else:
            sentiment_label = "neutral"

        # 计算置信度
        confidence = min(
            (positive_score + negative_score) / max(total_words * 0.05, 1), 1.0
        )

        return {
            "sentiment_score": round(sentiment_score, 3),
            "sentiment_label": sentiment_label,
            "positive_words": [w for w, _ in positive_found],
            "negative_words": [w for w, _ in negative_found],
            "positive_count": len(positive_found),
            "negative_count": len(negative_found),
            "confidence": round(confidence, 3),
        }

    def analyze_news(self, news_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析新闻情绪

        Args:
            news_list: 新闻列表，每项包含title, content等字段

        Returns:
            新闻情绪分析结果
        """
        if not news_list:
            return {
                "average_sentiment": 0,
                "sentiment_distribution": {},
                "article_analyses": [],
            }

        analyses = []
        sentiment_scores = []

        for article in news_list:
            # 合并标题和内容进行分析
            text = ""
            if isinstance(article, dict):
                text = f"{article.get('title', '')} {article.get('content', '')} {article.get('summary', '')}"
            elif isinstance(article, str):
                text = article

            analysis = self.analyze_text(text)
            analysis["source"] = (
                article.get("source", "") if isinstance(article, dict) else ""
            )
            analysis["date"] = (
                article.get("date", "") if isinstance(article, dict) else ""
            )

            analyses.append(analysis)
            sentiment_scores.append(analysis["sentiment_score"])

        # 计算平均情绪
        avg_sentiment = np.mean(sentiment_scores) if sentiment_scores else 0

        # 情绪分布
        labels = [a["sentiment_label"] for a in analyses]
        distribution = {
            "positive": labels.count("positive"),
            "neutral": labels.count("neutral"),
            "negative": labels.count("negative"),
        }

        return {
            "average_sentiment": round(avg_sentiment, 3),
            "sentiment_distribution": distribution,
            "article_count": len(news_list),
            "positive_ratio": round(distribution["positive"] / len(news_list), 3)
            if news_list
            else 0,
            "negative_ratio": round(distribution["negative"] / len(news_list), 3)
            if news_list
            else 0,
            "article_analyses": analyses,
        }

    def analyze_social_media(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析社交媒体情绪

        Args:
            posts: 社交媒体帖子列表

        Returns:
            社交媒体情绪分析结果
        """
        if not posts:
            return {
                "average_sentiment": 0,
                "sentiment_distribution": {},
                "buzz_score": 0,
                "discussion_volume": 0,
            }

        analyses = []
        sentiment_scores = []
        engagement_scores = []

        for post in posts:
            text = ""
            if isinstance(post, dict):
                text = post.get("content", "") or post.get("text", "")
                # 考虑互动数据（点赞、评论、转发）
                likes = post.get("likes", 0) or post.get("like_count", 0)
                comments = post.get("comments", 0) or post.get("comment_count", 0)
                shares = (
                    post.get("shares", 0)
                    or post.get("share_count", 0)
                    or post.get("retweets", 0)
                )
                engagement = likes + comments * 2 + shares * 3  # 加权计算
            else:
                text = str(post)
                engagement = 1

            analysis = self.analyze_text(text)
            analysis["engagement"] = engagement

            analyses.append(analysis)
            sentiment_scores.append(analysis["sentiment_score"])
            engagement_scores.append(engagement)

        # 加权平均情绪（考虑互动量）
        if sentiment_scores and engagement_scores:
            weighted_sentiment = np.average(sentiment_scores, weights=engagement_scores)
        else:
            weighted_sentiment = 0

        # 情绪分布
        labels = [a["sentiment_label"] for a in analyses]
        distribution = {
            "positive": labels.count("positive"),
            "neutral": labels.count("neutral"),
            "negative": labels.count("negative"),
        }

        # 热度评分（总互动量）
        total_engagement = sum(engagement_scores)
        buzz_score = min(total_engagement / 1000, 100)  # 标准化到0-100

        return {
            "average_sentiment": round(weighted_sentiment, 3),
            "sentiment_distribution": distribution,
            "buzz_score": round(buzz_score, 2),
            "discussion_volume": len(posts),
            "total_engagement": total_engagement,
            "post_analyses": analyses[:10],  # 只保留前10条详细分析
        }

    def analyze_analyst_reports(self, reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析分析师报告情绪

        Args:
            reports: 分析师报告列表

        Returns:
            分析师情绪分析结果
        """
        if not reports:
            return {
                "average_sentiment": 0,
                "rating_distribution": {},
                "consensus_rating": "neutral",
                "target_price_stats": {},
            }

        ratings = []
        sentiments = []
        target_prices = []

        for report in reports:
            if isinstance(report, dict):
                # 分析评级文本
                rating = report.get("rating", "")
                if rating:
                    ratings.append(rating.lower())

                    # 将评级转换为情绪分数
                    rating_sentiment = {
                        "strong buy": 1.0,
                        "buy": 0.8,
                        "outperform": 0.6,
                        "overweight": 0.6,
                        "hold": 0.0,
                        "neutral": 0.0,
                        "market perform": 0.0,
                        "sell": -0.8,
                        "strong sell": -1.0,
                        "underperform": -0.6,
                        "underweight": -0.6,
                    }
                    sentiment = rating_sentiment.get(rating.lower(), 0)
                    sentiments.append(sentiment)

                # 分析报告内容
                content = report.get("content", "") or report.get("summary", "")
                if content:
                    text_analysis = self.analyze_text(content)
                    sentiments.append(text_analysis["sentiment_score"])

                # 目标价格
                target = report.get("target_price", 0)
                if target:
                    target_prices.append(target)

        # 计算平均情绪
        avg_sentiment = np.mean(sentiments) if sentiments else 0

        # 评级分布
        rating_dist = Counter(ratings)

        # 共识评级
        if rating_dist:
            consensus = rating_dist.most_common(1)[0][0]
        else:
            consensus = "neutral"

        # 目标价格统计
        target_stats = {}
        if target_prices:
            target_stats = {
                "min": min(target_prices),
                "max": max(target_prices),
                "average": round(np.mean(target_prices), 2),
                "median": round(np.median(target_prices), 2),
            }

        return {
            "average_sentiment": round(avg_sentiment, 3),
            "rating_distribution": dict(rating_dist),
            "consensus_rating": consensus,
            "report_count": len(reports),
            "target_price_stats": target_stats,
        }

    def calculate_sentiment_score(self, sentiment_results: Dict[str, Any]) -> float:
        """
        计算综合情绪评分（0-100分）

        Args:
            sentiment_results: 情绪分析结果

        Returns:
            综合评分
        """
        scores = []
        weights = []

        # 新闻情绪权重 40%
        if "news_sentiment" in sentiment_results:
            news_score = sentiment_results["news_sentiment"].get("average_sentiment", 0)
            scores.append((news_score + 1) * 50)  # 转换到0-100
            weights.append(0.4)

        # 社交媒体情绪权重 30%
        if "social_sentiment" in sentiment_results:
            social_score = sentiment_results["social_sentiment"].get(
                "average_sentiment", 0
            )
            scores.append((social_score + 1) * 50)
            weights.append(0.3)

        # 分析师情绪权重 30%
        if "analyst_sentiment" in sentiment_results:
            analyst_score = sentiment_results["analyst_sentiment"].get(
                "average_sentiment", 0
            )
            scores.append((analyst_score + 1) * 50)
            weights.append(0.3)

        if scores and weights:
            # 加权平均
            total_weight = sum(weights)
            weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
            return round(weighted_score, 1)

        return 50.0  # 默认中性

    def analyze_all(
        self,
        news: Optional[List[Dict]] = None,
        social_posts: Optional[List[Dict]] = None,
        analyst_reports: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        执行完整的情绪分析

        Args:
            news: 新闻列表
            social_posts: 社交媒体帖子列表
            analyst_reports: 分析师报告列表

        Returns:
            完整的情绪分析结果
        """
        self.logger.info("开始情绪分析...")

        results = {}

        # 分析新闻
        if news:
            self.logger.info(f"分析 {len(news)} 条新闻...")
            results["news_sentiment"] = self.analyze_news(news)

        # 分析社交媒体
        if social_posts:
            self.logger.info(f"分析 {len(social_posts)} 条社交媒体帖子...")
            results["social_sentiment"] = self.analyze_social_media(social_posts)

        # 分析分析师报告
        if analyst_reports:
            self.logger.info(f"分析 {len(analyst_reports)} 份分析师报告...")
            results["analyst_sentiment"] = self.analyze_analyst_reports(analyst_reports)

        # 计算综合评分
        overall_score = self.calculate_sentiment_score(results)
        results["overall_score"] = overall_score

        # 确定整体情绪标签
        if overall_score >= 60:
            sentiment_label = "positive"
        elif overall_score <= 40:
            sentiment_label = "negative"
        else:
            sentiment_label = "neutral"

        results["sentiment_label"] = sentiment_label
        results["analysis_time"] = datetime.now().isoformat()

        self.logger.info(
            f"✅ 情绪分析完成: 评分={overall_score}, 情绪={sentiment_label}"
        )

        return results

    def generate_sentiment_report(self, symbol: str, results: Dict[str, Any]) -> str:
        """生成情绪分析报告"""

        report = f"""# 情绪分析报告 - {symbol}

**分析时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**分析工具**: QuanTr Sentiment Analyzer

## 1. 情绪总览

**综合情绪评分**: {results.get("overall_score", 0)}/100
**整体情绪**: {results.get("sentiment_label", "neutral").upper()}

"""

        # 新闻情绪
        if "news_sentiment" in results:
            news = results["news_sentiment"]
            report += f"""
## 2. 新闻情绪分析

**平均情绪**: {news.get("average_sentiment", 0):.3f} (-1到1，越高越正面)
**文章数量**: {news.get("article_count", 0)}

### 情绪分布
- 正面: {news.get("sentiment_distribution", {}).get("positive", 0)} 篇 ({news.get("positive_ratio", 0) * 100:.1f}%)
- 中性: {news.get("sentiment_distribution", {}).get("neutral", 0)} 篇
- 负面: {news.get("sentiment_distribution", {}).get("negative", 0)} 篇 ({news.get("negative_ratio", 0) * 100:.1f}%)

"""

        # 社交媒体情绪
        if "social_sentiment" in results:
            social = results["social_sentiment"]
            report += f"""
## 3. 社交媒体情绪分析

**平均情绪**: {social.get("average_sentiment", 0):.3f}
**讨论热度**: {social.get("buzz_score", 0)}/100
**讨论量**: {social.get("discussion_volume", 0)} 条
**总互动**: {social.get("total_engagement", 0)}

### 情绪分布
- 正面: {social.get("sentiment_distribution", {}).get("positive", 0)} 条
- 中性: {social.get("sentiment_distribution", {}).get("neutral", 0)} 条
- 负面: {social.get("sentiment_distribution", {}).get("negative", 0)} 条

"""

        # 分析师情绪
        if "analyst_sentiment" in results:
            analyst = results["analyst_sentiment"]
            report += f"""
## 4. 分析师情绪分析

**平均情绪**: {analyst.get("average_sentiment", 0):.3f}
**共识评级**: {analyst.get("consensus_rating", "neutral").upper()}
**报告数量**: {analyst.get("report_count", 0)} 份

### 评级分布
"""
            for rating, count in analyst.get("rating_distribution", {}).items():
                report += f"- {rating}: {count} 份\n"

            target_stats = analyst.get("target_price_stats", {})
            if target_stats:
                report += f"""
### 目标价格统计
- 最低: ¥{target_stats.get("min", 0):.2f}
- 最高: ¥{target_stats.get("max", 0):.2f}
- 平均: ¥{target_stats.get("average", 0):.2f}
- 中位数: ¥{target_stats.get("median", 0):.2f}
"""

        # 结论
        report += """
## 5. 情绪分析结论

"""

        sentiment = results.get("sentiment_label", "neutral")
        if sentiment == "positive":
            report += """**市场情绪积极**

- 媒体和投资者对股票持乐观态度
- 新闻和社交媒体讨论偏向正面
- 分析师普遍看好
- 注意：情绪过热可能存在回调风险
"""
        elif sentiment == "negative":
            report += """**市场情绪消极**

- 媒体和投资者对股票持谨慎态度
- 负面消息较多，需关注风险
- 分析师评级偏低
- 可能是逆向投资的机会
"""
        else:
            report += """**市场情绪中性**

- 市场情绪较为平衡
- 多空观点交织
- 建议关注基本面和技术面信号
- 等待更明确的市场方向
"""

        report += """
---
*本报告由QuanTr系统自动生成，仅供参考，不构成投资建议。*
"""

        return report


def main():
    """主函数，用于测试"""
    analyzer = SentimentAnalyzer()

    print("🔍 开始测试情绪分析器...")
    print("=" * 60)

    # 测试文本分析
    print("\n1. 测试文本情绪分析...")
    test_texts = [
        "该公司业绩超预期，股价大幅上涨，前景看好",
        "业绩不及预期，股价暴跌，投资者恐慌抛售",
        "公司基本面稳定，市场表现平淡",
        "This company shows strong growth potential and innovation",
        "The stock crashed due to poor earnings report",
    ]

    for text in test_texts:
        result = analyzer.analyze_text(text)
        print(f"   文本: {text[:40]}...")
        print(
            f"   情绪: {result['sentiment_label']} (得分: {result['sentiment_score']})"
        )

    # 测试新闻分析
    print("\n2. 测试新闻情绪分析...")
    sample_news = [
        {
            "title": "平安银行发布优异年报",
            "content": "业绩增长强劲，前景看好",
            "source": "新浪财经",
        },
        {
            "title": "市场震荡调整",
            "content": "短期波动属正常现象",
            "source": "证券时报",
        },
        {
            "title": "某股票遭遇重大利空",
            "content": "业绩大幅下滑，投资者担忧",
            "source": "东方财富",
        },
    ]

    news_result = analyzer.analyze_news(sample_news)
    print(f"   平均情绪: {news_result['average_sentiment']}")
    print(f"   情绪分布: {news_result['sentiment_distribution']}")

    # 测试社交媒体分析
    print("\n3. 测试社交媒体情绪分析...")
    sample_posts = [
        {"content": "这只股票太棒了！强烈买入！", "likes": 100, "comments": 20},
        {"content": "不太看好，先观望一下", "likes": 50, "comments": 10},
        {"content": "跌惨了，要不要割肉？", "likes": 80, "comments": 30},
    ]

    social_result = analyzer.analyze_social_media(sample_posts)
    print(f"   平均情绪: {social_result['average_sentiment']}")
    print(f"   热度评分: {social_result['buzz_score']}")

    # 测试完整分析
    print("\n4. 测试完整分析流程...")
    full_result = analyzer.analyze_all(
        news=sample_news,
        social_posts=sample_posts,
    )

    print(f"   综合评分: {full_result['overall_score']}/100")
    print(f"   整体情绪: {full_result['sentiment_label']}")

    # 生成报告
    print("\n5. 生成情绪分析报告...")
    report = analyzer.generate_sentiment_report("000001.SZ", full_result)
    print(f"   报告长度: {len(report)} 字符")
    print("\n报告预览（前500字符）:")
    print("-" * 60)
    print(report[:500])
    print("...")
    print("-" * 60)

    print("\n✅ 情绪分析器测试完成!")


if __name__ == "__main__":
    main()
