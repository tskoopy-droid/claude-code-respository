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
                    "--disable-gpu"
                ]
            )
            
            context = await browser.new_context()
            page = await context.new_page()

            # 1. Načtení stránky
            await page.goto("https://www.kontrolatachometru.cz/", wait_until="networkidle", timeout=30000)
            await page.fill("#Vin", vin)

            # 2. CAPTCHA obrázek
            captcha_img = await page.wait_for_selector("#CaptchaImage", timeout=10000)
            if not captcha_img:
                await browser.close()
                return {"status": "error", "message": "Element #CaptchaImage nenalezen"}

            screenshot_bytes = await captcha_img.screenshot()
            b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")

            # 3. Odeslání do Anti-Captcha
            task_resp = requests.post("https://api.anti-captcha.com/createTask", json={
                "clientKey": ANTI_CAPTCHA_KEY,
                "task": {
                    "type": "ImageToTextTask",
                    "body": b64_image
                }
            }, timeout=10).json()

            if task_resp.get("errorId") != 0:
                await browser.close()
                return {"status": "error", "message": f"AntiCaptcha error: {task_resp}"}

            task_id = task_resp["taskId"]

            # 4. Čekání na řešení
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

            # 5. Odeslání formuláře
            await page.fill("#Captcha", captcha_text)
            await page.click("#btnSubmit")

            # 6. Vyčtení výsledků
            await page.wait_for_selector("#table-results", timeout=12000)
            table_element = await page.query_selector("#table-results")
            text_content = await table_element.inner_text()
            lines = [line.strip() for line in text_content.split("\n") if line.strip()]

            await browser.close()
            return {"status": "ok", "vin": vin, "data": lines}

    except Exception as e:
        # Vrací přesný popis chyby místo obecné 500
        return {
            "status": "error",
            "exception_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
