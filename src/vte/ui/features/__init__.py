"""기능 라우트 모듈 등록부.

새 기능을 붙일 때: ``features/`` 아래 모듈을 하나 만들고, 그 모듈에
``def register(router, app): @router.get("/api/...") ...`` 형태로 핸들러를
등록한 뒤, 아래 ``FEATURES`` 목록에 한 줄 추가한다. 서버 코어는 손대지 않는다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..server import Router
    from ..app import ExtractionApp

from . import export, media, stream, extraction

FEATURES = (extraction, stream, media, export)


def register_all(router: "Router", app: "ExtractionApp") -> None:
    for feature in FEATURES:
        feature.register(router, app)
