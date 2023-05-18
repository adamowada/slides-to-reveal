import asyncio
import os
import re

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


class_number = ""
images_name_list = []


async def main():
    print("What is the class slides link?")
    print("- For example: 'https://docs.google.com/presentation/d/1OpUvVVCkp44f7vQcO-g2eml5s3gF85L2QIoth1zluBQ'")
    slide_link = input("> ")
    print("What is the 2 digit class number?")
    global class_number
    class_number = input("> ")
    print("\nProcessing...\n")
    async with async_playwright() as playwright:
        content = await parse_slide_deck(playwright, slide_link)
        with open("slides/slides.md", "w") as f:
            f.write(content)
            print("Success!")


async def parse_slide_deck(playwright, slide_link):
    # Login once. Saves context to ./user_data
    chromium = playwright.chromium
    user_data_dir = "./user_data"
    # browser = await chromium.launch_persistent_context(user_data_dir, headless=False, slow_mo=1000)  # can change to headed for initial login
    browser = await chromium.launch_persistent_context(user_data_dir)  # can change to headed for initial login
    page = await browser.new_page()

    # Get page content for images
    await page.set_viewport_size({"width": 1600, "height": 1200})
    await page.goto(slide_link)
    await page.click("#grid-view-icon")  # important to get all slide thumbnails loaded

    # Scroll to bottom of page
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    content = await page.content()

    # Download the images
    parse_images(content)

    # Get page content for text
    await page.goto(f"{slide_link}/htmlpresent")
    content = await page.content()
    soup = BeautifulSoup(content, features="html.parser")
    md = ""
    for idx, slide in enumerate(soup.find_all(role="article")):
        split = False

        # Set element class
        if slide.contents[0].find_all('li'):
            md += '<!-- .element class="split-screen dark" -->\n<div>\n\n'
            split = True

        else:
            md += '<!-- .element class="main-title" -->\n'

        # Build the md
        for div in slide.contents[0]:
            md += convert_html_to_revealjs(div)

        if split:
            md += '\n</div>\n'

        # Add image if there
        if images_name_list[idx]:  # images exist
            for image in images_name_list[idx]:
                md += f"\n![Image]({image})\n"  # add accessibility later

        # Add notes if there
        if len(slide.contents) > 1:
            md += "\nNOTE:\n"
            md += convert_html_to_revealjs(slide.contents[1])

        md += "\n---\n\n"  # new slide break

    # Clean with regex
    md = re.sub('[�’​]', lambda x: ' ' if x.group() == '�' or x.group() == '​' else "'", md)

    # Remove last 3 lines (the last --- )
    md = md.split("\n")
    md = md[:-3]
    md = "\n".join(md)

    return md


def parse_images(content):
    soup = BeautifulSoup(content, features="html.parser")
    images_list = []
    filmstrip_list = soup.find_all(class_="punch-filmstrip-thumbnail")
    for slide in filmstrip_list:
        slide_images = []
        for image in slide.find_all("image"):
            if image["height"] == "576" and image["width"] == "1024":
                continue
            slide_images.append(image["xlink:href"])
        images_list.append(slide_images)

    # make folders
    if not os.path.exists("slides"):
        os.makedirs("slides")
    if not os.path.exists("slides/assets"):
        os.makedirs("slides/assets")

    # make requests and download images with slide_index-image_index.png format
    for slide_num, images in enumerate(images_list):
        global images_name_list
        images_name_list.append([])  # holds strings of image path names for use in slides
        if not images:
            continue
        for image_num, url in enumerate(images):
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(f"slides/assets/{slide_num}_{image_num}.png", 'wb') as out_file:
                    out_file.write(response.content)
                    images_name_list[slide_num].append(f"/ops-201-guide/curriculum/class-{class_number}/slides/assets/{slide_num}_{image_num}.png")  # save file name in correct spot


def process_ul(ul, tab):
    md = ""
    for element in ul.find_all(['li', 'ul'], recursive=False):  # Process each direct child li
        if element.name == 'li':
            md += f"{tab * ' '}- {element.text}\n"
        if element.name == 'ul':
            md += process_ul(element, tab+2)
    return md


def convert_html_to_revealjs(slide):
    # create a markdown version of the slide
    md = ""
    for element in slide.find_all(lambda tag: tag.name in ['p', 'ul'] or 'slide-notes' in tag.get('class', []), recursive=False):
        if element.name == 'ul':
            md += process_ul(element, 0)
        elif element.name == 'p':
            style = element.get('style')  # get the style attribute
            if style:
                style_dict = dict(item.split(":") for item in style.split(";") if item)  # create a dictionary from the style string
                if 'font-weight' in style_dict and style_dict['font-weight'].strip() == '700':  # h1 element
                    md += f"# {element.text}\n\n"
                else:  # not h1 element
                    md += f"{element.text}\n"
        elif 'slide-notes' in element.get('class', []):
            md += "\nNOTE:\n"

    return md


if __name__ == "__main__":
    asyncio.run(main())
