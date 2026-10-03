import unittest

import httpx

from app.services.translation_service import GeminiTranslationProvider, TranslationUnavailable


def gemini_response(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": text}]}}]},
    )


class GeminiTranslationTests(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_fenced_json_and_translation_wrapper(self) -> None:
        transport = httpx.MockTransport(
            lambda request: gemini_response('```json\n{"translations":["Hello", "World"]}\n```')
        )
        async with httpx.AsyncClient(transport=transport) as client:
            provider = GeminiTranslationProvider(client, "key", "model")
            self.assertEqual(await provider.translate_many(["வணக்கம்", "உலகம்"], "ta", "en"), ["Hello", "World"])

    async def test_retries_malformed_multi_item_batch_individually(self) -> None:
        answers = iter([
            '["Hello"]',
            '["First"]',
            '["Second"]',
        ])
        transport = httpx.MockTransport(lambda request: gemini_response(next(answers)))
        async with httpx.AsyncClient(transport=transport) as client:
            provider = GeminiTranslationProvider(client, "key", "model")
            self.assertEqual(await provider.translate_many(["ஒன்று", "இரண்டு"], "ta", "en"), ["First", "Second"])

    async def test_rejects_invalid_single_item_response(self) -> None:
        transport = httpx.MockTransport(lambda request: gemini_response("[]"))
        async with httpx.AsyncClient(transport=transport) as client:
            provider = GeminiTranslationProvider(client, "key", "model")
            with self.assertRaises(TranslationUnavailable):
                await provider.translate("வணக்கம்", "ta", "en")


if __name__ == "__main__":
    unittest.main()
