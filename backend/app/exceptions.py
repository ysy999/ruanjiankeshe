from typing import Any


class ChatException(Exception):
    def __init__(self, code: int, msg: str, data: Any = None) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg
        self.data = data
