import json
import os
from asyncio import Event
from asyncio import Queue
from asyncio import QueueEmpty
from asyncio import gather
from asyncio import sleep
from contextlib import suppress
from re import compile

from pyperclip import paste

from source.expansion import Converter
from source.expansion import Namespace
from source.module import IDRecorder
from source.module import Manager
from source.module import (
    ROOT,
    ERROR,
    WARNING,
)
from source.module import logging
from source.module import wait
from source.translator import (
    LANGUAGE,
    Chinese,
    English,
)
from .download import Download
from .explore import Explore
from .image import Image
from .request import Html
from .video import Video

__all__ = ["XHS"]


class XHS:
    LINK = compile(r"https?://www\.xiaohongshu\.com/explore/[a-z0-9]+")
    SHARE = compile(r"https?://www\.xiaohongshu\.com/discovery/item/[a-z0-9]+")
    SHORT = compile(r"https?://xhslink\.com/[A-Za-z0-9]+")
    __INSTANCE = None

    def __new__(cls, *args, **kwargs):
        if not cls.__INSTANCE:
            cls.__INSTANCE = super().__new__(cls)
        return cls.__INSTANCE

    def __init__(
            self,
            work_path="",
            folder_name="Download",
            user_agent: str = None,
            cookie: str = None,
            proxy: str = None,
            timeout=10,
            chunk=1024 * 1024,
            max_retry=5,
            record_data=False,
            image_format="PNG",
            folder_mode=False,
            language="zh-CN",
            language_object: Chinese | English = None,
    ):
        self.prompt = language_object or LANGUAGE.get(language, Chinese)
        self.manager = Manager(
            ROOT,
            work_path,
            folder_name,
            user_agent,
            chunk,
            cookie,
            proxy,
            timeout,
            max_retry,
            record_data,
            image_format,
            folder_mode,
            self.prompt,
        )
        self.html = Html(self.manager)
        self.image = Image()
        self.video = Video()
        self.explore = Explore()
        self.convert = Converter()
        self.download = Download(self.manager)
        self.recorder = IDRecorder(self.manager)
        self.clipboard_cache: str = ""
        self.queue = Queue()
        self.event = Event()

    def __extract_image(self, container: dict, data: Namespace):
        container["下载地址"] = self.image.get_image_link(
            data, self.manager.image_format)

    def __extract_video(self, container: dict, data: Namespace):
        container["下载地址"] = self.video.get_video_link(data)

    async def __download_files(self, container: dict, folder_name, workId, download: bool, index, log, bar):
        name = self.__naming_rules_image(container)
        folder_name = folder_name.replace("temp/", "")
        # path = self.manager.folder
        path = folder_name
        if (u := container["下载地址"]) and download:
            if await self.skip_download(i := container["作品ID"]):
                logging(log, self.prompt.exist_record(i))
            else:
                path, result = await self.download.run(u, index, workId, name, container["作品类型"], log, bar)
                logging(log, self.prompt.exist_record(workId))
                logging(log, self.prompt.exist_record(path))
                logging(log, self.prompt.exist_record(name))
                await self.__add_record(i, result)
        elif not u:
            logging(log, self.prompt.download_link_error, ERROR)
        self.manager.save_data(path, name, container)

    async def __add_record(self, id_: str, result: tuple) -> None:
        if all(result):
            await self.recorder.add(id_)

    async def extract(self,
                      url: str,
                      download=False,
                      index: list | tuple = None,
                      efficient=False,
                      log=None,
                      bar=None) -> list[dict]:
        # return  # 调试代码
        urls = await self.__extract_links(url, log)
        if not urls:
            logging(log, self.prompt.extract_link_failure, WARNING)
        else:
            logging(log, self.prompt.pending_processing(len(urls)))
        # return urls  # 调试代码
        return [await self.__deal_extract(i, download, index, efficient, log, bar) for i in urls]

    async def extract_cli(self,
                          url: str,
                          download=True,
                          index: list | tuple = None,
                          efficient=True,
                          log=None,
                          bar=None) -> None:
        url = await self.__extract_links(url, log)
        if not url:
            logging(log, self.prompt.extract_link_failure, WARNING)
        else:
            await self.__deal_extract(url[0], download, index, efficient, log, bar)

    async def __extract_links(self, url: str, log) -> list:
        urls = []
        for i in url.split():
            if u := self.SHORT.search(i):
                i = await self.html.request_url(
                    u.group(), False, log)
            if u := self.SHARE.search(i):
                urls.append(u.group())
            elif u := self.LINK.search(i):
                urls.append(u.group())
        return urls

    async def __deal_extract(self, url: str, download: bool, index: list | tuple | None, efficient: bool, log, bar):
        logging(log, self.prompt.start_processing(url))
        headers = {
            'authority': 'www.xiaohongshu.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'cache-control': 'max-age=0',
            'cookie': 'webBuild=4.6.0; xsecappid=xhs-pc-web; a1=18e5591706e3i831y5ay8bg46g4o97ac9msf4y4s930000228368; webId=e0ed34ad22ff5e7f1c093861ad09562f; abRequestId%20=e0ed34ad22ff5e7f1c093861ad09562f; gid=yYd22jyWDWjWyYd22jyW86v4Kdq3Yqyv20vYMMjDk4Kk4iq8ljW0S4888JJYqKY8D08idj0q; abRequestId=e0ed34ad22ff5e7f1c093861ad09562f; web_session=040069b48c5c607eba80f201cf374bc877d5e6; websectiga=59d3ef1e60c4aa37a7df3c23467bd46d7f1da0b1918cf335ee7f2e9e52ac04cf; sec_poison_id=45b45e01-8a87-4ed8-bacc-3c7ef85f6663',
            'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }

        html = await self.html.request_url(url, True, log, headers=headers, verify_ssl=False)
        namespace = self.__generate_data_object(html)
        if not namespace:
            logging(log, self.prompt.get_data_failure(url), ERROR)
            return {}
        await self.__suspend(efficient)
        data = self.explore.run(namespace)
        # logging(log, data)  # 调试代码
        if not data:
            logging(log, self.prompt.extract_data_failure(url), ERROR)
            return {}
        match data["作品类型"]:
            case "视频":
                self.__extract_video(data, namespace)
            case "图文":
                self.__extract_image(data, namespace)
            case _:
                data["下载地址"] = []
        # 创建名为 "A" 的文件夹
        # folder_name =  "/Volumes/My Passport/Download/" + data["作品ID"]
        folder_name =  "/Volumes/Extreme SSD/Download/" + data["作品ID"]
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        # 将数据保存为 JSON 文件
        json_filename = os.path.join(folder_name, "data.json")
        with open(json_filename, "w", encoding="utf-8") as json_file:
            logging(log, json_filename, self.prompt.processing_completed(data["作品ID"]+"_check"))
            json.dump(data, json_file, indent=4, ensure_ascii=False)

        await self.__download_files(data, folder_name, data["作品ID"], download, index, log, bar)
        logging(log, self.prompt.processing_completed(url))
        return data

    def __generate_data_object(self, html: str) -> Namespace:
        data = self.convert.run(html)
        return Namespace(data)

    def __naming_rules(self, data: dict) -> str:
        time_ = data["发布时间"].replace(":", ".")
        author = self.manager.filter_name(data["作者昵称"]) or data["作者ID"]
        title = self.manager.filter_name(data["作品标题"]) or data["作品ID"]
        return f"{time_}_{author}_{title[:64]}"

    def __naming_rules_image(self, data: dict) -> str:
        title = data["作品ID"]
        return f"image_{title[:64]}_"

    async def monitor(self, delay=1, download=False, efficient=False, log=None, bar=None) -> None:
        self.event.clear()
        await gather(self.__push_link(delay), self.__receive_link(delay, download, efficient, log, bar))

    async def __push_link(self, delay: int):
        while not self.event.is_set():
            if (t := paste()).lower() == "close":
                self.stop_monitor()
            elif t != self.clipboard_cache:
                self.clipboard_cache = t
                [await self.queue.put(i) for i in await self.__extract_links(t, None)]
            await sleep(delay)

    async def __receive_link(self, delay: int, *args, **kwargs):
        while not self.event.is_set() or self.queue.qsize() > 0:
            with suppress(QueueEmpty):
                await self.__deal_extract(self.queue.get_nowait(), *args, **kwargs)
            await sleep(delay)

    def stop_monitor(self):
        self.event.set()

    async def skip_download(self, id_: str) -> bool:
        return bool(await self.recorder.select(id_))

    @staticmethod
    async def __suspend(efficient: bool) -> None:
        if efficient:
            return
        await wait()

    async def __aenter__(self):
        await self.recorder.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.recorder.__aexit__(exc_type, exc_value, traceback)
        await self.close()

    async def close(self):
        await self.manager.close()
