import base64
import time
import requests
from fastapi import FastAPI, HTTPException, Query
from playwright.async_api import async_playwright

app = FastAPI()

ANTI_CAPTCHA_KEY = "VÁŠ_ANTI_CAPTCHA_API_KEY"

def solve_captcha(b64_image: str) -> str:
    create_task_res = requests.post("https://api.anti-captcha.com/createTask", json={
        "clientKey": ANTI_CAPTCHA_KEY,
        "task": {
            "type": "ImageToTextTask",
            "body": b64_image,
            "phrase": False,
            "case": False,
            "numeric": 0,
            "math": False,
            "minLength": 5,
            "maxLength": 5
        }
    }).json()

    if create_task_res.get("errorId") != 0:
        return None

    task_id = create_task_res["taskId"]

    for _ in range(15):
        time.sleep(2)
        check_res = requests.post("https://api.anti-captcha.com/getTaskResult", json={
            "clientKey": ANTI_CAPTCHA_KEY,
            "taskId": task_id
        }).json()

        if check_res.get("status") == "ready":
            return check_res["solution"]["text"]

    return None

@app.get("/stk")
async def fetch_stk(vin: str = Query(..., description="VIN vozidla")):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto("https://www.kontrolatachometru.cz/", wait_until="networkidle")

            captcha_el = await page.wait_for_selector("#captcha_IMG", timeout=10000)
            img_bytes = await captcha_el.screenshot()
            b64_img = base64.b64encode(img_bytes).decode("utf-8")

            captcha_code = solve_captcha(b64_img)
            if not captcha_code:
                await browser.close()
                raise HTTPException(status_code=500, detail="CAPTCHA solving failed")

            await page.fill("input[name='VIN']", vin)
            await page.fill("input[name='captcha$TB']", captcha_code)

            await page.click("input[type='submit'], button[type='submit']")
            await page.wait_for_load_state("networkidle")

            rows = await page.query_selector_all("table tr")
            data = []
            for row in rows:
                cells = await row.query_selector_all("td, th")
                row_text = []
                for cell in cells:
                    t = await cell.inner_text()
                    if t.strip():
                        row_text.append(t.strip())
                if row_text:
                    data.append(" | ".join(row_text))

            await browser.close()
            return {"vin": vin, "data": data}

        except Exception as e:
            await browser.close()
            raise HTTPException(status_code=500, detail=str(e))