# programs/analyzers/technical_analyzer.py
"""
技术面分析程序
用于分析股票的技术指标、价格趋势、支撑阻力等
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


class TechnicalAnalyzer:
    """技术面分析器"""

    def __init__(self):
        """初始化技术面分析器"""
        self.config = config
        self.logger = self._setup_logger()
        self.logger.info("✅ 技术面分析器初始化成功")

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
            log_file = self.config.base_dir / "logs" / "technical_analyzer.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def analyze_trend(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        分析价格趋势

        Args:
            price_data: 价格数据DataFrame，包含开盘价、收盘价、最高价、最低价、成交量

        Returns:
            趋势分析结果
        """
        trend_analysis = {
            "trend_direction": "sideways",
            "trend_strength": 0.0,
            "moving_averages": {},
            "price_vs_ma": {},
        }

        try:
            if price_data.empty or len(price_data) < 20:
                self.logger.warning("价格数据不足，无法分析趋势")
                return trend_analysis

            # 获取最新价格
            current_price = price_data["收盘"].iloc[-1]

            # 计算移动平均线
            ma_periods = self.config.get(
                "analysis.moving_average_periods", [5, 10, 20, 60, 120]
            )

            for period in ma_periods:
                if len(price_data) >= period:
                    ma = price_data["收盘"].rolling(window=period).mean().iloc[-1]
                    trend_analysis["moving_averages"][f"ma_{period}"] = round(
                        float(ma), 2
                    )

                    # 计算价格与均线的偏离
                    deviation = (current_price - ma) / ma * 100
                    trend_analysis["price_vs_ma"][f"price_vs_ma{period}"] = round(
                        float(deviation), 2
                    )

            # 判断趋势方向
            ma_20 = trend_analysis["moving_averages"].get("ma_20", current_price)
            ma_60 = trend_analysis["moving_averages"].get("ma_60", current_price)

            if current_price > ma_20 > ma_60:
                trend_analysis["trend_direction"] = "up"
                trend_analysis["trend_strength"] = self._calculate_trend_strength(
                    price_data
                )
            elif current_price < ma_20 < ma_60:
                trend_analysis["trend_direction"] = "down"
                trend_analysis["trend_strength"] = self._calculate_trend_strength(
                    price_data
                )
            else:
                trend_analysis["trend_direction"] = "sideways"
                trend_analysis["trend_strength"] = 0.0

            self.logger.info(
                f"✅ 趋势分析完成: {trend_analysis['trend_direction']}, "
                f"强度: {trend_analysis['trend_strength']:.2f}"
            )

        except Exception as e:
            self.logger.error(f"❌ 趋势分析失败: {e}")

        return trend_analysis

    def _calculate_trend_strength(self, price_data: pd.DataFrame) -> float:
        """计算趋势强度"""
        try:
            if len(price_data) < 20:
                return 0.0

            # 使用价格变化的累积值来衡量趋势强度
            returns = price_data["收盘"].pct_change().dropna()

            if len(returns) < 10:
                return 0.0

            # 计算收益率的标准差
            std = returns.std()

            if std == 0:
                return 0.0

            # 计算Sharpe-like比率（平均收益/标准差）
            mean_return = returns.mean()
            strength = abs(mean_return / std) * np.sqrt(252)  # 年化

            return min(strength * 10, 100)  # 限制在100以内

        except Exception as e:
            self.logger.warning(f"计算趋势强度失败: {e}")
            return 0.0

    def analyze_momentum(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        分析动量指标

        Args:
            price_data: 价格数据DataFrame

        Returns:
            动量分析结果
        """
        momentum_analysis = {
            "rsi_14": 50.0,
            "rsi_status": "neutral",
            "macd": 0.0,
            "macd_signal": 0.0,
            "macd_histogram": 0.0,
        }

        try:
            if price_data.empty or len(price_data) < 26:
                self.logger.warning("价格数据不足，无法分析动量")
                return momentum_analysis

            close_prices = price_data["收盘"]

            # 计算RSI
            rsi_period = self.config.get("analysis.rsi_period", 14)
            momentum_analysis["rsi_14"] = round(self._calculate_rsi(close_prices), 2)

            # 判断RSI状态
            if momentum_analysis["rsi_14"] > 70:
                momentum_analysis["rsi_status"] = "overbought"
            elif momentum_analysis["rsi_14"] < 30:
                momentum_analysis["rsi_status"] = "oversold"
            else:
                momentum_analysis["rsi_status"] = "neutral"

            # 计算MACD
            macd_result = self._calculate_macd(close_prices)
            momentum_analysis.update(
                {
                    "macd": round(macd_result["macd"], 4),
                    "macd_signal": round(macd_result["signal"], 4),
                    "macd_histogram": round(macd_result["histogram"], 4),
                }
            )

            self.logger.info(
                f"✅ 动量分析完成: RSI={momentum_analysis['rsi_14']}, "
                f"MACD={momentum_analysis['macd']}"
            )

        except Exception as e:
            self.logger.error(f"❌ 动量分析失败: {e}")

        return momentum_analysis

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """计算RSI指标"""
        try:
            if len(prices) < period + 1:
                return 50.0

            # 计算价格变化
            delta = prices.diff().dropna()

            # 分离上涨和下跌
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            # 计算平均上涨和下跌
            avg_gain = gain.rolling(window=period).mean().iloc[-1]
            avg_loss = loss.rolling(window=period).mean().iloc[-1]

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return float(rsi)

        except Exception as e:
            self.logger.warning(f"计算RSI失败: {e}")
            return 50.0

    def _calculate_macd(
        self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Dict[str, float]:
        """计算MACD指标"""
        try:
            if len(prices) < slow + signal:
                return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

            # 计算EMA
            ema_fast = prices.ewm(span=fast, adjust=False).mean()
            ema_slow = prices.ewm(span=slow, adjust=False).mean()

            # MACD线
            macd_line = ema_fast - ema_slow

            # 信号线
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()

            # MACD柱状图
            histogram = macd_line - signal_line

            return {
                "macd": float(macd_line.iloc[-1]),
                "signal": float(signal_line.iloc[-1]),
                "histogram": float(histogram.iloc[-1]),
            }

        except Exception as e:
            self.logger.warning(f"计算MACD失败: {e}")
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

    def analyze_volatility(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        分析波动率指标

        Args:
            price_data: 价格数据DataFrame

        Returns:
            波动率分析结果
        """
        volatility_analysis = {
            "bollinger_upper": 0.0,
            "bollinger_middle": 0.0,
            "bollinger_lower": 0.0,
            "bollinger_position": 0.0,
            "atr": 0.0,
            "volatility_20d": 0.0,
        }

        try:
            if price_data.empty or len(price_data) < 20:
                self.logger.warning("价格数据不足，无法分析波动率")
                return volatility_analysis

            close_prices = price_data["收盘"]
            high_prices = price_data["最高"]
            low_prices = price_data["最低"]
            current_price = close_prices.iloc[-1]

            # 计算布林带
            period = 20
            std_multiplier = 2

            sma = close_prices.rolling(window=period).mean().iloc[-1]
            std = close_prices.rolling(window=period).std().iloc[-1]

            volatility_analysis["bollinger_middle"] = round(float(sma), 2)
            volatility_analysis["bollinger_upper"] = round(
                float(sma + std_multiplier * std), 2
            )
            volatility_analysis["bollinger_lower"] = round(
                float(sma - std_multiplier * std), 2
            )

            # 计算布林带位置（价格在布林带中的位置，0-100）
            if std != 0:
                bollinger_range = (
                    volatility_analysis["bollinger_upper"]
                    - volatility_analysis["bollinger_lower"]
                )
                if bollinger_range > 0:
                    position = (
                        (current_price - volatility_analysis["bollinger_lower"])
                        / bollinger_range
                        * 100
                    )
                    volatility_analysis["bollinger_position"] = round(
                        float(np.clip(position, 0, 100)), 2
                    )

            # 计算ATR（Average True Range）
            volatility_analysis["atr"] = round(self._calculate_atr(price_data), 4)

            # 计算20日波动率（年化标准差）
            returns = close_prices.pct_change().dropna()
            if len(returns) >= 20:
                volatility = returns.tail(20).std() * np.sqrt(252) * 100
                volatility_analysis["volatility_20d"] = round(float(volatility), 2)

            self.logger.info(
                f"✅ 波动率分析完成: 20日波动率={volatility_analysis['volatility_20d']}%, "
                f"布林带位置={volatility_analysis['bollinger_position']}"
            )

        except Exception as e:
            self.logger.error(f"❌ 波动率分析失败: {e}")

        return volatility_analysis

    def _calculate_atr(self, price_data: pd.DataFrame, period: int = 14) -> float:
        """计算ATR指标"""
        try:
            if len(price_data) < period + 1:
                return 0.0

            high = price_data["最高"]
            low = price_data["最低"]
            close = price_data["收盘"]

            # 计算真实波动范围（True Range）
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))

            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # 计算ATR
            atr = tr.rolling(window=period).mean().iloc[-1]

            return float(atr)

        except Exception as e:
            self.logger.warning(f"计算ATR失败: {e}")
            return 0.0

    def analyze_volume(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        分析成交量指标

        Args:
            price_data: 价格数据DataFrame，必须包含成交量列

        Returns:
            成交量分析结果
        """
        volume_analysis = {
            "volume_ma_20": 0.0,
            "volume_ratio": 1.0,
            "obv": 0,
            "volume_trend": "neutral",
        }

        try:
            if price_data.empty or len(price_data) < 20:
                self.logger.warning("价格数据不足，无法分析成交量")
                return volume_analysis

            if "成交量" not in price_data.columns:
                self.logger.warning("价格数据缺少成交量列")
                return volume_analysis

            volumes = price_data["成交量"]
            current_volume = volumes.iloc[-1]

            # 计算20日成交量均线
            volume_ma_20 = volumes.rolling(window=20).mean().iloc[-1]
            volume_analysis["volume_ma_20"] = round(float(volume_ma_20), 2)

            # 计算成交量比率（当前成交量/20日均量）
            if volume_ma_20 > 0:
                volume_ratio = current_volume / volume_ma_20
                volume_analysis["volume_ratio"] = round(float(volume_ratio), 2)

            # 计算OBV（On Balance Volume）
            obv = self._calculate_obv(price_data)
            volume_analysis["obv"] = int(obv)

            # 判断成交量趋势
            if volume_analysis["volume_ratio"] > 1.5:
                volume_analysis["volume_trend"] = "high"
            elif volume_analysis["volume_ratio"] < 0.7:
                volume_analysis["volume_trend"] = "low"
            else:
                volume_analysis["volume_trend"] = "normal"

            self.logger.info(
                f"✅ 成交量分析完成: 量比={volume_analysis['volume_ratio']}, "
                f"OBV={volume_analysis['obv']}"
            )

        except Exception as e:
            self.logger.error(f"❌ 成交量分析失败: {e}")

        return volume_analysis

    def _calculate_obv(self, price_data: pd.DataFrame) -> float:
        """计算OBV指标"""
        try:
            close_prices = price_data["收盘"]
            volumes = price_data["成交量"]

            obv = [volumes.iloc[0]]

            for i in range(1, len(close_prices)):
                if close_prices.iloc[i] > close_prices.iloc[i - 1]:
                    obv.append(obv[-1] + volumes.iloc[i])
                elif close_prices.iloc[i] < close_prices.iloc[i - 1]:
                    obv.append(obv[-1] - volumes.iloc[i])
                else:
                    obv.append(obv[-1])

            return float(obv[-1])

        except Exception as e:
            self.logger.warning(f"计算OBV失败: {e}")
            return 0.0

    def analyze_support_resistance(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        分析支撑和阻力位

        Args:
            price_data: 价格数据DataFrame

        Returns:
            支撑阻力分析结果
        """
        sr_analysis = {
            "support_levels": [],
            "resistance_levels": [],
            "current_support_distance": 0.0,
            "current_resistance_distance": 0.0,
        }

        try:
            if price_data.empty or len(price_data) < 60:
                self.logger.warning("价格数据不足，无法分析支撑阻力")
                return sr_analysis

            high_prices = price_data["最高"]
            low_prices = price_data["最低"]
            close_prices = price_data["收盘"]
            current_price = close_prices.iloc[-1]

            # 获取近期高低点
            recent_highs = high_prices.tail(60)
            recent_lows = low_prices.tail(60)

            # 找到主要阻力位（近期高点）
            resistance_1 = recent_highs.max()
            resistance_2 = recent_highs.quantile(0.75)
            resistance_3 = recent_highs.quantile(0.90)

            sr_analysis["resistance_levels"] = [
                round(float(resistance_1), 2),
                round(float(resistance_2), 2),
                round(float(resistance_3), 2),
            ]

            # 找到主要支撑位（近期低点）
            support_1 = recent_lows.min()
            support_2 = recent_lows.quantile(0.25)
            support_3 = recent_lows.quantile(0.10)

            sr_analysis["support_levels"] = [
                round(float(support_1), 2),
                round(float(support_2), 2),
                round(float(support_3), 2),
            ]

            # 计算到最近的支撑和阻力的距离
            if current_price > support_1:
                sr_analysis["current_support_distance"] = round(
                    (current_price - support_1) / current_price * 100, 2
                )

            if current_price < resistance_1:
                sr_analysis["current_resistance_distance"] = round(
                    (resistance_1 - current_price) / current_price * 100, 2
                )

            self.logger.info(
                f"✅ 支撑阻力分析完成: 支撑={sr_analysis['support_levels']}, "
                f"阻力={sr_analysis['resistance_levels']}"
            )

        except Exception as e:
            self.logger.error(f"❌ 支撑阻力分析失败: {e}")

        return sr_analysis

    def generate_technical_score(
        self, technical_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成技术面综合评分

        Args:
            technical_results: 技术分析结果

        Returns:
            综合评分结果
        """
        score_results = {
            "trend_score": 50.0,
            "momentum_score": 50.0,
            "volatility_score": 50.0,
            "volume_score": 50.0,
            "total_score": 50.0,
            "rating": "neutral",
        }

        try:
            # 趋势评分
            trend = technical_results.get("trend", {})
            trend_direction = trend.get("trend_direction", "sideways")
            trend_strength = trend.get("trend_strength", 0.0)

            if trend_direction == "up":
                score_results["trend_score"] = min(50 + trend_strength / 2, 100)
            elif trend_direction == "down":
                score_results["trend_score"] = max(50 - trend_strength / 2, 0)

            # 动量评分
            momentum = technical_results.get("momentum", {})
            rsi = momentum.get("rsi_14", 50.0)
            macd_hist = momentum.get("macd_histogram", 0.0)

            # RSI评分（理想区间40-60，偏离越远分数越低）
            rsi_deviation = abs(rsi - 50)
            rsi_score = max(100 - rsi_deviation * 2, 0)

            # MACD评分
            macd_score = 50
            if macd_hist > 0:
                macd_score = min(50 + macd_hist * 10, 100)
            elif macd_hist < 0:
                macd_score = max(50 + macd_hist * 10, 0)

            score_results["momentum_score"] = (rsi_score + macd_score) / 2

            # 波动率评分（适度波动较好，过高或过低都不好）
            volatility = technical_results.get("volatility", {})
            vol_20d = volatility.get("volatility_20d", 20.0)

            if 15 <= vol_20d <= 40:
                score_results["volatility_score"] = 70.0
            elif vol_20d < 15:
                score_results["volatility_score"] = 50.0
            else:
                score_results["volatility_score"] = max(100 - (vol_20d - 40), 30)

            # 成交量评分
            volume = technical_results.get("volume", {})
            volume_ratio = volume.get("volume_ratio", 1.0)

            if 0.8 <= volume_ratio <= 2.0:
                score_results["volume_score"] = 70.0
            elif volume_ratio > 2.0:
                score_results["volume_score"] = min(70 + (volume_ratio - 2) * 5, 90)
            else:
                score_results["volume_score"] = max(volume_ratio * 70, 30)

            # 计算总评分
            weights = {"trend": 0.3, "momentum": 0.3, "volatility": 0.2, "volume": 0.2}

            score_results["total_score"] = (
                score_results["trend_score"] * weights["trend"]
                + score_results["momentum_score"] * weights["momentum"]
                + score_results["volatility_score"] * weights["volatility"]
                + score_results["volume_score"] * weights["volume"]
            )

            # 确定评级
            if score_results["total_score"] >= 70:
                score_results["rating"] = "bullish"
            elif score_results["total_score"] <= 40:
                score_results["rating"] = "bearish"
            else:
                score_results["rating"] = "neutral"

            self.logger.info(
                f"✅ 技术面评分完成: {score_results['total_score']:.1f}, "
                f"评级: {score_results['rating']}"
            )

        except Exception as e:
            self.logger.error(f"❌ 技术面评分失败: {e}")

        return score_results

    def analyze_all(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        执行完整的技术面分析

        Args:
            price_data: 价格数据DataFrame

        Returns:
            完整的技术分析结果
        """
        self.logger.info(f"开始技术面分析，数据点数: {len(price_data)}")

        # 执行各维度分析
        trend = self.analyze_trend(price_data)
        momentum = self.analyze_momentum(price_data)
        volatility = self.analyze_volatility(price_data)
        volume = self.analyze_volume(price_data)
        support_resistance = self.analyze_support_resistance(price_data)

        # 汇总结果
        technical_results = {
            "trend": trend,
            "momentum": momentum,
            "volatility": volatility,
            "volume": volume,
            "support_resistance": support_resistance,
        }

        # 生成综合评分
        score_results = self.generate_technical_score(technical_results)
        technical_results["score"] = score_results

        self.logger.info("✅ 技术面分析全部完成")

        return technical_results

    def generate_technical_report(
        self, symbol: str, technical_results: Dict[str, Any]
    ) -> str:
        """
        生成技术面分析报告

        Args:
            symbol: 股票代码
            technical_results: 技术分析结果

        Returns:
            Markdown格式的报告
        """
        try:
            report = f"""# 技术面分析报告 - {symbol}

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**分析工具**: QuanTr Technical Analyzer

## 1. 趋势分析

"""

            # 趋势分析
            trend = technical_results.get("trend", {})
            report += f"**趋势方向**: {trend.get('trend_direction', 'N/A')}\n\n"
            report += f"**趋势强度**: {trend.get('trend_strength', 0):.2f}\n\n"
            report += "**移动平均线**:\n"
            for ma_name, ma_value in trend.get("moving_averages", {}).items():
                report += f"- {ma_name.upper()}: {ma_value}\n"

            report += "\n**价格与均线偏离**:\n"
            for dev_name, dev_value in trend.get("price_vs_ma", {}).items():
                report += f"- {dev_name}: {dev_value:.2f}%\n"

            # 动量分析
            report += "\n## 2. 动量指标\n\n"
            momentum = technical_results.get("momentum", {})
            report += f"**RSI (14)**: {momentum.get('rsi_14', 'N/A')}\n"
            report += f"**RSI状态**: {momentum.get('rsi_status', 'N/A')}\n\n"
            report += f"**MACD**: {momentum.get('macd', 'N/A')}\n"
            report += f"**MACD信号线**: {momentum.get('macd_signal', 'N/A')}\n"
            report += f"**MACD柱状图**: {momentum.get('macd_histogram', 'N/A')}\n"

            # 波动率分析
            report += "\n## 3. 波动率分析\n\n"
            volatility = technical_results.get("volatility", {})
            report += f"**布林带(20,2)**:\n"
            report += f"  - 上轨: {volatility.get('bollinger_upper', 'N/A')}\n"
            report += f"  - 中轨: {volatility.get('bollinger_middle', 'N/A')}\n"
            report += f"  - 下轨: {volatility.get('bollinger_lower', 'N/A')}\n"
            report += (
                f"\n**布林带位置**: {volatility.get('bollinger_position', 'N/A')}%\n"
            )
            report += f"**ATR**: {volatility.get('atr', 'N/A')}\n"
            report += f"**20日波动率**: {volatility.get('volatility_20d', 'N/A')}%\n"

            # 成交量分析
            report += "\n## 4. 成交量分析\n\n"
            volume = technical_results.get("volume", {})
            report += f"**20日成交量均线**: {volume.get('volume_ma_20', 'N/A')}\n"
            report += f"**成交量比率**: {volume.get('volume_ratio', 'N/A')}\n"
            report += f"**OBV**: {volume.get('obv', 'N/A')}\n"
            report += f"**成交量趋势**: {volume.get('volume_trend', 'N/A')}\n"

            # 支撑阻力
            report += "\n## 5. 支撑与阻力\n\n"
            sr = technical_results.get("support_resistance", {})
            report += f"**支撑位**: {sr.get('support_levels', [])}\n"
            report += f"**阻力位**: {sr.get('resistance_levels', [])}\n"
            report += (
                f"**到支撑位距离**: {sr.get('current_support_distance', 'N/A')}%\n"
            )
            report += (
                f"**到阻力位距离**: {sr.get('current_resistance_distance', 'N/A')}%\n"
            )

            # 综合评分
            report += "\n## 6. 技术面评分\n\n"
            score = technical_results.get("score", {})
            report += f"**综合评分**: {score.get('total_score', 0):.1f}/100\n"
            report += f"**评级**: {score.get('rating', 'N/A')}\n\n"
            report += "**分项评分**:\n"
            report += f"- 趋势评分: {score.get('trend_score', 0):.1f}\n"
            report += f"- 动量评分: {score.get('momentum_score', 0):.1f}\n"
            report += f"- 波动率评分: {score.get('volatility_score', 0):.1f}\n"
            report += f"- 成交量评分: {score.get('volume_score', 0):.1f}\n"

            # 交易建议
            report += """
## 7. 技术面交易建议

基于技术分析，建议如下：

"""

            trend_rating = score.get("rating", "neutral")
            if trend_rating == "bullish":
                report += """**信号**: 看多
**策略**: 考虑在回调时买入，突破阻力位加仓
**注意**: 关注成交量配合情况
"""
            elif trend_rating == "bearish":
                report += """**信号**: 看空
**策略**: 考虑减仓或观望，跌破支撑位止损
**注意**: 避免抄底，等待趋势反转信号
"""
            else:
                report += """**信号**: 中性
**策略**: 观望为主，等待明确趋势形成
**注意**: 关注关键支撑阻力位的突破情况
"""

            report += """
---
*本报告由QuanTr系统自动生成，仅供参考，不构成投资建议。*
"""

            self.logger.info(f"✅ 技术面分析报告生成完成: {symbol}")
            return report

        except Exception as e:
            self.logger.error(f"❌ 生成技术面分析报告失败: {e}")
            return f"# 技术面分析报告生成失败\n\n错误信息: {str(e)}"


def main():
    """主函数，用于测试"""
    analyzer = TechnicalAnalyzer()

    print("🔍 开始测试技术面分析器...")

    # 创建示例数据
    dates = pd.date_range(end=datetime.now(), periods=100, freq="D")
    np.random.seed(42)

    # 生成模拟价格数据
    base_price = 100
    prices = []
    volumes = []

    for i in range(100):
        change = np.random.normal(0.001, 0.02)  # 随机涨跌幅
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

    print(f"\n1. 分析趋势...")
    trend = analyzer.analyze_trend(sample_data)
    print(f"   趋势方向: {trend['trend_direction']}")
    print(f"   趋势强度: {trend['trend_strength']:.2f}")

    print(f"\n2. 分析动量...")
    momentum = analyzer.analyze_momentum(sample_data)
    print(f"   RSI: {momentum['rsi_14']}")
    print(f"   MACD: {momentum['macd']}")

    print(f"\n3. 分析波动率...")
    volatility = analyzer.analyze_volatility(sample_data)
    print(f"   布林带位置: {volatility['bollinger_position']}%")
    print(f"   20日波动率: {volatility['volatility_20d']}%")

    print(f"\n4. 分析成交量...")
    volume = analyzer.analyze_volume(sample_data)
    print(f"   成交量比率: {volume['volume_ratio']}")
    print(f"   OBV: {volume['obv']}")

    print(f"\n5. 综合分析...")
    results = analyzer.analyze_all(sample_data)
    score = results.get("score", {})
    print(f"   综合评分: {score.get('total_score', 0):.1f}")
    print(f"   评级: {score.get('rating', 'N/A')}")

    print(f"\n6. 生成报告...")
    report = analyzer.generate_technical_report("000001.SZ", results)

    # 保存报告
    report_dir = config.get_analysis_dir("test")
    report_dir.mkdir(parents=True, exist_ok=True)

    report_file = report_dir / "technical_analysis_test.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ 测试完成，报告已保存: {report_file}")
    print(f"\n📄 报告预览（前500字符）:")
    print("-" * 50)
    print(report[:500] + "...")
    print("-" * 50)


if __name__ == "__main__":
    main()
