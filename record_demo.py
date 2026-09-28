import asyncio
import os
import shutil
import glob
from playwright.async_api import async_playwright

async def record_demo():
    video_dir = "demo_video"
    if os.path.exists(video_dir):
        shutil.rmtree(video_dir)
    os.makedirs(video_dir, exist_ok=True)

    url = "https://smart-pantry-frontend-82502274399.us-west1.run.app"
    print(f"Opening app URL: {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=video_dir,
            record_video_size={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        print("Navigating to page...")
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(2)

        # 1. First Prompt: What's in my pantry?
        print("Clicking first prompt chip: What's in my pantry?")
        chip1 = page.locator("button.chip", has_text="What's in my pantry?")
        if await chip1.count() > 0:
            await chip1.click()
        else:
            await page.fill("#input", "What's in my pantry?")
            await page.click("button[type='submit']")

        # Wait for agent response
        print("Waiting for pantry response...")
        await asyncio.sleep(12)

        # 2. Second Rich Prompt: Generate image of avocado toast
        print("Clicking second prompt chip: Generate image of avocado toast")
        chip2 = page.locator("button.chip", has_text="Generate image of avocado toast")
        if await chip2.count() > 0:
            await chip2.click()
        else:
            await page.fill("#input", "Generate an image of avocado toast")
            await page.click("button[type='submit']")

        print("Waiting for image generation response...")
        await asyncio.sleep(15)

        # Pause to view final result
        await asyncio.sleep(4)

        video_path = await page.video.path()
        print(f"Recorded video saved to: {video_path}")

        await context.close()
        await browser.close()

        # Copy to artifact directory
        artifact_dir = "/config/.gemini/antigravity/brain/0b1ad293-3123-4a72-9c57-514f8e94cf80"
        os.makedirs(artifact_dir, exist_ok=True)
        target_path = os.path.join(artifact_dir, "smart_pantry_demo.webm")
        shutil.copy(video_path, target_path)
        print(f"Copied demo video to artifact directory: {target_path}")

if __name__ == "__main__":
    asyncio.run(record_demo())
