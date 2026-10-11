"""VideoTextExtractor local web UI.

표준 라이브러리만 사용하는 로컬 웹 인터페이스다. 서버는 브라우저용 정적
자산과 JSON/SSE API를 제공하고, 추출 파이프라인은 백그라운드 스레드에서
실행되며 진행 상황을 SSE로 스트리밍한다.

모듈 확장 방법
--------------
- 서버 라우트 추가: ``features/`` 아래 모듈을 하나 만들고
  ``register(router, app)`` 안에서 ``@router.get(...)`` 핸들러를 등록한 뒤,
  ``features/__init__.py`` 의 ``FEATURES`` 목록에 추가한다.
- 브라우저 패널 추가: ``static/js/panels/`` 아래 패널을 하나 만들고
  ``static/js/app.js`` 에 import + ``App.register(...)`` 한 줄을 추가한다.
"""

from __future__ import annotations

from .app import ExtractionApp, ExtractionJob
from .server import create_server, run_ui

__all__ = ["ExtractionApp", "ExtractionJob", "create_server", "run_ui"]
