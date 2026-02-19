# programs/data_fetchers/akshare_fetcher.py
"""
AKshare数据获取程序
用于从AKshare获取股票相关数据
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from quan_tr.config import config


class AKshareFetcher:
    """AKshare数据获取器"""

    def __init__(self):
        """初始化AKshare数据获取器"""
        self.config = config
        self.logger = self._setup_logger()

        # 检查AKshare是否可用
        self.akshare_available = self._check_akshare_availability()

        if self.akshare_available:
            self.logger.info("✅ AKshare数据获取器初始化成功")
        else:
            self.logger.warning("⚠️  AKshare不可用，部分功能可能受限")

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
            log_file = self.config.base_dir / "logs" / "akshare_fetcher.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _check_akshare_availability(self) -> bool:
        """检查AKshare是否可用"""
        try:
            import akshare as ak

            # 简单测试AKshare是否可用
            test_data = ak.stock_zh_a_spot_em()
            self.logger.debug(f"AKshare测试成功，获取到{len(test_data)}条数据")
            return True
        except ImportError:
            self.logger.error("❌ 未安装AKshare，请运行: pip install akshare")
            return False
        except Exception as e:
            self.logger.warning(f"⚠️  AKshare测试失败: {e}")
            return False

    def get_stock_basic_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基本信息

        Args:
            symbol: 股票代码，如 '000001.SZ'

        Returns:
            股票基本信息字典，失败返回None
        """
        if not self.akshare_available:
            self.logger.error("AKshare不可用，无法获取股票基本信息")
            return None

        try:
            import akshare as ak

            # 提取市场代码
            if symbol.endswith(".SZ"):
                market_code = "sz"
                clean_symbol = symbol.replace(".SZ", "")
            elif symbol.endswith(".SH"):
                market_code = "sh"
                clean_symbol = symbol.replace(".SH", "")
            else:
                self.logger.error(f"不支持的股票代码格式: {symbol}")
                return None

            # 获取股票基本信息
            stock_info = ak.stock_individual_info_em(symbol=clean_symbol)

            if stock_info is None or stock_info.empty:
                self.logger.warning(f"未找到股票信息: {symbol}")
                return None

            # 转换为字典
            info_dict = {}
            for _, row in stock_info.iterrows():
                key = row["item"]
                value = row["value"]
                info_dict[key] = value

            # 添加额外信息
            info_dict["symbol"] = symbol
            info_dict["clean_symbol"] = clean_symbol
            info_dict["market"] = market_code
            info_dict["fetch_time"] = datetime.now().isoformat()

            self.logger.info(f"✅ 获取股票基本信息成功: {symbol}")
            return info_dict

        except Exception as e:
            self.logger.error(f"❌ 获取股票基本信息失败 {symbol}: {e}")
            return None

    def get_stock_daily_data(
        self, symbol: str, start_date: str, end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        获取股票日线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期，格式 'YYYY-MM-DD'
            end_date: 结束日期，格式 'YYYY-MM-DD'

        Returns:
            日线数据DataFrame，失败返回None
        """
        if not self.akshare_available:
            self.logger.error("AKshare不可用，无法获取日线数据")
            return None

        try:
            import akshare as ak

            # 提取市场代码
            if symbol.endswith(".SZ"):
                market_code = "sz"
                clean_symbol = symbol.replace(".SZ", "")
            elif symbol.endswith(".SH"):
                market_code = "sh"
                clean_symbol = symbol.replace(".SH", "")
            else:
                self.logger.error(f"不支持的股票代码格式: {symbol}")
                return None

            # 获取日线数据
            daily_data = ak.stock_zh_a_hist(
                symbol=clean_symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",  # 前复权
            )

            if daily_data is None or daily_data.empty:
                self.logger.warning(
                    f"未找到日线数据: {symbol} ({start_date} 到 {end_date})"
                )
                return None

            # 添加额外信息
            daily_data["symbol"] = symbol
            daily_data["fetch_time"] = datetime.now().isoformat()

            self.logger.info(
                f"✅ 获取日线数据成功: {symbol} ({len(daily_data)} 条记录)"
            )
            return daily_data

        except Exception as e:
            self.logger.error(f"❌ 获取日线数据失败 {symbol}: {e}")
            return None

    def get_stock_financial_data(
        self, symbol: str, report_type: str = "年报"
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        获取股票财务数据

        Args:
            symbol: 股票代码
            report_type: 报告类型，可选 '年报', '中报', '一季报', '三季报'

        Returns:
            财务数据字典，失败返回None
        """
        if not self.akshare_available:
            self.logger.error("AKshare不可用，无法获取财务数据")
            return None

        try:
            import akshare as ak

            # 提取市场代码
            if symbol.endswith(".SZ"):
                market_code = "sz"
                clean_symbol = symbol.replace(".SZ", "")
            elif symbol.endswith(".SH"):
                market_code = "sh"
                clean_symbol = symbol.replace(".SH", "")
            else:
                self.logger.error(f"不支持的股票代码格式: {symbol}")
                return None

            financial_data = {}

            # 获取资产负债表
            try:
                balance_sheet = ak.stock_balance_sheet_by_report_em(symbol=clean_symbol)
                if balance_sheet is not None and not balance_sheet.empty:
                    financial_data["balance_sheet"] = balance_sheet
                    self.logger.debug(f"获取资产负债表成功: {symbol}")
            except Exception as e:
                self.logger.warning(f"获取资产负债表失败 {symbol}: {e}")

            # 获取利润表
            try:
                income_statement = ak.stock_profit_sheet_by_report_em(
                    symbol=clean_symbol
                )
                if income_statement is not None and not income_statement.empty:
                    financial_data["income_statement"] = income_statement
                    self.logger.debug(f"获取利润表成功: {symbol}")
            except Exception as e:
                self.logger.warning(f"获取利润表失败 {symbol}: {e}")

            # 获取现金流量表
            try:
                cash_flow = ak.stock_cash_flow_sheet_by_report_em(symbol=clean_symbol)
                if cash_flow is not None and not cash_flow.empty:
                    financial_data["cash_flow"] = cash_flow
                    self.logger.debug(f"获取现金流量表成功: {symbol}")
            except Exception as e:
                self.logger.warning(f"获取现金流量表失败 {symbol}: {e}")

            if not financial_data:
                self.logger.warning(f"未找到财务数据: {symbol}")
                return None

            self.logger.info(
                f"✅ 获取财务数据成功: {symbol} ({len(financial_data)} 张表)"
            )
            return financial_data

        except Exception as e:
            self.logger.error(f"❌ 获取财务数据失败 {symbol}: {e}")
            return None

    def save_data_to_file(
        self, data: Any, symbol: str, data_type: str, date_str: Optional[str] = None
    ) -> Optional[Path]:
        """
        保存数据到文件

        Args:
            data: 要保存的数据
            symbol: 股票代码
            data_type: 数据类型，如 'basic_info', 'daily_data', 'financial_data'
            date_str: 日期字符串，格式 'YYYY-MM-DD'，默认为今天

        Returns:
            保存的文件路径，失败返回None
        """
        try:
            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")

            # 创建保存目录
            save_dir = self.config.get_data_dir(date_str) / "akshare_data"
            save_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件名
            clean_symbol = symbol.replace(".", "_")
            filename = f"stock_{clean_symbol}_{data_type}_{date_str}"

            if isinstance(data, pd.DataFrame):
                # 保存为CSV
                file_path = save_dir / f"{filename}.csv"
                data.to_csv(file_path, index=False, encoding="utf-8-sig")
                self.logger.info(f"✅ 数据已保存为CSV: {file_path}")

                # 同时保存为JSON（便于查看）
                json_path = save_dir / f"{filename}.json"
                data_dict = data.to_dict(orient="records")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data_dict, f, ensure_ascii=False, indent=2)
                self.logger.debug(f"数据已保存为JSON: {json_path}")

            elif isinstance(data, dict):
                # 保存为JSON
                file_path = save_dir / f"{filename}.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"✅ 数据已保存为JSON: {file_path}")
            else:
                self.logger.error(f"不支持的数据类型: {type(data)}")
                return None

            return file_path

        except Exception as e:
            self.logger.error(f"❌ 保存数据失败: {e}")
            return None

    def fetch_all_stock_data(
        self, symbols: List[str], date_str: Optional[str] = None
    ) -> Dict[str, Dict]:
        """
        批量获取所有股票数据

        Args:
            symbols: 股票代码列表
            date_str: 日期字符串，默认为今天

        Returns:
            数据获取结果字典
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        results = {
            "date": date_str,
            "total_stocks": len(symbols),
            "success_count": 0,
            "failed_count": 0,
            "details": {},
        }

        self.logger.info(f"开始批量获取 {len(symbols)} 只股票的数据...")

        for i, symbol in enumerate(symbols, 1):
            self.logger.info(f"处理股票 {i}/{len(symbols)}: {symbol}")

            stock_results = {
                "basic_info": {"success": False, "file_path": None},
                "daily_data": {"success": False, "file_path": None},
                "financial_data": {"success": False, "file_path": None},
            }

            # 获取基本信息
            basic_info = self.get_stock_basic_info(symbol)
            if basic_info:
                file_path = self.save_data_to_file(
                    basic_info, symbol, "basic_info", date_str
                )
                if file_path:
                    stock_results["basic_info"]["success"] = True
                    stock_results["basic_info"]["file_path"] = str(file_path)
                    results["success_count"] += 1

            # 获取日线数据（最近30天）
            end_date = date_str
            start_date = (
                datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=30)
            ).strftime("%Y-%m-%d")

            daily_data = self.get_stock_daily_data(symbol, start_date, end_date)
            if daily_data is not None:
                file_path = self.save_data_to_file(
                    daily_data, symbol, "daily_data", date_str
                )
                if file_path:
                    stock_results["daily_data"]["success"] = True
                    stock_results["daily_data"]["file_path"] = str(file_path)

            # 获取财务数据
            financial_data = self.get_stock_financial_data(symbol)
            if financial_data:
                file_path = self.save_data_to_file(
                    financial_data, symbol, "financial_data", date_str
                )
                if file_path:
                    stock_results["financial_data"]["success"] = True
                    stock_results["financial_data"]["file_path"] = str(file_path)

            results["details"][symbol] = stock_results

            # 避免请求过于频繁
            time.sleep(0.5)

        results["failed_count"] = results["total_stocks"] - results["success_count"]

        self.logger.info(
            f"批量获取完成: 成功 {results['success_count']}, 失败 {results['failed_count']}"
        )
        return results


def main():
    """主函数，用于测试"""
    fetcher = AKshareFetcher()

    if not fetcher.akshare_available:
        print("❌ AKshare不可用，请安装: pip install akshare")
        return

    # 测试股票
    test_symbols = ["000001.SZ"]  # 平安银行

    # 获取今天日期
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"🔍 开始测试AKshare数据获取器...")
    print(f"📅 日期: {today}")
    print(f"📊 测试股票: {test_symbols}")

    # 测试单只股票
    symbol = test_symbols[0]

    print(f"\n1. 获取股票基本信息: {symbol}")
    basic_info = fetcher.get_stock_basic_info(symbol)
    if basic_info:
        print(f"   ✅ 成功获取基本信息")
        print(f"     股票名称: {basic_info.get('股票简称', 'N/A')}")
        print(f"     当前价格: {basic_info.get('最新价', 'N/A')}")
    else:
        print(f"   ❌ 获取基本信息失败")

    print(f"\n2. 获取日线数据: {symbol}")
    end_date = today
    start_date = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=7)).strftime(
        "%Y-%m-%d"
    )

    daily_data = fetcher.get_stock_daily_data(symbol, start_date, end_date)
    if daily_data is not None:
        print(f"   ✅ 成功获取日线数据 ({len(daily_data)} 条记录)")
        print(
            f"     最新日期: {daily_data.iloc[-1]['日期'] if len(daily_data) > 0 else 'N/A'}"
        )
        print(
            f"     最新收盘价: {daily_data.iloc[-1]['收盘'] if len(daily_data) > 0 else 'N/A'}"
        )
    else:
        print(f"   ❌ 获取日线数据失败")

    print(f"\n3. 批量获取所有股票数据")
    results = fetcher.fetch_all_stock_data(test_symbols, today)

    print(f"\n📊 批量获取结果:")
    print(f"   总股票数: {results['total_stocks']}")
    print(f"   成功数: {results['success_count']}")
    print(f"   失败数: {results['failed_count']}")

    print(f"\n✅ AKshare数据获取器测试完成")


if __name__ == "__main__":
    main()
