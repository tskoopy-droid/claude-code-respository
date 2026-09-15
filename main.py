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
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = await context.new_page()

            await page.goto("https://www.kontrolatachometru.cz/", wait_until="networkidle", timeout=30000)

            # 1. Vyplnění VIN
            await page.wait_for_selector("#VIN", timeout=15000)
            await page.fill("#VIN", vin)

            # 2. Zachycení CAPTCHA obrázku
            captcha_img = await page.wait_for_selector("#captcha_IMG, #CaptchaImage, img[src*='Captcha']", timeout=10000)
            if not captcha_img:
                await browser.close()
                return {"status": "error", "message": "Element CAPTCHA obrázku nenalezen"}

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

            # 4. Vyplnění CAPTCHA a potvrdit stiskem Enter i klikem
            await page.fill("#captcha_TB_I", captcha_text)
            await page.press("#captcha_TB_I", "Enter")
            await page.click("#btnSubmit")

            # 5. Vyčkání na výstupní tabulku nebo odchycení chyby
            try:
                await page.wait_for_selector("#table-results, table.table, .result-table", timeout=15000)
            except Exception:
                body_text = await page.inner_text("body")
                # Zkrácení obsahu na podstatný text bez bílých znaků
                clean_text = " ".join(body_text.split())
                await browser.close()
                return {
                    "status": "error",
                    "message": f"Tabulka nenalezena. Reakce webu: '{clean_text[:300]}...'"
                }

            table_element = await page.query_selector("#table-results, table.table, .result-table")
            text_content = await table_element.inner_text()
            lines = [line.strip() for line in text_content.split("\n") if line.strip()]

            await browser.close()
            return {"status": "ok", "vin": vin, "data": lines}

    except Exception as e:
        return {
            "status": "error",
            "exception_type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
