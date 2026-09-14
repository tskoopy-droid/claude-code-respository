import base64
import asyncio
import traceback
from fastapi import FastAPI
from playwright.async_api import async_playwright
import requests

app = FastAPI()

ANTI_CAPTCHA_KEY = "1f0a6a869b38e9ef3c1c0fd97546d2f4"

@app.get("/")
async def root():
    return {"status": "running"}

@app.get("/stk")
async def get_stk(vin: str):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu"
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="cs-CZ",
                viewport={"width": 1280, "height": 800}
            )

            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = await context.new_page()

            await page.goto("https://www.kontrolatachometru.cz/", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            target_frame = None
            vin_field = None

            for frame in page.frames:
                try:
                    field = await frame.query_selector("#Vin, input[name='Vin'], input[id*='Vin']")
                    if field:
                        target_frame = frame
                        vin_field = field
                        break
                except Exception:
                    pass

            if not vin_field or not target_frame:
                body_html = await page.inner_html("body")
                await browser.close()
                return {
                    "status": "error",
                    "message": "Políčko pro VIN nebylo nalezeno ani v iframech.",
                    "body_snippet": body_html[:500]
                }

            await vin_field.fill(vin)

            captcha_img = await target_frame.wait_for_selector("#CaptchaImage", timeout=10000)
            if not captcha_img:
                await browser.close()
                return {"status": "error", "message": "Element #CaptchaImage nenalezen"}

            screenshot_bytes = await captcha_img.screenshot()
            b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")

            task_resp = requests.post("https://api.anti-captcha.com/createTask", json={
                "clientKey": ANTI_CAPTCHA_KEY,
                "task": {
                    "type": "ImageToTextTask",
                    "body": b64_image
                }
            }, timeout=10).json()

            if task_resp.get("errorId") != 0:
                await browser.close()
                return {"status": "error", "message": f"AntiCaptcha chyba: {task_resp}"}

            task_id = task_resp["taskId"]

            captcha_text = None
            for _ in range(15):
                await asyncio.sleep(2)
                res = requests.post("https://api.anti-captcha.com/getTaskResult", json={
                    "clientKey": ANTI_CAPTCHA_KEY,
                    "taskId": task_id
                }, timeout=10).json()

                if res.get("status") == "ready":
                    captcha_text = res["solution"]["text"]
                    break

            if not captcha_text:
                await browser.close()
                return {"status": "error", "message": "AntiCaptcha timeout"}

            await target_frame.fill("#Captcha", captcha_text)
            await target_frame.click("#btnSubmit")

            await target_frame.wait_for_selector("#table-results", timeout=15000)
            table_element = await target_frame.query_selector("#table-results")
            text_content = await table_element.inner_text()
            lines = [line.strip() for line in text_content.split("\n") if line.strip()]

            await browser.close()
            return {"status": "ok", "vin": vin, "data": lines}
