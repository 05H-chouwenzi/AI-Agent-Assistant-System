import asyncio

from rag.parsers import ParsedBlock
from services.knowledge_files import _describe_image_blocks


def _image_block(index: int) -> ParsedBlock:
    return ParsedBlock(
        content="",
        content_type="image",
        metadata={"page_number": index + 1},
        image_path=f"image-{index + 1}.png",
        ocr_text=f"ocr {index + 1}",
    )


async def test_vision_descriptions_use_bounded_concurrency_and_keep_order(monkeypatch):
    blocks = [_image_block(index) for index in range(8)]
    state = {"active": 0, "max_active": 0}

    async def fake_describe(block, filename):
        state["active"] += 1
        state["max_active"] = max(state["max_active"], state["active"])
        await asyncio.sleep(0.02)
        state["active"] -= 1
        return f"vision-{block.metadata['page_number']}"

    monkeypatch.setattr("services.knowledge_files._describe_block_image", fake_describe)

    descriptions, failures = await _describe_image_blocks(blocks, "document.pdf")

    assert state["max_active"] == 3
    assert descriptions == [f"vision-{index + 1}" for index in range(8)]
    assert failures == []


async def test_vision_failure_is_recorded_without_fabricating_a_result(monkeypatch):
    blocks = [_image_block(index) for index in range(2)]

    async def fake_describe(block, filename):
        if block.metadata["page_number"] == 2:
            raise RuntimeError("vision unavailable")
        return "vision-1"

    monkeypatch.setattr("services.knowledge_files._describe_block_image", fake_describe)

    descriptions, failures = await _describe_image_blocks(blocks, "document.pdf")

    assert descriptions == ["vision-1", None]
    assert len(failures) == 1
    assert failures[0][0] == 1
    assert isinstance(failures[0][1], RuntimeError)
    assert str(failures[0][1]) == "vision unavailable"
