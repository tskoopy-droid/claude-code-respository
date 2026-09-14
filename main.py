import base64
import asyncio
from fastapi import FastAPI, HTTPException
from playwright.async_api import async_playwright
import requests

app = FastAPI()

ANTI_CAPTCHA_KEY = "1f0a6a869b38e9ef3c1c0fd97546d2f4"

@app.get("/stk")
async def get_stk(vin: str):
    async with async_playwright() as p:
        # Úsporné parametry pro zamezení pádu na RAM
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu"
            ]
        )
        
        last_error = ""

        try:
            for attempt in range(1, MAX_RETRIES + 1):
                context = await browser.new_context()
                page = await context.new_page()

                try:
                    await page.goto("https://www.kontrolatachometru.cz/", wait_until="domcontentloaded", timeout=20000)
                    await page.fill("#Vin", vin)

                    captcha_img = await page.locator("#CaptchaImage").element_handle()
                    if not captcha_img:
                        raise Exception("Obrázek CAPTCHA nenalezen")
                    
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
                        raise Exception(f"Anti-Captcha chyba: {task_resp.get('errorDescription')}")

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
                        raise Exception("Vypršel časový limit pro vyřešení CAPTCHA")

                    await page.fill("#Captcha", captcha_text)
                    await page.click("#btnSubmit")

                    await page.wait_for_selector("#table-results", timeout=10000)

                    table_element = await page.query_selector("#table-results")
                    text_content = await table_element.inner_text()
                    lines = [line.strip() for line in text_content.split("\n") if line.strip()]

                    await context.close()
                    await browser.close()
                    return {"status": "ok", "vin": vin, "data": lines}

                except Exception as e:
                    last_error = str(e)
                    await context.close()
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(2)

        finally:
            await browser.close()

        raise HTTPException(
            status_code=500, 
            detail=f"Selhalo po {MAX_RETRIES} pokusech: {last_error}"
        )
