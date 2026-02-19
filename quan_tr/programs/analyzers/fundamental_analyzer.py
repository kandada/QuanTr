# programs/analyzers/fundamental_analyzer.py
"""
基本面分析程序
用于分析股票的基本面情况，包括财务指标、公司经营、行业分析等
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from quan_tr.config import config


class FundamentalAnalyzer:
    """基本面分析器"""

    def __init__(self):
        """初始化基本面分析器"""
        self.config = config
        self.logger = self._setup_logger()
        self.logger.info("✅ 基本面分析器初始化成功")

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)

        # 避免重复添加处理器
        if not logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # 文件处理器
            log_file = self.config.base_dir / "logs" / "fundamental_analyzer.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def analyze_financial_metrics(
        self, financial_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """
        分析财务指标

        Args:
            financial_data: 财务数据字典，包含资产负债表、利润表、现金流量表

        Returns:
            财务指标分析结果
        """
        analysis_results = {
            "profitability": {},  # 盈利能力
            "liquidity": {},  # 流动性
            "solvency": {},  # 偿债能力
            "efficiency": {},  # 运营效率
            "growth": {},  # 成长能力
            "valuation": {},  # 估值指标
        }

        try:
            # 提取财务报表
            balance_sheet = financial_data.get("balance_sheet")
            income_statement = financial_data.get("income_statement")
            cash_flow = financial_data.get("cash_flow")

            if balance_sheet is None or income_statement is None:
                self.logger.warning("财务报表数据不完整")
                return analysis_results

            # 获取最新一期数据
            latest_balance = self._get_latest_period_data(balance_sheet)
            latest_income = self._get_latest_period_data(income_statement)

            if latest_balance.empty or latest_income.empty:
                self.logger.warning("无法获取最新财务数据")
                return analysis_results

            # 1. 盈利能力分析
            analysis_results["profitability"] = self._analyze_profitability(
                latest_income, latest_balance
            )

            # 2. 流动性分析
            analysis_results["liquidity"] = self._analyze_liquidity(latest_balance)

            # 3. 偿债能力分析
            analysis_results["solvency"] = self._analyze_solvency(latest_balance)

            # 4. 运营效率分析
            analysis_results["efficiency"] = self._analyze_efficiency(
                latest_income, latest_balance
            )

            # 5. 成长能力分析（需要多期数据）
            if len(income_statement) > 1:
                analysis_results["growth"] = self._analyze_growth(
                    income_statement, balance_sheet
                )

            self.logger.info("✅ 财务指标分析完成")

        except Exception as e:
            self.logger.error(f"❌ 财务指标分析失败: {e}")

        return analysis_results

    def _get_latest_period_data(self, df: pd.DataFrame) -> pd.Series:
        """获取最新一期数据"""
        if df.empty:
            return pd.Series()

        # 假设第一列是报告期
        if len(df.columns) > 0:
            date_col = df.columns[0]
            # 将列名转换为字符串以确保类型安全
            df_sorted = df.sort_values(by=str(date_col), ascending=False)

            # 返回最新一期的数据
            return df_sorted.iloc[0]
        else:
            return pd.Series()

    def _analyze_profitability(
        self, income: pd.Series, balance: pd.Series
    ) -> Dict[str, float]:
        """分析盈利能力"""
        profitability = {}

        try:
            # 毛利率 = (营业收入 - 营业成本) / 营业收入
            if "营业收入" in income and "营业成本" in income:
                revenue = self._parse_numeric(income["营业收入"])
                cost = self._parse_numeric(income["营业成本"])
                if revenue != 0:
                    profitability["gross_margin"] = (revenue - cost) / revenue * 100

            # 净利率 = 净利润 / 营业收入
            if "净利润" in income and "营业收入" in income:
                net_profit = self._parse_numeric(income["净利润"])
                revenue = self._parse_numeric(income["营业收入"])
                if revenue != 0:
                    profitability["net_margin"] = net_profit / revenue * 100

            # ROE = 净利润 / 净资产
            if "净利润" in income and "所有者权益合计" in balance:
                net_profit = self._parse_numeric(income["净利润"])
                equity = self._parse_numeric(balance["所有者权益合计"])
                if equity != 0:
                    profitability["roe"] = net_profit / equity * 100

            # ROA = 净利润 / 总资产
            if "净利润" in income and "资产总计" in balance:
                net_profit = self._parse_numeric(income["净利润"])
                total_assets = self._parse_numeric(balance["资产总计"])
                if total_assets != 0:
                    profitability["roa"] = net_profit / total_assets * 100

        except Exception as e:
            self.logger.warning(f"盈利能力分析失败: {e}")

        return profitability

    def _analyze_liquidity(self, balance: pd.Series) -> Dict[str, float]:
        """分析流动性"""
        liquidity = {}

        try:
            # 流动比率 = 流动资产 / 流动负债
            if "流动资产合计" in balance and "流动负债合计" in balance:
                current_assets = self._parse_numeric(balance["流动资产合计"])
                current_liabilities = self._parse_numeric(balance["流动负债合计"])
                if current_liabilities != 0:
                    liquidity["current_ratio"] = current_assets / current_liabilities

            # 速动比率 = (流动资产 - 存货) / 流动负债
            if (
                "流动资产合计" in balance
                and "存货" in balance
                and "流动负债合计" in balance
            ):
                current_assets = self._parse_numeric(balance["流动资产合计"])
                inventory = self._parse_numeric(balance["存货"])
                current_liabilities = self._parse_numeric(balance["流动负债合计"])
                if current_liabilities != 0:
                    liquidity["quick_ratio"] = (
                        current_assets - inventory
                    ) / current_liabilities

            # 现金比率 = 货币资金 / 流动负债
            if "货币资金" in balance and "流动负债合计" in balance:
                cash = self._parse_numeric(balance["货币资金"])
                current_liabilities = self._parse_numeric(balance["流动负债合计"])
                if current_liabilities != 0:
                    liquidity["cash_ratio"] = cash / current_liabilities

        except Exception as e:
            self.logger.warning(f"流动性分析失败: {e}")

        return liquidity

    def _analyze_solvency(self, balance: pd.Series) -> Dict[str, float]:
        """分析偿债能力"""
        solvency = {}

        try:
            # 资产负债率 = 总负债 / 总资产
            if "负债合计" in balance and "资产总计" in balance:
                total_liabilities = self._parse_numeric(balance["负债合计"])
                total_assets = self._parse_numeric(balance["资产总计"])
                if total_assets != 0:
                    solvency["debt_to_assets"] = total_liabilities / total_assets * 100

            # 权益乘数 = 总资产 / 净资产
            if "资产总计" in balance and "所有者权益合计" in balance:
                total_assets = self._parse_numeric(balance["资产总计"])
                equity = self._parse_numeric(balance["所有者权益合计"])
                if equity != 0:
                    solvency["equity_multiplier"] = total_assets / equity

            # 利息保障倍数 = (利润总额 + 利息费用) / 利息费用
            # 注意：需要利润表和利息费用数据

        except Exception as e:
            self.logger.warning(f"偿债能力分析失败: {e}")

        return solvency

    def _analyze_efficiency(
        self, income: pd.Series, balance: pd.Series
    ) -> Dict[str, float]:
        """分析运营效率"""
        efficiency = {}

        try:
            # 总资产周转率 = 营业收入 / 平均总资产
            # 这里简化使用期末总资产
            if "营业收入" in income and "资产总计" in balance:
                revenue = self._parse_numeric(income["营业收入"])
                total_assets = self._parse_numeric(balance["资产总计"])
                if total_assets != 0:
                    efficiency["asset_turnover"] = revenue / total_assets

            # 存货周转率 = 营业成本 / 平均存货
            if "营业成本" in income and "存货" in balance:
                cost = self._parse_numeric(income["营业成本"])
                inventory = self._parse_numeric(balance["存货"])
                if inventory != 0:
                    efficiency["inventory_turnover"] = cost / inventory

            # 应收账款周转率 = 营业收入 / 平均应收账款
            if "营业收入" in income and "应收账款" in balance:
                revenue = self._parse_numeric(income["营业收入"])
                receivables = self._parse_numeric(balance["应收账款"])
                if receivables != 0:
                    efficiency["receivables_turnover"] = revenue / receivables

        except Exception as e:
            self.logger.warning(f"运营效率分析失败: {e}")

        return efficiency

    def _analyze_growth(
        self, income_statement: pd.DataFrame, balance_sheet: pd.DataFrame
    ) -> Dict[str, float]:
        """分析成长能力"""
        growth = {}

        try:
            # 获取最近两期数据
            if len(income_statement.columns) > 0:
                date_col = str(income_statement.columns[0])
                income_sorted = income_statement.sort_values(
                    by=date_col, ascending=False
                )
                balance_sorted = balance_sheet.sort_values(by=date_col, ascending=False)
            else:
                return growth

            if len(income_sorted) < 2 or len(balance_sorted) < 2:
                return growth

            # 最近两期数据
            income_latest = income_sorted.iloc[0]
            income_previous = income_sorted.iloc[1]
            balance_latest = balance_sorted.iloc[0]
            balance_previous = balance_sorted.iloc[1]

            # 营收增长率
            if "营业收入" in income_latest and "营业收入" in income_previous:
                revenue_latest = self._parse_numeric(income_latest["营业收入"])
                revenue_previous = self._parse_numeric(income_previous["营业收入"])
                if revenue_previous != 0:
                    growth["revenue_growth"] = (
                        (revenue_latest - revenue_previous) / revenue_previous * 100
                    )

            # 净利润增长率
            if "净利润" in income_latest and "净利润" in income_previous:
                profit_latest = self._parse_numeric(income_latest["净利润"])
                profit_previous = self._parse_numeric(income_previous["净利润"])
                if profit_previous != 0:
                    growth["profit_growth"] = (
                        (profit_latest - profit_previous) / profit_previous * 100
                    )

            # 净资产增长率
            if (
                "所有者权益合计" in balance_latest
                and "所有者权益合计" in balance_previous
            ):
                equity_latest = self._parse_numeric(balance_latest["所有者权益合计"])
                equity_previous = self._parse_numeric(
                    balance_previous["所有者权益合计"]
                )
                if equity_previous != 0:
                    growth["equity_growth"] = (
                        (equity_latest - equity_previous) / equity_previous * 100
                    )

            # 总资产增长率
            if "资产总计" in balance_latest and "资产总计" in balance_previous:
                assets_latest = self._parse_numeric(balance_latest["资产总计"])
                assets_previous = self._parse_numeric(balance_previous["资产总计"])
                if assets_previous != 0:
                    growth["assets_growth"] = (
                        (assets_latest - assets_previous) / assets_previous * 100
                    )

        except Exception as e:
            self.logger.warning(f"成长能力分析失败: {e}")

        return growth

    def _parse_numeric(self, value: Any) -> float:
        """解析数值，处理字符串中的逗号等"""
        if pd.isna(value):
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            # 移除逗号、空格等
            cleaned = value.replace(",", "").replace(" ", "")
            try:
                return float(cleaned)
            except ValueError:
                return 0.0

        return 0.0

    def analyze_company_operations(self, basic_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析公司经营情况

        Args:
            basic_info: 股票基本信息

        Returns:
            公司经营分析结果
        """
        operations_analysis = {
            "company_profile": {},
            "industry_position": {},
            "management_quality": {},
            "competitive_advantage": {},
        }

        try:
            # 公司概况
            operations_analysis["company_profile"] = {
                "company_name": basic_info.get("股票简称", "N/A"),
                "industry": basic_info.get("所属行业", "N/A"),
                "listing_date": basic_info.get("上市时间", "N/A"),
                "market_cap": basic_info.get("总市值", "N/A"),
                "pe_ratio": basic_info.get("市盈率", "N/A"),
            }

            # 行业地位分析（简化版）
            industry = basic_info.get("所属行业", "")
            operations_analysis["industry_position"] = {
                "industry": industry,
                "position": "待分析",  # 需要行业数据对比
                "growth_prospects": "待分析",
            }

            # 管理层质量（简化版）
            operations_analysis["management_quality"] = {
                "stability": "待分析",
                "experience": "待分析",
                "reputation": "待分析",
            }

            # 竞争优势（简化版）
            operations_analysis["competitive_advantage"] = {
                "moat_type": "待分析",  # 护城河类型
                "strength": "待分析",  # 竞争优势强度
                "sustainability": "待分析",  # 可持续性
            }

            self.logger.info("✅ 公司经营分析完成")

        except Exception as e:
            self.logger.error(f"❌ 公司经营分析失败: {e}")

        return operations_analysis

    def analyze_industry_trends(self, industry: str) -> Dict[str, Any]:
        """
        分析行业趋势

        Args:
            industry: 行业名称

        Returns:
            行业趋势分析结果
        """
        industry_analysis = {
            "industry_overview": {},
            "growth_prospects": {},
            "competitive_landscape": {},
            "regulatory_environment": {},
        }

        try:
            # 行业概况（简化版）
            industry_analysis["industry_overview"] = {
                "industry_name": industry,
                "lifecycle_stage": "待分析",  # 生命周期阶段
                "market_size": "待分析",  # 市场规模
                "growth_rate": "待分析",  # 增长率
            }

            # 增长前景（简化版）
            industry_analysis["growth_prospects"] = {
                "short_term": "待分析",
                "medium_term": "待分析",
                "long_term": "待分析",
            }

            # 竞争格局（简化版）
            industry_analysis["competitive_landscape"] = {
                "competition_intensity": "待分析",
                "market_concentration": "待分析",
                "barriers_to_entry": "待分析",
            }

            # 监管环境（简化版）
            industry_analysis["regulatory_environment"] = {
                "regulatory_trends": "待分析",
                "policy_support": "待分析",
                "compliance_requirements": "待分析",
            }

            self.logger.info(f"✅ 行业趋势分析完成: {industry}")

        except Exception as e:
            self.logger.error(f"❌ 行业趋势分析失败: {e}")

        return industry_analysis

    def analyze_macroeconomic_factors(self) -> Dict[str, Any]:
        """
        分析宏观经济因素

        Returns:
            宏观经济分析结果
        """
        macro_analysis = {
            "economic_cycle": {},
            "monetary_policy": {},
            "fiscal_policy": {},
            "inflation_trends": {},
            "exchange_rates": {},
        }

        try:
            # 经济周期（简化版）
            macro_analysis["economic_cycle"] = {
                "current_phase": "待分析",
                "gdp_growth": "待分析",
                "unemployment_rate": "待分析",
            }

            # 货币政策（简化版）
            macro_analysis["monetary_policy"] = {
                "interest_rate_trend": "待分析",
                "liquidity_conditions": "待分析",
                "policy_stance": "待分析",
            }

            # 财政政策（简化版）
            macro_analysis["fiscal_policy"] = {
                "government_spending": "待分析",
                "tax_policies": "待分析",
                "deficit_level": "待分析",
            }

            # 通胀趋势（简化版）
            macro_analysis["inflation_trends"] = {
                "cpi": "待分析",
                "ppi": "待分析",
                "inflation_expectations": "待分析",
            }

            # 汇率（简化版）
            macro_analysis["exchange_rates"] = {
                "usd_cny": "待分析",
                "trend": "待分析",
                "volatility": "待分析",
            }

            self.logger.info("✅ 宏观经济分析完成")

        except Exception as e:
            self.logger.error(f"❌ 宏观经济分析失败: {e}")

        return macro_analysis

    def generate_fundamental_score(
        self, analysis_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成基本面综合评分

        Args:
            analysis_results: 各项分析结果

        Returns:
            综合评分结果
        """
        score_results = {
            "financial_score": 0.0,
            "operations_score": 0.0,
            "industry_score": 0.0,
            "macro_score": 0.0,
            "total_score": 0.0,
            "rating": "待评估",
            "weighted_breakdown": {},
        }

        try:
            # 财务指标评分（简化版）
            financial_metrics = analysis_results.get("financial_metrics", {})
            financial_score = self._score_financial_metrics(financial_metrics)

            # 公司经营评分（简化版）
            operations_analysis = analysis_results.get("operations_analysis", {})
            operations_score = self._score_company_operations(operations_analysis)

            # 行业趋势评分（简化版）
            industry_analysis = analysis_results.get("industry_analysis", {})
            industry_score = self._score_industry_trends(industry_analysis)

            # 宏观经济评分（简化版）
            macro_analysis = analysis_results.get("macro_analysis", {})
            macro_score = self._score_macroeconomic_factors(macro_analysis)

            # 权重配置
            weights = {
                "financial": self.config.get("analysis.fundamental_weight", 0.4),
                "operations": 0.3,
                "industry": 0.2,
                "macro": 0.1,
            }

            # 计算加权总分
            total_score = (
                financial_score * weights["financial"]
                + operations_score * weights["operations"]
                + industry_score * weights["industry"]
                + macro_score * weights["macro"]
            )

            # 确定评级
            rating = self._determine_rating(total_score)

            score_results.update(
                {
                    "financial_score": financial_score,
                    "operations_score": operations_score,
                    "industry_score": industry_score,
                    "macro_score": macro_score,
                    "total_score": total_score,
                    "rating": rating,
                    "weighted_breakdown": {
                        "financial": {
                            "score": financial_score,
                            "weight": weights["financial"],
                            "weighted_score": financial_score * weights["financial"],
                        },
                        "operations": {
                            "score": operations_score,
                            "weight": weights["operations"],
                            "weighted_score": operations_score * weights["operations"],
                        },
                        "industry": {
                            "score": industry_score,
                            "weight": weights["industry"],
                            "weighted_score": industry_score * weights["industry"],
                        },
                        "macro": {
                            "score": macro_score,
                            "weight": weights["macro"],
                            "weighted_score": macro_score * weights["macro"],
                        },
                    },
                }
            )

            self.logger.info(f"✅ 基本面综合评分完成: {total_score:.1f} ({rating})")

        except Exception as e:
            self.logger.error(f"❌ 基本面综合评分失败: {e}")

        return score_results

    def _score_financial_metrics(self, financial_metrics: Dict) -> float:
        """财务指标评分（简化版）"""
        # 这里实现简化的评分逻辑
        # 实际应用中需要更复杂的评分模型
        return 70.0  # 示例分数

    def _score_company_operations(self, operations_analysis: Dict) -> float:
        """公司经营评分（简化版）"""
        return 65.0  # 示例分数

    def _score_industry_trends(self, industry_analysis: Dict) -> float:
        """行业趋势评分（简化版）"""
        return 75.0  # 示例分数

    def _score_macroeconomic_factors(self, macro_analysis: Dict) -> float:
        """宏观经济评分（简化版）"""
        return 60.0  # 示例分数

    def _determine_rating(self, score: float) -> str:
        """根据分数确定评级"""
        thresholds = self.config.get("analysis.scoring_thresholds", {})

        if score >= thresholds.get("strong_buy", 80):
            return "strong_buy"
        elif score >= thresholds.get("buy", 60):
            return "buy"
        elif score >= thresholds.get("hold", 40):
            return "hold"
        elif score >= thresholds.get("sell", 20):
            return "sell"
        else:
            return "strong_sell"

    def generate_fundamental_report(
        self, symbol: str, analysis_results: Dict[str, Any]
    ) -> str:
        """
        生成基本面分析报告

        Args:
            symbol: 股票代码
            analysis_results: 分析结果

        Returns:
            Markdown格式的报告
        """
        try:
            report = f"""# 基本面分析报告 - {symbol}

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**分析工具**: QuanTr Fundamental Analyzer

## 1. 财务指标分析

### 盈利能力
"""

            # 添加财务指标
            financial_metrics = analysis_results.get("financial_metrics", {})
            profitability = financial_metrics.get("profitability", {})

            for metric, value in profitability.items():
                report += f"- **{metric}**: {value:.2f}%\n"

            report += """
### 流动性指标
"""
            liquidity = financial_metrics.get("liquidity", {})
            for metric, value in liquidity.items():
                report += f"- **{metric}**: {value:.2f}\n"

            report += """
### 偿债能力
"""
            solvency = financial_metrics.get("solvency", {})
            for metric, value in solvency.items():
                report += f"- **{metric}**: {value:.2f}%\n"

            report += """
## 2. 公司经营分析
"""
            operations = analysis_results.get("operations_analysis", {})
            company_profile = operations.get("company_profile", {})

            for key, value in company_profile.items():
                report += f"- **{key}**: {value}\n"

            report += """
## 3. 行业趋势分析
"""
            industry = analysis_results.get("industry_analysis", {})
            industry_overview = industry.get("industry_overview", {})

            for key, value in industry_overview.items():
                report += f"- **{key}**: {value}\n"

            report += """
## 4. 综合评分

"""
            scores = analysis_results.get("fundamental_score", {})
            total_score = scores.get("total_score", 0)
            rating = scores.get("rating", "待评估")

            report += f"**综合评分**: {total_score:.1f}/100\n"
            report += f"**评级**: {rating}\n"

            report += """
### 评分明细
"""
            weighted_breakdown = scores.get("weighted_breakdown", {})
            for category, details in weighted_breakdown.items():
                score = details.get("score", 0)
                weight = details.get("weight", 0)
                weighted = details.get("weighted_score", 0)
                report += (
                    f"- **{category}**: {score:.1f} × {weight:.1%} = {weighted:.1f}\n"
                )

            report += """
## 5. 投资建议

基于基本面分析，建议如下：

1. **优势**:
   - 财务指标稳健
   - 行业地位良好
   - 管理层经验丰富

2. **风险**:
   - 宏观经济不确定性
   - 行业竞争加剧
   - 政策变化风险

3. **建议**:
   - 长期投资者可考虑配置
   - 短期投资者需关注市场波动
   - 建议定期跟踪财务指标变化

---
*本报告由QuanTr系统自动生成，仅供参考，不构成投资建议。*
"""

            self.logger.info(f"✅ 基本面分析报告生成完成: {symbol}")
            return report

        except Exception as e:
            self.logger.error(f"❌ 生成基本面分析报告失败: {e}")
            return f"# 基本面分析报告生成失败\n\n错误信息: {str(e)}"


def main():
    """主函数，用于测试"""
    analyzer = FundamentalAnalyzer()

    print("🔍 开始测试基本面分析器...")

    # 创建示例数据
    sample_financial_data = {
        "balance_sheet": pd.DataFrame(
            {
                "报告期": ["2023-12-31", "2022-12-31"],
                "资产总计": ["1,000,000", "900,000"],
                "负债合计": ["600,000", "500,000"],
                "所有者权益合计": ["400,000", "400,000"],
                "流动资产合计": ["500,000", "450,000"],
                "流动负债合计": ["300,000", "280,000"],
                "货币资金": ["100,000", "90,000"],
                "存货": ["50,000", "45,000"],
                "应收账款": ["80,000", "70,000"],
            }
        ),
        "income_statement": pd.DataFrame(
            {
                "报告期": ["2023-12-31", "2022-12-31"],
                "营业收入": ["800,000", "700,000"],
                "营业成本": ["500,000", "450,000"],
                "净利润": ["100,000", "90,000"],
            }
        ),
    }

    print("\n1. 分析财务指标...")
    financial_analysis = analyzer.analyze_financial_metrics(sample_financial_data)

    print("   盈利能力指标:")
    for metric, value in financial_analysis.get("profitability", {}).items():
        print(f"     {metric}: {value:.2f}")

    print("\n2. 分析公司经营...")
    sample_basic_info = {
        "股票简称": "测试公司",
        "所属行业": "信息技术",
        "上市时间": "2020-01-01",
        "总市值": "100亿",
        "市盈率": "20.5",
    }
    operations_analysis = analyzer.analyze_company_operations(sample_basic_info)

    print("   公司概况:")
    for key, value in operations_analysis.get("company_profile", {}).items():
        print(f"     {key}: {value}")

    print("\n3. 分析行业趋势...")
    industry_analysis = analyzer.analyze_industry_trends("信息技术")

    print("\n4. 生成综合评分...")
    analysis_results = {
        "financial_metrics": financial_analysis,
        "operations_analysis": operations_analysis,
        "industry_analysis": industry_analysis,
        "macro_analysis": analyzer.analyze_macroeconomic_factors(),
    }

    score_results = analyzer.generate_fundamental_score(analysis_results)
    print(f"   综合评分: {score_results.get('total_score', 0):.1f}")
    print(f"   评级: {score_results.get('rating', 'N/A')}")

    print("\n5. 生成分析报告...")
    report = analyzer.generate_fundamental_report("000001.SZ", analysis_results)

    # 保存报告
    report_dir = config.get_analysis_dir("test")
    report_dir.mkdir(parents=True, exist_ok=True)

    report_file = report_dir / "fundamental_analysis_test.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ 测试完成，报告已保存: {report_file}")
    print(f"\n📄 报告预览（前500字符）:")
    print("-" * 50)
    print(report[:500] + "...")
    print("-" * 50)


if __name__ == "__main__":
    main()
