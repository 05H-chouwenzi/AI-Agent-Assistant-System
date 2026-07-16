import re, sys

with open('services/llm_async.py', 'r', encoding='utf-8-sig') as f:
    src = f.read()

# 1. Add params to async_call_llm
old_sig = r"(async def async_call_llm\(\s*system_prompt: str,\s*messages: list\[dict\],\s*tools: list \| None = None,\s*\))"
new_sig = r"\1\n    max_tokens: int | None = None,\n    temperature: float = 0.1,"
src = re.sub(old_sig, new_sig, src)

# 2. Update body: add max_tokens
src = src.replace(
    '        temperature=0.1,\n        tools=tools or [],',
    '        temperature=temperature,\n        tools=tools or [],\n        max_tokens=max_tokens,'
)

# 3. Add params to async_stream_with_tools
old_sig2 = r"(async def async_stream_with_tools\(\s*system_prompt: str,\s*messages: list\[dict\],\s*tools: list \| None = None,\s*stream_queue=None,\s*\))"
new_sig2 = r"\1\n    max_tokens: int | None = None,\n    temperature: float = 0.7,"
src = re.sub(old_sig2, new_sig2, src)

# 4. Update stream body
src = src.replace(
    '        temperature=0.7,\n        tools=tools or [],\n        stream=True,\n        stream_options={"include_usage": True},',
    '        temperature=temperature,\n        tools=tools or [],\n        stream=True,\n        stream_options={"include_usage": True},\n        max_tokens=max_tokens,'
)

# 5. Update timeout
src = src.replace(
    '    timeout=30.0,\n    max_retries=1,',
    '    timeout=25.0,\n    max_retries=0,'
)

compile(src.replace('\ufeff', ''), 'llm_async.py', 'exec')
with open('services/llm_async.py', 'w', encoding='utf-8') as f:
    f.write(src)
print('llm_async.py OK')

# === nodes.py ===
with open('agent/graph/nodes.py', 'r', encoding='utf-8-sig') as f:
    src2 = f.read()

# The exact text in the file (before the except block)
# We need to add max_tokens=512, temperature=0.1 to the 2nd streaming call
# Find the 2nd async_stream_with_tools call (the one with tools=None)
# Look for "stream_queue=queue,\n            )\n        except Exception:\n            final_content"
old = 'stream_queue=queue,\n            )\n        except Exception:\n            final_content, _ = await async_call_llm(\n                "\u4f60\u662f\u4e00\u4e2a\u4e13\u4e1a\u7684\u4f01\u4e1aAI\u52a9\u624b\uff0c\u8bf7\u7528\u4e2d\u6587\u7b80\u6d01\u5730\u56de\u7b54\u7528\u6237\u95ee\u9898\u3002",\n                [{"role": "user", "content": answer_prompt}],\n            )'
new = 'stream_queue=queue,\n                max_tokens=512,\n                temperature=0.1,\n            )\n        except Exception:\n            final_content, _ = await async_call_llm(\n                "\u4f60\u662f\u4e00\u4e2a\u4e13\u4e1a\u7684\u4f01\u4e1aAI\u52a9\u624b\uff0c\u8bf7\u7528\u4e2d\u6587\u7b80\u6d01\u5730\u56de\u7b54\u7528\u6237\u95ee\u9898\u3002",\n                [{"role": "user", "content": answer_prompt}],\n                max_tokens=512,\n                temperature=0.1,\n            )'

if old in src2:
    src2 = src2.replace(old, new)
    print('nodes.py: updated 2nd LLM call')
else:
    print('nodes.py: WARNING - pattern not found, checking lines...')
    # Debug: find the lines with stream_queue=queue
    lines = src2.split('\n')
    for i, line in enumerate(lines):
        if 'stream_queue=queue' in line and 'max_tokens' not in line:
            context = '\n'.join(lines[max(0,i-2):i+6])
            print(f'Found at line {i+1}:\n{context}')

compile(src2.replace('\ufeff', ''), 'nodes.py', 'exec')
with open('agent/graph/nodes.py', 'w', encoding='utf-8') as f:
    f.write(src2)
print('nodes.py OK')
