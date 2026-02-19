# programs/stock_analyzer.py
"""
股票分析主程序
整合基本面、技术面、风险分析等模块，生成完整的股票分析报告
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from quan_tr.config import config
from quan_tr.programs.data_fetchers.akshare_fetcher import AKshareFetcher
from quan_tr.programs.analyzers.fundamental_analyzer import FundamentalAnalyzer
from quan_tr.programs.analyzers.technical_analyzer import TechnicalAnalyzer
from quan_tr.programs.analyzers.risk_analyzer import RiskAnalyzer
from quan_tr.programs.utils.data_processor import DataProcessor, ReportGenerator


class StockAnalyzer:
    """股票分析器主类"""

    def __init__(self):
        """初始化股票分析器"""
        self.config = config
        self.logger = self._setup_logger()

        # 初始化各模块
        self.data_fetcher = AKshareFetcher()
        self.fundamental_analyzer = FundamentalAnalyzer()
        self.technical_analyzer = TechnicalAnalyzer()
        self.risk_analyzer = RiskAnalyzer()

        self.logger.info("✅ 股票分析器初始化成功")

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

            log_file = self.config.base_dir / "logs" / "stock_analyzer.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def analyze_stock(
        self, symbol: str, date_str: Optional[str] = None, save_results: bool = True
    ) -> Dict[str, Any]:
        """
        分析单只股票

        Args:
            symbol: 股票代码
            date_str: 日期字符串，默认为今天
            save_results: 是否保存结果

        Returns:
            完整的分析结果
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        self.logger.info(f"\n{'=' * 60}")
        self.logger.info(f"开始分析股票: {symbol}")
        self.logger.info(f"分析日期: {date_str}")
        self.logger.info(f"{'=' * 60}\n")

        try:
            # 1. 获取数据
            self.logger.info("📊 获取股票数据...")

            # 基本信息
            basic_info = self.data_fetcher.get_stock_basic_info(symbol)
            if not basic_info:
                self.logger.error(f"❌ 无法获取股票 {symbol} 的基本信息")
                return self._create_empty_result(symbol, "无法获取基本信息")

            # 价格数据（最近90天）
            end_date = date_str
            start_date = (
                datetime.strptime(date_str, "%Y-%m-%d") - pd.Timedelta(days=90)
            ).strftime("%Y-%m-%d")

            price_data = self.data_fetcher.get_stock_daily_data(
                symbol, start_date, end_date
            )

            if price_data is None or price_data.empty:
                self.logger.error(f"❌ 无法获取股票 {symbol} 的价格数据")
                return self._create_empty_result(symbol, "无法获取价格数据")

            # 清洗价格数据
            price_data = DataProcessor.clean_price_data(price_data)

            # 财务数据
            financial_data = self.data_fetcher.get_stock_financial_data(symbol)

            self.logger.info(f"✅ 数据获取完成: {len(price_data)} 条价格记录")

            # 2. 基本面分析
            self.logger.info("📈 执行基本面分析...")
            fundamental_analysis = {}

            if financial_data:
                financial_metrics = self.fundamental_analyzer.analyze_financial_metrics(
                    financial_data
                )
                operations = self.fundamental_analyzer.analyze_company_operations(
                    basic_info
                )
                industry = self.fundamental_analyzer.analyze_industry_trends(
                    basic_info.get("所属行业", "")
                )
                macro = self.fundamental_analyzer.analyze_macroeconomic_factors()

                # 生成基本面评分
                fundamental_input = {
                    "financial_metrics": financial_metrics,
                    "operations_analysis": operations,
                    "industry_analysis": industry,
                    "macro_analysis": macro,
                }
                fundamental_score = (
                    self.fundamental_analyzer.generate_fundamental_score(
                        fundamental_input
                    )
                )

                fundamental_analysis = {
                    "financial_metrics": financial_metrics,
                    "operations_analysis": operations,
                    "industry_analysis": industry,
                    "macro_analysis": macro,
                    "score": fundamental_score,
                }

                self.logger.info(
                    f"✅ 基本面分析完成: 评分={fundamental_score.get('total_score', 0):.1f}"
                )
            else:
                self.logger.warning("⚠️ 财务数据不可用，基本面分析受限")
                fundamental_analysis = self._create_empty_fundamental_analysis()

            # 3. 技术面分析
            self.logger.info("📉 执行技术面分析...")
            technical_analysis = self.technical_analyzer.analyze_all(price_data)
            self.logger.info(
                f"✅ 技术面分析完成: 评分={technical_analysis.get('score', {}).get('total_score', 0):.1f}"
            )

            # 4. 风险分析
            self.logger.info("⚠️  执行风险分析...")
            risk_analysis = self.risk_analyzer.analyze_all(
                price_data, financial_data=financial_data
            )
            self.logger.info(
                f"✅ 风险分析完成: 等级={risk_analysis.get('assessment', {}).get('risk_level', 'N/A')}"
            )

            # 5. 整合结果
            self.logger.info("🔄 整合分析结果...")
            result = self._compile_analysis_result(
                symbol=symbol,
                date_str=date_str,
                basic_info=basic_info,
                price_data=price_data,
                fundamental_analysis=fundamental_analysis,
                technical_analysis=technical_analysis,
                risk_analysis=risk_analysis,
            )

            # 6. 保存结果
            if save_results:
                self._save_analysis_result(symbol, date_str, result)

            self.logger.info(f"\n✅ 股票 {symbol} 分析完成!")
            self.logger.info(
                f"综合评分: {result.get('scoring_system', {}).get('overall_score', 0):.1f}"
            )
            self.logger.info(
                f"推荐等级: {result.get('investment_recommendation', {}).get('recommendation', 'N/A')}"
            )

            return result

        except Exception as e:
            self.logger.error(f"❌ 分析股票 {symbol} 时出错: {e}")
            import traceback

            self.logger.error(traceback.format_exc())
            return self._create_empty_result(symbol, str(e))

    def _compile_analysis_result(
        self,
        symbol: str,
        date_str: str,
        basic_info: Dict,
        price_data: pd.DataFrame,
        fundamental_analysis: Dict,
        technical_analysis: Dict,
        risk_analysis: Dict,
    ) -> Dict[str, Any]:
        """编译分析结果"""

        # 当前价格
        current_price = price_data["收盘"].iloc[-1] if not price_data.empty else 0

        # 计算涨跌幅
        if len(price_data) > 1:
            prev_close = price_data["收盘"].iloc[-2]
            day_change = current_price - prev_close
            day_change_pct = (day_change / prev_close) * 100
        else:
            day_change = 0
            day_change_pct = 0

        # 综合评分计算
        fund_score = fundamental_analysis.get("score", {}).get("total_score", 50)
        tech_score = technical_analysis.get("score", {}).get("total_score", 50)
        risk_score = 100 - risk_analysis.get("assessment", {}).get("risk_score", 50)

        # 权重配置
        weights = {
            "fundamental": 0.4,
            "technical": 0.3,
            "risk": 0.2,
            "sentiment": 0.1,
        }

        overall_score = (
            fund_score * weights["fundamental"]
            + tech_score * weights["technical"]
            + risk_score * weights["risk"]
            + 50 * weights["sentiment"]  # 情绪分析暂用默认值
        )

        # 确定推荐等级
        recommendation = self._determine_recommendation(overall_score, risk_analysis)

        result = {
            # 元数据
            "analysis_timestamp": datetime.now().isoformat(),
            "next_update_schedule": "每日更新",
            # 基本信息
            "basic_info": {
                "stock_name": basic_info.get("股票简称", ""),
                "stock_code": symbol,
                "market": "A股",
                "sector": basic_info.get("所属行业", ""),
                "company_name": basic_info.get("股票名称", ""),
            },
            # 价格信息
            "price_info": {
                "current_price": round(current_price, 2),
                "previous_close": round(price_data["收盘"].iloc[-2], 2)
                if len(price_data) > 1
                else current_price,
                "day_change": round(day_change, 2),
                "day_change_percent": round(day_change_pct, 2),
                "day_high": round(price_data["最高"].iloc[-1], 2)
                if not price_data.empty
                else current_price,
                "day_low": round(price_data["最低"].iloc[-1], 2)
                if not price_data.empty
                else current_price,
                "volume": int(price_data["成交量"].iloc[-1])
                if not price_data.empty and "成交量" in price_data.columns
                else 0,
                "market_cap": basic_info.get("总市值", 0),
            },
            # 基本面分析
            "fundamental_analysis": {
                "financial_metrics": fundamental_analysis.get("financial_metrics", {}),
                "valuation_metrics": {
                    "pe_ratio": basic_info.get("市盈率", 0),
                    "pb_ratio": basic_info.get("市净率", 0),
                },
            },
            # 技术面分析
            "technical_analysis": {
                "trend_indicators": technical_analysis.get("trend", {}).get(
                    "moving_averages", {}
                ),
                "momentum_indicators": technical_analysis.get("momentum", {}),
                "support_resistance": technical_analysis.get("support_resistance", {}),
            },
            # 风险分析
            "risk_analysis": {
                "overall_risk_assessment": risk_analysis.get("assessment", {}),
            },
            # 评分系统
            "scoring_system": {
                "fundamental_score": {
                    "score": round(fund_score, 1),
                    "weight": weights["fundamental"],
                },
                "technical_score": {
                    "score": round(tech_score, 1),
                    "weight": weights["technical"],
                },
                "risk_score": {
                    "score": round(risk_score, 1),
                    "weight": weights["risk"],
                },
                "sentiment_score": {
                    "score": 50.0,
                    "weight": weights["sentiment"],
                },
                "overall_score": round(overall_score, 1),
            },
            # 投资建议
            "investment_recommendation": {
                "recommendation": recommendation,
                "confidence_level": "medium",
                "reasoning": f"综合评分{overall_score:.1f}分，基于基本面、技术面和风险分析",
                "time_horizon": "medium_term",
                "target_price": {
                    "base_case": round(
                        current_price * (1 + (overall_score - 50) / 500), 2
                    ),
                    "current_price_upside": round((overall_score - 50) / 5, 1),
                },
            },
            # 关键亮点
            "key_highlights": {
                "strengths": [],
                "weaknesses": [],
                "opportunities": [],
                "threats": risk_analysis.get("assessment", {}).get("risk_factors", []),
            },
        }

        return result

    def _determine_recommendation(self, score: float, risk_analysis: Dict) -> str:
        """确定推荐等级"""
        risk_level = risk_analysis.get("assessment", {}).get("risk_level", "medium")

        # 根据分数确定推荐
        if score >= 75:
            base_rec = "strong_buy"
        elif score >= 60:
            base_rec = "buy"
        elif score >= 40:
            base_rec = "hold"
        elif score >= 25:
            base_rec = "sell"
        else:
            base_rec = "strong_sell"

        # 高风险调整
        if risk_level == "high" and base_rec in ["strong_buy", "buy"]:
            if base_rec == "strong_buy":
                return "buy"
            else:
                return "hold"

        return base_rec

    def _create_empty_result(self, symbol: str, error_msg: str) -> Dict[str, Any]:
        """创建空的分析结果"""
        return {
            "basic_info": {"stock_code": symbol, "stock_name": "Unknown"},
            "price_info": {"current_price": 0},
            "scoring_system": {"overall_score": 0},
            "investment_recommendation": {"recommendation": "hold"},
            "error": error_msg,
        }

    def _create_empty_fundamental_analysis(self) -> Dict[str, Any]:
        """创建空的基本面分析结果"""
        return {
            "financial_metrics": {},
            "operations_analysis": {},
            "industry_analysis": {},
            "macro_analysis": {},
            "score": {"total_score": 50.0},
        }

    def _save_analysis_result(
        self, symbol: str, date_str: str, result: Dict[str, Any]
    ) -> None:
        """保存分析结果"""
        try:
            # 保存目录
            save_dir = self.config.get_analysis_dir(date_str)
            save_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件名
            clean_symbol = symbol.replace(".", "_")
            stock_name = result.get("basic_info", {}).get("stock_name", "unknown")

            # 保存Markdown报告
            md_file = save_dir / f"stock_{stock_name}_{clean_symbol}_analysis.md"
            report = self._generate_markdown_report(symbol, result)
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(report)

            self.logger.info(f"✅ 分析报告已保存: {md_file}")

            # 保存JSON（单个股票）
            json_file = save_dir / f"stock_{stock_name}_{clean_symbol}.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"❌ 保存分析结果失败: {e}")

    def _generate_markdown_report(self, symbol: str, result: Dict[str, Any]) -> str:
        """生成Markdown格式的分析报告"""
        basic = result.get("basic_info", {})
        price = result.get("price_info", {})
        scores = result.get("scoring_system", {})
        recommendation = result.get("investment_recommendation", {})

        report = f"""# 股票分析报告 - {basic.get("stock_name", symbol)} ({symbol})

**分析日期**: {datetime.now().strftime("%Y-%m-%d")}
**生成时间**: {datetime.now().strftime("%H:%M:%S")}

---

## 基本信息

- **股票名称**: {basic.get("stock_name", "N/A")}
- **股票代码**: {symbol}
- **所属行业**: {basic.get("sector", "N/A")}

## 价格信息

- **当前价格**: ¥{price.get("current_price", 0):.2f}
- **涨跌额**: ¥{price.get("day_change", 0):.2f}
- **涨跌幅**: {price.get("day_change_percent", 0):.2f}%
- **成交量**: {price.get("volume", 0):,}

## 综合评分

**总体评分**: {scores.get("overall_score", 0):.1f}/100

### 分项评分

- **基本面**: {scores.get("fundamental_score", {}).get("score", 0):.1f}分 (权重40%)
- **技术面**: {scores.get("technical_score", {}).get("score", 0):.1f}分 (权重30%)
- **风险**: {scores.get("risk_score", {}).get("score", 0):.1f}分 (权重20%)
- **情绪**: {scores.get("sentiment_score", {}).get("score", 0):.1f}分 (权重10%)

## 投资建议

**推荐等级**: {recommendation.get("recommendation", "hold").upper()}

**目标价格**: ¥{recommendation.get("target_price", {}).get("base_case", 0):.2f}

**预期涨幅**: {recommendation.get("target_price", {}).get("current_price_upside", 0):.1f}%

**推荐理由**: {recommendation.get("reasoning", "N/A")}

---

*本报告由QuanTr系统自动生成，仅供参考，不构成投资建议。*
*股市有风险，投资需谨慎。*
"""

        return report


def main():
    """主函数，用于测试"""
    analyzer = StockAnalyzer()

    print("🔍 开始测试股票分析器...")
    print(f"AKshare可用: {analyzer.data_fetcher.akshare_available}")

    if not analyzer.data_fetcher.akshare_available:
        print("❌ AKshare不可用，跳过测试")
        return

    # 测试股票
    test_symbol = "000001.SZ"

    print(f"\n分析股票: {test_symbol}")
    result = analyzer.analyze_stock(test_symbol, save_results=True)

    print(f"\n{'=' * 60}")
    print("分析结果:")
    print(f"{'=' * 60}")
    print(f"股票名称: {result.get('basic_info', {}).get('stock_name', 'N/A')}")
    print(f"当前价格: ¥{result.get('price_info', {}).get('current_price', 0):.2f}")
    print(f"综合评分: {result.get('scoring_system', {}).get('overall_score', 0):.1f}")
    print(
        f"推荐等级: {result.get('investment_recommendation', {}).get('recommendation', 'N/A')}"
    )
    print(f"{'=' * 60}\n")

    print("✅ 测试完成!")


if __name__ == "__main__":
    main()
