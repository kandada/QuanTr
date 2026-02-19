# QuanTr主入口
# main_quan_tr.py
# !/usr/bin/env python3
"""
QuanTr - 基于AI Agent的股票量化分析与策略回测系统主入口
基于aacode框架，专门用于股票分析和策略回测任务
"""

import argparse
import asyncio
import os
import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from core.main_agent import MainAgent
from utils.context_manager import ContextManager
from utils.safety import SafetyGuard
from config import settings


class QuanTrCoder:
    """QuanTr量化交易分析主类"""

    def __init__(
        self,
        project_path: str,
        model_config: Optional[Dict] = None,
        target_project: Optional[str] = None,
    ):
        """
        初始化QuanTr量化交易分析助手

        Args:
            project_path: aacode工作目录（存放日志、上下文等）
            model_config: 模型配置
            target_project: 用户的实际项目目录（可选，如果指定则工具操作在此目录）
        """
        self.project_path = Path(project_path).absolute()

        # 如果指定了目标项目，使用目标项目作为工作目录
        if target_project:
            self.target_project = Path(target_project).absolute()
            if not self.target_project.exists():
                raise ValueError(f"目标项目目录不存在: {self.target_project}")
            print(f"🎯 目标项目: {self.target_project}")
        else:
            self.target_project = self.project_path
            print(f"📁 工作目录: {self.project_path}")

        # 检查并创建项目目录，处理权限问题
        try:
            self.project_path.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            print(f"❌ 权限错误: 无法创建项目目录 '{self.project_path}'")
            print(f"   错误信息: {e}")
            print(f"   请检查目录权限或使用有写入权限的目录")
            raise

        # 检查目录写入权限
        test_file = self.project_path / ".permission_test"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError as e:
            print(f"❌ 权限错误: 对目录 '{self.project_path}' 没有写入权限")
            print(f"   错误信息: {e}")
            print(f"   请使用 'chmod' 命令修改目录权限或选择其他目录")
            raise

        # 不使用chdir，避免路径混乱问题
        # 所有工具都会使用target_project作为基准路径

        # 初始化核心组件（使用target_project作为安全护栏的基准）
        self.safety_guard = SafetyGuard(self.target_project)
        # 上下文管理器使用aacode工作目录（存放日志等）
        self.context_manager = ContextManager(self.project_path)
        # 主Agent使用目标项目目录（实际操作目录）
        self.main_agent = MainAgent(
            project_path=self.target_project,
            context_manager=self.context_manager,
            safety_guard=self.safety_guard,
            model_config=model_config or settings.DEFAULT_MODEL,
        )

        # 加载项目初始化指令
        self._load_init_instructions()

        # 初始化类方法映射器
        self._init_class_method_mapper()

        # 初始化QuanTr特定配置
        self._init_quantr_config()

    def _init_quantr_config(self):
        """初始化QuanTr特定配置"""
        # 检查股票池文件是否存在
        self.stocks_pool_path = self.target_project / "stocks_pool.json"
        if not self.stocks_pool_path.exists():
            print(f"⚠️  股票池文件不存在: {self.stocks_pool_path}")
            print("💡 请先创建股票池配置文件")
        else:
            print(f"✅ 股票池文件已加载: {self.stocks_pool_path.name}")
            # 尝试加载股票池
            try:
                with open(self.stocks_pool_path, "r", encoding="utf-8") as f:
                    self.stocks_pool = json.load(f)
                stock_count = len(self.stocks_pool.get("stocks", []))
                print(f"📊 股票池包含 {stock_count} 只股票")
            except Exception as e:
                print(f"⚠️  无法加载股票池文件: {e}")
                self.stocks_pool = None

        # 设置当前日期
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        print(f"📅 当前分析日期: {self.current_date}")

        # 检查分析结果目录
        self.analysis_results_dir = self.target_project / "analysis_results"
        self.analysis_results_dir.mkdir(parents=True, exist_ok=True)

        # 检查回测报告目录
        self.backtest_reports_dir = self.target_project / "backtest_reports"
        self.backtest_reports_dir.mkdir(parents=True, exist_ok=True)

        # 检查数据文件目录
        self.data_files_dir = self.target_project / "data_files"
        self.data_files_dir.mkdir(parents=True, exist_ok=True)

    def get_stock_count(self):
        """获取股票池中的股票数量"""
        if hasattr(self, "stocks_pool") and self.stocks_pool:
            return len(self.stocks_pool.get("stocks", []))
        return 0

    def check_existing_analysis(self, date_str=None):
        """检查指定日期是否已有分析结果"""
        if date_str is None:
            date_str = self.current_date

        analysis_dir = self.analysis_results_dir / date_str
        if analysis_dir.exists():
            json_files = list(analysis_dir.glob("*.json"))
            csv_files = list(analysis_dir.glob("*.csv"))
            md_files = list(analysis_dir.glob("*.md"))

            return {
                "exists": True,
                "json_count": len(json_files),
                "csv_count": len(csv_files),
                "md_count": len(md_files),
                "path": analysis_dir,
            }
        return {"exists": False, "path": analysis_dir}

    def get_recent_analysis_dates(self, days=7):
        """获取最近几天的分析日期"""
        dates = []
        if self.analysis_results_dir.exists():
            for item in self.analysis_results_dir.iterdir():
                if item.is_dir():
                    try:
                        # 检查目录名是否为日期格式
                        datetime.strptime(item.name, "%Y-%m-%d")
                        dates.append(item.name)
                    except ValueError:
                        continue

        # 按日期排序，返回最近的日期
        dates.sort(reverse=True)
        return dates[:days]

    def _load_init_instructions(self):
        """加载项目初始化指令"""
        # 优先从目标项目加载init.md，如果不存在则从工作目录加载
        init_file = self.target_project / "init.md"
        if not init_file.exists():
            init_file = self.project_path / "init.md"
        if not init_file.exists():
            # 创建默认指令
            default_init = """# 项目指导原则

## 核心规则
1. 每个代码文件顶部必须用注释标注路径：`# {relative_path}`
2. 优先修改现有文件而非创建新文件
3. 所有文件操作必须在项目目录内
4. 危险命令需要用户确认

## 工作流程
1. 先分析需求，制定计划
2. 小步快跑，频繁测试
3. 编写自包含的测试函数
4. 使用工具前检查安全性

## 代码质量
- 遵循PEP 8/Python最佳实践
- 函数尽量不超过60行
- 添加必要的文档字符串
- 错误处理要优雅"""
            init_file.write_text(default_init)

        self.init_instructions = init_file.read_text()

    def _init_class_method_mapper(self):
        """初始化类方法映射器"""
        try:
            # 尝试使用增强版映射器（现在在class_method_mapper.py中）
            from utils.class_method_mapper import EnhancedClassMethodMapper

            self.class_method_mapper = EnhancedClassMethodMapper(self.target_project)
            print("✅ 增强版类方法映射器初始化成功（支持多语言）")
        except ImportError as e:
            print(f"⚠️  无法导入增强版类方法映射器: {e}")
            try:
                # 回退到基础版映射器
                from utils.class_method_mapper import ClassMethodMapper

                self.class_method_mapper = ClassMethodMapper(self.target_project)
                print("✅ 基础版类方法映射器初始化成功（仅Python）")
            except ImportError as e2:
                print(f"⚠️  无法导入类方法映射器: {e2}")
                self.class_method_mapper = None

        # 初始化to-do-list管理器（使用aacode工作目录）
        from utils.todo_manager import get_todo_manager

        self.todo_manager = get_todo_manager(self.project_path)

    def analyze_project_structure(self) -> str:
        """分析项目结构并生成类方法映射"""
        if not self.class_method_mapper:
            return "类方法映射器未初始化"

        try:
            print("🔍 开始分析项目结构...")
            summary = self.class_method_mapper.analyze_project()

            # 尝试使用增强版方法
            try:
                # 增强版映射器
                map_file = self.class_method_mapper.save_enhanced_map()
                # 获取语言摘要用于提示
                language_summary = self.class_method_mapper.get_language_summary()

                print(f"✅ 项目结构分析完成:")
                if "multi_lang_analysis" in summary:
                    lang_stats = summary["multi_lang_analysis"]["languages"]
                    for lang, stats in lang_stats.items():
                        print(
                            f"   - {lang}: {stats['file_count']} 个文件, {stats['total_lines']} 行"
                        )
                print(f"   - 结构文件: {map_file.name}")

                # 返回语言摘要和映射内容
                map_content = map_file.read_text(encoding="utf-8")
                return f"{language_summary}\n\n完整结构见文件: {map_file.name}"

            except AttributeError:
                # 回退到基础版方法
                map_file = self.class_method_mapper.save_class_method_map()
                map_content = map_file.read_text(encoding="utf-8")

                print(f"✅ Python项目结构分析完成:")
                print(f"   - 类数量: {summary.get('class_count', 0)}")
                print(f"   - 函数数量: {summary.get('function_count', 0)}")
                print(f"   - 文件数量: {summary.get('file_count', 0)}")
                print(f"   - 映射文件: {map_file.name}")

                return map_content[:2000]  # 返回前2000字符作为摘要

        except Exception as e:
            error_msg = f"项目结构分析失败: {e}"
            print(f"❌ {error_msg}")
            return error_msg

    def update_class_method_map(
        self, changed_files: Optional[List[Path]] = None
    ) -> str:
        """更新类方法映射"""
        if not self.class_method_mapper:
            return "类方法映射器未初始化"

        try:
            print("🔄 更新类方法映射...")
            # 处理None情况
            files_to_update = changed_files if changed_files is not None else []

            # 将字符串转换为Path对象（相对路径转换为绝对路径）
            files_to_update = [
                (self.project_path / f) if isinstance(f, str) else f
                for f in files_to_update
            ]

            # 尝试使用增强版方法
            try:
                success = self.class_method_mapper.update_analysis(files_to_update)
                map_file = self.project_path / "project_structure.md"
            except AttributeError:
                # 回退到基础版方法
                success = self.class_method_mapper.update_class_method_map(
                    files_to_update
                )
                map_file = self.project_path / "class_method_map.md"

            if success:
                if map_file.exists():
                    map_content = map_file.read_text(encoding="utf-8")
                    return f"类方法映射已更新\n\n{map_content[:1000]}..."
                else:
                    return "类方法映射更新失败：文件未生成"
            else:
                return "类方法映射更新失败"

        except Exception as e:
            error_msg = f"更新类方法映射失败: {e}"
            print(f"❌ {error_msg}")
            return error_msg

    async def run(self, task: str, max_iterations: int = 30) -> Dict[str, Any]:
        """
        执行任务

        Args:
            task: 任务描述
            max_iterations: 最大迭代次数

        Returns:
            执行结果
        """
        print(f"\n🎯 开始任务: {task}")
        print(f"📁 aacode工作目录: {self.project_path}")
        print(f"🎯 目标项目目录: {self.target_project}")
        print(f"📝 初始化指令已加载 ({len(self.init_instructions.split())} 字)")

        # 任务开始前分析项目结构
        print("\n🔍 任务开始前分析项目结构...")
        analysis_result = self.analyze_project_structure()
        if "失败" not in analysis_result:
            print("✅ 项目结构分析完成，类方法映射已生成")
        else:
            print("⚠️  项目结构分析未完成，但任务将继续")

        # 创建任务目录
        task_dir = (
            self.project_path
            / ".aacode"
            / f"task_{int(asyncio.get_event_loop().time())}"
        )
        task_dir.mkdir(parents=True, exist_ok=True)

        # 创建to-do-list，并同步到上下文管理器
        print("\n📋 创建任务待办清单...")
        todo_file = await self.todo_manager.create_todo_list(
            task, context_manager=self.context_manager
        )
        print(f"✅ 待办清单已创建: {todo_file}")

        try:
            # 运行主Agent，传递类方法映射信息
            result = await self.main_agent.execute(
                task=task,
                init_instructions=self.init_instructions,
                task_dir=task_dir,
                max_iterations=max_iterations,
                project_analysis=analysis_result,
                todo_manager=self.todo_manager,  # 传递todo管理器
            )
            return result
        except asyncio.CancelledError:
            # 异步任务被取消
            print("\n⏹️ 任务被取消")
            return {
                "status": "cancelled",
                "error": "任务被用户取消",
                "iterations": 0,
                "execution_time": 0,
                "session_id": f"cancelled_{int(asyncio.get_event_loop().time())}",
            }
        except Exception as e:
            # 捕获并处理异常，避免程序崩溃
            print(f"\n❌ 任务执行失败: {e}")
            import traceback

            traceback.print_exc()
            # 返回一个包含错误信息的结果，而不是抛出异常
            return {
                "status": "error",
                "error": str(e),
                "iterations": 0,
                "execution_time": 0,
                "session_id": f"error_{int(asyncio.get_event_loop().time())}",
            }
        finally:
            # 确保资源被清理
            try:
                # 清理web_tools资源
                if hasattr(self.main_agent, "web_tools"):
                    await self.main_agent.web_tools.cleanup()
            except Exception as e:
                print(f"⚠️  清理资源时出错: {e}")


async def continue_session(coder, project_dir):
    """继续会话，执行追加任务"""
    print("\n" + "=" * 50)
    print("🔁 继续会话模式")
    print("=" * 50)

    # 检查是否有待办清单
    todo_dir = project_dir / ".aacode" / "todos"
    if todo_dir.exists():
        todo_files = list(todo_dir.glob("*.md"))
        if todo_files:
            print(f"\n📋 发现 {len(todo_files)} 个待办清单:")
            for i, todo_file in enumerate(todo_files[-3:], 1):  # 显示最近3个
                print(f"  {i}. {todo_file.name}")
            print("💡 输入 'todo' 查看待办清单详情")

    # 检查是否有会话日志
    log_dir = project_dir / ".aacode" / "logs"
    if log_dir.exists():
        log_files = list(log_dir.glob("*.log"))
        if log_files:
            print(f"📝 发现 {len(log_files)} 个会话日志")

    while True:
        try:
            print("\n当前项目目录:", project_dir)
            print("可用命令:")
            print("  - 输入任务描述继续工作")
            print("  - 输入 'list' 查看项目文件")
            print("  - 输入 'todo' 查看待办清单")
            print("  - 输入 'logs' 查看会话日志")
            print("  - 输入 'exit' 或 'quit' 退出")
            print("  - 输入 'clear' 清空项目目录")
            print("  - 输入 '继续' 查看恢复任务说明")
            print("  - 输入 'help' 查看帮助")

            user_input = input("\n> ").strip()

            if user_input.lower() in ["exit", "quit", "q"]:
                print("👋 退出会话")
                break
            elif user_input.lower() == "list":
                # 列出项目文件
                print("\n📁 项目文件:")
                files = list(project_dir.glob("*"))
                if not files:
                    print("  (空目录)")
                else:
                    for file in files:
                        if file.is_file():
                            size = file.stat().st_size
                            print(f"  - {file.name} ({size} bytes)")
                continue
            elif user_input.lower() == "todo":
                # 查看待办清单
                if todo_dir.exists():
                    todo_files = list(todo_dir.glob("*.md"))
                    if todo_files:
                        print("\n📋 待办清单:")
                        for i, todo_file in enumerate(todo_files, 1):
                            with open(todo_file, "r", encoding="utf-8") as f:
                                first_line = f.readline().strip()
                            print(f"  {i}. {todo_file.name}")
                            print(f"     内容: {first_line[:80]}...")
                        print("\n💡 输入待办清单编号查看详情，或输入 'back' 返回")
                        choice = input("选择待办清单 (编号/back): ").strip()
                        if choice.lower() != "back" and choice.isdigit():
                            idx = int(choice) - 1
                            if 0 <= idx < len(todo_files):
                                with open(todo_files[idx], "r", encoding="utf-8") as f:
                                    print(f"\n📄 {todo_files[idx].name}:")
                                    print(f.read())
                    else:
                        print("📭 没有待办清单")
                else:
                    print("📭 待办目录不存在")
                continue
            elif user_input.lower() == "logs":
                # 查看会话日志
                if log_dir.exists():
                    log_files = list(log_dir.glob("*.log"))
                    if log_files:
                        print("\n📝 会话日志:")
                        for i, log_file in enumerate(log_files[-5:], 1):  # 显示最近5个
                            size = log_file.stat().st_size
                            print(f"  {i}. {log_file.name} ({size} bytes)")
                        print("\n💡 输入日志编号查看最后几行，或输入 'back' 返回")
                        choice = input("选择日志 (编号/back): ").strip()
                        if choice.lower() != "back" and choice.isdigit():
                            idx = int(choice) - 1
                            if 0 <= idx < len(log_files):
                                with open(log_files[idx], "r", encoding="utf-8") as f:
                                    lines = f.readlines()
                                    print(f"\n📄 {log_files[idx].name} (最后20行):")
                                    for line in lines[-20:]:
                                        print(line.rstrip())
                    else:
                        print("📭 没有会话日志")
                else:
                    print("📭 日志目录不存在")
                continue
            elif user_input.lower() == "clear":
                # 确认清空项目
                confirm = (
                    input("⚠️  确认清空项目目录? (输入 'yes' 确认): ").strip().lower()
                )
                if confirm == "yes":
                    for file in project_dir.glob("*"):
                        if file.is_file() and file.name != ".env":
                            file.unlink()
                    print("✅ 项目目录已清空")
                continue
            elif user_input.lower() in ["继续", "continue"]:
                # 处理"继续"命令
                print("\n" + "=" * 50)
                print("🔄 恢复任务说明")
                print("=" * 50)
                print("\n要恢复之前中断的任务，有以下几种方式:")
                print("\n1. 🎯 输入具体的任务描述")
                print("   例如: '完成用户注册功能'")
                print("   系统会自动参考之前的待办清单继续工作")
                print("\n2. 🔄 使用会话ID恢复")
                print("   重新运行程序时使用: --session <session_id>")
                print("   会话ID会在任务开始时显示")
                print("   例如: python main.py --session session_20260212_123548_3")
                print("\n3. 📋 基于待办清单继续")
                print("   输入 'todo' 查看现有待办清单")
                print("   选择待办清单后，输入相关任务描述")
                print("\n4. 🔍 查看项目状态")
                print("   输入 'list' 查看项目文件")
                print("   输入 'logs' 查看会话日志")
                print("\n💡 建议: 输入具体的任务描述是最直接的方式")
                continue
            elif user_input.lower() == "help":
                print("\n" + "=" * 50)
                print("📚 帮助文档")
                print("=" * 50)
                print("\n🔧 常用命令:")
                print("  list    - 查看项目文件")
                print("  todo    - 查看待办清单")
                print("  logs    - 查看会话日志")
                print("  clear   - 清空项目目录")
                print("  exit    - 退出会话")
                print("  help    - 显示帮助")
                print("\n🎯 任务执行:")
                print("  直接输入任务描述即可开始工作")
                print("  例如: '添加用户登录功能'")
                print("  系统会自动分析项目并制定计划")
                print("\n🔄 恢复任务:")
                print("  输入 '继续' 查看恢复任务说明")
                print("  或直接输入任务描述继续工作")
                print("\n⚠️  注意事项:")
                print("  1. 确保API密钥已正确设置")
                print("  2. 大型项目可能需要较长时间")
                print("  3. 可以使用Ctrl+C中断当前任务")
                print("  4. 中断后输入 'y' 可以继续会话")
                continue
            elif user_input:
                # 检查是否是"继续任务"或类似命令
                if user_input.lower() in ["继续任务", "继续之前的任务", "恢复任务"]:
                    # 尝试恢复最近的任务
                    print(f"\n🔄 尝试恢复最近的任务...")

                    # 检查待办清单目录
                    todo_dir = project_dir / ".aacode" / "todos"
                    if todo_dir.exists():
                        todo_files = list(todo_dir.glob("*.md"))
                        if todo_files:
                            # 获取最新的待办清单
                            latest_todo = max(
                                todo_files, key=lambda f: f.stat().st_mtime
                            )
                            print(f"📋 找到待办清单: {latest_todo.name}")

                            # 读取待办清单内容
                            with open(latest_todo, "r", encoding="utf-8") as f:
                                todo_content = f.read()

                            # 提取任务描述
                            import re

                            task_match = re.search(r"\*\*任务\*\*: (.+)", todo_content)
                            if task_match:
                                original_task = task_match.group(1)
                                print(f"🎯 原始任务: {original_task}")

                                # 询问用户是否继续这个任务
                                confirm = (
                                    input(f"是否继续这个任务? (y/n): ").strip().lower()
                                )
                                if confirm == "y":
                                    user_input = original_task
                                    print(f"🔄 继续任务: {original_task}")
                                else:
                                    print("请输入新的任务描述:")
                                    user_input = input("> ").strip()
                            else:
                                print("❌ 无法从待办清单中提取任务描述")
                                print("请输入任务描述:")
                                user_input = input("> ").strip()
                        else:
                            print("📭 没有找到待办清单")
                            print("请输入任务描述:")
                            user_input = input("> ").strip()
                    else:
                        print("📭 待办目录不存在")
                        print("请输入任务描述:")
                        user_input = input("> ").strip()

                # 执行任务
                print(f"\n🎯 开始执行任务: {user_input}")
                print("正在准备...")

                try:
                    result = await coder.run(user_input)

                    # 检查任务是否成功
                    if result.get("status") == "error":
                        print(f"\n❌ 任务执行失败: {result.get('error', '未知错误')}")
                        print("💡 建议: 检查错误信息，或输入新任务重试")
                    else:
                        print(f"\n✅ 任务完成!")
                        print(f"迭代次数: {result.get('iterations', 0)}")
                        print(f"执行时间: {result.get('execution_time', 0):.2f}秒")

                        # 显示会话ID以便后续恢复
                        session_id = result.get("session_id")
                        if session_id and not session_id.startswith("error_"):
                            print(f"会话ID: {session_id}")
                            print(f"使用 --session {session_id} 可以继续此会话")
                except Exception as e:
                    print(f"\n❌ 任务执行失败: {e}")
                    print("💡 建议: 检查错误信息，或输入新任务重试")

                continue
            else:
                print("❌ 请输入有效命令")

        except KeyboardInterrupt:
            print("\n\n⏸️  会话中断")
            print("输入 'y' 继续当前会话，输入 'n' 退出程序")
            choice = input("继续? (y/n): ").strip().lower()
            if choice == "y":
                continue
            else:
                print("👋 退出程序")
                break
        except Exception as e:
            print(f"\n❌ 执行出错: {e}")
            import traceback

            traceback.print_exc()
            print("\n💡 建议: 检查错误信息，或输入新任务重试")
            print("   输入 'help' 查看帮助文档")


def generate_stock_analysis_task(rewrite=False):
    """生成股票分析任务描述"""
    current_date = datetime.now().strftime("%Y-%m-%d")

    # 检查现有分析结果
    from pathlib import Path

    analysis_dir = Path("quan_tr") / "analysis_results" / current_date
    existing_analysis = analysis_dir.exists() and any(analysis_dir.glob("*.json"))

    if rewrite or not existing_analysis:
        task_type = "重新分析" if rewrite else "执行"
        skip_note = (
            "" if rewrite else "（如果程序缺失或有问题，请先开发或优化相应程序）"
        )

        return f"""
执行股票分析任务：{task_type}{current_date}的股票池

## 任务概述
基于QuanTr量化交易系统，对股票池中的股票进行全面的量化分析，生成详细的分析报告和交易策略建议。

## 详细任务要求

### 1. 准备工作
- 检查项目目录结构是否完整（data_files/, analysis_results/, backtest_reports/, programs/等）
- 验证股票池配置文件：quan_tr/stocks_pool.json
- 检查系统配置文件：quan_tr/config.py 和 quan_tr/config.yaml
- 确保必要的Python库已安装（akshare, yfinance, pandas, numpy等）
- 检查近期是否有回测报告，检查programs/README.md，根据回测报告反思和优化程序并测试（优化后在programs/README.md中记下本次优化记录）

### 2. 数据获取与归档
- 从以下数据源获取今日股票数据：
  - **AKshare**: 获取股票基本信息、财务数据、行情数据
  - **Yahoo Finance**: 获取历史价格数据、公司信息
  - **东方财富**: 获取实时行情、财务数据、公告信息
- 将原始数据归档到 `data_files/{current_date}/` 目录下，按数据源分类存储
- 确保数据文件命名规范：`stock_<名称>_<代码>_<数据类型>_<日期>.json`
- 使用现有的数据获取程序（`programs/data_fetchers/`），如有问题请优化

### 3. 股票分析（对每只股票独立进行）
#### 基本面分析
- **公司经营分析**: 公司治理、竞争力、产品技术、行业地位
- **财务指标分析**: 
  - 盈利能力（毛利率、净利率、ROE、ROA）
  - 偿债能力（资产负债率、流动比率、速动比率）
  - 运营效率（资产周转率、存货周转率）
  - 成长能力（营收增长率、净利润增长率）
- **行业分析**: 行业生命周期、竞争格局、政策环境、发展趋势
- **宏观经济分析**: 经济周期、货币政策、通货膨胀、汇率变化
- **风险分析**: 系统性风险、非系统性风险、重点风险识别

#### 技术面分析
- **价格分析**: 当前价格、历史高低位、价格趋势、支撑阻力位
- **技术指标**:
  - 移动平均线（MA5, MA10, MA20, MA60, MA120）
  - 相对强弱指数（RSI）
  - MACD指标
  - 布林带（Bollinger Bands）
  - 成交量分析
- **价值评估**: 市盈率（PE）、市净率（PB）、股息率、估值合理性

#### 分析方法
- **基本分析法**: 基于经济学、金融学、财务管理学原理
- **技术分析法**: 基于K线理论、形态理论、技术指标理论
- **量化分析法**: 基于证券估值、组合优化、风险计量模型

### 4. 分析报告生成
- 为每只股票生成详细分析报告：`stock_<名称>_<代码>_analysis_{current_date}.md`
- 报告位置：`analysis_results/{current_date}/`
- 报告内容要求：
  1. 股票基本信息
  2. 基本面分析详细结果
  3. 技术面分析详细结果
  4. 风险评估
  5. 投资建议和操作策略
  6. 关键指标汇总

### 5. 买入卖出建议
- **股票低位区间判断**: 基于历史价格和估值分析
- **量化评分系统**: 对买入卖出时机进行0-100分评分
- **操作周期建议**: 
  - 短期（半月内）
  - 中期（1-3个月）
  - 长期（半年以上）
- **当日买入判断**: 横向对比所有股票，识别最佳买入机会
- **风险控制建议**: 止损位、止盈位、仓位控制

### 6. 结果汇总与结构化（**极其重要**）
- 将所有股票分析结果汇总为结构化数据
- **严格按照模板生成JSON文件**：`analysis_results/templates/stocks_analysis_template.json`
- **生成JSON格式汇总文件**：`stocks_analysis_{current_date}.json`
- **文件位置**：`analysis_results/{current_date}/`
- **必须严格遵循模板结构，必须包含以下所有字段（不能删减、不能简化）**：
  - `basic_info`: 股票名称、代码、市场、行业、公司全称、上市日期、股票类型等
  - `price_info`: 当前价格、涨跌幅、成交量、市值、52周高低位等
  - `fundamental_analysis`: 公司概况、行业分析、财务指标（营收、利润、毛利率、ROE等）、估值指标（PE、PB、股息率等）、增长指标、盈利能力指标
  - `technical_analysis`: 价格分析、趋势指标（MA5/10/20/60/120、趋势方向等）、动量指标（RSI、MACD、随机指标等）、波动率指标（布林带、ATR等）、成交量指标、支撑阻力位
  - `risk_analysis`: 系统性风险、非系统性风险、流动性风险、总体风险评估
  - `sentiment_analysis`: 新闻情绪、社交情绪、分析师情绪（买入/持有/卖出评级、目标价等）
  - `scoring_system`: 基本面评分(权重40%)、技术面评分(权重30%)、风险评分(权重20%)、情绪评分(权重10%)、加权得分、综合评分(0-100分)
  - `investment_recommendation`: 推荐等级(strong_buy/buy/hold/sell/strong_sell)、置信度、推荐理由、投资周期、目标价格（保守/基准/乐观）、仓位建议、进出策略（入场点、止盈止损位）、风险收益比、预期收益、预期持有期
  - `comparative_analysis`: 行业排名、同行对比、竞争地位
  - `key_highlights`: SWOT分析（优势、劣势、机会、威胁）和关键亮点
  - `reference_documents`: 官方文档（年报、季报）、研究报告、新闻文章、监管文件、公司网站、本地分析文件路径
  - `data_sources`: 价格数据源、财务数据源、新闻数据源、情绪数据源
  - `related_files`: 相关的分析文件路径列表
- **重要提示**：
  - 必须参考模板文件 `analysis_results/templates/stocks_analysis_template.json` 的完整结构
  - 数值型字段没有数据时用0填充，字符串字段用空字符串""填充，但不能省略字段
  - 确保JSON文件可以通过schema验证，字段名必须与模板完全一致
  - 每只股票的JSON对象必须包含模板中stocks数组中定义的每个字段
  - 生成的JSON文件大小应合理（单个股票至少包含100+个字段），不能是简化版

### 7. 程序检查与优化{skip_note}
- 检查现有数据获取程序：`programs/data_fetchers/`
- 检查现有分析程序：`programs/analyzers/`
- 如有程序缺失、错误或性能问题，请开发或优化相应程序
- 确保所有程序可正常运行，错误处理完善
- 更新程序文档和注释

### 8. 质量保证（**极其重要**）
- **验证数据完整性**：确保所有必要数据都已获取
- **检查分析逻辑**：确保分析方法科学合理
- **验证报告格式**：确保报告内容完整、格式规范
- **验证JSON结构（重点）**：
  - 必须使用 `read_file` 工具读取并参考 `analysis_results/templates/stocks_analysis_template.json` 的完整结构
  - 生成的JSON必须包含模板中定义的所有字段，不能遗漏
  - 使用 `read_file` 验证生成的 `stocks_analysis_{current_date}.json` 是否包含完整字段
  - 检查每只股票的字段是否与模板一致（basic_info、price_info、fundamental_analysis、technical_analysis等模块）
  - 如发现字段缺失，必须补充完整，可以使用占位值（0、空字符串等）但不能省略字段
  - JSON必须通过语法验证，确保无语法错误
- **测试程序稳定性**：确保程序可重复运行
- **交叉验证**：对比Markdown报告和JSON数据的一致性，确保数据不矛盾

## 注意事项
1. **数据使用合规**: 遵守各数据源的使用条款，控制请求频率
2. **风险提示**: 所有分析结果仅供参考，不构成投资建议
3. **程序优先**: 优先使用现有程序，如需开发新程序请确保模块化设计
4. **错误处理**: 完善的异常处理和日志记录
5. **文档更新**: 更新相关文档，记录分析过程和结果

## 产出期望
1. 原始数据文件（按日期和数据源分类存储）
2. 每只股票的详细分析报告（Markdown格式）
3. 结构化汇总数据（**JSON格式，极其重要**）：
   - **文件名**：`stocks_analysis_{current_date}.json`
   - **位置**：`analysis_results/{current_date}/`
   - **结构要求**：**必须严格遵循** `analysis_results/templates/stocks_analysis_template.json` 的完整字段结构
   - **内容要求**：包含模板中定义的所有字段模块（basic_info、price_info、fundamental_analysis、technical_analysis、risk_analysis、sentiment_analysis、scoring_system、investment_recommendation、comparative_analysis、key_highlights、reference_documents、data_sources、related_files等）
   - **数据完整性**：每只股票的JSON对象必须包含模板中定义的所有字段，不能简化或删减。数值型字段无数据时用0填充，字符串字段用空字符串填充
   - **验证要求**：生成后必须使用工具验证JSON结构是否符合模板，如发现字段缺失必须补充完整
4. 程序优化记录（如有）
5. 分析过程日志

**任务状态**: {"覆盖已有分析" if rewrite else "增量分析（跳过已完成的股票）"}
"""
    else:
        # 增量分析模式
        return f"""
执行股票分析任务：增量分析{current_date}的股票池

## 任务概述
基于已有分析结果，对今日尚未分析的股票进行补充分析，确保股票池中的所有股票都有今日的分析报告。

## 详细任务要求

### 1. 状态检查
- 检查 `analysis_results/{current_date}/` 目录下的现有分析结果
- 识别已分析的股票和未分析的股票
- 统计已完成和待完成的分析数量

### 2. 增量数据获取
- 仅获取未分析股票的数据
- 使用现有数据获取程序（`programs/data_fetchers/`）
- 确保数据获取效率，避免重复请求

### 3. 增量分析
- 对未分析的股票执行完整的分析流程：
  - 基本面分析
  - 技术面分析
  - 风险评估
  - 投资建议生成
- 使用现有分析程序（`programs/analyzers/`）

### 4. 报告生成与更新
- 为未分析的股票生成分析报告
- 更新汇总文件（JSON），包含所有股票的分析结果
- 确保新增数据与现有数据格式一致

### 5. 质量验证
- 验证新增分析结果的质量
- 检查数据一致性
- 确保汇总文件包含所有股票

### 6. 程序维护
- 检查程序运行状态
- 如有问题，进行必要的优化
- 更新运行日志

## 注意事项
1. **效率优先**: 避免重复获取已分析股票的数据
2. **数据一致性**: 确保新增数据与现有数据格式一致
3. **完整性检查**: 最终确保所有股票都有分析结果
4. **错误处理**: 如遇数据获取失败，记录并跳过，继续处理其他股票

## 产出期望
1. 新增股票的分析报告
2. 更新后的汇总文件（包含所有股票）
3. 增量分析完成报告
4. 如有问题，记录问题详情和解决方案

**任务状态**: 增量分析（跳过已完成的股票）
"""


def generate_backtest_task(period="weekly"):
    """生成策略回测任务描述"""
    current_date = datetime.now().strftime("%Y-%m-%d")

    if period == "weekly":
        days = 7
        period_desc = "近一周（7天）"
    else:  # monthly
        days = 30
        period_desc = "近一个月"

    return f"""
执行策略回测任务：对{period_desc}的分析策略进行回测验证

任务要求：
1. 数据准备：
   - 收集最近{days}天的股票分析结果（JSON文件）
   - 获取相应的历史价格数据用于回测
   - 确保数据完整性和一致性

2. 回测策略定义：
   - 基于分析结果中的买入卖出建议定义交易策略
   - 考虑交易成本、滑点等现实因素
   - 定义回测参数：初始资金、持仓限制、风险控制等

3. 回测执行：
   - 对每只股票的策略进行历史回测
   - 计算关键绩效指标：收益率、夏普比率、最大回撤、胜率等
   - 记录每笔交易的详细信息

4. 结果分析：
   - 分析策略在不同市场环境下的表现
   - 识别策略的优势和不足
   - 提供策略优化建议

5. 报告生成：
   - 生成详细的回测报告：strategies_backtest_report_{current_date}.md
   - 报告内容包括：回测概述、绩效指标、交易记录、策略分析、优化建议
   - 可视化图表：净值曲线、回撤曲线、收益分布等

6. 程序检查与优化：
   - 检查现有回测程序
   - 如有问题或缺失，开发或优化回测程序
   - 确保回测程序可正常运行

注意：回测结果仅供参考，不构成投资建议。
"""


async def main():
    """QuanTr命令行主函数"""
    import time as time_module

    parser = argparse.ArgumentParser(
        description="📈 QuanTr - 基于AI Agent的股票量化分析与策略回测系统",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
使用示例:
  # 常规股票分析任务
  python3 main_quan_tr.py
  python3 main_quan_tr.py --normal
  
  # 重新分析当日股票
  python3 main_quan_tr.py --rewrite
  
  # 策略回测任务
  python3 main_quan_tr.py --backtest
  python3 main_quan_tr.py --backtest_weekly
  python3 main_quan_tr.py --backtest_monthly
  
  # 自定义任务
  python3 main_quan_tr.py "开发新的技术指标分析程序"
  
  # 指定工作目录
  python3 main_quan_tr.py -p projects/quan_tr_analysis
        """,
    )
    parser.add_argument(
        "-p",
        "--project",
        default="quan_tr",
        help="aacode工作目录，用于存放日志和上下文文件，默认为quan_tr",
    )
    parser.add_argument(
        "-t",
        "--target",
        default="quan_tr",
        help="目标项目目录(用户实际项目路径)，默认使用quan_tr目录",
    )
    parser.add_argument(
        "task",
        nargs="*",
        help='自定义任务描述，例如 "开发新的技术指标分析程序"',
    )

    # QuanTr特定参数
    parser.add_argument(
        "--normal", action="store_true", help="常规股票分析任务（默认）"
    )
    parser.add_argument("--rewrite", action="store_true", help="重新分析当日股票")
    parser.add_argument(
        "--backtest", action="store_true", help="回测近一周（7天）的分析策略"
    )
    parser.add_argument(
        "--backtest_weekly", action="store_true", help="回测近一周（7天）的分析策略"
    )
    parser.add_argument(
        "--backtest_monthly", action="store_true", help="回测近一个月的分析策略"
    )

    # 原有参数（保持兼容）
    parser.add_argument("--continue", action="store_true", help="继续上一个会话")
    parser.add_argument("--session", help="指定会话ID")
    parser.add_argument("--plan-first", action="store_true", help="先规划再执行模式")
    parser.add_argument("--interactive", action="store_true", help="交互式模式")

    args = parser.parse_args()

    # 加载环境变量配置
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

    # 解析任务和目标项目
    # 如果第一个参数是路径（存在的目录），则作为目标项目
    target_project = args.target
    task_parts = args.task

    if task_parts and not target_project:
        first_arg = task_parts[0]
        # 检查第一个参数是否是存在的目录
        # 添加长度检查，避免把长任务描述当作路径
        if len(first_arg) < 200 and Path(first_arg).is_dir():
            target_project = first_arg
            task_parts = task_parts[1:]  # 剩余部分作为任务
            print(f"🎯 检测到目标项目: {target_project}")

    # 如果命令行没给任务，就交互式询问
    user_task = " ".join(task_parts).strip()
    if not user_task:
        user_task = input("请输入任务（可选，直接回车使用默认任务）: ").strip()

    # 创建QuanTr编码助手实例
    # 从环境变量读取模型配置
    model_config = {
        "api_key": os.environ.get("LLM_API_KEY", ""),
        "base_url": os.environ.get("LLM_API_URL", "https://api.deepseek.com/v1"),
        "model": os.environ.get("LLM_MODEL_NAME", "deepseek-chat"),
        "searchxng_url": os.environ.get("SEARCHXNG_URL", ""),
    }
    coder = QuanTrCoder(
        args.project, model_config=model_config, target_project=target_project
    )

    # 根据命令行参数确定预置任务类型
    base_task = None
    task_type_name = ""
    if args.backtest or args.backtest_weekly:
        base_task = generate_backtest_task("weekly")
        task_type_name = "近7天分析策略回测"
    elif args.backtest_monthly:
        base_task = generate_backtest_task("monthly")
        task_type_name = "近一个月分析策略回测"
    elif args.rewrite:
        base_task = generate_stock_analysis_task(rewrite=True)
        task_type_name = "重新分析当日股票"
    elif args.normal or not user_task:
        base_task = generate_stock_analysis_task()
        task_type_name = "常规股票分析"

    # 合并预置任务和用户输入的任务
    if base_task and user_task:
        # 有预置任务，也有用户输入，进行拼接
        task = f"""{base_task}

## 用户补充任务
{user_task}

"""
        print(f"📈 执行股票分析任务: {task_type_name}")
        print(f"📝 用户补充: {user_task}")
    elif base_task:
        # 只有预置任务，没有用户输入
        task = base_task
        print(f"📈 执行股票分析任务: {task_type_name}")
    else:
        # 没有预置任务（使用了自定义参数但没有指定具体任务类型），使用用户输入
        task = user_task
        print(f"🎯 执行自定义任务: {task}")

    # 运行任务
    try:
        result = await coder.run(task)

        print(f"\n✅ 任务完成!")
        print(f"📋 会话ID: {result.get('session_id', 'N/A')}")
        print(f"迭代次数: {result.get('iterations', 0)}")
        print(f"最终状态: {result.get('status', 'unknown')}")
        print(f"执行时间: {result.get('execution_time', 0):.2f}秒")

        # 检查生成的文件
        project_dir = Path(args.project)
        created_files = []

        # 递归查找项目目录下的Python文件（排除.aacode和虚拟环境）
        exclude_dirs = {
            ".aacode",
            ".venv",
            "venv",
            "__pycache__",
            ".git",
            "node_modules",
        }

        for py_file in project_dir.rglob("*.py"):
            # 排除特定目录和主程序
            if py_file.name != "main.py" and not any(
                excluded in py_file.parts for excluded in exclude_dirs
            ):
                # 检查文件是否是最近创建的（5分钟内）
                import time

                if time.time() - py_file.stat().st_mtime < 300:  # 5分钟 = 300秒
                    created_files.append(py_file)
        """
        # 这个后续动作有点生硬，先注释
        if created_files:
            print("\n📁 生成的文件:")
            for file in created_files:
                # 显示相对路径
                rel_path = file.relative_to(project_dir)
                print(f"  - {rel_path}")

                # 询问是否运行Python文件
                try:
                    response = input(f"是否运行 {rel_path}? (y/n): ").strip().lower()
                    if response == 'y':
                        print(f"🚀 运行 {rel_path}:")

                        # 方法1: 尝试使用项目根目录作为工作目录
                        result = subprocess.run([sys.executable, str(rel_path)], 
                                              cwd=project_dir, 
                                              capture_output=True, text=True,
                                              env={**os.environ, 'PYTHONPATH': str(project_dir)})

                        if result.returncode == 0:
                            print(f"✅ 输出: {result.stdout.strip()}")
                        else:
                            error_msg = result.stderr.strip()
                            print(f"❌ 错误: {error_msg}")

                            # 提供更详细的错误信息和解决建议
                            if error_msg:
                                print(f"\n💡 错误分析:")
                                if "No module named" in error_msg:
                                    print(f"   - 导入错误: 缺少依赖模块")
                                    print(f"   - 建议: 检查是否需要安装依赖包")
                                    print(f"   - 或者: 文件可能需要在特定目录运行")
                                elif "FileNotFoundError" in error_msg or "No such file" in error_msg:
                                    print(f"   - 文件路径错误")
                                    print(f"   - 建议: 检查文件中使用的相对路径")
                                else:
                                    print(f"   - 建议: 检查代码逻辑和语法")
                except (KeyboardInterrupt, EOFError):
                    print("\n跳过运行")
                    break
        """

        # 任务完成后，默认进入继续会话模式
        print("\n" + "=" * 50)
        print("✅ 任务已完成！")
        print("=" * 50)

        # 询问是否继续执行追加任务
        try:
            response = (
                input("\n🔁 是否继续执行其他任务? (y/n，默认y): ").strip().lower()
            )
            if not response or response == "y":
                await continue_session(coder, project_dir)
        except (KeyboardInterrupt, EOFError):
            print("\n👋 退出程序")

    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
        # 即使中断，也询问是否继续
        try:
            response = (
                input("\n🔁 任务被中断，是否继续执行其他任务? (y/n): ").strip().lower()
            )
            if response == "y":
                project_dir = Path(args.project)
                await continue_session(coder, project_dir)
        except:
            pass
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback

        traceback.print_exc()
        # 错误后也询问是否继续
        try:
            response = (
                input("\n🔁 发生错误，是否继续执行其他任务? (y/n): ").strip().lower()
            )
            if response == "y":
                project_dir = Path(args.project)
                await continue_session(coder, project_dir)
        except:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ 程序被用户中断，正常退出")
        sys.exit(0)
