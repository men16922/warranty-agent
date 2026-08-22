"""배포 계획을 렌더한다 — 값은 전부 `warranty.config`에서 온다.

Spec: specs/warranty/design/10-deployment.md §2, §5 (REQ-602, REQ-805)

⛔ **이 도구는 아무것도 배포하지 않는다.** `gcloud`를 부르지도, 네트워크를 열지도 않는다.
   문자열을 찍을 뿐이고, 그것을 실행하는 것은 `scripts/deploy.sh`이며 **사람이** 부른다.
⚠️ 이 파일이 존재하는 이유는 편의가 아니라 **출처**다. 셸이 플래그를 직접 적으면
   서비스명·리전·`min-instances`가 코드 밖에 두 번째 사본으로 살게 되고, 그 사본은
   배포가 성공할 때까지 아무도 안 읽는다. 게이트가 그 어긋남을 대신 묻는다
   (tests/test_deploy_artifacts.py).
"""

from __future__ import annotations

import argparse
import sys

from warranty.config import ConfigError, deploy_argv, image_uri, load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="배포 계획을 렌더한다 (배포는 안 한다)")
    parser.add_argument("--tag", required=True, help="이미지 태그. `latest`를 쓰지 않는다")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--image", action="store_true", help="이미지 주소 한 줄")
    mode.add_argument("--args", action="store_true", help="gcloud 인자, 한 줄에 하나")
    ns = parser.parse_args(argv)

    try:
        settings = load_settings()
        # ⚠️ 한 줄에 하나로 찍는 이유: 셸이 공백으로 다시 쪼개면 라벨·환경변수처럼
        #    쉼표와 등호가 든 인자에서 조용히 갈라진다.
        lines = [image_uri(settings, ns.tag)] if ns.image else list(deploy_argv(settings, ns.tag))
    except ConfigError as exc:
        print(f"설정이 성립하지 않는다: {exc}", file=sys.stderr)
        return 2

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
