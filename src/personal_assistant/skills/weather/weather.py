#!/usr/bin/env python3
"""天气查询脚本——使用 wttr.in 免费 API，无需 API key。

用法::

    python weather.py "城市名"
    python weather.py "北京"
    python weather.py "Tokyo"

输出格式::

    城市: 北京
    天气: 晴
    温度: 15°C
    体感温度: 13°C
    湿度: 45%
    风力: 北风 3级
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

# Windows 终端默认 GBK 编码，强制 stdout 使用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get_weather(city: str) -> str:
    """查询指定城市的天气，返回格式化文本。"""
    if not city.strip():
        return "错误：城市名不能为空"

    try:
        # wttr.in 提供免费天气 API，支持中文城市名
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Python-Assistant/1.0",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))

        # 提取当前天气信息
        current = data.get("current_condition", [{}])[0]
        area = data.get("nearest_area", [{}])[0]

        # 城市名（优先中文，其次英文）
        city_name = city
        area_names = area.get("areaName", [])
        if area_names:
            city_name = area_names[-1].get("value", city)

        # 天气描述
        weather_desc = current.get("weatherDesc", [{}])[0].get("value", "未知")
        temp_c = current.get("temp_C", "N/A")
        feels_like_c = current.get("FeelsLikeC", "N/A")
        humidity = current.get("humidity", "N/A")
        wind_speed = current.get("windspeedKmph", "N/A")
        wind_dir = current.get("winddir16Point", "N/A")

        # 格式化输出
        lines = [
            f"城市: {city_name}",
            f"天气: {weather_desc}",
            f"温度: {temp_c}°C",
            f"体感温度: {feels_like_c}°C",
            f"湿度: {humidity}%",
            f"风力: {wind_dir} {wind_speed}km/h",
        ]

        return "\n".join(lines)

    except urllib.error.URLError as e:
        return f"查询失败：网络错误 ({e.reason})"
    except Exception as e:
        return f"查询失败：{e!r}"


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python weather.py <城市名>")
        print("示例: python weather.py 北京")
        return 1

    city = " ".join(sys.argv[1:])
    print(get_weather(city))
    return 0


if __name__ == "__main__":
    sys.exit(main())
