# programs/utils/data_processor.py
"""
数据处理工具
用于数据清洗、转换、格式化等操作
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from quan_tr.config import config


class DataProcessor:
    """数据处理器"""

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """标准化股票代码格式"""
        symbol = symbol.strip().upper()

        # 处理不同格式
        if symbol.endswith(".SZ") or symbol.endswith(".SH"):
            return symbol
        elif symbol.startswith("6"):
            return f"{symbol}.SH"
        elif symbol.startswith("0") or symbol.startswith("3"):
            return f"{symbol}.SZ"
        else:
            return symbol

    @staticmethod
    def clean_price_data(df: pd.DataFrame) -> pd.DataFrame:
        """清洗价格数据"""
        if df.empty:
            return df

        # 深拷贝避免修改原始数据
        df = df.copy()

        # 标准化列名
        column_mapping = {
            "open": "开盘",
            "close": "收盘",
            "high": "最高",
            "low": "最低",
            "volume": "成交量",
            "amount": "成交额",
            "date": "日期",
        }

        df.columns = [column_mapping.get(str(col).lower(), col) for col in df.columns]

        # 转换数值列
        numeric_cols = ["开盘", "收盘", "最高", "最低", "成交量", "成交额"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 处理日期列
        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
            df = df.sort_values("日期").reset_index(drop=True)

        # 删除包含NaN的行
        df = df.dropna(subset=["收盘"])

        return df

    @staticmethod
    def calculate_returns(prices: pd.Series, periods: int = 1) -> pd.Series:
        """计算收益率"""
        return prices.pct_change(periods).dropna()

    @staticmethod
    def resample_data(df: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
        """重采样数据"""
        if df.empty or "日期" not in df.columns:
            return df

        df = df.copy()
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.set_index("日期")

        resampled = (
            df.resample(freq)
            .agg(
                {
                    "开盘": "first",
                    "最高": "max",
                    "最低": "min",
                    "收盘": "last",
                    "成交量": "sum",
                }
            )
            .dropna()
        )

        return resampled.reset_index()

    @staticmethod
    def merge_dataframes(
        dfs: List[pd.DataFrame], on: str = "日期", how: str = "outer"
    ) -> pd.DataFrame:
        """合并多个DataFrame"""
        if not dfs:
            return pd.DataFrame()

        result = dfs[0]
        for df in dfs[1:]:
            if not df.empty:
                result = pd.merge(result, df, on=on, how=how, suffixes=("", "_dup"))
                # 删除重复的列
                result = result.loc[:, ~result.columns.str.endswith("_dup")]

        return result


class ReportGenerator:
    """报告生成器"""

    @staticmethod
    def generate_summary_report(
        analysis_results: List[Dict[str, Any]], date_str: Optional[str] = None
    ) -> str:
        """生成汇总报告"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        report = f"""# 股票分析汇总报告

**分析日期**: {date_str}
**分析股票数量**: {len(analysis_results)}
**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 汇总统计

"""

        if not analysis_results:
            report += "暂无分析结果\n"
            return report

        # 统计推荐分布
        recommendations = {
            "strong_buy": 0,
            "buy": 0,
            "hold": 0,
            "sell": 0,
            "strong_sell": 0,
        }
        total_scores = []

        for result in analysis_results:
            rec = result.get("investment_recommendation", {}).get(
                "recommendation", "hold"
            )
            recommendations[rec] = recommendations.get(rec, 0) + 1

            score = result.get("scoring_system", {}).get("overall_score", 0)
            total_scores.append(score)

        report += "### 推荐分布\n\n"
        for rec, count in recommendations.items():
            rec_name = {
                "strong_buy": "强烈买入",
                "buy": "买入",
                "hold": "持有",
                "sell": "卖出",
                "strong_sell": "强烈卖出",
            }.get(rec, rec)
            report += f"- **{rec_name}**: {count} 只\n"

        # 评分统计
        if total_scores:
            report += f"\n### 评分统计\n\n"
            report += f"- **平均分**: {np.mean(total_scores):.2f}\n"
            report += f"- **最高分**: {max(total_scores):.2f}\n"
            report += f"- **最低分**: {min(total_scores):.2f}\n"

        # 前5名和后5名
        sorted_results = sorted(
            analysis_results,
            key=lambda x: x.get("scoring_system", {}).get("overall_score", 0),
            reverse=True,
        )

        report += "\n### 评分前5名\n\n"
        for i, result in enumerate(sorted_results[:5], 1):
            name = result.get("basic_info", {}).get("stock_name", "Unknown")
            code = result.get("basic_info", {}).get("stock_code", "Unknown")
            score = result.get("scoring_system", {}).get("overall_score", 0)
            rec = result.get("investment_recommendation", {}).get(
                "recommendation", "hold"
            )
            report += f"{i}. **{name} ({code})**: {score:.1f}分 [{rec}]\n"

        report += "\n---\n*本报告由QuanTr系统自动生成，仅供参考，不构成投资建议。*\n"

        return report

    @staticmethod
    def save_analysis_to_json(
        analysis_results: List[Dict[str, Any]], output_path: Path
    ) -> bool:
        """保存分析结果为JSON"""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "metadata": {
                    "analysis_date": datetime.now().strftime("%Y-%m-%d"),
                    "generated_at": datetime.now().isoformat(),
                    "total_stocks": len(analysis_results),
                },
                "stocks": analysis_results,
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"保存JSON失败: {e}")
            return False

    @staticmethod
    def save_analysis_to_csv(
        analysis_results: List[Dict[str, Any]], output_path: Path
    ) -> bool:
        """保存分析结果为CSV"""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 提取关键字段
            records = []
            for result in analysis_results:
                record = {
                    "stock_name": result.get("basic_info", {}).get("stock_name", ""),
                    "stock_code": result.get("basic_info", {}).get("stock_code", ""),
                    "current_price": result.get("price_info", {}).get(
                        "current_price", 0
                    ),
                    "overall_score": result.get("scoring_system", {}).get(
                        "overall_score", 0
                    ),
                    "recommendation": result.get("investment_recommendation", {}).get(
                        "recommendation", ""
                    ),
                    "fundamental_score": result.get("scoring_system", {})
                    .get("fundamental_score", {})
                    .get("score", 0),
                    "technical_score": result.get("scoring_system", {})
                    .get("technical_score", {})
                    .get("score", 0),
                    "risk_score": result.get("scoring_system", {})
                    .get("risk_score", {})
                    .get("score", 0),
                }
                records.append(record)

            df = pd.DataFrame(records)
            df.to_csv(output_path, index=False, encoding="utf-8-sig")

            return True
        except Exception as e:
            print(f"保存CSV失败: {e}")
            return False


def main():
    """测试函数"""
    print("🧪 测试数据处理工具...")

    # 测试数据清洗
    sample_data = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=10),
            "open": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "close": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            "high": [102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
            "low": [99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
            "volume": [1000000] * 10,
        }
    )

    cleaned = DataProcessor.clean_price_data(sample_data)
    print(f"✅ 数据清洗完成: {len(cleaned)} 行")

    # 测试报告生成
    sample_results = [
        {
            "basic_info": {"stock_name": "测试股票1", "stock_code": "000001.SZ"},
            "price_info": {"current_price": 10.5},
            "scoring_system": {
                "overall_score": 85.5,
                "fundamental_score": {"score": 80},
                "technical_score": {"score": 90},
                "risk_score": {"score": 85},
            },
            "investment_recommendation": {"recommendation": "strong_buy"},
        }
    ]

    report = ReportGenerator.generate_summary_report(sample_results)
    print(f"\n📄 报告预览:")
    print(report[:500])

    print("\n✅ 数据处理工具测试完成")


if __name__ == "__main__":
    main()
