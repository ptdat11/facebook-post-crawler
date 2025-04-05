from typing import Any, Sequence
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver import Chrome
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

import re
import traceback
import sys
import os
import json
import time
import bs4
import pandas as pd
from pathlib import Path
from ..base_crawler import BaseCrawler
from EC import more_items_loaded, element_attribute_changed
from utils.parsing import parse_post_date, parse_text_from_element, get_video_url_from_source, get_text_from_cmt_bubble, get_id_from_cmt_bubble
from utils.utils import to_bs4, to_etree, ordinal, sha256, tqdm_output, check_unavailable, write_element
from utils.colors import *

from urllib.parse import urlparse, parse_qs
from html import unescape
from datetime import datetime
from typing import Literal
from psutil import virtual_memory
from tqdm import tqdm


class Crawler(BaseCrawler):
    posts_xpath = "(//div[@class='x9f619 x1n2onr6 x1ja2u2z xeuugli xs83m0k xjl7jj x1xmf6yo x1emribx x1e56ztr x1i64zmx x19h7ccj xu9j1y6 x7ep2pv']/div)[last()]/div//div[@class='x1yztbdb x1n2onr6 xh8yej3 x1ja2u2z']"
    anchor_xpath = "((//div[@class='x9f619 x1n2onr6 x1ja2u2z xeuugli xs83m0k xjl7jj x1xmf6yo x1emribx x1e56ztr x1i64zmx x19h7ccj xu9j1y6 x7ep2pv']/div)[last()]/div//div[@class='x1yztbdb x1n2onr6 xh8yej3 x1ja2u2z'])//div[@data-ad-rendering-role='profile_name']/../../../div[2]//a"
    content_on_hover_xpath = "(//div[@class='x78zum5 xdt5ytf x1n2onr6 xat3117 xxzkxad']/div)[2]/div"
    lvl1_comment_xpath = "//div[@class='x1n2onr6 x1ye3gou x1iorvi4 x78zum5 x1q0g3np x1a2a7pz']"
    emoji_src_map = {
        "An-HX414PnqCVzyEq9OFFdayyrdj8c3jnyPbPcierija6hpzsUvw-1VPQ260B2M9EbxgmP7pYlNQSjYAXF782_vnvvpDLxvJQD74bwdWEJ0DhcErkDga6gazZZUYm_Q.png": "like",
        "An8VnwvdkGMXIQcr4C62IqyP-g1O5--yQu9PnL-k4yvIbj8yTSE32ea4ORp0OwFNGEWJbb86MHBaLY-SMvUKdUYJnNFcexEoUGoVzcVd50SaAIzBE-K5dxR8Y-MJn5E.png": "love",
        "An-POmkU-_NNTTsdRMlBuMNo0AY4ErdT38vLDNtGKtUSrILEfybR2XqG2yRrfGfN1vBl3SAsfomCLcWikp72R2ay__g5C5Ufwb-77V2qflOKGqve2111p7Pu_qihMMCw.png": "angry",
        "An95QHaxAbMTp2SyUXLpDATL4RVXaXWyMMPZdhhNbQvXSEtO4mBobyhl440IsX6aUdwySIdlo5h4V7oqQ3FNgrsS1ZCe5rj7-534rtBlVLAm3GMjBK9wsB53peUgOw.png": "care",
        "An-r5ENfro_aq4TtchBwMAVpq461_uMMZX8CbykXeZm3K5tLEtYF2nA1Pcw8d0sbbq0OlIGksDIXALp3ar6dWf5LBjKs9OFlVqQY0wT42aI9jmUG62LKClEYB7Msj7Q.png": "wow",
        "An8jKAygX0kuKnUS351UNmsULZ5k4-fMTFmFHmO7SrQJO1CWNfvoTzEEAr5ZjSoZJRjncZcWMCU1B4of5Vw7bMygV5NmjoeSdthAyQVsakIDduXmYDseOeVRf40MOA.png": "haha",
        "An855a_dxeehKWf2PSOqZw5jG_X5jD0RtPu4XCOJEiUkOgEjN08FocslKz_Ex-1X4l2nyxwET8fM7vQtp4UWea1ndn808NC5OXHaPll4vMdgaoE8ttu-hOlUSetdVjU.png": "sad",
    }

    class PostCollectCriterion:
        def __init__(
            self,
            criterion: Literal["elapsed_minutes", "n_posts", "post_time"],
            threshold: float | int | datetime,
        ) -> None:
            self.criterion = criterion
            self.threshold = threshold
            self.reset()

        def reset(self):
            if self.criterion == "elapsed_minutes":
                self.start = datetime.now()
                self.progress = 0.0
            elif self.criterion == "n_posts":
                self.progress = 0
            elif self.criterion == "post_time":
                self.progress = datetime.now()

        def update_progress(self, driver: Chrome):
            if self.criterion == "elapsed_minutes":
                self.progress = (datetime.now() - self.start).total_seconds() / 60
            elif self.criterion == "n_posts":
                self.progress = len(driver.find_elements(By.XPATH, Crawler.posts_xpath))
            elif self.criterion == "post_time":
                datetime_div = driver.find_element(
                    By.XPATH, Crawler.content_on_hover_xpath
                )
                last_post_datetime_a = driver.find_element(
                    By.XPATH,
                    f"(({Crawler.posts_xpath})[last()]//h2/../../../../div)[2]//a",
                )
                self.action.move_to_element(last_post_datetime_a).perform()
                self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "(//div[@class='x78zum5 xdt5ytf x1n2onr6 xat3117 xxzkxad']/div)[2]/div/div"))
                )
                soup = to_bs4(datetime_div)
                raw_datetime = soup.text
                self.progress = parse_post_date(raw_datetime, lang=self.language)

        def condition_met(self):
            if self.criterion == "elapsed_minutes":
                return self.progress >= self.threshold
            elif self.criterion == "n_posts":
                return self.progress >= self.threshold
            elif self.criterion == "post_time":
                return self.progress <= self.threshold

    def __init__(
        self,
        page_id: str,
        post_collect_threshold: float | int | datetime,
        post_collect_criterion: Literal[
            "elapsed_minutes", "n_posts", "post_time"
        ] = "n_posts",
        continue_queue: bool = False,
        max_ram_percentage: float = 0.95,
        language: Literal["vi", "en"] = "vi",
        theme: Literal["light", "dark"] = "light",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs, name="Page Crawler")

        self.post_collect_criteria = Crawler.PostCollectCriterion(
            criterion=post_collect_criterion,
            threshold=post_collect_threshold,
        )
        self.max_ram_percentage = max_ram_percentage
        self.page_id = page_id
        self.continue_queue = continue_queue
        self.pagename = None
        self.language = language
        self.theme = theme
        self.set_pipeline_path_format(page_id=page_id)
        # self.queue_file_path = Path(self.crawler_dir) / self.page_id / "queue_posts.txt"
        self.remaining_urls_path = Path(f"{self.crawler_dir}/{self.page_id}/remaining_posts.json")


    def on_parse_error(self):
        self.post_collect_criteria.reset()

    def get_loaded_posts(self, start: int = 1, stop: int = -1):
        if stop < 0:
            stop = f"last(){stop}"
        return self.chrome.find_elements(By.XPATH, f"({Crawler.posts_xpath})[position() >= {start} and position() <= {stop}]")

    def scroll_to_load_more(self):
        self.chrome.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        self.wait.until(
            more_items_loaded(
                posts_locator=(By.XPATH, Crawler.posts_xpath),
                current_count=len(self.get_loaded_posts()),
            ),
            message="No more post loaded"
        )
        self.post_collect_criteria.update_progress(self.chrome)

    def parse(self):
        self.pagename = self.chrome.find_element(By.XPATH, "//h1").text.strip()
        self.remove([
            "(//div[@class='x9f619 x1n2onr6 x1ja2u2z x78zum5 xdt5ytf xeuugli x1r8uery x1iyjqo2 xs83m0k x1swvt13 x1pi30zi xqdwrps x16i7wwg x1y5dvz6'])[3]",
            "//div[@role='banner']",
            "//div[@class='x9f619 x1ja2u2z x1xzczws x7wzq59']"
        ])
        if os.path.exists(self.remaining_urls_path):
            self.logger.info("Found post URLs previously saved")
            with open(self.remaining_urls_path) as f:
                post_urls = json.load(f)
        else:
            post_urls = {}
            cover_photo_text = {"vi": re.compile(r"đã cập nhật ảnh bìa của họ\.$"), "en": re.compile(r" updated their cover photo\.$")}
            n_scraped_posts = 0
            current_post_idx = 1
            crashed = False

            with tqdm_output(tqdm(total=round(virtual_memory().total / 1024**3, ndigits=2), desc="RAM Usage (GB)")) as bar:
                # Scroll though page's feed
                self.chrome.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                while (ram_usage := virtual_memory()).percent / 100 < self.max_ram_percentage \
                        and not (met := self.post_collect_criteria.condition_met()) \
                        and not crashed:
                    bar.n = round(ram_usage.percent * ram_usage.total / 100 / 1024**3, ndigits=2)
                    bar.refresh()
                    
                    self.wait.until(
                        more_items_loaded(
                            posts_locator=(By.XPATH, Crawler.posts_xpath),
                            current_count=len(self.get_loaded_posts()),
                        ),
                        message="No more post loaded"
                    )
                    self.post_collect_criteria.update_progress(self.chrome)

                    post_div = self.get_loaded_posts(start=1, stop=1)[0]
                    post = None
                    scraped = False
                    self.scroll_into_view(post_div)

                    try:
                        # Check if reel
                        if to_bs4(post_div).find("a")["href"].startswith("/reel"):
                            self.logger.info(f"Found {ordinal(current_post_idx)} post as reel, skipping...")

                        # Check if update avatar
                        elif to_bs4(post_div).find("img", {"data-imgperflogname": "feedCoverPhoto"}):
                            self.logger.info(f"Found {ordinal(current_post_idx)} post as avatar, skipping...")

                        # Check if update cover photo
                        elif to_bs4(post_div).find("h2").find(string=cover_photo_text[self.language]):
                            self.logger.info(f"Found {ordinal(current_post_idx)} post as cover photo, skipping...")
                            
                        # Normal post
                        else:
                            post = self.parse_post(post_div)
                            scraped = True
                    except Exception as e:
                        exc_type, value, tb = sys.exc_info()
                        self.logger.warning(f"Skipping {ordinal(current_post_idx)} post: {red(exc_type.__name__)}: {value}\n{traceback.format_exc()}")

                        if str(e).startswith("Message: tab crashed"):
                            crashed = True
                        continue
                    finally:
                        current_post_idx += 1
                        try:
                            # Remove post div from HTML
                            self.remove_element(post_div.find_element(By.XPATH, "./../.."))
                            self.clean_memory()
                        except: 
                            crashed = True
                            break

                    # Return result
                    if post:
                        yield post
                        if post["num_comments"] != 0:
                            post_urls[post["post_id"]] = post["post_url"]
                    # Continue looping
                    n_scraped_posts += scraped
                    bar.set_postfix_str(f"Scraped: {n_scraped_posts}")

            if met:
                self.logger.info(f"Post collect stopping criteria has met with threshold of {self.post_collect_criteria.threshold}")

            self.start_driver()
            self.on_start()
            self.ensure_logged_in()

        yield []
        self.collect_comments_step(post_urls)
        # self.pagename = self.chrome.find_element(By.XPATH, "//h1").text.strip()
        # self.remove_header()

        # post_urls = self.collect_post_urls()

        # try:
        #     while post_urls:
        #         url = post_urls.pop()
        #         self.chrome.close()
        #         self.chrome.switch_to.window(self.chrome.window_handles[-1])
        #         self.new_tab(url)
        #         self.wait_DOM()
        #         yield self.parse_post()
        #         self.sleep()
        # except:
        #     os.makedirs(Path(self.crawler_dir) / self.page_id, exist_ok=True)
        #     with open(self.queue_file_path, "w+") as f:
        #         f.write("\n".join(post_urls))

        # if self.post_collect_criteria.condition_met():
        #     self.logger.info(
        #         f"Post collect stopping criteria has met with threshold of {self.post_collect_criteria.threshold}"
        #     )

    def scroll_step(self):
        post_urls = {}
        cover_photo_text = {"vi": re.compile(r"đã cập nhật ảnh bìa của họ\.$"), "en": re.compile(r" updated their cover photo\.$")}
        n_scraped_posts = 0
        current_post_idx = 1
        crashed = False

        with tqdm_output(tqdm(total=round(virtual_memory().total / 1024**3, ndigits=2), desc="RAM Usage (GB)")) as bar:
            # Scroll though page's feed
            self.chrome.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            while (ram_usage := virtual_memory()).percent / 100 < self.max_ram_percentage \
                    and not (met := self.post_collect_criteria.condition_met()) \
                    and not crashed:
                bar.n = round(ram_usage.percent * ram_usage.total / 100 / 1024**3, ndigits=2)
                bar.refresh()
                
                self.wait.until(
                    more_items_loaded(
                        posts_locator=(By.XPATH, Crawler.posts_xpath),
                        current_count=len(self.get_loaded_posts()),
                    ),
                    message="No more post loaded"
                )
                self.post_collect_criteria.update_progress(self.chrome)

                for post_div in self.get_loaded_posts(start=1, stop=1):
                    post = None
                    scraped = False
                    self.scroll_into_view(post_div)

                    try:
                        # Check if reel
                        if to_bs4(post_div).find("a")["href"].startswith("/reel"):
                            self.logger.info(f"Found {ordinal(current_post_idx)} post as reel, skipping...")

                        # Check if update avatar
                        elif to_bs4(post_div).find("img", {"data-imgperflogname": "feedCoverPhoto"}):
                            self.logger.info(f"Found {ordinal(current_post_idx)} post as avatar, skipping...")

                        # Check if update cover photo
                        elif to_bs4(post_div).find("h2").find(string=cover_photo_text[self.language]):
                            self.logger.info(f"Found {ordinal(current_post_idx)} post as cover photo, skipping...")
                            
                        # Normal post
                        else:
                            post = self.parse_post(post_div)
                            scraped = True
                    except Exception as e:
                        exc_type, value, tb = sys.exc_info()
                        self.logger.warning(f"Skipping {ordinal(current_post_idx)} post: {red(exc_type.__name__)}: {value}\n{traceback.format_exc()}")
                        if str(e).startswith("Message: tab crashed"):
                            crashed = True
                        continue

                    current_post_idx += 1
                    try:
                        self.remove_element(post_div.find_element(By.XPATH, "./../.."))
                        self.clean_memory()
                    except: 
                        crashed = True
                        break

                    # Return result
                    if post:
                        yield post
                        if post["num_comments"] != 0:
                            post_urls[post["post_id"]] = post["post_url"]
                    # Continue looping
                    n_scraped_posts += scraped
                    bar.set_postfix_str(f"Scraped: {n_scraped_posts}")

        if met:
            self.logger.info(f"Post collect stopping criteria has met with threshold of {self.post_collect_criteria.threshold}")

    def collect_comments_step(self, post_urls: dict[str, str]):
        self.logger.info(f"Begin to collect comments from {len(post_urls)} posts.")
        with tqdm_output(tqdm(total=len(post_urls), desc="Collecting Comments", unit="post")) as bar:
            comment_csv_path = f"{self.crawler_dir}/{self.page_id}/comments.csv"
            try:
                while post_urls:
                    id, url = tuple(post_urls.items())[0]
                    self.chrome.get(url)
                    self.wait_DOM()
                    self.remove([
                        "//div[@role='banner']",
                        "//div[@class='x7wzq59 xxzkxad xh8yej3 xzkaem6']",
                    ])
                    main_div = self.chrome.find_element(By.XPATH, "//div[@role='main']")
                    if (
                        len(to_etree(main_div).xpath("//h2")) > 0
                        and "".join(to_etree(main_div).xpath("//h2//text()")).strip()
                        == "Bạn hiện không xem được nội dung này"
                    ):
                        self.logger.warning(f"Post is no longer available at {url}")
    
                    comments = self.get_comments()
                    cmt_data = pd.DataFrame(comments)
                    cmt_data["post_id"] = id
                    cmt_data.to_csv(
                        comment_csv_path,
                        index=False,
                        mode="a",
                        header=not os.path.exists(comment_csv_path),
                    )

                    post_urls.pop(id)
                    bar.update()
                    self.sleep()
                if os.path.exists(self.remaining_urls_path):
                    os.remove(self.remaining_urls_path)
            finally:
                with open(self.remaining_urls_path, "w+") as f:
                    json.dump(post_urls, f, indent=2)

                # exc_type, value, tb = sys.exc_info()
                # self.logger.error(f"Saving remaining post URLs at {self.remaining_urls_path} due to error {red(exc_type.__name__): {value}\n{traceback.format_exc()}}")

    def on_parse_complete(self, data):
        if data:
            data["pagename"] = self.pagename
        return data

    def remove(self, remove_xpaths: list[str]):
        for rm_xpath in remove_xpaths:
            if to_etree(self.chrome.find_element(By.TAG_NAME, "body")).xpath(rm_xpath):
                to_be_removed = self.chrome.find_element(By.XPATH, rm_xpath)
                self.remove_element(to_be_removed)

    def parse_post(self, post_div: WebElement):
        hover_content_div = self.chrome.find_element(By.XPATH, Crawler.content_on_hover_xpath)

        post_content_divs = post_div.find_element(
            By.XPATH, "./descendant::div[@class='html-div xdj266r x11i5rnm xat24cr x1mh8g0r xexx8yu x4uap5 x18d9i69 xkhd6sd']"
        ).find_elements(By.XPATH, f"./div/div/div")

        # Get profile div
        profile_div = post_div.find_element(By.XPATH, "./descendant::div[@data-ad-rendering-role='profile_name']")

        # Get content (caption + image/video) div
        content_div = post_content_divs[2]
        text_content_div = content_div.find_elements(By.XPATH, "./descendant::div[@data-ad-rendering-role='story_message']")
        text_content_div = text_content_div[0] if text_content_div else None

        # Get comment, share div
        interaction_div = post_content_divs[3].find_element(By.XPATH, "./descendant::div[@class='x1n2onr6']/div")
        reaction_div = interaction_div.find_element(By.XPATH, "./div/div")
        cmt_share_div = interaction_div.find_element(By.XPATH, "(./div)[last()]")

        num_comments, num_shares = 0, 0
        if to_bs4(cmt_share_div).find_all("div", {"role": "button"}):
            for btn in cmt_share_div.find_elements(By.XPATH, "./descendant::div[@role='button']"):
                btn_text_match = re.search(r"^([\d,]+K?) (.+)$", btn.text)
                count, btn_text = btn_text_match.group(1), btn_text_match.group(2)
                comment_text = {"vi": "bình luận", "en": "comments"}
                share_text = {"vi": "lượt chia sẻ", "en": "shares"}
                if btn_text == comment_text[self.language]:
                    num_comments = count
                elif btn_text == share_text[self.language]:
                    num_shares = count

        # Get reaction counts
        total_reactions = reaction_div.find_element(By.XPATH, ".//span[@class='xrbpyxo x6ikm8r x10wlt62 xlyipyv x1exxlbk']").text
        # self.action.click(reaction_div).pause(1).perform()
        # reaction_modal = self.chrome.find_element(By.XPATH, "//div[@role='dialog']")
        # reaction_counts = reaction_modal.find_elements(By.XPATH, "./descendant::div[@class='x1swvt13 x1pi30zi']/descendant::div[@class='x6ikm8r x10wlt62 xlshs6z']/div")
        # modal_close = reaction_modal.find_element(By.XPATH, "./descendant::div[@class='x1d52u69 xktsk01']/div")
        # reactions = {r: 0 for src, r in Crawler.emoji_src_map.items()}
        # for _reaction in reaction_counts:
        #     all_reaction_text = {"vi": "Tất cả", "en": "All"}
        #     if (text := to_bs4(_reaction.find_element(By.XPATH, ".//span")).text) == all_reaction_text[self.language]:
        #         continue
        #     icon_src = _reaction.find_element(By.XPATH, ".//img").get_attribute("src")
        #     icon_src = re.search(r"/t6/([^\.]+\.png)\?", icon_src).group(1)
        #     count = text
        #     reactions[Crawler.emoji_src_map[icon_src]] = count
        # modal_close.click()

        # Ensure post's text content showing full version
        see_more_text = {"vi": "Xem thêm", "en": "See more"}
        if to_bs4(content_div).find("div", attrs={"role": "button"}, string=see_more_text[self.language]):
            show_more_btn = content_div.find_element(By.XPATH, f"./descendant::div[@role='button' and text()='{see_more_text[self.language]}']")
            self.action.move_to_element(show_more_btn).click(show_more_btn).pause(0.1).move_to_element(post_div).perform()

        # Get post's datetime a element
        post_datetime_a = profile_div.find_element(By.XPATH, "(../../../div)[2]//a")
        self.scroll_into_view(post_datetime_a, pause=0.2)
        WebDriverWait(self.chrome, 5).until(
            EC.presence_of_element_located((By.XPATH, f"{Crawler.content_on_hover_xpath}/descendant::div[contains(@class, '__fb-light-mode')]"))
        )
        datetime_soup = to_bs4(hover_content_div.find_element(By.XPATH, "./div[@class='__fb-light-mode'][last()]"))
        self.chrome.execute_script(f"document.querySelector('div.x78zum5.xdt5ytf.x1n2onr6.xat3117.xxzkxad>div:nth-of-type(2)>div>div.__fb-light-mode').remove()")
        raw_datetime = datetime_soup.text
        post_datetime = parse_post_date(raw_datetime, lang=self.language)

        # Get post's raw URL
        post_datetime_a = profile_div.find_element(By.XPATH, "(../../../div)[2]//a")
        post_raw_url = post_datetime_a.get_attribute("href")
        # Get post's ID
        post_id = Path(urlparse(post_raw_url).path).name
        # Get post's link
        post_link = f"https://www.facebook.com/{post_id}"

        # Get post's caption
        caption = (
            parse_text_from_element(text_content_div)
            if text_content_div
            else ""
        )
        caption = unescape(re.sub(r"href\(, [^\)]+\)", "", caption).strip())

        result = {
            "post_id": sha256(post_id),
            "post_url": post_link,
            "post_datetime": post_datetime,
            "crawl_time": datetime.now(),
            "caption": caption,
            "num_comments": num_comments,
            "num_shares": num_shares,
            "num_reactions": total_reactions,
        }
        # result.update(reactions)
        return result

    def get_comments(self):
        comments = {
            "comment_id": [],
            "comment_text": []
        }
        if self.page_source_soup().find("span", {"class": "x193iq5w xeuugli x13faqbe x1vvkbs x10flsy6 x1lliihq x1s928wv xhkezso x1gmr53x x1cpjm7i x1fgarty x1943h6x x4zkp8e x41vudc x6prxxf xvq8zen xo1l8bm x1fey0fg"}):
            self.chrome.find_element(By.XPATH, "//span[@class='x193iq5w xeuugli x13faqbe x1vvkbs x10flsy6 x1lliihq x1s928wv xhkezso x1gmr53x x1cpjm7i x1fgarty x1943h6x x4zkp8e x41vudc x6prxxf xvq8zen xo1l8bm x1fey0fg']").click()

        self.show_all_comments()
        self.sleep(0.5)

        while not self.load_all_lvl1_cmts():
            break

        n_comments = len(self.chrome.find_elements(By.XPATH, Crawler.lvl1_comment_xpath))
        for i in range(1, n_comments+1):
            cmt_bubble = self.chrome.find_element(By.XPATH, f"({Crawler.lvl1_comment_xpath})[{i}]")
            id = get_id_from_cmt_bubble(cmt_bubble)
            text = get_text_from_cmt_bubble(cmt_bubble, lang=self.language)

            if text != "":
                comments["comment_id"].append(id)
                comments["comment_text"].append(text)

        return comments
    
    def show_all_comments(self):
        if not self.page_source_soup().find("div", {"class": "x6s0dn4 x78zum5 xdj266r x11i5rnm xat24cr x1mh8g0r xe0p6wg"}):
            return

        cmt_show_mode_btn = self.chrome.find_element(By.XPATH, "//div[@class='x6s0dn4 x78zum5 xdj266r x11i5rnm xat24cr x1mh8g0r xe0p6wg']/div")
        self.click(cmt_show_mode_btn)
        show_all_btn = self.chrome.find_element(By.XPATH, "(//div[@role='menuitem'])[last()]")
        self.click(show_all_btn)
    
    def load_all_lvl1_cmts(self):
        current_n_cmts = len(self.chrome.find_elements(By.XPATH, Crawler.lvl1_comment_xpath))
        if current_n_cmts == 0:
            return False
        
        last_comment = self.chrome.find_element(By.XPATH, f"({Crawler.lvl1_comment_xpath})[last()]")
        comments_section = last_comment.find_element(By.XPATH, "./../../../..")
        self.chrome.execute_script("arguments[0].scrollIntoView(true);", last_comment)
        # self.scroll_into_view(last_comment)
        if to_bs4(comments_section).find("div", {"class": "x1i10hfl xjbqb8w xjqpnuy xa49m3k xqeqjp1 x2hbi6w x13fuv20 xu3j5b3 x1q0q8m5 x26u7qi x972fbf xcfux6l x1qhh985 xm0m39n x9f619 x1ypdohk xdl72j9 xe8uvvx xdj266r x11i5rnm xat24cr x1mh8g0r x2lwn1j xeuugli xexx8yu x18d9i69 xkhd6sd x1n2onr6 x16tdsg8 x1hl2dhg xggy1nq x1ja2u2z x1t137rt x1o1ewxj x3x9cwd x1e5q0jg x13rtm0m x3nfvp2 x87ps6o x1lku1pv x1a2a7pz x6s0dn4 xi81zsa x1q0g3np x1iyjqo2 xs83m0k xsyo7zv"}):
            load_more_btn = comments_section.find_element(By.XPATH, ".//div[@class='x1i10hfl xjbqb8w xjqpnuy xa49m3k xqeqjp1 x2hbi6w x13fuv20 xu3j5b3 x1q0q8m5 x26u7qi x972fbf xcfux6l x1qhh985 xm0m39n x9f619 x1ypdohk xdl72j9 xe8uvvx xdj266r x11i5rnm xat24cr x1mh8g0r x2lwn1j xeuugli xexx8yu x18d9i69 xkhd6sd x1n2onr6 x16tdsg8 x1hl2dhg xggy1nq x1ja2u2z x1t137rt x1o1ewxj x3x9cwd x1e5q0jg x13rtm0m x3nfvp2 x87ps6o x1lku1pv x1a2a7pz x6s0dn4 xi81zsa x1q0g3np x1iyjqo2 xs83m0k xsyo7zv']")
            self.chrome.execute_script("arguments[0].scrollIntoView(true);", load_more_btn)
            load_more_btn.click()

        try:
            WebDriverWait(self.chrome, 2).until(
                more_items_loaded(
                    posts_locator=(By.XPATH, Crawler.lvl1_comment_xpath),
                    current_count=current_n_cmts,
                ),
                message="No more comment loaded"
            )
            return False
        except:
            return True
            
    def start(self):
        super().start(start_url=f"https://www.facebook.com/{self.page_id}")
