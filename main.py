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

            # Maskování automatizovaného prohlížeče
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            page = await context.new_page()

            # Kompletní načtení stránky
            await page.goto("https://www.kontrolatachometru.cz/", wait_until="load", timeout=30000)
            
            # Vyhledání a vyplnění pola VIN
            try:
                vin_field = await page.wait_for_selector("#Vin, input[name='Vin'], input[id*='Vin']", timeout=15000)
                await vin_field.fill(vin)
            except Exception:
                inputs = await page.eval_on_selector_all("input", "elements => elements.map(e => ({id: e.id, name: e.name, type: e.type}))")
                title = await page.title()
                await browser.close()
                return {
                    "status": "error",
                    "message": f"Formulářové pole pro VIN nebyla nalezena. Titulek: '{title}'",
                    "found_inputs": inputs
                }

            # Získání CAPTCHA
            captcha_img = await page.wait_for_selector("#CaptchaImage", timeout=10000)
            if not captcha_img:
                await browser.close()
                return {"status": "error", "message": "Element #CaptchaImage nenalezen"}

            screenshot_bytes = await captcha_img.screenshot()
            b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")

            # Odeslání do Anti-Captcha
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

            # Čekání na řešení CAPTCHA
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

            # Vyplnění a odeslání
            await page.fill("#Captcha", captcha_text)
            await page.click("#btnSubmit")

            # Načtení výsledků
            await page.wait_for_selector("#table-results", timeout=15000)
            table_element = await page.query_selector("#table-results")
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
