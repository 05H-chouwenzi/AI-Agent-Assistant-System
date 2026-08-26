"""
Weather Tool —— 天气查询工具（基于 wttr.in 免费 API）

性能特性：
  - 内置 10 分钟缓存（每个城市独立），重复查询无需网络请求
  - 网络超时 5 秒，避免慢 API 拖慢响应
"""
import asyncio
import json
import time
import urllib.request
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

        # ====== 2. 从网络获取（httpx + 超时，HTTPS 失败自动回退 HTTP）======
        encoded_city = quote(city)
        # HTTP 优先：实测 wttr.in HTTPS 在部分网络下经常 TLS 中断，HTTP 更稳定
        urls = [
            f"http://wttr.in/{encoded_city}?format=j1&lang=zh",
            f"https://wttr.in/{encoded_city}?format=j1&lang=zh",
        ]
        last_error = None
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AI-Agent-Assistant/1.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    raw = resp.read().decode("utf-8")
                if resp.status == 200:
                    data = json.loads(raw)
                    weather_info = _parse_weather(data, city, days)
                    _set_cache(city, weather_info)
                    elapsed = (time.time() - start) * 1000
                    return ToolResult(
                        success=True,
                        data=weather_info,
                        tool_name=self.name,
                        execution_time_ms=round(elapsed, 2)
                    )
                last_error = f"HTTP {resp.status}"
            except Exception as e:
                last_error = str(e)

        elapsed = (time.time() - start) * 1000
        return ToolResult(
            success=False,
            error=f"天气 API 请求失败: {last_error}",
            tool_name=self.name,
            execution_time_ms=round(elapsed, 2)
        )

    async def aexecute(self, **kwargs) -> ToolResult:
        """异步版本：urllib 放入线程池执行，不阻塞事件循环"""
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

        encoded_city = quote(city)
        # HTTP 优先：实测 wttr.in HTTPS 在部分网络下经常 TLS 中断，HTTP 更稳定
        urls = [
            f"http://wttr.in/{encoded_city}?format=j1&lang=zh",
            f"https://wttr.in/{encoded_city}?format=j1&lang=zh",
        ]
        last_error = None
        for url in urls:
            try:
                def _fetch(url=url):
                    req = urllib.request.Request(url, headers={"User-Agent": "AI-Agent-Assistant/1.0"})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        return resp.status, resp.read().decode("utf-8")
                status, raw = await asyncio.to_thread(_fetch)
                if status == 200:
                    data = json.loads(raw)
                    weather_info = _parse_weather(data, city, days)
                    _set_cache(city, weather_info)
                    elapsed = (time.time() - start) * 1000
                    return ToolResult(
                        success=True,
                        data=weather_info,
                        tool_name=self.name,
                        execution_time_ms=round(elapsed, 2)
                    )
                last_error = f"HTTP {status}"
            except Exception as e:
                last_error = str(e)

        elapsed = (time.time() - start) * 1000
        return ToolResult(
            success=False,
            error=f"天气 API 请求失败: {last_error}",
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


