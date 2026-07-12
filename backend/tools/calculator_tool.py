"""
Calculator Tool —— 数学计算工具（安全沙箱版）

支持的运算：
  - 基本算术：+ - * / %
  - 数学函数：sqrt() sin() cos() tan() log() ln() abs() ceil() floor() round()
  - 幂运算：pow(x, y) / **
  - 常量：π(3.14159...) e(2.71828...)

安全性：
  - 仅允许数学表达式，禁用 __import__、eval 的危险操作
  - 通过限制 globals 白名单实现沙箱
"""
import math
import re
import time
from typing import Any

from tools.base_tool import BaseTool, ToolResult


class CalculatorTool(BaseTool):

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "执行数学计算，支持加减乘除、平方根、三角函数、对数等运算。适用于计算表达式、公式求解等。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，如 '123+456'、'sqrt(64)'、'(1+2)*3'、'sin(30)'",
                }
            },
            "required": ["expression"],
        }

    # 安全白名单 —— 只允许纯数学函数和常量
    _SAFE_GLOBALS = {
        "__builtins__": {},
        "abs": abs,
        "round": round,
        "int": int,
        "float": float,
        "pow": pow,
        "max": max,
        "min": min,
        "sum": sum,
    }

    _SAFE_MATH = {
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "atan2": math.atan2,
        "log": math.log,
        "log2": math.log2,
        "log10": math.log10,
        "ln": math.log,
        "sinh": math.sinh,
        "cosh": math.cosh,
        "tanh": math.tanh,
        "degrees": math.degrees,
        "radians": math.radians,
        "ceil": math.ceil,
        "floor": math.floor,
        "trunc": math.trunc,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
        "inf": math.inf,
    }

    def execute(self, **kwargs) -> ToolResult:
        expression = kwargs.get("expression", "").strip()

        if not expression:
            return ToolResult(
                success=False,
                error="缺少表达式参数",
                tool_name=self.name,
            )

        start = time.time()

        try:
            # 安全检查1：禁止双下划线（Python 内省攻击）
            if '__' in expression:
                return ToolResult(
                    success=False,
                    error="表达式包含不安全的字符",
                    tool_name=self.name,
                )

            # 安全检查2：只允许数学表达式相关字符
            allowed_chars = r'^[\d+\-*/%.()\s,a-zA-Z_\[\]<>!=]+$'
            if not re.match(allowed_chars, expression):
                return ToolResult(
                    success=False,
                    error="表达式包含不允许的字符，仅支持数学运算",
                    tool_name=self.name,
                )

            # 安全检查3：禁止属性访问（. 操作符），防止对象方法调用
            if re.search(r'\.[a-zA-Z_]', expression):
                return ToolResult(
                    success=False,
                    error="表达式包含不允许的操作",
                    tool_name=self.name,
                )

            # 构建安全命名空间：彻底禁用所有 builtins
            safe_globals = {"__builtins__": None, **self._SAFE_MATH, **self._SAFE_GLOBALS}

            # 使用安全的 eval 沙箱
            result = eval(expression, {"__builtins__": {}}, safe_globals)

            # 格式化结果
            if isinstance(result, float):
                # 处理浮点数精度
                if result == int(result) and abs(result) < 1e15:
                    formatted = str(int(result))
                else:
                    formatted = f"{result:.6f}".rstrip("0").rstrip(".")
            else:
                formatted = str(result)

            elapsed = (time.time() - start) * 1000

            return ToolResult(
                success=True,
                data={
                    "expression": expression,
                    "result": formatted,
                },
                tool_name=self.name,
                execution_time_ms=round(elapsed, 2),
            )

        except SyntaxError:
            return ToolResult(
                success=False,
                error=f"表达式语法错误: '{expression}'",
                tool_name=self.name,
            )
        except ZeroDivisionError:
            return ToolResult(
                success=False,
                error="除数不能为零",
                tool_name=self.name,
            )
        except (ValueError, TypeError, ArithmeticError) as e:
            return ToolResult(
                success=False,
                error=f"计算错误: {str(e)}",
                tool_name=self.name,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"计算异常: {str(e)}",
                tool_name=self.name,
            )
