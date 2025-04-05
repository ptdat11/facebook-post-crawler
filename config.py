from utils import LinkExtractor
from pipeline import Pipeline, SaveAsCSV, SaveImages, SaveVideos, HandleHrefs
from datetime import datetime

PIPELINE = Pipeline(
    HandleHrefs(action="ignore"),
    # SaveImages(save_dir="{crawler_dir}/{page_id}", img_url_col="img_urls", id_col="post_id"),
    # SaveVideos(save_dir="{crawler_dir}/{page_id}", vid_url_col="video_urls", audio_url_col="video_audio_urls", id_col="post_id"),
    SaveAsCSV(save_dir="{crawler_dir}/{page_id}"),
)

NAVIGATE_LINK_EXTRACTOR = LinkExtractor(allow_regex=r"", deny_regex=r".*")

PARSE_LINK_EXTRACTOR = LinkExtractor(
    allow_regex=r"https://www\.facebook\.com/[^/\s\?]+$", deny_regex=r""
)

CRAWLER_ARGUMENTS = {
    "page_crawler": dict(
        page_id="shynhpremiumhcm",
        post_collect_threshold=2000,
        language="vi",  # ["vi", "en"]
        theme="dark",  # ["light", "dark"]
        max_ram_percentage=0.95, # Should be at least 0.9 for Facebook to autoclean its memory
    ),
    "bank_crawler": dict(
        page_id="PVcomBankFanpage",
        continue_queue=False,
        # post_collect_criterion="post_time",  # ["elapsed_minutes", "n_posts", "post_time"]
        # post_collect_threshold=datetime(year=2024, month=9, day=1),
        post_collect_criterion="n_posts",
        post_collect_threshold=2000,
        language="vi",  # ["vi", "en"]
        theme="dark",  # ["light", "dark"]
        max_ram_percentage=0.95, # Should be at least 0.9 for Facebook to autoclean its memory
    )
}
