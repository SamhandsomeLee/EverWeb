from turtle import title
from playwright.sync_api import sync_playwright

def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)

        context = browser.new_context()
        page = context.new_page()

        cdp = context.new_cdp_session(page)

        cdp.send("Network.enable")

        def on_request(event:dict)->None:
            request = event["request"]

            print(
                request["method"],
                request["url"],
            )

        cdp.on(
            "Network.requestWillBeSent",
            on_request,
        )

        page.goto("https://www.baidu.com")

        result = cdp.send(
            "Runtime.evaluate",
            {"expression": "document.title",
            "returnByValue": True,
            },
        )

        title = result["result"]["value"]
        print(f"Page title: {title}")

        cdp.detach()

        browser.close()

if __name__ == "__main__":
    main()