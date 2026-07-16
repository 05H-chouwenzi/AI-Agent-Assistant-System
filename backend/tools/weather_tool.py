"""
Weather Tool —— 天气查询工具（基于 wttr.in 免费 API）

性能特性：
  - 内置 10 分钟缓存（每个城市独立），重复查询无需网络请求
  - 网络超时 5 秒，避免慢 API 拖慢响应
"""
import json
import time
import httpx
from urllib.parse import quote

from tools.base_tool import BaseTool, ToolResult

# ---------- 内存缓存：10 分钟 TTL ----------
_cache: dict[str, tuple[float, dict]] = {}      # city -> (timestamp, data)
CACHE_TTL = 600  # 10 分钟（600秒）

def _get_cached(city: str) -> dict | None:
    """获取缓存的天气数据"""
    entry = _cache.get(city)
    if entry and (time.time() - entry[0]) < CACHE_TTL:
        return entry[1]
    return None

def _set_cache(city: str, data: dict):
    """写入天气缓存"""
    _cache[city] = (time.time(), data)


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

        # ====== 1. 查缓存（相同城市 10 分钟内直接返回）======
        cached = _get_cached(city)
        if cached:
            if "预报" in cached or days <= 1:
                elapsed = (time.time() - start) * 1000
                return ToolResult(
                    success=True,
                    data=cached,
                    tool_name=self.name,
                    execution_time_ms=round(elapsed, 2)
                )

        # ====== 2. 从网络获取（httpx + 3s 超时）======
        try:
            encoded_city = quote(city)
            url = f"https://wttr.in/{encoded_city}?format=j1&lang=zh"
            resp = httpx.get(url, headers={"User-Agent": "AI-Agent-Assistant/1.0"}, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
            else:
                raise Exception(f"HTTP {resp.status_code}")

            weather_info = _parse_weather(data, city, days)

            _set_cache(city, weather_info)

            elapsed = (time.time() - start) * 1000
            return ToolResult(
                success=True,
                data=weather_info,
                tool_name=self.name,
                execution_time_ms=round(elapsed, 2)
            )

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return ToolResult(
                success=False,
                error=f"天气 API 请求失败: {str(e)}",
                tool_name=self.name,
                execution_time_ms=round(elapsed, 2)
            )

    async def aexecute(self, **kwargs) -> ToolResult:
        """异步版本：使用 httpx.AsyncClient，真正不阻塞事件循环"""
        city = kwargs.get("city", "")
        days = kwargs.get("days", 1)

        if not city:
            return ToolResult(success=False, error="缺少城市参数", tool_name=self.name)

        start = time.time()

        # 查缓存
        cached = _get_cached(city)
        if cached:
            if "预报" in cached or days <= 1:
                elapsed = (time.time() - start) * 1000
                return ToolResult(
                    success=True,
                    data=cached,
                    tool_name=self.name,
                    execution_time_ms=round(elapsed, 2)
                )

        try:
            encoded_city = quote(city)
            url = f"https://wttr.in/{encoded_city}?format=j1&lang=zh"
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url, headers={"User-Agent": "AI-Agent-Assistant/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                else:
                    raise Exception(f"HTTP {resp.status_code}")

            weather_info = _parse_weather(data, city, days)
            _set_cache(city, weather_info)

            elapsed = (time.time() - start) * 1000
            return ToolResult(
                success=True,
                data=weather_info,
                tool_name=self.name,
                execution_time_ms=round(elapsed, 2)
            )

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return ToolResult(
                success=False,
                error=f"天气 API 请求失败: {str(e)}",
                tool_name=self.name,
                execution_time_ms=round(elapsed, 2)
            )


def _parse_weather(data: dict, city: str, days: int) -> dict:
    """解析 wttr.in 返回的天气数据（sync/async 共用）"""
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

    if days > 1:
        forecasts = []
        for day_data in data.get("weather", [])[1:days]:
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

    return weather_info


