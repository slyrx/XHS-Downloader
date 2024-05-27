import re
from asyncio import gather
from pathlib import Path

from aiohttp import ClientError

from source.module import ERROR
from source.module import Manager
from source.module import logging
from source.module import retry as re_download

__all__ = ['Download']


class Download:
    CONTENT_TYPE_MAP = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "application/octet-stream": "",
        "video/quicktime": "mov",
    }

    def __init__(self, manager: Manager, ):
        self.manager = manager
        self.folder = manager.folder
        self.temp = manager.temp
        self.proxy = manager.proxy
        self.chunk = manager.chunk
        self.session = manager.download_session
        self.retry = manager.retry
        self.prompt = manager.prompt
        self.folder_mode = manager.folder_mode
        self.video_format = "mp4"
        self.image_format = manager.image_format

    async def run(self, urls: list, index: list | tuple | None, workId: str, name: str, type_: str, log, bar) -> tuple[Path, tuple]:
        path = self.__generate_path(workId, name)
        match type_:
            case "视频":
                tasks = self.__ready_download_video(urls, path, name, log)
            case "图文":
                tasks = self.__ready_download_image(
                    urls, index, path, name, log)
            case _:
                raise ValueError
        tasks = [
            self.__download(
                url,
                path,
                name,
                format_,
                log,
                bar) for url,
            name,
            format_ in tasks]
        result = await gather(*tasks)
        return path, result

    def __generate_path(self, work_id: str, name: str):
        path = self.manager.archive(self.folder.joinpath(work_id), name, self.folder_mode)
        path.mkdir(exist_ok=True)
        return path

    def __ready_download_video(
            self,
            urls: list[str],
            path: Path,
            name: str,
            log) -> list:
        if any(path.glob(f"{name}.*")):
            logging(log, self.prompt.skip_download(name))
            return []
        return [(urls[0], name, self.video_format)]

    def __ready_download_image(
            self,
            urls: list[str],
            index: list | tuple | None,
            path: Path,
            name: str,
            log) -> list:
        tasks = []
        for i, j in enumerate(urls, start=1):
            if index and i not in index:
                continue
            # 使用正则表达式提取 / 和 ? 之间的内容
            match = re.search(r'ci.xiaohongshu.com/(.*?)(\?)', j)
            extracted_content = ""
            if match:
                extracted_content = match.group(1)
            file = f"{name}_{extracted_content}_{i}"
            if any(path.glob(f"{file}.*")):
                logging(log, self.prompt.skip_download(file))
                continue
            tasks.append([j, file, self.image_format])
        return tasks

    @re_download
    async def __download(self, url: str, path: Path, name: str, format_: str, log, bar):
        try:
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
            async with self.session.get(url, proxy=self.proxy, headers=headers, verify_ssl=False) as response: # , verify_ssl=False
                if response.status != 200:
                    return False
                suffix = self.__extract_type(
                    response.headers.get("Content-Type")) or format_
                print(name)
                temp = self.temp.joinpath(name)
                real = path.joinpath(f"{name}.{suffix}")
                logging(log, self.prompt.download_success(path))
                # self.__create_progress(
                #     bar, int(
                #         response.headers.get(
                #             'content-length', 0)) or None)
                with temp.open("wb") as f:
                    async for chunk in response.content.iter_chunked(self.chunk):
                        f.write(chunk)
                        # self.__update_progress(bar, len(chunk))
            self.manager.move(temp, real)
            # self.__create_progress(bar, None)
            logging(log, self.prompt.download_success(name))
            # logging(log, real)
            return True
        except ClientError as error:
            try:
                self.manager.delete(temp)
            except UnboundLocalError:
                # 如果捕捉到 UnboundLocalError 错误，则执行以下逻辑
                with open("error_logs.txt", "a") as file:
                    file.write(f"UnboundLocalError occurred: name={name}\n")
            # self.manager.delete(temp)
            # self.__create_progress(bar, None)
            logging(log, str(error), ERROR)
            logging(log, self.prompt.download_error(name), ERROR)
            return False

    @staticmethod
    def __create_progress(bar, total: int | None):
        if bar:
            bar.update(total=total)

    @staticmethod
    def __update_progress(bar, advance: int):
        if bar:
            bar.advance(advance)

    @classmethod
    def __extract_type(cls, content: str) -> str:
        return cls.CONTENT_TYPE_MAP.get(content, "")
