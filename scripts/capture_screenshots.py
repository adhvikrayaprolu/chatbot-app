"""Refresh README screenshots from a running app with a ready document and local models.

    .venv/bin/python scripts/capture_screenshots.py --url http://127.0.0.1:5000 \
        --document "GPU Study Notes (original demo)" --question "Can a barrier synchronize separate blocks?"
"""
import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('--url', default='http://127.0.0.1:5000')
parser.add_argument('--document', required=True, help='library title to select as the source')
parser.add_argument('--question', required=True)
parser.add_argument('--method', default='Agent')
args = parser.parse_args()
out = Path(__file__).resolve().parents[1] / 'docs'

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1360, 'height': 860}, device_scale_factor=2, color_scheme='light')
    page.goto(args.url)
    page.get_by_role('combobox').select_option(label=args.document)
    page.get_by_role('radio', name=args.method).click()
    page.get_by_label('Message').fill(args.question)
    page.get_by_label('Message').press('Enter')
    answer = page.locator('.message.assistant').last
    expect(answer.locator('.stats')).to_be_visible(timeout=180_000)
    answer.locator('.trace').evaluate('el => el.open = true')
    page.screenshot(path=out / 'screenshot-desktop.png')
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=out / 'screenshot-mobile.png')
    browser.close()
print('Wrote', out / 'screenshot-desktop.png', 'and', out / 'screenshot-mobile.png')
