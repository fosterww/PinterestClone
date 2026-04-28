import base64
from unittest.mock import Mock

from pins import task as pins_task


def test_tag_pin_image_task_does_not_enqueue_index_when_pin_is_missing(monkeypatch):
    async def fake_tag_pin_image(pin_id, image_bytes, generate_ai_description):
        return False

    index_delay = Mock()
    monkeypatch.setattr(pins_task, "_tag_pin_image", fake_tag_pin_image)
    monkeypatch.setattr(pins_task.index_image_task, "delay", index_delay)

    pins_task.tag_pin_image_task.run(
        "missing-pin-id", base64.b64encode(b"image").decode("utf-8"), False
    )

    index_delay.assert_not_called()
