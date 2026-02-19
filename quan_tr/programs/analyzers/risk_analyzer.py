# programs/analyzers/risk_analyzer.py
"""
风险分析程序
用于分析股票的风险状况，包括系统性风险、非系统性风险、流动性风险等
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from quan_tr.config import config


class RiskAnalyzer:
    """风险分析器"""

    def __init__(self):
        """初始化风险分析器"""
        self.config = config
        self.logger = self._setup_logger()
        self.logger.info("✅ 风险分析器初始化成功")

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
            log_file = self.config.base_dir / "logs" / "risk_analyzer.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def analyze_systematic_risk(
        self, price_data: pd.DataFrame, market_data: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        分析系统性风险

        Args:
            price_data: 股票价格数据
            market_data: 市场指数数据（如沪深300）

        Returns:
            系统性风险分析结果
        """
        systematic_risk = {
            "market_risk_score": 50.0,
            "sector_risk_score": 50.0,
            "macro_risk_score": 50.0,
            "beta": 1.0,
            "correlation_with_market": 0.5,
            "volatility_vs_market": 1.0,
        }

        try:
            if price_data.empty or len(price_data) < 30:
                self.logger.warning("价格数据不足，无法分析系统性风险")
                return systematic_risk

            stock_returns = price_data["收盘"].pct_change().dropna()

            if len(stock_returns) < 20:
                return systematic_risk

            # 计算股票的Beta值（如果没有市场数据，使用估算）
            if market_data is not None and not market_data.empty:
                market_returns = market_data["收盘"].pct_change().dropna()

                # 对齐数据
                min_len = min(len(stock_returns), len(market_returns))
                if min_len >= 20:
                    stock_ret = stock_returns.tail(min_len)
                    market_ret = market_returns.tail(min_len)

                    # 计算Beta
                    covariance = stock_ret.cov(market_ret)
                    market_variance = market_ret.var()

                    if market_variance != 0:
                        beta = covariance / market_variance
                        systematic_risk["beta"] = round(float(beta), 2)

                    # 计算相关系数
                    correlation = stock_ret.corr(market_ret)
                    systematic_risk["correlation_with_market"] = round(
                        float(correlation), 2
                    )

            # 计算相对市场波动率
            stock_volatility = stock_returns.std() * np.sqrt(252)
            market_volatility = 0.20  # 假设市场年化波动率20%

            if market_volatility > 0:
                relative_volatility = stock_volatility / market_volatility
                systematic_risk["volatility_vs_market"] = round(
                    float(relative_volatility), 2
                )

            # 市场风险评分（基于Beta值）
            beta = systematic_risk["beta"]
            if beta < 0.8:
                systematic_risk["market_risk_score"] = 30.0  # 低风险
            elif beta < 1.2:
                systematic_risk["market_risk_score"] = 50.0  # 中等风险
            else:
                systematic_risk["market_risk_score"] = min(70 + (beta - 1.2) * 25, 100)

            # 行业风险评分（简化，需要行业数据）
            systematic_risk["sector_risk_score"] = 50.0  # 默认值

            # 宏观风险评分（基于市场波动性）
            if market_data is not None:
                market_vol = market_returns.std() * np.sqrt(252) * 100
                if market_vol < 15:
                    systematic_risk["macro_risk_score"] = 30.0
                elif market_vol < 25:
                    systematic_risk["macro_risk_score"] = 50.0
                else:
                    systematic_risk["macro_risk_score"] = min(
                        50 + (market_vol - 25) * 2, 100
                    )

            self.logger.info(
                f"✅ 系统性风险分析完成: Beta={systematic_risk['beta']}, "
                f"市场风险={systematic_risk['market_risk_score']:.1f}"
            )

        except Exception as e:
            self.logger.error(f"❌ 系统性风险分析失败: {e}")

        return systematic_risk

    def analyze_unsystematic_risk(
        self, price_data: pd.DataFrame, financial_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        分析非系统性风险（公司特有风险）

        Args:
            price_data: 股票价格数据
            financial_data: 财务数据字典

        Returns:
            非系统性风险分析结果
        """
        unsystematic_risk = {
            "company_risk_score": 50.0,
            "financial_risk_score": 50.0,
            "operational_risk_score": 50.0,
            "governance_risk_score": 50.0,
            "specific_risk_factors": [],
        }

        try:
            # 1. 公司特有风险（基于价格波动中非系统性部分）
            if not price_data.empty and len(price_data) >= 30:
                returns = price_data["收盘"].pct_change().dropna()

                if len(returns) >= 20:
                    # 计算特异波动率（残差波动率）
                    # 简化：假设特异波动率 = 总波动率 * (1 - R²)
                    total_volatility = returns.std() * np.sqrt(252)

                    # 假设R²约为0.3（市场解释30%的波动）
                    r_squared = 0.3
                    specific_volatility = total_volatility * np.sqrt(1 - r_squared)

                    # 评分：特异波动率越高，风险越高
                    if specific_volatility < 0.20:
                        unsystematic_risk["company_risk_score"] = 30.0
                    elif specific_volatility < 0.35:
                        unsystematic_risk["company_risk_score"] = 50.0
                    else:
                        unsystematic_risk["company_risk_score"] = min(
                            50 + (specific_volatility - 0.35) * 100, 100
                        )

            # 2. 财务风险（基于财务数据）
            if financial_data:
                financial_risk = self._analyze_financial_risk(financial_data)
                unsystematic_risk["financial_risk_score"] = financial_risk["score"]
                unsystematic_risk["specific_risk_factors"].extend(
                    financial_risk.get("risk_factors", [])
                )

            # 3. 经营风险（基于业务稳定性）
            # 简化：基于价格稳定性
            if not price_data.empty and len(price_data) >= 60:
                returns = price_data["收盘"].pct_change().dropna()

                if len(returns) >= 60:
                    # 计算最大回撤
                    cumulative = (1 + returns).cumprod()
                    running_max = cumulative.expanding().max()
                    drawdown = (cumulative - running_max) / running_max
                    max_drawdown = drawdown.min()

                    if max_drawdown > -0.20:
                        unsystematic_risk["operational_risk_score"] = 30.0
                    elif max_drawdown > -0.35:
                        unsystematic_risk["operational_risk_score"] = 50.0
                    else:
                        unsystematic_risk["operational_risk_score"] = min(
                            50 + abs(max_drawdown + 0.35) * 100, 100
                        )

            # 4. 治理风险（简化，需要公司治理数据）
            unsystematic_risk["governance_risk_score"] = 50.0  # 默认值

            self.logger.info(
                f"✅ 非系统性风险分析完成: 公司风险={unsystematic_risk['company_risk_score']:.1f}, "
                f"财务风险={unsystematic_risk['financial_risk_score']:.1f}"
            )

        except Exception as e:
            self.logger.error(f"❌ 非系统性风险分析失败: {e}")

        return unsystematic_risk

    def _analyze_financial_risk(self, financial_data: Dict) -> Dict[str, Any]:
        """分析财务风险"""
        result = {"score": 50.0, "risk_factors": []}

        try:
            balance_sheet = financial_data.get("balance_sheet")
            income_statement = financial_data.get("income_statement")

            if balance_sheet is not None and not balance_sheet.empty:
                latest_data = (
                    balance_sheet.iloc[0]
                    if isinstance(balance_sheet, pd.DataFrame)
                    else balance_sheet
                )

                # 资产负债率
                if "资产负债率" in latest_data.index:
                    debt_ratio = latest_data["资产负债率"]
                    if isinstance(debt_ratio, str):
                        debt_ratio = float(debt_ratio.replace("%", ""))

                    if debt_ratio > 70:
                        result["score"] += 20
                        result["risk_factors"].append(
                            f"资产负债率过高 ({debt_ratio:.1f}%)"
                        )
                    elif debt_ratio < 40:
                        result["score"] -= 10

                # 流动比率
                if "流动比率" in latest_data.index:
                    current_ratio = latest_data["流动比率"]
                    if isinstance(current_ratio, str):
                        current_ratio = float(current_ratio)

                    if current_ratio < 1.0:
                        result["score"] += 15
                        result["risk_factors"].append(
                            f"流动比率偏低 ({current_ratio:.2f})"
                        )
                    elif current_ratio > 2.0:
                        result["score"] -= 5

            # 限制分数范围
            result["score"] = max(0, min(100, result["score"]))

        except Exception as e:
            self.logger.warning(f"财务风险分析失败: {e}")

        return result

    def analyze_liquidity_risk(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        分析流动性风险

        Args:
            price_data: 股票价格数据，需包含成交量

        Returns:
            流动性风险分析结果
        """
        liquidity_risk = {
            "liquidity_score": 50.0,
            "volume_liquidity": 50.0,
            "price_impact": 50.0,
            "turnover_score": 50.0,
        }

        try:
            if price_data.empty or len(price_data) < 20:
                self.logger.warning("价格数据不足，无法分析流动性风险")
                return liquidity_risk

            if "成交量" not in price_data.columns:
                self.logger.warning("价格数据缺少成交量列")
                return liquidity_risk

            volumes = price_data["成交量"]

            # 1. 成交量流动性
            avg_volume = volumes.tail(20).mean()

            if avg_volume > 1000000:  # 日均成交量100万以上
                liquidity_risk["volume_liquidity"] = 30.0
            elif avg_volume > 500000:
                liquidity_risk["volume_liquidity"] = 50.0
            else:
                liquidity_risk["volume_liquidity"] = min(
                    50 + (500000 - avg_volume) / 10000, 100
                )

            # 2. 价格波动影响（简化）
            close_prices = price_data["收盘"]
            daily_returns = close_prices.pct_change().abs()
            avg_volatility = daily_returns.tail(20).mean() * 100

            if avg_volatility < 2.0:
                liquidity_risk["price_impact"] = 30.0
            elif avg_volatility < 5.0:
                liquidity_risk["price_impact"] = 50.0
            else:
                liquidity_risk["price_impact"] = min(
                    50 + (avg_volatility - 5) * 10, 100
                )

            # 3. 换手率评分（如果有市值数据）
            # 简化：假设市值为10亿，计算换手率
            assumed_market_cap = 1e9
            avg_turnover = avg_volume * close_prices.iloc[-1] / assumed_market_cap * 100

            if avg_turnover > 3.0:
                liquidity_risk["turnover_score"] = 30.0
            elif avg_turnover > 1.0:
                liquidity_risk["turnover_score"] = 50.0
            else:
                liquidity_risk["turnover_score"] = min(
                    50 + (1 - avg_turnover) * 20, 100
                )

            # 综合流动性评分
            liquidity_risk["liquidity_score"] = (
                liquidity_risk["volume_liquidity"] * 0.4
                + liquidity_risk["price_impact"] * 0.3
                + liquidity_risk["turnover_score"] * 0.3
            )

            self.logger.info(
                f"✅ 流动性风险分析完成: 流动性评分={liquidity_risk['liquidity_score']:.1f}, "
                f"日均成交量={avg_volume:.0f}"
            )

        except Exception as e:
            self.logger.error(f"❌ 流动性风险分析失败: {e}")

        return liquidity_risk

    def analyze_tail_risk(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        分析尾部风险（极端风险）

        Args:
            price_data: 股票价格数据

        Returns:
            尾部风险分析结果
        """
        tail_risk = {
            "var_95": 0.0,
            "var_99": 0.0,
            "expected_shortfall": 0.0,
            "max_drawdown": 0.0,
            "skewness": 0.0,
            "kurtosis": 0.0,
            "tail_risk_score": 50.0,
        }

        try:
            if price_data.empty or len(price_data) < 60:
                self.logger.warning("价格数据不足，无法分析尾部风险")
                return tail_risk

            returns = price_data["收盘"].pct_change().dropna()

            if len(returns) < 60:
                return tail_risk

            # 计算VaR（历史模拟法）
            var_95 = np.percentile(returns, 5)
            var_99 = np.percentile(returns, 1)

            tail_risk["var_95"] = round(float(var_95 * 100), 2)
            tail_risk["var_99"] = round(float(var_99 * 100), 2)

            # 计算期望损失（CVaR）
            es_95 = returns[returns <= var_95].mean()
            tail_risk["expected_shortfall"] = round(float(es_95 * 100), 2)

            # 计算最大回撤
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min()

            tail_risk["max_drawdown"] = round(float(max_drawdown * 100), 2)

            # 计算偏度和峰度
            tail_risk["skewness"] = round(float(returns.skew()), 2)
            tail_risk["kurtosis"] = round(float(returns.kurtosis()), 2)

            # 尾部风险评分
            score = 50.0

            # 基于VaR调整
            if var_95 < -0.05:
                score += 15
            if var_99 < -0.08:
                score += 15

            # 基于最大回撤调整
            if max_drawdown < -0.30:
                score += 20
            elif max_drawdown < -0.20:
                score += 10

            # 基于峰度调整（高峰度表示尾部风险大）
            if tail_risk["kurtosis"] > 3:
                score += 10

            tail_risk["tail_risk_score"] = min(score, 100)

            self.logger.info(
                f"✅ 尾部风险分析完成: VaR(95%)={tail_risk['var_95']}%, "
                f"最大回撤={tail_risk['max_drawdown']}%"
            )

        except Exception as e:
            self.logger.error(f"❌ 尾部风险分析失败: {e}")

        return tail_risk

    def generate_risk_assessment(self, risk_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成综合风险评估

        Args:
            risk_results: 各维度风险分析结果

        Returns:
            综合风险评估结果
        """
        assessment = {
            "risk_level": "medium",
            "risk_score": 50.0,
            "risk_factors": [],
            "risk_breakdown": {},
        }

        try:
            # 系统性风险
            systematic = risk_results.get("systematic", {})
            sys_score = systematic.get("market_risk_score", 50.0)

            # 非系统性风险
            unsystematic = risk_results.get("unsystematic", {})
            unsys_score = (
                unsystematic.get("company_risk_score", 50.0) * 0.3
                + unsystematic.get("financial_risk_score", 50.0) * 0.3
                + unsystematic.get("operational_risk_score", 50.0) * 0.2
                + unsystematic.get("governance_risk_score", 50.0) * 0.2
            )

            # 流动性风险
            liquidity = risk_results.get("liquidity", {})
            liq_score = liquidity.get("liquidity_score", 50.0)

            # 尾部风险
            tail = risk_results.get("tail", {})
            tail_score = tail.get("tail_risk_score", 50.0)

            # 风险分解
            assessment["risk_breakdown"] = {
                "systematic": {"score": sys_score, "weight": 0.25},
                "unsystematic": {"score": unsys_score, "weight": 0.35},
                "liquidity": {"score": liq_score, "weight": 0.25},
                "tail": {"score": tail_score, "weight": 0.15},
            }

            # 计算加权风险评分
            assessment["risk_score"] = (
                sys_score * 0.25
                + unsys_score * 0.35
                + liq_score * 0.25
                + tail_score * 0.15
            )

            # 确定风险等级
            if assessment["risk_score"] < 35:
                assessment["risk_level"] = "low"
            elif assessment["risk_score"] < 65:
                assessment["risk_level"] = "medium"
            else:
                assessment["risk_level"] = "high"

            # 收集风险因素
            risk_factors = []

            if systematic.get("beta", 1.0) > 1.5:
                risk_factors.append("高Beta值，对市场波动敏感")

            if unsystematic.get("financial_risk_score", 50) > 70:
                risk_factors.append("财务风险较高")

            if unsystematic.get("operational_risk_score", 50) > 70:
                risk_factors.append("经营风险较高")

            if liquidity.get("liquidity_score", 50) > 70:
                risk_factors.append("流动性风险较高")

            if tail.get("max_drawdown", 0) < -30:
                risk_factors.append(
                    f"历史最大回撤较大 ({tail.get('max_drawdown', 0):.1f}%)"
                )

            assessment["risk_factors"] = risk_factors

            self.logger.info(
                f"✅ 综合风险评估完成: 风险等级={assessment['risk_level']}, "
                f"风险评分={assessment['risk_score']:.1f}"
            )

        except Exception as e:
            self.logger.error(f"❌ 综合风险评估失败: {e}")

        return assessment

    def analyze_all(
        self,
        price_data: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None,
        financial_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        执行完整的风险分析

        Args:
            price_data: 股票价格数据
            market_data: 市场指数数据
            financial_data: 财务数据

        Returns:
            完整的风险分析结果
        """
        self.logger.info(f"开始风险分析，数据点数: {len(price_data)}")

        # 执行各维度风险分析
        systematic = self.analyze_systematic_risk(price_data, market_data)
        unsystematic = self.analyze_unsystematic_risk(price_data, financial_data)
        liquidity = self.analyze_liquidity_risk(price_data)
        tail = self.analyze_tail_risk(price_data)

        # 汇总结果
        risk_results = {
            "systematic": systematic,
            "unsystematic": unsystematic,
            "liquidity": liquidity,
            "tail": tail,
        }

        # 生成综合评估
        assessment = self.generate_risk_assessment(risk_results)
        risk_results["assessment"] = assessment

        self.logger.info("✅ 风险分析全部完成")

        return risk_results

    def generate_risk_report(self, symbol: str, risk_results: Dict[str, Any]) -> str:
        """
        生成风险分析报告

        Args:
            symbol: 股票代码
            risk_results: 风险分析结果

        Returns:
            Markdown格式的报告
        """
        try:
            report = f"""# 风险分析报告 - {symbol}

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**分析工具**: QuanTr Risk Analyzer

## 1. 风险总览

"""

            assessment = risk_results.get("assessment", {})
            report += f"**风险等级**: {assessment.get('risk_level', 'N/A').upper()}\n\n"
            report += f"**综合风险评分**: {assessment.get('risk_score', 0):.1f}/100\n\n"
            report += "*(分数越高表示风险越大)*\n\n"

            # 风险因素
            risk_factors = assessment.get("risk_factors", [])
            if risk_factors:
                report += "### 主要风险因素\n\n"
                for factor in risk_factors:
                    report += f"- ⚠️ {factor}\n"
            else:
                report += "### 主要风险因素\n\n未发现明显风险因素\n"

            # 风险分解
            report += "\n## 2. 风险分解\n\n"
            breakdown = assessment.get("risk_breakdown", {})
            for risk_type, details in breakdown.items():
                score = details.get("score", 0)
                weight = details.get("weight", 0)
                weighted_score = score * weight

                risk_name = {
                    "systematic": "系统性风险",
                    "unsystematic": "非系统性风险",
                    "liquidity": "流动性风险",
                    "tail": "尾部风险",
                }.get(risk_type, risk_type)

                report += f"**{risk_name}** (权重{weight:.0%}): {score:.1f}分 → 加权{weighted_score:.1f}分\n\n"

            # 系统性风险详情
            report += "\n## 3. 系统性风险详情\n\n"
            systematic = risk_results.get("systematic", {})
            report += f"**Beta值**: {systematic.get('beta', 'N/A')}\n"
            report += f"*Beta > 1表示比市场波动更大，Beta < 1表示比市场波动更小*\n\n"
            report += f"**与市场相关性**: {systematic.get('correlation_with_market', 'N/A')}\n"
            report += (
                f"**相对市场波动率**: {systematic.get('volatility_vs_market', 'N/A')}\n"
            )

            # 非系统性风险详情
            report += "\n## 4. 非系统性风险详情\n\n"
            unsystematic = risk_results.get("unsystematic", {})
            report += (
                f"**公司特有风险**: {unsystematic.get('company_risk_score', 0):.1f}分\n"
            )
            report += (
                f"**财务风险**: {unsystematic.get('financial_risk_score', 0):.1f}分\n"
            )
            report += (
                f"**经营风险**: {unsystematic.get('operational_risk_score', 0):.1f}分\n"
            )
            report += (
                f"**治理风险**: {unsystematic.get('governance_risk_score', 0):.1f}分\n"
            )

            # 流动性风险详情
            report += "\n## 5. 流动性风险详情\n\n"
            liquidity = risk_results.get("liquidity", {})
            report += (
                f"**综合流动性评分**: {liquidity.get('liquidity_score', 0):.1f}分\n\n"
            )
            report += (
                f"**成交量流动性**: {liquidity.get('volume_liquidity', 0):.1f}分\n"
            )
            report += f"**价格冲击风险**: {liquidity.get('price_impact', 0):.1f}分\n"
            report += f"**换手率评分**: {liquidity.get('turnover_score', 0):.1f}分\n"

            # 尾部风险详情
            report += "\n## 6. 尾部风险详情\n\n"
            tail = risk_results.get("tail", {})
            report += f"**VaR (95%)**: {tail.get('var_95', 0):.2f}%\n"
            report += f"*表示在正常市场条件下，95%的概率单日损失不会超过此值*\n\n"
            report += f"**VaR (99%)**: {tail.get('var_99', 0):.2f}%\n"
            report += f"**期望损失**: {tail.get('expected_shortfall', 0):.2f}%\n"
            report += f"**历史最大回撤**: {tail.get('max_drawdown', 0):.2f}%\n"
            report += f"**收益率偏度**: {tail.get('skewness', 0):.2f}\n"
            report += f"**收益率峰度**: {tail.get('kurtosis', 0):.2f}\n"

            # 风险管理建议
            report += """
## 7. 风险管理建议

基于风险分析，提出以下建议：

"""

            risk_level = assessment.get("risk_level", "medium")
            if risk_level == "high":
                report += """**⚠️ 高风险警告**

- 建议严格控制仓位，不超过投资组合的5%
- 建议设置较紧的止损位（5-8%）
- 避免在市场波动期建仓
- 密切关注财务和经营状况变化
"""
            elif risk_level == "medium":
                report += """**⚡ 中等风险**

- 建议适度配置，占投资组合的5-15%
- 建议设置合理止损位（8-12%）
- 定期评估风险状况
- 关注行业和宏观经济变化
"""
            else:
                report += """**✅ 低风险**

- 可考虑适度重仓配置
- 建议设置较宽松的止损位（10-15%）
- 适合长期持有
- 仍需定期监控风险指标
"""

            report += """
---
*本报告由QuanTr系统自动生成，仅供参考，不构成投资建议。*
"""

            self.logger.info(f"✅ 风险分析报告生成完成: {symbol}")
            return report

        except Exception as e:
            self.logger.error(f"❌ 生成风险分析报告失败: {e}")
            return f"# 风险分析报告生成失败\n\n错误信息: {str(e)}"


def main():
    """主函数，用于测试"""
    analyzer = RiskAnalyzer()

    print("🔍 开始测试风险分析器...")

    # 创建示例数据
    dates = pd.date_range(end=datetime.now(), periods=100, freq="D")
    np.random.seed(42)

    # 生成模拟价格数据
    base_price = 100
    prices = []
    volumes = []

    for i in range(100):
        change = np.random.normal(0.001, 0.02)
        if i > 0:
            price = prices[-1] * (1 + change)
        else:
            price = base_price
        prices.append(price)
        volumes.append(np.random.randint(1000000, 5000000))

    sample_data = pd.DataFrame(
        {
            "日期": dates,
            "开盘": [p * (1 + np.random.uniform(-0.01, 0.01)) for p in prices],
            "收盘": prices,
            "最高": [p * (1 + np.random.uniform(0, 0.02)) for p in prices],
            "最低": [p * (1 - np.random.uniform(0, 0.02)) for p in prices],
            "成交量": volumes,
        }
    )

    print(f"\n1. 分析系统性风险...")
    systematic = analyzer.analyze_systematic_risk(sample_data)
    print(f"   Beta: {systematic['beta']}")
    print(f"   市场风险: {systematic['market_risk_score']:.1f}分")

    print(f"\n2. 分析非系统性风险...")
    unsystematic = analyzer.analyze_unsystematic_risk(sample_data)
    print(f"   公司风险: {unsystematic['company_risk_score']:.1f}分")
    print(f"   财务风险: {unsystematic['financial_risk_score']:.1f}分")

    print(f"\n3. 分析流动性风险...")
    liquidity = analyzer.analyze_liquidity_risk(sample_data)
    print(f"   流动性评分: {liquidity['liquidity_score']:.1f}分")

    print(f"\n4. 分析尾部风险...")
    tail = analyzer.analyze_tail_risk(sample_data)
    print(f"   VaR(95%): {tail['var_95']:.2f}%")
    print(f"   最大回撤: {tail['max_drawdown']:.2f}%")

    print(f"\n5. 综合分析...")
    results = analyzer.analyze_all(sample_data)
    assessment = results.get("assessment", {})
    print(f"   风险等级: {assessment.get('risk_level', 'N/A')}")
    print(f"   风险评分: {assessment.get('risk_score', 0):.1f}分")

    print(f"\n6. 生成报告...")
    report = analyzer.generate_risk_report("000001.SZ", results)

    # 保存报告
    report_dir = config.get_analysis_dir("test")
    report_dir.mkdir(parents=True, exist_ok=True)

    report_file = report_dir / "risk_analysis_test.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ 测试完成，报告已保存: {report_file}")
    print(f"\n📄 报告预览（前500字符）:")
    print("-" * 50)
    print(report[:500] + "...")
    print("-" * 50)


if __name__ == "__main__":
    main()
