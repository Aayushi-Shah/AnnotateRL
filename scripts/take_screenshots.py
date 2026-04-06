"""
Take screenshots of AnnotateRL for the README.
Usage: python3 scripts/take_screenshots.py
Requires: pip install playwright && playwright install chromium
"""

import asyncio
import os
import sys
from pathlib import Path

BASE_URL = "http://localhost:3000"
API_URL = "http://localhost:8000"
OUT_DIR = Path(__file__).parent.parent / "docs" / "screenshots"

RESEARCHER = {"email": "alice@annotaterl.dev", "password": "researcher123"}
ANNOTATOR = {"email": "carol@annotaterl.dev", "password": "annotator123"}

VIEWPORT = {"width": 1440, "height": 900}


async def login(page, creds):
    await page.goto(f"{BASE_URL}/login", wait_until="networkidle")
    await page.fill('input[type="email"]', creds["email"])
    await page.fill('input[type="password"]', creds["password"])
    await page.click('button[type="submit"]')
    await page.wait_for_url(lambda url: "/login" not in url, timeout=10000)
    await page.wait_for_load_state("networkidle")


async def screenshot(page, path, full_page=False):
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(800)  # let charts/animations settle
    await page.screenshot(path=str(OUT_DIR / path), full_page=full_page)
    print(f"  ✓  {path}")


async def main():
    from playwright.async_api import async_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Saving screenshots to {OUT_DIR}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # ── 1. Login page ──────────────────────────────────────────────
        page = await browser.new_page(viewport=VIEWPORT)
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        await page.wait_for_timeout(500)
        await screenshot(page, "login.png")

        # ── 2–5. Researcher pages ──────────────────────────────────────
        await login(page, RESEARCHER)

        # Dashboard
        await page.goto(f"{BASE_URL}/researcher/dashboard", wait_until="networkidle")
        await screenshot(page, "researcher-dashboard.png")

        # Tasks list
        await page.goto(f"{BASE_URL}/researcher/tasks", wait_until="networkidle")
        await screenshot(page, "tasks-list.png")

        # Task detail — grab first task id from the page
        await page.goto(f"{BASE_URL}/researcher/tasks", wait_until="networkidle")
        await page.wait_for_timeout(500)
        task_links = await page.query_selector_all('a[href^="/researcher/tasks/"]')
        if task_links:
            href = await task_links[0].get_attribute("href")
            await page.goto(f"{BASE_URL}{href}", wait_until="networkidle")
            await screenshot(page, "task-detail.png")
        else:
            print("  ⚠  no tasks found — skipping task-detail.png")

        # Fine-tune page
        await page.goto(f"{BASE_URL}/researcher/finetune", wait_until="networkidle")
        await screenshot(page, "finetune-page.png")

        # Datasets page
        await page.goto(f"{BASE_URL}/researcher/datasets", wait_until="networkidle")
        await screenshot(page, "datasets-page.png")

        # ── 6–7. Annotator pages ───────────────────────────────────────
        annotator_page = await browser.new_page(viewport=VIEWPORT)
        await login(annotator_page, ANNOTATOR)

        # Queue
        await annotator_page.goto(f"{BASE_URL}/annotator/queue", wait_until="networkidle")
        await screenshot(annotator_page, "annotator-queue.png")

        # Claim first available task and screenshot the workspace
        import httpx
        async with httpx.AsyncClient() as client:
            # log in via API to get token
            r = await client.post(f"{API_URL}/auth/login", json=ANNOTATOR)
            if r.status_code == 200:
                token = r.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}
                # get available tasks
                queue = await client.get(f"{API_URL}/queue", headers=headers)
                tasks = queue.json() if queue.status_code == 200 else []
                if tasks:
                    task_id = tasks[0]["id"]
                    claim = await client.post(f"{API_URL}/queue/{task_id}/claim", headers=headers)
                    if claim.status_code == 201:
                        assignment_id = claim.json()["id"]
                        await annotator_page.goto(
                            f"{BASE_URL}/annotator/workspace/{assignment_id}",
                            wait_until="networkidle",
                        )
                        await screenshot(annotator_page, "annotation-workspace.png")
                    else:
                        # try my-tasks
                        my = await client.get(f"{API_URL}/queue/mine", headers=headers)
                        assignments = my.json() if my.status_code == 200 else []
                        in_progress = [a for a in assignments if a.get("status") == "in_progress"]
                        if in_progress:
                            assignment_id = in_progress[0]["id"]
                            await annotator_page.goto(
                                f"{BASE_URL}/annotator/workspace/{assignment_id}",
                                wait_until="networkidle",
                            )
                            await screenshot(annotator_page, "annotation-workspace.png")
                        else:
                            print("  ⚠  no claimable tasks — skipping workspace screenshot")
                else:
                    print("  ⚠  queue empty — skipping workspace screenshot")

        await browser.close()

    print(f"\nDone. {len(list(OUT_DIR.glob('*.png')))} screenshots saved to docs/screenshots/")


if __name__ == "__main__":
    # check httpx available
    try:
        import httpx  # noqa: F401
    except ImportError:
        print("Installing httpx...")
        os.system(f"{sys.executable} -m pip install --break-system-packages httpx")

    asyncio.run(main())
