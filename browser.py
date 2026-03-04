import re
import io
import os
import time
import uuid
import anthropic
import random
import global_settings
from PIL import Image
from rich import print
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from client.gemini import GeminiClient

OPEN_PAGES = { }
llm_client = anthropic.Anthropic(
    api_key=global_settings.anthropic_api_key,
    base_url=global_settings.anthropic_base_url
)
gemini_cli = GeminiClient(global_settings)
playwrite_instance = sync_playwright().start()
browser = playwrite_instance.chromium.launch(headless=False)
context = browser.new_context()

def get_full_html_fixed(page):
    script = """
    () => {
        const serialize = (node) => {
            if (node.nodeType === Node.TEXT_NODE) {
                return node.textContent;
            }
            
            if (node.nodeType !== Node.ELEMENT_NODE && node.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) {
                return "";
            }

            let html = "";
            if (node.nodeType === Node.ELEMENT_NODE) {
                const tagName = node.tagName.toLowerCase();
                const clone = node.cloneNode(false);
                const outer = clone.outerHTML;
                
                const isSelfClosing = /^(area|base|br|col|embed|hr|img|input|link|meta|param|source|track|wbr)$/i.test(tagName);
                
                const tagSplitIndex = outer.indexOf(">") + 1;
                const openingTag = outer.substring(0, tagSplitIndex);
                const closingTag = isSelfClosing ? "" : `</${tagName}>`;

                html += openingTag;
                if (node.shadowRoot) {
                    html += `${serialize(node.shadowRoot)}`;
                }
                for (const child of node.childNodes) {
                    html += serialize(child);
                }
                html += closingTag;
            } 
            else {
                for (const child of node.childNodes) {
                    html += serialize(child);
                }
            }
            return html;
        };
        return "<!DOCTYPE html>" + serialize(document.documentElement);
    }
    """
    return page.evaluate(script)

def open_url(url, workdir):
    page = context.new_page()
    stealth = Stealth()
    stealth.apply_stealth_sync(page)

    page.goto(url)
    time.sleep(5)

    page_id = str(uuid.uuid4())
    page_content = get_full_html_fixed(page)
    cleaned_content = strip_attributes_keep_structure(page_content)
    # print(page_content)
    # print('\n\n\n')
    # print(cleaned_content)
    # print('\n\n\n')

    file_path = f"{workdir}tmp/{page_id}-rawhtml.html" if workdir.endswith('/') else f"{workdir}/tmp/{page_id}-rawhtml.html"
    full_path = os.path.expanduser(file_path)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(page_content)
    file_path2 = f"{workdir}tmp/{page_id}-cleanedhtml.html" if workdir.endswith('/') else f"{workdir}/tmp/{page_id}-cleanedhtml.html"
    full_path2 = os.path.expanduser(file_path2)
    with open(full_path2, "w", encoding="utf-8") as f:
        f.write(cleaned_content)

    OPEN_PAGES[page_id] = {
        "page_id": page_id,
        "page": page,
        "url": url,
        "browser": browser,
        "raw_content": page_content,
        "cleaned_content": cleaned_content
    }
    return page_id, file_path, file_path2

def summarize_page(page_id):
    page_info = OPEN_PAGES.get(page_id)
    if not page_info:
        return "Page not found"
    if page_info.get("summary") is not None:
        return page_info["summary"]
    
    content = page_info["cleaned_content"]
    message = llm_client.messages.create(
        model=global_settings.anthropic_model,
        max_tokens=1024,
        system=f"""Summarize the following web page content in a concise manner, focusing on the main points and key information. 
        The summary should be informative and capture the essence of the page without unnecessary details.  
        If sign in or login elements are detected in the content, please include that in the summary as well.
        If downloads are detected in the content, please include specific urls in the summary as well.
        If somthing blocked by not login, adice user use the login tool to login.
        """,
        messages=[{
            "role": "user",
            "content": [ { "type": "text", "text": content } ]
        }]
    )
    for block in message.content:
        if block.type == "text":
            page_info["summary"] = block.text
            return block.text
    return "Failed to summarize page content"

def get_page_info(page_id):
    page_info = OPEN_PAGES.get(page_id)
    if not page_info:
        return None
    
    return {
        "page_id": page_info["page_id"],
        "url": page_info["url"],
        "summary": page_info["summary"]
    }

def list_open_pages():
    return OPEN_PAGES.values()

def close_page(page_id):
    page_info = OPEN_PAGES.get(page_id)
    if not page_info:
        return False
    
    driver = page_info["driver"]
    driver.quit()
    del OPEN_PAGES[page_id]
    return True

# =================================================================
# download related functions
# =================================================================

import requests
from pathlib import Path
from urllib.parse import urlparse, unquote

def is_valid_filename(filename):
    pattern = r'^[^<>:"/\\|?*\x00-\x1f]+\.[a-zA-Z]+$'
    return bool(re.match(pattern, filename))

def extract_filename_from_url(url, headers):
    encoded_name = Path(urlparse(url).path).name
    filename = unquote(encoded_name)
    if is_valid_filename(filename):
        return filename
    cd = headers.get('content-disposition')
    if cd:
        fname = re.findall('filename="(.+)"', cd)
        if len(fname) > 0: 
            return fname[0]
    return None

def download_file(url, save_folder, file_name):
    with requests.get(url, stream=True) as r:
        if r.status_code == 200:
            save_path = save_folder + file_name if save_folder.endswith('/') else save_folder + '/' + file_name
            with open(Path(save_path).expanduser(), 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"[green]File downloaded successfully and saved to {save_path}[/green]")
            return f'File downloaded successfully and saved to {save_path}'
        if r.status_code == 404:
            print(f"[red]File not found at {url}[/red]")
            return f"Error: File not found at {url}"
        if r.status_code == 401 or r.status_code == 403:
            print(f"[red]Unauthorized access to {url}. Status code: {r.status_code}[/red]")
            return f"Error: Unauthorized access to {url}. Status code: {r.status_code}"
        print(f"[red]Failed to download file from {url}. Status code: {r.status_code}[/red]")
        return f"Error: Failed to download file from {url}. Status code: {r.status_code}"

# =================================================================
# login related functions
# =================================================================

def extract_captcha_text(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    # img.show()
    response = gemini_cli.generate("gemini-2.5-flash", [
        "Identify the text in the following image and return. Do not other things except the text.", img
    ])
    return response

def get_xpath_from_soup_element(element):
    components = []
    child = element
    for parent in child.parents:
        if parent is None:
            break
        siblings = parent.find_all(child.name, recursive=False)
        if len(siblings) > 1:
            index = siblings.index(child) + 1
            components.append(f"{child.name}[{index}]")
        else:
            components.append(child.name)
        child = parent
    components.reverse()
    return "/" + "/".join(components)

def find_login_button(html):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a', href=True):
        if 'login' in a['href'].lower() or 'sign in' in a.get_text().lower():
            return get_xpath_from_soup_element(a)
    for button in soup.find_all('button'):
        if 'login' in button.get_text().lower() or 'sign in' in button.get_text().lower():
            return get_xpath_from_soup_element(button)
    return None

def human_input(page, selector, text, paste=False):
    element = page.locator(selector)
    box = element.bounding_box()

    offset_x = box['width'] * random.uniform(0.2, 0.8) if box else 0
    offset_y = box['height'] * random.uniform(0.2, 0.8) if box else 0
    element.hover(position={'x': offset_x, 'y': offset_y})
    time.sleep(random.uniform(0.3, 0.6))
    element.click(position={'x': offset_x, 'y': offset_y})
    time.sleep(random.uniform(0.1, 0.4))

    offset_x = box['width'] * random.uniform(0.2, 0.8) if box else 0
    offset_y = box['height'] * random.uniform(0.2, 0.8) if box else 0
    element.hover(position={'x': offset_x, 'y': offset_y})
    time.sleep(random.uniform(0.3, 0.6))
    element.click(position={'x': offset_x, 'y': offset_y})
    time.sleep(random.uniform(0.1, 0.4))

    if paste:
        page.evaluate(f"navigator.clipboard.writeText('{text}')")
        modifier = "Meta" if "Mac" in page.evaluate("navigator.platform") else "Control"
        page.keyboard.press(f"{modifier}+V")
    else:
        for t in text:
            element.type(t)
            time.sleep(random.uniform(0.2, 0.4))
    return True

def human_click(button):
    box = button.bounding_box()
    offset_x = box['width'] * random.uniform(0.2, 0.8) if box else 0
    offset_y = box['height'] * random.uniform(0.2, 0.8) if box else 0
    button.hover(position={'x': offset_x, 'y': offset_y})
    time.sleep(random.uniform(0.3, 0.6))

    offset_x = box['width'] * random.uniform(0.2, 0.8) if box else 0
    offset_y = box['height'] * random.uniform(0.2, 0.8) if box else 0
    button.hover(position={'x': offset_x, 'y': offset_y})
    time.sleep(random.uniform(0.3, 0.6))

    button.click(position={'x': offset_x, 'y': offset_y})
    time.sleep(random.uniform(0.1, 0.4))

def input_username(page, username):
    if page.locator('#email').count() > 0:
        return human_input(page, '#email', username)
    elif page.locator('#username').count() > 0:
        return human_input(page, '#username', username)
    elif page.locator('input[type="email"]').count() > 0:
        return human_input(page, 'input[type="email"]', username)
    elif page.locator('input[autocomplete="email"]').count() > 0:
        return human_input(page, 'input[autocomplete="email"]', username)
    elif page.locator('input[autocomplete="username"]').count() > 0:
        return human_input(page, 'input[autocomplete="username"]', username)
    return False
    
def input_password(page, password):
    if page.locator('#password').count() > 0:
        return human_input(page, '#password', password)
    elif page.locator('input[type="password"]').count() > 0:
        return human_input(page, 'input[type="password"]', password)
    elif page.locator('input[autocomplete="current-password"]').count() > 0:
        return human_input(page, 'input[autocomplete="current-password"]', password)
    elif page.locator('input[autocomplete="new-password"]').count() > 0:
        return human_input(page, 'input[autocomplete="new-password"]', password)
    return False

def input_captcha(page):
    all_imgs = page.locator("img")
    captcha_element = None
    for i in range(all_imgs.count()):
        img = all_imgs.nth(i)
        alt_text = img.get_attribute("alt") or ""
        src_text = img.get_attribute("src") or ""
        id_text = img.get_attribute("id") or ""

        if "captcha" in src_text.lower() or "captcha" in alt_text or "captcha" in id_text.lower():
            captcha_element = img
            break
    if captcha_element is None:
        return True

    img_bytes = captcha_element.screenshot()
    captcha_text = extract_captcha_text(img_bytes).replace(" ", "").replace("-", "")
    print(f"[yellow]Extracted captcha text: {captcha_text}[/yellow]")

    if page.locator('#captcha').count() > 0:
        return human_input(page, '#captcha', captcha_text)
    elif page.locator('input[name="captcha"]').count() > 0:
        return human_input(page, 'input[name="captcha"]', captcha_text)
    elif page.locator('input[id*="captcha"]').count() > 0:
        return human_input(page, 'input[id*="captcha"]', captcha_text)
    return False

def click_submit(page):
    all_buttons = page.locator('button[type="submit"]')
    for i in range(all_buttons.count()):
        button = all_buttons.nth(i)
        text = button.text_content() or ""
        if button.is_visible() and 'submit' in text.lower() or 'login' in text.lower() or 'sign in' in text.lower():
            human_click(button)
            return True
    return False

def login_page(page_id):
    page_info = OPEN_PAGES.get(page_id)
    if not page_info:
        print(f"[red]Page with ID {page_id} not found.[/red]")
        return False, "Page not found"
    
    html = page_info["raw_content"]
    login_xpath = find_login_button(html)
    if not login_xpath:
        print(f"[red]Login button not found on page {page_id}.[/red]")
        return False, "Login button not found"
    
    print(f"[yellow]Found login button at XPath: {login_xpath}[/yellow]")
    page = page_info["page"]
    page.locator('xpath=' + login_xpath).click()
    time.sleep(random.uniform(5, 10))
    # time.sleep(30)

    try:
        username = input("Enter username for login: ")
        password = input("Enter password for login: ")

        input_username(page, username)
        time.sleep(random.uniform(1, 4))
        input_password(page, password)
        time.sleep(random.uniform(1, 4))
        input_captcha(page)
        time.sleep(random.uniform(1, 4))
        click_submit(page)

        # human_input(page, '#email', username, paste=True)
        # time.sleep(random.uniform(1, 4))
        # human_input(page, '#password', password, paste=True)
        # time.sleep(random.uniform(1, 4))
        # captcha_img = page.locator('#captchaImg')
        # img_bytes =captcha_img.screenshot()
        # captcha_text = extract_captcha_text(img_bytes)
        # print(f"[yellow]Extracted captcha text: {captcha_text}[/yellow]")
        # human_input(page, '#captcha', captcha_text)
        # time.sleep(random.uniform(1, 4))
        # human_click(page.locator('#emailButton'))

        time.sleep(10)
        print(f"[green]Login successful for page {page_id}.[/green]")
        return True, "Login successful"
    except Exception as e:
        print(f"[red]Login failed for page {page_id}. Error: {str(e)}[/red]")
        return False, f"Login failed: {str(e)}"

def strip_attributes_keep_structure(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    target_root = soup

    for useless in target_root(["script", "style", "svg", "noscript", "footer", "head"]):
        useless.decompose()
    
    for tag in target_root.find_all(True):
        if tag.name == 'a' and 'href' in tag.attrs:
            tag.attrs = {'href': tag.attrs['href']}
        elif tag.name == 'img' and 'src' in tag.attrs:
            tag.attrs = {'src': tag.attrs['src']}
        else:
            tag.attrs = {}

    text = target_root.decode_contents()
    return re.sub(r'\s+', ' ', text)

# =================================================================
import trafilatura
import html2text

def clean_html_basic(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    for element in soup(["script", "style", "header", "footer", "nav"]):
        element.decompose()
    text = soup.get_text(separator='\n')
    lines = (line.strip() for line in text.splitlines())
    return '\n'.join(chunk for chunk in lines if chunk)

def extract_readable_text(html_content):
    result = trafilatura.extract(html_content)
    return result

def html_to_markdown(html_content):
    h = html2text.HTML2Text()
    h.ignore_links = False 
    h.ignore_images = True
    return h.handle(html_content)
