import time

from pyperclip import paste
from rich.text import Text
from textual import on
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalScroll
from textual.containers import ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button
from textual.widgets import Footer
from textual.widgets import Header
from textual.widgets import Input
from textual.widgets import Label
from textual.widgets import RichLog

from source.application import XHS
from source.module import (
    PROJECT,
    PROMPT,
    MASTER,
    ERROR,
    WARNING,
    LICENCE,
    REPOSITORY,
    GENERAL,
)
from source.translator import (
    English,
    Chinese,
)

__all__ = ["Index"]


class Index(Screen):
    BINDINGS = [
        Binding(key="q", action="quit", description="退出程序/Quit"),
        Binding(key="u", action="check_update", description="检查更新/Update"),
        Binding(key="s", action="settings", description="程序设置/Settings"),
        Binding(key="r", action="record", description="下载记录/Record"),
        Binding(key="m", action="monitor", description="开启监听/Monitor"),
        # Binding(key="a", action="about", description="关于项目/About"),
    ]

    def __init__(self, app: XHS, language: Chinese | English):
        super().__init__()
        self.xhs = app
        self.prompt = language
        self.url = None
        self.tip = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Label(
                Text(
                    f"{self.prompt.open_source_protocol}{LICENCE}",
                    style=MASTER)
            ),
            Label(
                Text(
                    f"{self.prompt.project_address}{REPOSITORY}",
                    style=MASTER)
            ),
            Label(
                Text(
                    self.prompt.input_box_title,
                    style=PROMPT), classes="prompt",
            ),
            Input(placeholder=self.prompt.input_prompt),
            HorizontalScroll(
                Button(self.prompt.download_button, id="deal"),
                Button(self.prompt.paste_button, id="paste"),
                Button(self.prompt.reset_button, id="reset"),
            ),
        )
        yield RichLog(markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = PROJECT
        self.url = self.query_one(Input)
        self.tip = self.query_one(RichLog)
        self.tip.write(Text("\n".join(self.prompt.disclaimer), style=MASTER))

    @on(Button.Pressed, "#deal")
    async def deal_button(self):
        self.deal()
        # if self.url.value:
        #     self.deal()
        # else:
        #     self.tip.write(Text(self.prompt.invalid_link, style=WARNING))
        #     self.tip.write(Text(">" * 50, style=GENERAL))

    @on(Button.Pressed, "#reset")
    def reset_button(self):
        self.query_one(Input).value = ""

    @on(Button.Pressed, "#paste")
    def paste_button(self):
        self.query_one(Input).value = paste()

    @work()
    async def deal(self):
        await self.app.push_screen("loading")
        # # 按照文件的方式传输地址
        file_path = '/Users/slyrx/Desktop/test_XHS.txt'
        with open(file_path, 'r') as file:
            lines = file.readlines()
            i = 0
            for line in lines:
                if i % 10 == 0:
                    time.sleep(1)
                i = i+1
                if any(await self.xhs.extract(line, True, log=self.tip)): # self.url.value
                    self.url.value = ""
                else:
                    self.tip.write(Text(self.prompt.download_failure, style=ERROR))

        # if any(await self.xhs.extract(self.url.value, True, log=self.tip)): # self.url.value
        #     self.url.value = ""
        # else:
        #     self.tip.write(Text(self.prompt.download_failure, style=ERROR))
        self.tip.write(Text(">" * 50, style=GENERAL))
        self.app.pop_screen()
