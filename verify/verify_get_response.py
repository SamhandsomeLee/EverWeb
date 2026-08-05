import asyncio
import base64
from typing import Any

from playwright.async_api import async_playwright

async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()

        cdp = await page.context.new_cdp_session(page)

        await cdp.send(
            "Network.enable",
            {
                "maxTotalBufferSize": 100 * 1024 * 1024,
                "maxResourceBufferSize": 10 * 1024 * 1024,
            },
        )

        responses: dict[str, dict[str, Any]] = {}

        def on_response(event: dict[str, Any]) -> None:
            response = event["response"]
            request_id = event["requestId"]

            responses[request_id] = {
                "url": response["url"],
                "status": response["status"],
                "mime_type": response["mimeType"],
            }

        cdp.on("Network.responseReceived", on_response)

        await page.goto(
            "https://www.baidu.com",
            wait_until="networkidle",
        )

        for request_id, response_info in responses.items():
            mime_type = response_info["mime_type"]

            # 示例中只读取文本类响应
            if not (
                mime_type.startswith("text/")
                or "json" in mime_type
                or "javascript" in mime_type
            ):
                continue

            try:
                body_result = await cdp.send(
                    "Network.getResponseBody",
                    {"requestId": request_id},
                )

                body = body_result["body"]

                if body_result.get("base64Encoded"):
                    body = base64.b64decode(body).decode(
                        "utf-8",
                        errors="replace",
                    )

                print("=" * 80)
                print(response_info["status"], response_info["url"])
                print(body[:500])

            except Exception as exc:
                # 缓存、重定向、流式响应等情况下可能无法读取
                print(
                    "无法获取响应正文：",
                    response_info["url"],
                    exc,
                )

        await browser.close()

asyncio.run(main())