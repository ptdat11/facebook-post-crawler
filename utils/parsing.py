from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
import re
from datetime import datetime

from bs4 import BeautifulSoup
from typing import Literal
from utils.utils import unicode_escape_url, write_element, to_bs4

en_month_map = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12
}

def parse_post_date(raw_data: str, lang: Literal["vi", "en"] = "vi"):
    assert lang in ["vi", "en"]
    raw_data = raw_data.lower()
    if lang == "vi":
        raw = re.search(
            r"\d{1,2} tháng \d{1,2}, \d{4} lúc \d{1,2}:\d{1,2}",
            raw_data,
        ).group(0)
        result = datetime.strptime(raw, "%d tháng %m, %Y lúc %H:%M")
    elif lang == "en":
        raw = re.search(
            r"\d{1,2} [^\s]+ \d{4} at \d{1,2}:\d{1,2}",
            raw_data,
        ).group(0)
        raw = re.sub(r"\S+", lambda m: str(en_month_map.get(m.group(), m.group())), raw)
        result = datetime.strptime(raw, "%d %m %Y at %H:%M")
    return result


def parse_text_from_element(text_element: WebElement):
    text = text_element.get_attribute("innerHTML")
    text = re.sub(r"(<img[^>]*alt=\"([^\"]+)\")[^>]*>", r"\2", text)
    text = re.sub(r"<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"href(\2, \1)", text)
    text = re.sub(r"(?<=</div>)()(?=<div)", r"\n", text)
    text = re.sub(r"<.*?>", "", text)
    return text


def get_video_url_from_source(source: str):
    # try:
    h2 = BeautifulSoup(source, "lxml").find("h2")
    if h2 and h2.text == "This content isn't available at the moment":
        return {
            "video_url": "",
            "audio_url": ""
        }

    video_url = re.search(r'"base_url":"([^"]+)"', source).group(1)
    video_url = unicode_escape_url(video_url)
    audio_url = re.search(r'"audio\\/mp4","codecs":"[^"]+","base_url":"([^"]+)"', source)
    if audio_url:
        audio_url = audio_url.group(1)
        audio_url = unicode_escape_url(audio_url)
    else:
        audio_url = "<not_found>"

    return {
        "video_url": video_url,
        "audio_url": audio_url
    }
    # except:
    #     print("ERROR")
    #     with open("index.html", "w") as f:
    #         f.write(source)
    #     return {
    #         "video_url": "",
    #         "audio_url": ""
    #     }

def get_text_from_cmt_bubble(comment_bubble: WebElement, lang: Literal["vi", "en"]):
    see_more_text = {"vi": "Xem thêm", "en": "See more"}
    if to_bs4(comment_bubble).find("div", {"role": "button"}, string=see_more_text[lang]):
        comment_bubble.find_element(By.XPATH, f".//div[@role='button' and text()='{see_more_text[lang]}']").click()

    if not to_bs4(comment_bubble).find("div", attrs={"class": "x1lliihq xjkvuk6 x1iorvi4"}):
        return ""

    text_div = comment_bubble.find_element(By.XPATH, ".//div[@class='x1lliihq xjkvuk6 x1iorvi4']")
    text = parse_text_from_element(text_div)
    return text

def get_id_from_cmt_bubble(comment_bubble: WebElement):
    link_a = comment_bubble.find_element(By.XPATH, ".//div[@class='x6s0dn4 x3nfvp2']//a[@role='link' and @tabindex='0']")
    link = link_a.get_attribute("href")
    id = re.search(r"comment_id=(\d+)", link).group(1)
    return id