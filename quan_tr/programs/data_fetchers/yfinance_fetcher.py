# quan_tr/programs/data_fetchers/yfinance_fetcher.py
"""
Yahoo Finance数据获取程序
用于从Yahoo Finance获取全球股票数据
适用于A股、港股、美股等多种市场
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import numpy as np

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from quan_tr.config import config


class YFinanceFetcher:
    """Yahoo Finance数据获取器"""

    def __init__(self):
        """初始化Yahoo Finance数据获取器"""
        self.config = config
        self.logger = self._setup_logger()
        self.yf_available = self._check_yfinance_availability()

        if self.yf_available:
            self.logger.info("✅ Yahoo Finance数据获取器初始化成功")
        else:
            self.logger.warning("⚠️  yfinance不可用，部分功能可能受限")

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

            log_file = self.config.base_dir / "logs" / "yfinance_fetcher.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _check_yfinance_availability(self) -> bool:
        """检查yfinance是否可用"""
        try:
            import yfinance as yf

            # 简单测试
            test_ticker = yf.Ticker("AAPL")
            test_info = test_ticker.info
            self.logger.info("✅ yfinance可用")
            return True
        except ImportError:
            self.logger.error("❌ 未安装yfinance，请运行: pip install yfinance")
            return False
        except Exception as e:
            self.logger.warning(f"⚠️  yfinance测试失败: {e}")
            return False

    def convert_symbol_to_yahoo(self, symbol: str) -> str:
        """
        将股票代码转换为Yahoo Finance格式

        Args:
            symbol: 原始股票代码，如 '000001.SZ'

        Returns:
            Yahoo Finance格式的代码
        """
        symbol = symbol.strip().upper()

        # A股处理
        if symbol.endswith(".SZ"):
            # 深交所: 000001.SZ -> 000001.SZ
            return symbol
        elif symbol.endswith(".SS") or symbol.endswith(".SH"):
            # 上交所: 600000.SH -> 600000.SS
            return symbol.replace(".SH", ".SS").replace(".ss", ".SS")
        elif symbol.startswith("6") and len(symbol) == 6:
            # 上交所股票代码: 600000 -> 600000.SS
            return f"{symbol}.SS"
        elif (
            symbol.startswith("0") or symbol.startswith("3") or symbol.startswith("2")
        ) and len(symbol) == 6:
            # 深交所股票代码: 000001 -> 000001.SZ
            return f"{symbol}.SZ"

        # 港股处理
        elif symbol.endswith(".HK"):
            return symbol
        elif symbol.isdigit() and len(symbol) <= 5:
            # 港股代码: 0700 -> 0700.HK
            return f"{symbol.zfill(4)}.HK"

        # 默认返回原代码（美股等）
        return symbol

    def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基本信息

        Args:
            symbol: 股票代码

        Returns:
            股票基本信息字典
        """
        if not self.yf_available:
            self.logger.error("yfinance不可用")
            return None

        try:
            import yfinance as yf

            yahoo_symbol = self.convert_symbol_to_yahoo(symbol)
            ticker = yf.Ticker(yahoo_symbol)
            info = ticker.info

            if not info:
                self.logger.warning(f"未找到股票信息: {symbol}")
                return None

            # 提取关键信息
            stock_info = {
                "symbol": symbol,
                "yahoo_symbol": yahoo_symbol,
                "name": info.get("longName", info.get("shortName", "N/A")),
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "country": info.get("country", "N/A"),
                "currency": info.get("currency", "CNY"),
                "market_cap": info.get("marketCap", 0),
                "enterprise_value": info.get("enterpriseValue", 0),
                "trailing_pe": info.get("trailingPE", 0),
                "forward_pe": info.get("forwardPE", 0),
                "peg_ratio": info.get("pegRatio", 0),
                "price_to_book": info.get("priceToBook", 0),
                "price_to_sales": info.get("priceToSalesTrailing12Months", 0),
                "enterprise_to_revenue": info.get("enterpriseToRevenue", 0),
                "enterprise_to_ebitda": info.get("enterpriseToEbitda", 0),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow", 0),
                "fifty_day_average": info.get("fiftyDayAverage", 0),
                "two_hundred_day_average": info.get("twoHundredDayAverage", 0),
                "avg_volume": info.get("averageVolume", 0),
                "avg_volume_10days": info.get("averageVolume10days", 0),
                "shares_outstanding": info.get("sharesOutstanding", 0),
                "float_shares": info.get("floatShares", 0),
                "held_percent_insiders": info.get("heldPercentInsiders", 0),
                "held_percent_institutions": info.get("heldPercentInstitutions", 0),
                "short_ratio": info.get("shortRatio", 0),
                "beta": info.get("beta", 0),
                "dividend_rate": info.get("dividendRate", 0),
                "dividend_yield": info.get("dividendYield", 0),
                "ex_dividend_date": info.get("exDividendDate", "N/A"),
                "payout_ratio": info.get("payoutRatio", 0),
                "five_year_avg_dividend_yield": info.get("fiveYearAvgDividendYield", 0),
                "fetch_time": datetime.now().isoformat(),
            }

            self.logger.info(f"✅ 获取股票信息成功: {symbol}")
            return stock_info

        except Exception as e:
            self.logger.error(f"❌ 获取股票信息失败 {symbol}: {e}")
            return None

    def get_historical_data(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        获取历史价格数据

        Args:
            symbol: 股票代码
            period: 时间段 ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
            interval: 时间间隔 ('1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo')
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            历史数据DataFrame
        """
        if not self.yf_available:
            self.logger.error("yfinance不可用")
            return None

        try:
            import yfinance as yf

            yahoo_symbol = self.convert_symbol_to_yahoo(symbol)
            ticker = yf.Ticker(yahoo_symbol)

            # 如果提供了日期范围，使用日期范围；否则使用period
            if start_date and end_date:
                hist = ticker.history(start=start_date, end=end_date, interval=interval)
            else:
                hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                self.logger.warning(f"未找到历史数据: {symbol}")
                return None

            # 标准化列名
            hist = hist.reset_index()
            hist.columns = [col.lower().replace(" ", "_") for col in hist.columns]

            # 添加股票代码
            hist["symbol"] = symbol
            hist["yahoo_symbol"] = yahoo_symbol
            hist["fetch_time"] = datetime.now().isoformat()

            self.logger.info(f"✅ 获取历史数据成功: {symbol} ({len(hist)} 条记录)")
            return hist

        except Exception as e:
            self.logger.error(f"❌ 获取历史数据失败 {symbol}: {e}")
            return None

    def get_financials(self, symbol: str) -> Optional[Dict[str, pd.DataFrame]]:
        """
        获取财务报表数据

        Args:
            symbol: 股票代码

        Returns:
            财务报表数据字典
        """
        if not self.yf_available:
            self.logger.error("yfinance不可用")
            return None

        try:
            import yfinance as yf

            yahoo_symbol = self.convert_symbol_to_yahoo(symbol)
            ticker = yf.Ticker(yahoo_symbol)

            financials = {}

            # 获取损益表
            try:
                income_stmt = ticker.income_stmt
                if income_stmt is not None and not income_stmt.empty:
                    financials["income_statement"] = income_stmt
                    self.logger.debug(f"获取损益表成功: {symbol}")
            except Exception as e:
                self.logger.warning(f"获取损益表失败 {symbol}: {e}")

            # 获取资产负债表
            try:
                balance_sheet = ticker.balance_sheet
                if balance_sheet is not None and not balance_sheet.empty:
                    financials["balance_sheet"] = balance_sheet
                    self.logger.debug(f"获取资产负债表成功: {symbol}")
            except Exception as e:
                self.logger.warning(f"获取资产负债表失败 {symbol}: {e}")

            # 获取现金流量表
            try:
                cash_flow = ticker.cashflow
                if cash_flow is not None and not cash_flow.empty:
                    financials["cash_flow"] = cash_flow
                    self.logger.debug(f"获取现金流量表成功: {symbol}")
            except Exception as e:
                self.logger.warning(f"获取现金流量表失败 {symbol}: {e}")

            # 获取季度财务数据
            try:
                quarterly_income = ticker.quarterly_income_stmt
                if quarterly_income is not None and not quarterly_income.empty:
                    financials["quarterly_income_statement"] = quarterly_income
                    self.logger.debug(f"获取季度损益表成功: {symbol}")
            except Exception as e:
                self.logger.warning(f"获取季度损益表失败 {symbol}: {e}")

            if not financials:
                self.logger.warning(f"未找到财务数据: {symbol}")
                return None

            self.logger.info(f"✅ 获取财务数据成功: {symbol}")
            return financials

        except Exception as e:
            self.logger.error(f"❌ 获取财务数据失败 {symbol}: {e}")
            return None

    def get_recommendations(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        获取分析师推荐数据

        Args:
            symbol: 股票代码

        Returns:
            推荐数据DataFrame
        """
        if not self.yf_available:
            self.logger.error("yfinance不可用")
            return None

        try:
            import yfinance as yf

            yahoo_symbol = self.convert_symbol_to_yahoo(symbol)
            ticker = yf.Ticker(yahoo_symbol)

            recommendations = ticker.recommendations

            if recommendations is None or recommendations.empty:
                self.logger.warning(f"未找到推荐数据: {symbol}")
                return None

            recommendations = recommendations.reset_index()
            recommendations["symbol"] = symbol

            self.logger.info(f"✅ 获取推荐数据成功: {symbol}")
            return recommendations

        except Exception as e:
            self.logger.error(f"❌ 获取推荐数据失败 {symbol}: {e}")
            return None

    def get_major_holders(self, symbol: str) -> Optional[Dict[str, pd.DataFrame]]:
        """
        获取主要股东信息

        Args:
            symbol: 股票代码

        Returns:
            股东信息字典
        """
        if not self.yf_available:
            self.logger.error("yfinance不可用")
            return None

        try:
            import yfinance as yf

            yahoo_symbol = self.convert_symbol_to_yahoo(symbol)
            ticker = yf.Ticker(yahoo_symbol)

            holders = {}

            # 主要股东
            try:
                major_holders = ticker.major_holders
                if major_holders is not None and not major_holders.empty:
                    holders["major_holders"] = major_holders
            except Exception as e:
                self.logger.debug(f"获取主要股东失败: {e}")

            # 机构持股
            try:
                institutional_holders = ticker.institutional_holders
                if (
                    institutional_holders is not None
                    and not institutional_holders.empty
                ):
                    holders["institutional_holders"] = institutional_holders
            except Exception as e:
                self.logger.debug(f"获取机构持股失败: {e}")

            # 内部人持股
            try:
                insider_holders = ticker.insider_holders
                if insider_holders is not None and not insider_holders.empty:
                    holders["insider_holders"] = insider_holders
            except Exception as e:
                self.logger.debug(f"获取内部人持股失败: {e}")

            if not holders:
                return None

            self.logger.info(f"✅ 获取股东信息成功: {symbol}")
            return holders

        except Exception as e:
            self.logger.error(f"❌ 获取股东信息失败 {symbol}: {e}")
            return None

    def get_news(self, symbol: str, max_news: int = 10) -> Optional[List[Dict]]:
        """
        获取股票相关新闻

        Args:
            symbol: 股票代码
            max_news: 最大新闻数量

        Returns:
            新闻列表
        """
        if not self.yf_available:
            self.logger.error("yfinance不可用")
            return None

        try:
            import yfinance as yf

            yahoo_symbol = self.convert_symbol_to_yahoo(symbol)
            ticker = yf.Ticker(yahoo_symbol)

            news = ticker.news

            if not news:
                self.logger.warning(f"未找到新闻: {symbol}")
                return None

            # 处理新闻数据
            processed_news = []
            for item in news[:max_news]:
                processed_news.append(
                    {
                        "symbol": symbol,
                        "title": item.get("title", ""),
                        "publisher": item.get("publisher", ""),
                        "published_time": item.get("published", ""),
                        "summary": item.get("summary", ""),
                        "url": item.get("link", ""),
                    }
                )

            self.logger.info(f"✅ 获取新闻成功: {symbol} ({len(processed_news)} 条)")
            return processed_news

        except Exception as e:
            self.logger.error(f"❌ 获取新闻失败 {symbol}: {e}")
            return None

    def save_data_to_file(
        self, data: Any, symbol: str, data_type: str, date_str: Optional[str] = None
    ) -> Optional[Path]:
        """
        保存数据到文件

        Args:
            data: 要保存的数据
            symbol: 股票代码
            data_type: 数据类型
            date_str: 日期字符串

        Returns:
            保存的文件路径
        """
        try:
            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")

            save_dir = self.config.get_data_dir(date_str) / "yfinance_data"
            save_dir.mkdir(parents=True, exist_ok=True)

            clean_symbol = symbol.replace(".", "_")
            filename = f"stock_{clean_symbol}_{data_type}_{date_str}"

            if isinstance(data, pd.DataFrame):
                file_path = save_dir / f"{filename}.csv"
                data.to_csv(file_path, index=False, encoding="utf-8-sig")

                # 同时保存JSON
                json_path = save_dir / f"{filename}.json"
                data_dict = data.to_dict(orient="records")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data_dict, f, ensure_ascii=False, indent=2, default=str)

            elif isinstance(data, dict):
                file_path = save_dir / f"{filename}.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    # 处理DataFrame
                    serializable_data = {}
                    for key, value in data.items():
                        if isinstance(value, pd.DataFrame):
                            serializable_data[key] = value.to_dict(orient="records")
                        else:
                            serializable_data[key] = value
                    json.dump(
                        serializable_data, f, ensure_ascii=False, indent=2, default=str
                    )
            else:
                file_path = save_dir / f"{filename}.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            self.logger.info(f"✅ 数据已保存: {file_path}")
            return file_path

        except Exception as e:
            self.logger.error(f"❌ 保存数据失败: {e}")
            return None


def main():
    """主函数，用于测试"""
    fetcher = YFinanceFetcher()

    if not fetcher.yf_available:
        print("❌ yfinance不可用，请安装: pip install yfinance")
        return

    # 测试股票列表
    test_symbols = [
        "000001.SZ",  # 平安银行 (A股)
        "0700.HK",  # 腾讯控股 (港股)
        "AAPL",  # 苹果 (美股)
    ]

    print(f"🔍 开始测试Yahoo Finance数据获取器...")
    print(f"📊 测试股票: {test_symbols}\n")

    for symbol in test_symbols:
        print(f"\n{'=' * 60}")
        print(f"测试股票: {symbol}")
        print(f"{'=' * 60}")

        # 1. 测试股票信息
        print(f"\n1. 获取股票信息...")
        info = fetcher.get_stock_info(symbol)
        if info:
            print(f"   ✅ 成功")
            print(f"   名称: {info.get('name', 'N/A')}")
            print(f"   行业: {info.get('industry', 'N/A')}")
            print(f"   市值: {info.get('market_cap', 0):,}")
            print(f"   PE: {info.get('trailing_pe', 'N/A')}")
        else:
            print(f"   ❌ 失败")

        # 2. 测试历史数据
        print(f"\n2. 获取历史数据...")
        hist_data = fetcher.get_historical_data(symbol, period="1mo")
        if hist_data is not None:
            print(f"   ✅ 成功 ({len(hist_data)} 条记录)")
            if not hist_data.empty:
                print(f"   最新日期: {hist_data.iloc[-1].get('date', 'N/A')}")
                print(f"   最新收盘: {hist_data.iloc[-1].get('close', 'N/A')}")
        else:
            print(f"   ❌ 失败")

        # 3. 测试新闻
        print(f"\n3. 获取新闻...")
        news = fetcher.get_news(symbol, max_news=3)
        if news:
            print(f"   ✅ 成功 ({len(news)} 条新闻)")
            for i, item in enumerate(news[:2], 1):
                print(f"   {i}. {item.get('title', 'N/A')[:50]}...")
        else:
            print(f"   ⚠️  无新闻数据")

        time.sleep(1)  # 避免请求过于频繁

    print(f"\n{'=' * 60}")
    print(f"✅ Yahoo Finance数据获取器测试完成")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
