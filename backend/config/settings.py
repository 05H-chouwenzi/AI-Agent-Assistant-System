"""
全局配置 —— 从 .env 读取
"""
import os 
from pathlib import Path 
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DASHSCOPE_API_KEY=os.getenv("DASHSCOPE_API_KEY","")
DASHSCOPE_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL="qwen3.6-plus-2026-04-02"

