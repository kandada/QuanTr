# quan_tr/programs/backtesters/strategy_backtester.py
"""
策略回测程序
用于对股票分析策略进行历史回测验证
支持多种策略类型和绩效评估指标
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from quan_tr.config import config


class StrategyBacktester:
    """策略回测器"""

    def __init__(self, initial_capital: float = 100000.0):
        """
        初始化回测器

        Args:
            initial_capital: 初始资金，默认10万
        """
        self.config = config
        self.logger = self._setup_logger()
        self.initial_capital = initial_capital

        # 交易成本设置
        self.commission_rate = config.get(
            "backtest.commission_rate", 0.0003
        )  # 佣金费率
        self.slippage_rate = config.get("backtest.slippage_rate", 0.0001)  # 滑点费率

        # 风险控制设置
        self.stop_loss_rate = config.get("backtest.stop_loss_rate", 0.1)  # 止损比例
        self.take_profit_rate = config.get("backtest.take_profit_rate", 0.2)  # 止盈比例
        self.max_position_ratio = config.get(
            "backtest.max_position_ratio", 0.8
        )  # 最大持仓比例

        self.logger.info(f"✅ 策略回测器初始化成功，初始资金: ¥{initial_capital:,.2f}")

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

            log_file = self.config.base_dir / "logs" / "strategy_backtester.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def load_analysis_results(
        self, start_date: str, end_date: str
    ) -> Dict[str, List[Dict]]:
        """
        加载历史分析结果

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            日期到分析结果列表的映射
        """
        results_by_date = {}

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")

            current = start
            while current <= end:
                date_str = current.strftime("%Y-%m-%d")
                analysis_dir = self.config.get_analysis_dir(date_str)

                # 查找JSON汇总文件
                json_file = analysis_dir / f"stocks_analysis_{date_str}.json"

                if json_file.exists():
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        results_by_date[date_str] = data.get("stocks", [])
                        self.logger.info(
                            f"✅ 加载分析结果: {date_str} ({len(data.get('stocks', []))} 只股票)"
                        )

                current += timedelta(days=1)

            if not results_by_date:
                self.logger.warning(f"⚠️  未找到 {start_date} 到 {end_date} 的分析结果")

            return results_by_date

        except Exception as e:
            self.logger.error(f"❌ 加载分析结果失败: {e}")
            return {}

    def generate_signals(
        self, analysis_results: Dict[str, List[Dict]], strategy_type: str = "simple"
    ) -> Dict[str, List[Dict]]:
        """
        根据分析结果生成交易信号

        Args:
            analysis_results: 分析结果字典
            strategy_type: 策略类型 ('simple', 'momentum', 'contrarian')

        Returns:
            日期到交易信号列表的映射
        """
        signals_by_date = {}

        for date_str, stocks in analysis_results.items():
            signals = []

            for stock in stocks:
                symbol = stock.get("basic_info", {}).get("stock_code", "")
                recommendation = stock.get("investment_recommendation", {}).get(
                    "recommendation", "hold"
                )
                score = stock.get("scoring_system", {}).get("overall_score", 50)
                current_price = stock.get("price_info", {}).get("current_price", 0)

                if current_price <= 0:
                    continue

                # 根据策略类型生成信号
                if strategy_type == "simple":
                    # 简单策略：基于推荐等级
                    if recommendation in ["strong_buy", "buy"]:
                        signal = {
                            "symbol": symbol,
                            "action": "buy",
                            "price": current_price,
                            "confidence": score / 100,
                            "reason": f"推荐等级: {recommendation}, 评分: {score:.1f}",
                        }
                        signals.append(signal)
                    elif recommendation in ["strong_sell", "sell"]:
                        signal = {
                            "symbol": symbol,
                            "action": "sell",
                            "price": current_price,
                            "confidence": (100 - score) / 100,
                            "reason": f"推荐等级: {recommendation}, 评分: {score:.1f}",
                        }
                        signals.append(signal)

                elif strategy_type == "momentum":
                    # 动量策略：只买入评分最高的股票
                    if score >= 70 and recommendation in ["strong_buy", "buy"]:
                        signal = {
                            "symbol": symbol,
                            "action": "buy",
                            "price": current_price,
                            "confidence": score / 100,
                            "reason": f"动量信号: 评分 {score:.1f}",
                        }
                        signals.append(signal)

                elif strategy_type == "contrarian":
                    # 逆向策略：买入评分低但基本面良好的股票
                    fund_score = (
                        stock.get("scoring_system", {})
                        .get("fundamental_score", {})
                        .get("score", 50)
                    )
                    if score < 50 and fund_score >= 60:
                        signal = {
                            "symbol": symbol,
                            "action": "buy",
                            "price": current_price,
                            "confidence": fund_score / 100,
                            "reason": f"逆向信号: 综合评分 {score:.1f}, 基本面 {fund_score:.1f}",
                        }
                        signals.append(signal)

            # 按置信度排序，只保留前N个信号
            signals.sort(key=lambda x: x["confidence"], reverse=True)
            signals_by_date[date_str] = signals[:20]  # 每天最多20个信号

            if signals:
                self.logger.info(f"📊 {date_str}: 生成 {len(signals)} 个交易信号")

        return signals_by_date

    def execute_backtest(
        self,
        signals: Dict[str, List[Dict]],
        price_data: Dict[str, pd.DataFrame],
        rebalance_freq: str = "daily",
    ) -> Dict[str, Any]:
        """
        执行回测

        Args:
            signals: 交易信号字典
            price_data: 价格数据字典 {symbol: DataFrame}
            rebalance_freq: 再平衡频率 ('daily', 'weekly', 'monthly')

        Returns:
            回测结果
        """
        self.logger.info("🚀 开始执行回测...")

        # 初始化
        capital = self.initial_capital
        positions = {}  # 持仓 {symbol: {'shares': x, 'cost': y, 'date': z}}
        trades = []  # 交易记录
        daily_values = []  # 每日资产价值

        sorted_dates = sorted(signals.keys())

        for date_str in sorted_dates:
            day_signals = signals.get(date_str, [])

            # 计算当前持仓市值
            portfolio_value = capital
            for symbol, pos in positions.items():
                if symbol in price_data and not price_data[symbol].empty:
                    # 获取当日价格
                    current_price = self._get_price_on_date(
                        price_data[symbol], date_str
                    )
                    if current_price > 0:
                        portfolio_value += pos["shares"] * current_price

            daily_values.append(
                {
                    "date": date_str,
                    "portfolio_value": portfolio_value,
                    "cash": capital,
                    "positions_value": portfolio_value - capital,
                }
            )

            # 执行交易信号
            for signal in day_signals:
                symbol = signal["symbol"]
                action = signal["action"]
                target_price = signal["price"]

                if symbol not in price_data:
                    continue

                # 获取实际交易价格（加入滑点）
                actual_price = self._get_price_on_date(price_data[symbol], date_str)
                if actual_price <= 0:
                    continue

                # 买入信号
                if action == "buy" and symbol not in positions:
                    # 计算可买入股数（均分资金）
                    max_position_value = (
                        portfolio_value * self.max_position_ratio / len(day_signals)
                        if day_signals
                        else 0
                    )
                    max_shares = (
                        int(max_position_value / actual_price / 100) * 100
                    )  # 整手

                    if max_shares > 0 and capital >= max_shares * actual_price * (
                        1 + self.commission_rate
                    ):
                        cost = max_shares * actual_price
                        commission = cost * self.commission_rate
                        total_cost = cost + commission

                        if capital >= total_cost:
                            positions[symbol] = {
                                "shares": max_shares,
                                "cost": actual_price,
                                "date": date_str,
                                "highest_price": actual_price,  # 用于移动止盈
                            }
                            capital -= total_cost

                            trades.append(
                                {
                                    "date": date_str,
                                    "symbol": symbol,
                                    "action": "buy",
                                    "shares": max_shares,
                                    "price": actual_price,
                                    "commission": commission,
                                    "total_cost": total_cost,
                                    "reason": signal.get("reason", ""),
                                }
                            )

                            self.logger.debug(
                                f"买入 {symbol}: {max_shares}股 @ ¥{actual_price:.2f}"
                            )

                # 卖出信号
                elif action == "sell" and symbol in positions:
                    pos = positions[symbol]
                    shares = pos["shares"]
                    revenue = shares * actual_price
                    commission = revenue * self.commission_rate
                    net_revenue = revenue - commission

                    capital += net_revenue

                    # 计算盈亏
                    profit = net_revenue - (
                        shares * pos["cost"] * (1 + self.commission_rate)
                    )

                    trades.append(
                        {
                            "date": date_str,
                            "symbol": symbol,
                            "action": "sell",
                            "shares": shares,
                            "price": actual_price,
                            "commission": commission,
                            "net_revenue": net_revenue,
                            "profit": profit,
                            "return_pct": profit / (shares * pos["cost"]) * 100,
                            "reason": signal.get("reason", ""),
                        }
                    )

                    del positions[symbol]
                    self.logger.debug(
                        f"卖出 {symbol}: {shares}股 @ ¥{actual_price:.2f}, 盈亏: ¥{profit:.2f}"
                    )

            # 检查止损止盈
            for symbol in list(positions.keys()):
                pos = positions[symbol]
                current_price = self._get_price_on_date(
                    price_data.get(symbol, pd.DataFrame()), date_str
                )

                if current_price <= 0:
                    continue

                # 更新最高价（用于移动止盈）
                if current_price > pos["highest_price"]:
                    pos["highest_price"] = current_price

                # 止损检查
                loss_pct = (pos["cost"] - current_price) / pos["cost"]
                if loss_pct >= self.stop_loss_rate:
                    # 执行止损
                    shares = pos["shares"]
                    revenue = shares * current_price
                    commission = revenue * self.commission_rate
                    net_revenue = revenue - commission

                    capital += net_revenue
                    profit = net_revenue - (
                        shares * pos["cost"] * (1 + self.commission_rate)
                    )

                    trades.append(
                        {
                            "date": date_str,
                            "symbol": symbol,
                            "action": "sell",
                            "shares": shares,
                            "price": current_price,
                            "commission": commission,
                            "net_revenue": net_revenue,
                            "profit": profit,
                            "return_pct": profit / (shares * pos["cost"]) * 100,
                            "reason": f"止损: 跌幅 {loss_pct * 100:.2f}%",
                        }
                    )

                    del positions[symbol]
                    self.logger.debug(f"止损 {symbol}: 跌幅 {loss_pct * 100:.2f}%")

                # 止盈检查
                profit_pct = (current_price - pos["cost"]) / pos["cost"]
                if profit_pct >= self.take_profit_rate:
                    # 执行止盈
                    shares = pos["shares"]
                    revenue = shares * current_price
                    commission = revenue * self.commission_rate
                    net_revenue = revenue - commission

                    capital += net_revenue
                    profit = net_revenue - (
                        shares * pos["cost"] * (1 + self.commission_rate)
                    )

                    trades.append(
                        {
                            "date": date_str,
                            "symbol": symbol,
                            "action": "sell",
                            "shares": shares,
                            "price": current_price,
                            "commission": commission,
                            "net_revenue": net_revenue,
                            "profit": profit,
                            "return_pct": profit_pct * 100,
                            "reason": f"止盈: 涨幅 {profit_pct * 100:.2f}%",
                        }
                    )

                    del positions[symbol]
                    self.logger.debug(f"止盈 {symbol}: 涨幅 {profit_pct * 100:.2f}%")

        # 计算最终价值（清空持仓）
        final_value = capital
        for symbol, pos in positions.items():
            if symbol in price_data and not price_data[symbol].empty:
                last_date = sorted_dates[-1] if sorted_dates else None
                if last_date:
                    current_price = self._get_price_on_date(
                        price_data[symbol], last_date
                    )
                    if current_price > 0:
                        final_value += pos["shares"] * current_price

        # 生成回测结果
        result = self._calculate_performance(
            initial_capital=self.initial_capital,
            final_value=final_value,
            trades=trades,
            daily_values=daily_values,
            start_date=sorted_dates[0] if sorted_dates else "",
            end_date=sorted_dates[-1] if sorted_dates else "",
        )

        result["trades"] = trades
        result["positions"] = positions
        result["daily_values"] = daily_values

        self.logger.info(
            f"✅ 回测完成: 收益率 {result.get('total_return_pct', 0):.2f}%"
        )

        return result

    def _get_price_on_date(self, price_df: pd.DataFrame, date_str: str) -> float:
        """获取指定日期的价格"""
        try:
            if price_df.empty:
                return 0.0

            # 查找日期
            if "date" in price_df.columns:
                row = price_df[price_df["date"] == date_str]
                if not row.empty:
                    return float(row.iloc[0].get("close", 0))

            # 如果没有精确匹配，返回最后一个价格
            if "close" in price_df.columns and not price_df.empty:
                return float(price_df["close"].iloc[-1])

            return 0.0
        except:
            return 0.0

    def _calculate_performance(
        self,
        initial_capital: float,
        final_value: float,
        trades: List[Dict],
        daily_values: List[Dict],
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """计算绩效指标"""

        # 总收益率
        total_return = final_value - initial_capital
        total_return_pct = (total_return / initial_capital) * 100

        # 交易统计
        total_trades = len(trades)
        buy_trades = [t for t in trades if t["action"] == "buy"]
        sell_trades = [t for t in trades if t["action"] == "sell"]

        winning_trades = [t for t in sell_trades if t.get("profit", 0) > 0]
        losing_trades = [t for t in sell_trades if t.get("profit", 0) <= 0]

        win_rate = len(winning_trades) / len(sell_trades) * 100 if sell_trades else 0

        total_profit = sum(t.get("profit", 0) for t in winning_trades)
        total_loss = sum(t.get("profit", 0) for t in losing_trades)

        profit_factor = (
            abs(total_profit / total_loss) if total_loss != 0 else float("inf")
        )

        avg_profit = total_profit / len(winning_trades) if winning_trades else 0
        avg_loss = total_loss / len(losing_trades) if losing_trades else 0

        # 计算最大回撤
        max_drawdown = 0
        max_drawdown_pct = 0
        peak = initial_capital

        for dv in daily_values:
            value = dv["portfolio_value"]
            if value > peak:
                peak = value
            drawdown = peak - value
            drawdown_pct = (drawdown / peak) * 100 if peak > 0 else 0

            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_pct = drawdown_pct

        # 计算夏普比率（简化版，假设无风险利率为3%）
        if len(daily_values) > 1:
            daily_returns = []
            for i in range(1, len(daily_values)):
                prev_value = daily_values[i - 1]["portfolio_value"]
                curr_value = daily_values[i]["portfolio_value"]
                if prev_value > 0:
                    daily_return = (curr_value - prev_value) / prev_value
                    daily_returns.append(daily_return)

            if daily_returns:
                avg_daily_return = np.mean(daily_returns)
                std_daily_return = np.std(daily_returns)

                # 年化夏普比率
                if std_daily_return > 0:
                    sharpe_ratio = ((avg_daily_return * 252) - 0.03) / (
                        std_daily_return * np.sqrt(252)
                    )
                else:
                    sharpe_ratio = 0
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0

        # 计算年化收益率
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            days = (end - start).days
            years = days / 365.25

            if years > 0:
                annual_return_pct = (
                    (final_value / initial_capital) ** (1 / years) - 1
                ) * 100
            else:
                annual_return_pct = total_return_pct
        except:
            annual_return_pct = total_return_pct

        return {
            "initial_capital": initial_capital,
            "final_value": final_value,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "annual_return_pct": annual_return_pct,
            "total_trades": total_trades,
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_profit": avg_profit,
            "avg_loss": avg_loss,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown_pct,
            "sharpe_ratio": sharpe_ratio,
            "start_date": start_date,
            "end_date": end_date,
        }

    def generate_backtest_report(self, result: Dict[str, Any]) -> str:
        """生成回测报告"""

        report = f"""# 策略回测报告

**回测期间**: {result.get("start_date", "N/A")} 至 {result.get("end_date", "N/A")}
**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 1. 回测概览

| 指标 | 数值 |
|------|------|
| 初始资金 | ¥{result.get("initial_capital", 0):,.2f} |
| 最终资产 | ¥{result.get("final_value", 0):,.2f} |
| 总收益 | ¥{result.get("total_return", 0):,.2f} |
| **总收益率** | **{result.get("total_return_pct", 0):.2f}%** |
| 年化收益率 | {result.get("annual_return_pct", 0):.2f}% |

## 2. 交易统计

| 指标 | 数值 |
|------|------|
| 总交易次数 | {result.get("total_trades", 0)} |
| 买入次数 | {result.get("buy_trades", 0)} |
| 卖出次数 | {result.get("sell_trades", 0)} |
| 盈利交易 | {result.get("winning_trades", 0)} |
| 亏损交易 | {result.get("losing_trades", 0)} |
| **胜率** | **{result.get("win_rate", 0):.2f}%** |
| 盈亏比 | {result.get("profit_factor", 0):.2f} |
| 平均盈利 | ¥{result.get("avg_profit", 0):,.2f} |
| 平均亏损 | ¥{result.get("avg_loss", 0):,.2f} |

## 3. 风险指标

| 指标 | 数值 |
|------|------|
| **最大回撤** | **{result.get("max_drawdown_pct", 0):.2f}%** |
| 最大回撤金额 | ¥{result.get("max_drawdown", 0):,.2f} |
| 夏普比率 | {result.get("sharpe_ratio", 0):.2f} |

## 4. 交易记录

"""

        # 添加最近的交易记录
        trades = result.get("trades", [])
        if trades:
            report += "| 日期 | 股票 | 操作 | 股数 | 价格 | 盈亏 | 原因 |\n"
            report += "|------|------|------|------|------|------|------|\n"

            for trade in trades[-20:]:  # 只显示最近20条
                date = trade.get("date", "")
                symbol = trade.get("symbol", "")
                action = trade.get("action", "")
                shares = trade.get("shares", 0)
                price = trade.get("price", 0)
                profit = trade.get("profit", 0)
                reason = trade.get("reason", "")[:30]

                report += f"| {date} | {symbol} | {action} | {shares} | ¥{price:.2f} | ¥{profit:.2f} | {reason} |\n"
        else:
            report += "暂无交易记录\n"

        report += """

## 5. 策略评估

"""

        # 策略评估
        total_return_pct = result.get("total_return_pct", 0)
        win_rate = result.get("win_rate", 0)
        max_drawdown_pct = result.get("max_drawdown_pct", 0)
        sharpe_ratio = result.get("sharpe_ratio", 0)

        if total_return_pct > 20 and win_rate > 50 and max_drawdown_pct < 15:
            report += "**策略评价**: ✅ 表现优秀\n\n"
            report += "- 收益率较高，胜率良好\n"
            report += "- 回撤控制较好\n"
            report += "- 建议继续优化使用\n"
        elif total_return_pct > 0:
            report += "**策略评价**: ⚡ 表现一般\n\n"
            report += "- 策略有盈利能力但需改进\n"
            report += "- 建议调整参数或优化信号生成逻辑\n"
        else:
            report += "**策略评价**: ❌ 表现不佳\n\n"
            report += "- 策略未能盈利\n"
            report += "- 建议重新设计策略逻辑\n"

        report += """

---

**免责声明**: 本回测结果基于历史数据，仅供参考，不构成投资建议。 past performance does not guarantee future results.
"""

        return report

    def run_backtest(
        self,
        start_date: str,
        end_date: str,
        strategy_type: str = "simple",
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> Dict[str, Any]:
        """
        运行完整回测流程

        Args:
            start_date: 开始日期
            end_date: 结束日期
            strategy_type: 策略类型
            price_data: 价格数据（可选，如果不提供需要从数据源获取）

        Returns:
            回测结果
        """
        self.logger.info(f"🚀 启动回测: {start_date} 至 {end_date}")

        # 1. 加载历史分析结果
        analysis_results = self.load_analysis_results(start_date, end_date)
        if not analysis_results:
            self.logger.error("❌ 未找到分析结果，无法进行回测")
            return {"error": "未找到分析结果"}

        # 2. 生成交易信号
        signals = self.generate_signals(analysis_results, strategy_type)
        if not signals:
            self.logger.error("❌ 未生成交易信号")
            return {"error": "未生成交易信号"}

        # 3. 获取价格数据（如果未提供）
        if price_data is None:
            # 这里简化处理，实际应该从数据源获取
            self.logger.warning("⚠️  未提供价格数据，使用模拟数据")
            price_data = {}

        # 4. 执行回测
        result = self.execute_backtest(signals, price_data)

        # 5. 生成报告
        report = self.generate_backtest_report(result)
        result["report"] = report

        # 6. 保存结果
        self._save_backtest_result(result, start_date, end_date)

        return result

    def _save_backtest_result(
        self, result: Dict[str, Any], start_date: str, end_date: str
    ) -> None:
        """保存回测结果"""
        try:
            save_dir = self.config.get_backtest_dir()
            save_dir.mkdir(parents=True, exist_ok=True)

            filename = f"backtest_{start_date}_to_{end_date}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 保存JSON
            json_path = save_dir / f"{filename}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                # 移除不可序列化的数据
                save_data = {
                    k: v
                    for k, v in result.items()
                    if k not in ["trades", "positions", "daily_values"]
                }
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            # 保存报告
            report_path = save_dir / f"{filename}.md"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(result.get("report", ""))

            self.logger.info(f"✅ 回测结果已保存: {report_path}")

        except Exception as e:
            self.logger.error(f"❌ 保存回测结果失败: {e}")


def main():
    """主函数，用于测试"""
    print("🧪 策略回测器测试")
    print("=" * 60)

    # 创建回测器
    backtester = StrategyBacktester(initial_capital=100000.0)

    # 模拟分析结果
    mock_analysis = {
        "2024-01-01": [
            {
                "basic_info": {"stock_code": "000001.SZ"},
                "price_info": {"current_price": 10.0},
                "scoring_system": {"overall_score": 85},
                "investment_recommendation": {"recommendation": "buy"},
            },
            {
                "basic_info": {"stock_code": "000002.SZ"},
                "price_info": {"current_price": 20.0},
                "scoring_system": {"overall_score": 45},
                "investment_recommendation": {"recommendation": "hold"},
            },
        ],
        "2024-01-02": [
            {
                "basic_info": {"stock_code": "000001.SZ"},
                "price_info": {"current_price": 10.5},
                "scoring_system": {"overall_score": 80},
                "investment_recommendation": {"recommendation": "buy"},
            },
        ],
    }

    # 模拟价格数据
    mock_prices = {
        "000001.SZ": pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "close": [10.0, 10.5, 11.0],
            }
        ),
    }

    # 生成信号
    print("\n1. 生成交易信号...")
    signals = backtester.generate_signals(mock_analysis, strategy_type="simple")
    print(f"   生成 {sum(len(s) for s in signals.values())} 个信号")

    # 执行回测
    print("\n2. 执行回测...")
    result = backtester.execute_backtest(signals, mock_prices)

    print(f"\n3. 回测结果:")
    print(f"   初始资金: ¥{result.get('initial_capital', 0):,.2f}")
    print(f"   最终资产: ¥{result.get('final_value', 0):,.2f}")
    print(f"   总收益率: {result.get('total_return_pct', 0):.2f}%")
    print(f"   交易次数: {result.get('total_trades', 0)}")
    print(f"   胜率: {result.get('win_rate', 0):.2f}%")

    # 生成报告
    print("\n4. 生成报告...")
    report = backtester.generate_backtest_report(result)
    print(f"   报告长度: {len(report)} 字符")

    print("\n✅ 回测器测试完成!")


if __name__ == "__main__":
    main()
