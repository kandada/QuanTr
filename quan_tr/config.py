# quan_tr/config.py
"""
QuanTr量化交易系统配置模块
包含系统配置、数据源配置、分析参数等
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class QuanTrConfig:
    """QuanTr量化交易系统配置类"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置

        Args:
            config_path: 配置文件路径，默认为当前目录下的config.yaml
        """
        self.base_dir = Path(__file__).parent
        self.config_path = (
            Path(config_path) if config_path else self.base_dir / "config.yaml"
        )

        # 默认配置
        self.default_config = {
            "version": "1.0.0",
            "system": {
                "project_name": "QuanTr量化交易分析系统",
                "author": "QuanTr AI Agent",
                "version": "1.0.0",
                "description": "基于AI Agent的股票量化分析与策略回测系统",
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "data_sources": {
                "akshare": {
                    "enabled": True,
                    "description": "AKshare - 纯Python开源财经数据接口库",
                    "rate_limit": 5,  # 每秒请求限制
                    "timeout": 30,  # 请求超时时间（秒）
                    "retry_times": 3,  # 重试次数
                },
                "yfinance": {
                    "enabled": True,
                    "description": "Yahoo Finance - 国际通用股票数据接口",
                    "rate_limit": 2,
                    "timeout": 30,
                    "retry_times": 3,
                },
                "eastmoney": {
                    "enabled": True,
                    "description": "东方财富 - 国内股票数据接口",
                    "rate_limit": 3,
                    "timeout": 30,
                    "retry_times": 3,
                },
            },
            "analysis": {
                "fundamental_weight": 0.4,  # 基本面分析权重
                "technical_weight": 0.3,  # 技术面分析权重
                "risk_weight": 0.2,  # 风险分析权重
                "sentiment_weight": 0.1,  # 情绪分析权重
                "scoring_thresholds": {
                    "strong_buy": 80,
                    "buy": 60,
                    "hold": 40,
                    "sell": 20,
                    "strong_sell": 0,
                },
                "default_analysis_period": "1y",  # 默认分析周期
                "moving_average_periods": [5, 10, 20, 60, 120],  # 移动平均线周期
                "rsi_period": 14,  # RSI周期
                "macd_fast": 12,  # MACD快线周期
                "macd_slow": 26,  # MACD慢线周期
                "macd_signal": 9,  # MACD信号线周期
            },
            "backtest": {
                "initial_capital": 100000,  # 初始资金
                "commission_rate": 0.0003,  # 佣金费率
                "slippage_rate": 0.0001,  # 滑点费率
                "max_position_ratio": 0.8,  # 最大持仓比例
                "stop_loss_rate": 0.1,  # 止损比例
                "take_profit_rate": 0.2,  # 止盈比例
                "backtest_periods": {
                    "weekly": 7,  # 周回测周期
                    "monthly": 30,  # 月回测周期
                },
            },
            "file_structure": {
                "data_files_dir": "data_files",
                "analysis_results_dir": "analysis_results",
                "backtest_reports_dir": "backtest_reports",
                "programs_dir": "programs",
                "resources_dir": "resources",
                "templates_dir": "analysis_results/templates",
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file_path": "logs/quan_tr.log",
                "max_file_size": 10485760,  # 10MB
                "backup_count": 5,
            },
            "performance": {
                "cache_enabled": True,
                "cache_ttl": 3600,  # 缓存过期时间（秒）
                "parallel_processing": True,
                "max_workers": 4,  # 最大工作线程数
                "batch_size": 10,  # 批量处理大小
            },
        }

        # 加载配置文件
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if self.config_path.exists():
                import yaml

                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_config = yaml.safe_load(f) or {}
            else:
                user_config = {}

            # 合并默认配置和用户配置
            config = self.deep_merge(self.default_config, user_config)
            return config

        except Exception as e:
            print(f"⚠️  加载配置文件失败: {e}")
            print("💡 使用默认配置")
            return self.default_config

    def deep_merge(self, base: Dict, update: Dict) -> Dict:
        """深度合并两个字典"""
        result = base.copy()

        for key, value in update.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self.deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def save_config(self, config: Optional[Dict] = None) -> bool:
        """保存配置文件"""
        try:
            import yaml

            if config:
                self.config = config

            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    self.config,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )

            print(f"✅ 配置文件已保存: {self.config_path}")
            return True

        except Exception as e:
            print(f"❌ 保存配置文件失败: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> bool:
        """设置配置值"""
        try:
            keys = key.split(".")
            config = self.config

            # 遍历到最后一个键的父级
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]

            # 设置值
            config[keys[-1]] = value

            # 保存配置
            return self.save_config()

        except Exception as e:
            print(f"❌ 设置配置值失败: {e}")
            return False

    def get_stocks_pool(self) -> List[Dict]:
        """获取股票池"""
        stocks_pool_path = self.base_dir / "stocks_pool.json"

        try:
            if stocks_pool_path.exists():
                with open(stocks_pool_path, "r", encoding="utf-8") as f:
                    stocks_data = json.load(f)
                    return stocks_data.get("stocks", [])
            else:
                print(f"⚠️  股票池文件不存在: {stocks_pool_path}")
                return []

        except Exception as e:
            print(f"❌ 加载股票池失败: {e}")
            return []

    def get_data_dir(self, date_str: Optional[str] = None) -> Path:
        """获取数据目录路径"""
        data_dir = self.base_dir / self.get("file_structure.data_files_dir")

        if date_str:
            data_dir = data_dir / date_str

        return data_dir

    def get_analysis_dir(self, date_str: Optional[str] = None) -> Path:
        """获取分析结果目录路径"""
        analysis_dir = self.base_dir / self.get("file_structure.analysis_results_dir")

        if date_str:
            analysis_dir = analysis_dir / date_str

        return analysis_dir

    def get_backtest_dir(self) -> Path:
        """获取回测报告目录路径"""
        return self.base_dir / self.get("file_structure.backtest_reports_dir")

    def get_programs_dir(self) -> Path:
        """获取程序目录路径"""
        return self.base_dir / self.get("file_structure.programs_dir")

    def get_resources_dir(self) -> Path:
        """获取资源目录路径"""
        return self.base_dir / self.get("file_structure.resources_dir")

    def get_templates_dir(self) -> Path:
        """获取模板目录路径"""
        return self.base_dir / self.get("file_structure.templates_dir")

    def validate_config(self) -> Dict[str, List[str]]:
        """验证配置完整性"""
        issues = {"warnings": [], "errors": []}

        # 检查必要目录
        required_dirs = [
            ("data_files_dir", self.get_data_dir()),
            ("analysis_results_dir", self.get_analysis_dir()),
            ("backtest_reports_dir", self.get_backtest_dir()),
            ("programs_dir", self.get_programs_dir()),
            ("resources_dir", self.get_resources_dir()),
        ]

        for dir_name, dir_path in required_dirs:
            if not dir_path.exists():
                issues["warnings"].append(f"目录不存在: {dir_name} ({dir_path})")

        # 检查股票池文件
        stocks_pool_path = self.base_dir / "stocks_pool.json"
        if not stocks_pool_path.exists():
            issues["warnings"].append(f"股票池文件不存在: {stocks_pool_path}")

        # 检查配置文件
        if not self.config_path.exists():
            issues["warnings"].append(f"配置文件不存在: {self.config_path}")

        # 检查分析权重总和
        weights = [
            self.get("analysis.fundamental_weight"),
            self.get("analysis.technical_weight"),
            self.get("analysis.risk_weight"),
            self.get("analysis.sentiment_weight"),
        ]

        weight_sum = sum(weights)
        if abs(weight_sum - 1.0) > 0.001:
            issues["errors"].append(f"分析权重总和应为1.0，当前为{weight_sum:.3f}")

        return issues

    def print_summary(self):
        """打印配置摘要"""
        print("=" * 60)
        print("📊 QuanTr配置摘要")
        print("=" * 60)

        print(f"\n📁 目录结构:")
        print(f"  数据文件目录: {self.get_data_dir()}")
        print(f"  分析结果目录: {self.get_analysis_dir()}")
        print(f"  回测报告目录: {self.get_backtest_dir()}")
        print(f"  程序目录: {self.get_programs_dir()}")
        print(f"  资源目录: {self.get_resources_dir()}")

        print(f"\n📈 分析配置:")
        print(f"  基本面权重: {self.get('analysis.fundamental_weight')}")
        print(f"  技术面权重: {self.get('analysis.technical_weight')}")
        print(f"  风险权重: {self.get('analysis.risk_weight')}")
        print(f"  情绪权重: {self.get('analysis.sentiment_weight')}")

        print(f"\n📊 回测配置:")
        print(f"  初始资金: ¥{self.get('backtest.initial_capital'):,.2f}")
        print(f"  佣金费率: {self.get('backtest.commission_rate') * 100:.2f}%")
        print(f"  最大持仓比例: {self.get('backtest.max_position_ratio') * 100:.0f}%")

        print(f"\n📡 数据源:")
        data_sources = self.get("data_sources", {})
        for source_name, source_config in data_sources.items():
            enabled = "✅" if source_config.get("enabled", False) else "❌"
            print(f"  {enabled} {source_name}: {source_config.get('description', '')}")

        # 验证配置
        issues = self.validate_config()
        if issues["warnings"] or issues["errors"]:
            print(f"\n⚠️  配置验证:")
            for warning in issues["warnings"]:
                print(f"  ⚠️  {warning}")
            for error in issues["errors"]:
                print(f"  ❌ {error}")

        print("=" * 60)


# 全局配置实例
config = QuanTrConfig()


if __name__ == "__main__":
    # 测试配置模块
    config.print_summary()

    # 验证配置
    issues = config.validate_config()
    if not issues["errors"]:
        print("\n✅ 配置验证通过")
    else:
        print("\n❌ 配置验证失败，请修复错误")
