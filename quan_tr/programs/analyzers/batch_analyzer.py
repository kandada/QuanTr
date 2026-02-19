# programs/batch_analyzer.py
"""
批量分析程序
用于批量分析股票池中的所有股票
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from quan_tr.config import config
from quan_tr.programs.analyzers.stock_analyzer import StockAnalyzer
from quan_tr.programs.utils.data_processor import ReportGenerator


class BatchAnalyzer:
    """批量分析器"""

    def __init__(self):
        """初始化批量分析器"""
        self.config = config
        self.stock_analyzer = StockAnalyzer()
        self.results = []

    def load_stocks_pool(self) -> List[Dict[str, Any]]:
        """加载股票池"""
        stocks = config.get_stocks_pool()

        if not stocks:
            print("⚠️  股票池为空或无法加载")
            return []

        print(f"✅ 成功加载 {len(stocks)} 只股票")
        return stocks

    def analyze_all_stocks(
        self, date_str: Optional[str] = None, symbols: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        批量分析所有股票

        Args:
            date_str: 分析日期
            symbols: 指定分析的股票列表，None则分析股票池中的所有股票

        Returns:
            所有股票的分析结果列表
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # 确定要分析的股票列表
        if symbols is None:
            stocks = self.load_stocks_pool()
            symbols = [stock.get("symbol") for stock in stocks if stock.get("symbol")]

        if not symbols:
            print("❌ 没有要分析的股票")
            return []

        print(f"\n{'=' * 60}")
        print(f"开始批量分析")
        print(f"分析日期: {date_str}")
        print(f"股票数量: {len(symbols)}")
        print(f"{'=' * 60}\n")

        results = []
        success_count = 0
        fail_count = 0

        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] 分析股票: {symbol}")
            print("-" * 40)

            try:
                result = self.stock_analyzer.analyze_stock(
                    symbol=symbol, date_str=date_str, save_results=True
                )

                results.append(result)

                if result.get("error"):
                    fail_count += 1
                    print(f"⚠️  分析失败: {result.get('error')}")
                else:
                    success_count += 1
                    score = result.get("scoring_system", {}).get("overall_score", 0)
                    rec = result.get("investment_recommendation", {}).get(
                        "recommendation", "N/A"
                    )
                    print(f"✅ 分析完成 - 评分: {score:.1f}, 推荐: {rec}")

            except Exception as e:
                fail_count += 1
                print(f"❌ 分析异常: {e}")
                results.append({"basic_info": {"stock_code": symbol}, "error": str(e)})

        print(f"\n{'=' * 60}")
        print("批量分析完成")
        print(f"{'=' * 60}")
        print(f"总计: {len(symbols)} 只")
        print(f"成功: {success_count} 只")
        print(f"失败: {fail_count} 只")
        print(f"{'=' * 60}\n")

        # 保存汇总结果
        self._save_summary_results(results, date_str)

        return results

    def _save_summary_results(
        self, results: List[Dict[str, Any]], date_str: str
    ) -> None:
        """保存汇总结果"""
        try:
            # 保存目录
            save_dir = self.config.get_analysis_dir(date_str)
            save_dir.mkdir(parents=True, exist_ok=True)

            # 过滤掉有错误的结果
            valid_results = [r for r in results if not r.get("error")]

            if not valid_results:
                print("⚠️  没有有效的分析结果可供保存")
                return

            # 生成汇总报告
            print("\n📝 生成汇总报告...")

            # 1. 保存JSON汇总
            json_path = save_dir / f"stocks_analysis_{date_str}.json"
            if ReportGenerator.save_analysis_to_json(valid_results, json_path):
                print(f"✅ JSON汇总已保存: {json_path}")

            # 2. 保存CSV汇总
            csv_path = save_dir / f"stocks_analysis_{date_str}.csv"
            if ReportGenerator.save_analysis_to_csv(valid_results, csv_path):
                print(f"✅ CSV汇总已保存: {csv_path}")

            # 3. 生成Markdown汇总报告
            md_report = ReportGenerator.generate_summary_report(valid_results, date_str)
            md_path = save_dir / f"stocks_analysis_report_{date_str}.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_report)
            print(f"✅ Markdown报告已保存: {md_path}")

            # 显示汇总统计
            self._display_summary(valid_results)

        except Exception as e:
            print(f"❌ 保存汇总结果失败: {e}")

    def _display_summary(self, results: List[Dict[str, Any]]) -> None:
        """显示汇总统计"""
        if not results:
            return

        print(f"\n{'=' * 60}")
        print("分析汇总统计")
        print(f"{'=' * 60}")

        # 推荐分布
        rec_count = {}
        for result in results:
            rec = result.get("investment_recommendation", {}).get(
                "recommendation", "hold"
            )
            rec_count[rec] = rec_count.get(rec, 0) + 1

        print("\n推荐分布:")
        rec_names = {
            "strong_buy": "强烈买入",
            "buy": "买入",
            "hold": "持有",
            "sell": "卖出",
            "strong_sell": "强烈卖出",
        }
        for rec, count in sorted(rec_count.items(), key=lambda x: x[1], reverse=True):
            name = rec_names.get(rec, rec)
            pct = count / len(results) * 100
            print(f"  {name}: {count}只 ({pct:.1f}%)")

        # 评分统计
        scores = [r.get("scoring_system", {}).get("overall_score", 0) for r in results]
        if scores:
            print(f"\n评分统计:")
            print(f"  平均分: {sum(scores) / len(scores):.1f}")
            print(f"  最高分: {max(scores):.1f}")
            print(f"  最低分: {min(scores):.1f}")

        # 前5名
        sorted_results = sorted(
            results,
            key=lambda x: x.get("scoring_system", {}).get("overall_score", 0),
            reverse=True,
        )

        print(f"\n评分前5名:")
        for i, result in enumerate(sorted_results[:5], 1):
            name = result.get("basic_info", {}).get("stock_name", "Unknown")
            code = result.get("basic_info", {}).get("stock_code", "Unknown")
            score = result.get("scoring_system", {}).get("overall_score", 0)
            rec = result.get("investment_recommendation", {}).get(
                "recommendation", "hold"
            )
            print(f"  {i}. {name} ({code}): {score:.1f}分 [{rec}]")

        print(f"{'=' * 60}\n")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="批量分析股票")
    parser.add_argument("--date", help="分析日期 (YYYY-MM-DD格式，默认为今天)")
    parser.add_argument("--symbols", nargs="+", help="指定要分析的股票代码列表")
    parser.add_argument(
        "--test", action="store_true", help="使用测试模式（只分析第一只股票）"
    )

    args = parser.parse_args()

    # 创建分析器
    analyzer = BatchAnalyzer()

    if args.test:
        # 测试模式：只分析一只股票
        print("🧪 测试模式：只分析第一只股票")
        stocks = analyzer.load_stocks_pool()
        if stocks:
            test_symbol = stocks[0].get("symbol")
            if test_symbol:
                results = analyzer.analyze_all_stocks(
                    date_str=args.date, symbols=[test_symbol]
                )
        else:
            # 使用默认测试股票
            results = analyzer.analyze_all_stocks(
                date_str=args.date, symbols=["000001.SZ"]
            )
    else:
        # 正常模式：分析所有股票
        results = analyzer.analyze_all_stocks(date_str=args.date, symbols=args.symbols)

    print("\n✅ 批量分析程序执行完成")


if __name__ == "__main__":
    main()
