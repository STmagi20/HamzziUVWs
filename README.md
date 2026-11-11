# HamzziUVWs

이미 펼친 UV를 편집하는 Blender 애드온입니다. 3ds Max Unwrap UVW에서 쓰던 정렬, Stitch, 연결 엣지 표시 같은 기능을 Blender에서 쓸 수 있게 합니다.

- Blender 4.2 이상 (5.2에서 테스트)
- 제작: StudyingHamzzi
- 사용법: [docs/GUIDE.md](docs/GUIDE.md)

## 설치

1. 저장소의 **Releases**에서 `HamzziUVWs.zip`을 받습니다. 압축은 풀지 않습니다.
2. Blender에서 Edit → Preferences → Get Extensions를 엽니다.
3. 오른쪽 위 화살표 메뉴에서 Install from Disk를 고르고 받은 zip을 선택합니다.

업데이트할 때도 같은 방법으로 새 zip을 받아 다시 설치하면 됩니다.

> 초록색 Code 버튼의 Download ZIP은 저장소 전체를 담고 있어 그대로 설치할 수 없습니다. 애드온은 `HamzziUVWs/` 폴더 안에 있습니다.

## 기능

메시를 Edit Mode로 두면 3D 뷰포트와 UV 에디터 사이드바(N 키)의 **HamzziUVWs** 탭에 패널이 나타납니다. 자세한 사용법은 [가이드](docs/GUIDE.md)에 있습니다.

| 패널 | 기능 |
|---|---|
| Align Islands | 아일랜드를 좌·우·상·하·중앙으로 정렬 (선택 영역 또는 0–1 타일 기준) |
| Distribute / Tile | 간격 균등·고정 분배, UDIM 타일 이동, 타일 안 자동 배치 |
| Transform | 90°·180°·임의 각도 회전, 뒤집기, 자동 방향 맞춤, 선택 엣지를 축에 맞춤, 아일랜드별 U·V 배율 |
| Texel Density | 밀도 측정, 목표값 적용, 평균으로 통일, 활성 면 기준 맞춤 |
| UV Vertices | 선택한 UV 정점 정렬(엣지 펴기)과 균등 분배 |
| Stitch | 선택한 UV 엣지를 이웃 아일랜드의 짝 엣지에 붙임 (Bias, Align, Scale) |
| Unstretch | 선택한 UV만 다시 풀어 왜곡 해소, 스트레치 오버레이 토글 |
| Connected Edges | 선택한 점·선·면이 다른 아일랜드의 어디로 이어지는지 파란색으로 표시 |
| About | 버전과 제작자 |

## 알려진 한계

- Stitch는 선택한 엣지 단위로만 동작하며, 가까운 엣지를 자동으로 찾아 붙이지는 않습니다.
- Unstretch는 브러시가 아니라 선택 영역에 한 번에 적용됩니다.
- Connected Edges는 Edit Mode의 면이 Face Limit(기본 1만 개)을 넘으면 표시를 건너뜁니다.

## 개발

애드온에 쓰이는 파일은 모두 `HamzziUVWs/` 폴더에 있습니다.

| 경로 | 내용 |
|---|---|
| `HamzziUVWs/__init__.py` | 등록·해제 |
| `HamzziUVWs/blender_manifest.toml` | 확장 정보와 버전 |
| `HamzziUVWs/info.py` | 이름, 제작자, 버전 |
| `HamzziUVWs/icons.py` | 상단 로고 이미지 로드 (`HamzziUVWs/images/logo.png`, 없어도 동작) |
| `HamzziUVWs/core.py` | UV 데이터 접근: 편집 오브젝트, 선택 판정, 아일랜드 |
| `HamzziUVWs/properties.py` | 패널에 보이는 설정값 |
| `HamzziUVWs/operators/` | 도구별 연산자 (`islands`, `density`, `elements`, `stitch`, `relax`) |
| `HamzziUVWs/overlay.py` | UV 에디터의 연결 엣지 표시 |
| `HamzziUVWs/ui.py` | 사이드바 패널 |
| `docs/GUIDE.md` | 사용 가이드 |

버전은 `blender_manifest.toml`에만 적습니다. 패널에 보이는 버전은 이 파일에서 읽어 옵니다.

설치용 zip은 커밋한 뒤 아래 명령으로 만듭니다. zip 최상위에 `blender_manifest.toml`이 오도록 폴더 내용만 묶습니다.

```bash
git archive --format=zip -o HamzziUVWs.zip HEAD:HamzziUVWs
```

## 라이선스

GPL-3.0-or-later. 전문은 [LICENSE](LICENSE)에 있습니다.

Copyright (C) 2026 StudyingHamzzi
