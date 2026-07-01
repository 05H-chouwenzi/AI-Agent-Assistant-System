"""
Weather Tool —— 天气查询工具（基于 wttr.in 免费 API）
"""
import json
import time
import urllib.request
import urllib.parse
from tools.base_tool import BaseTool, ToolResult


class WeatherTool(BaseTool):

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return "查询指定城市的实时天气信息，包括温度、天气状况、湿度、风速等。可用于查询当天或未来几天的天气。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，中文或英文均可，如 '北京'、'Shanghai'、'Tokyo'"
                },
                "days": {
                    "type": "integer",
                    "description": "预报天数，2=今天+明天，3=今天+明天+后天。默认 1 表示仅今天（不含预报）。查明天天气请传 2",
                    "default": 1
                }
            },
            "required": ["city"]
        }

    def execute(self, **kwargs) -> ToolResult:
        city = kwargs.get("city", "")
        days = kwargs.get("days", 1)

        if not city:
            return ToolResult(success=False, error="缺少城市参数", tool_name=self.name)

        start = time.time()
        try:
            encoded_city = urllib.parse.quote(city)
            url = f"https://wttr.in/{encoded_city}?format=j1&lang=zh"

            req = urllib.request.Request(url, headers={"User-Agent": "AI-Agent-Assistant/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            # 解析关键字段
            current = data.get("current_condition", [{}])[0]
            weather_info = {
                "城市": city,
                "当前温度": f"{current.get('temp_C', 'N/A')}°C",
                "体感温度": f"{current.get('FeelsLikeC', 'N/A')}°C",
                "天气状况": current.get("weatherDesc", [{}])[0].get("value", "N/A"),
                "湿度": f"{current.get('humidity', 'N/A')}%",
                "风速": f"{current.get('windspeedKmph', 'N/A')} km/h",
                "风向": current.get("winddir16Point", "N/A"),
                "能见度": f"{current.get('visibility', 'N/A')} km",
                "紫外线指数": current.get("uvIndex", "N/A"),
            }

            # 添加天气预报（跳过今天，从明天开始）
            if days > 1:
                forecasts = []
                for day_data in data.get("weather", [])[1:days]:  # weather[0]=今天, [1:days]=未来days-1天
                    date = day_data.get("date", "")
                    max_temp = day_data.get("maxtempC", "N/A")
                    min_temp = day_data.get("mintempC", "N/A")
                    avg_temp = day_data.get("avgtempC", "N/A")
                    forecasts.append({
                        "日期": date,
                        "最高温": f"{max_temp}°C",
                        "最低温": f"{min_temp}°C",
                        "平均温": f"{avg_temp}°C",
                    })
                weather_info["预报"] = forecasts

            elapsed = (time.time() - start) * 1000
            return ToolResult(
                success=True,
                data=weather_info,
                tool_name=self.name,
                execution_time_ms=round(elapsed, 2)
            )

        except urllib.error.URLError as e:
            return ToolResult(success=False, error=f"网络请求失败: {str(e)}", tool_name=self.name)
        except json.JSONDecodeError:
            return ToolResult(success=False, error="天气数据解析失败", tool_name=self.name)
        except Exception as e:
            return ToolResult(success=False, error=f"未知错误: {str(e)}", tool_name=self.name)
