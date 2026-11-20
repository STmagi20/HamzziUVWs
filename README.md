<p align="center">
  <img src="docs/images/Ham_Body_UV.png" alt="Hamzzi UV Toolkit" width="240">
</p>

<h1 align="center">Hamzzi UV Toolkit</h1>

<p align="center">이미 펼친 UV를 정리하는 Blender 애드온</p>

<p align="center"><b>한국어</b> | <a href="README.en.md">English</a> | <a href="README.ja.md">日本語</a></p>

이미 펼쳐 둔 UV를 손보는 도구 모음입니다. 아일랜드 정렬과 타일 배치, 이음선 붙이기, 늘어진 UV 풀기, 텍셀 밀도 맞추기를 사이드바 버튼으로 할 수 있습니다. UV를 새로 펼치는 기능은 없습니다.

- Blender 4.2 이상 (5.2에서 테스트했고, 그 아래 버전에서는 실행해 보지 않았습니다)
- 제작: StudyingHamzzi
- 자세한 사용법: [사용 가이드](docs/GUIDE.md) ([English](docs/GUIDE.en.md), [日本語](docs/GUIDE.ja.md))

## 화면

메시를 Edit Mode로 두면 3D 뷰포트와 UV 에디터의 사이드바(N 키)에 **Hamzzi UV Toolkit** 탭이 나타납니다.

<table>
  <tr>
    <td valign="top"><img src="docs/images/sidebar.png" alt="Hamzzi UV Toolkit 사이드바" width="250"></td>
    <td valign="top"><img src="docs/images/pack.png" alt="Pack into Tile 전후" width="620"><br><sub>Pack into Tile 한 번으로 흩어진 아일랜드를 타일 안에 모은 모습</sub></td>
  </tr>
</table>

## 기능

| 패널 | 할 수 있는 일 |
|---|---|
| Align Islands | 아일랜드를 가장자리나 가운데에 맞춤 (기준: 선택 영역 또는 0–1 타일) |
| Distribute / Sort | 간격을 고르게 분배, 3D 위치 순서대로 한 줄(또는 한 열)에 나열 |
| Tile / Pack | UDIM 타일로 이동, 타일 안에 줄 맞춰 자동 배치 (Margin, Scale to Fit) |
| Transform | 회전(90°, 180°, 원하는 각도), 뒤집기, 자동 방향 맞춤, 선택 엣지를 축에 맞춤, U·V 배율 조정, UV가 뒤집힌 면을 빨간색으로 표시 |
| Texel Density | 밀도 측정, 목표값 적용, 평균으로 통일, 활성 면의 밀도에 맞춤 |
| UV Vertices | 선택한 UV 정점의 정렬, 균등 분배, 엣지 한 줄 직선으로 펴기 (Straighten) |
| Stitch | 선택한 UV 엣지를 이웃 아일랜드의 같은 엣지에 붙임. 두 엣지의 모양이 달라도 끝점을 맞춰 붙임. Detach Selected는 반대로 선택한 엣지를 따라 아일랜드를 가름 |
| Unstretch | 늘어난 UV를 3D 표면의 비율에 가깝게 다시 계산, 스트레치 표시 켜고 끄기 |
| Connected Edges | 선택한 점·선·면이 다른 아일랜드의 어디로 이어지는지 파란색으로 표시 |

## 설치

1. 저장소의 **Releases**에서 `HamzziUVToolkit.zip`을 받습니다. 압축은 풀지 않습니다.
2. Blender에서 Edit → Preferences → Get Extensions를 엽니다.
3. 오른쪽 위 화살표 메뉴에서 **Install from Disk**를 고르고 받은 zip을 선택합니다.
4. 설치가 끝나면 애드온이 켜져 있는지 확인합니다.

> 초록색 Code 버튼의 Download ZIP은 저장소 전체라서 그대로는 설치되지 않습니다. 애드온 본체는 `HamzziUVToolkit/` 폴더입니다.

<table>
  <tr>
    <td><img src="docs/images/Ham_Body_UV_UP.png" alt="UPDATE" width="130"></td>
    <td valign="middle"><b>업데이트할 때</b>는 새 zip을 같은 방법으로 설치합니다. 패널이 예전 모습 그대로면 Blender를 다시 시작하세요.</td>
  </tr>
</table>

## 빠른 시작

1. 메시를 선택하고 Tab 키로 Edit Mode에 들어갑니다.
2. UV 에디터를 열고 N 키로 사이드바를 연 뒤 **Hamzzi UV Toolkit** 탭을 누릅니다.
3. 아일랜드 도구는 선택한 아일랜드에 적용되고, 아무것도 선택하지 않으면 보이는 아일랜드 전체에 적용됩니다. 실행한 도구는 Ctrl+Z로 되돌릴 수 있습니다.

예를 들어 흩어진 아일랜드를 정리하려면 **Tile / Pack**에서 U 0, V 0을 확인하고 **Pack into Tile**을 누릅니다. 나머지 도구의 사용법과 작업 예시는 [사용 가이드](docs/GUIDE.md)에 적어 두었습니다.

## 알려진 한계

- Stitch는 선택한 엣지에만 동작하며, 가까운 엣지를 자동으로 찾아 붙이지는 않습니다.
- Unstretch는 브러시가 아니라 선택 영역에 한 번에 적용됩니다.
- 구처럼 평평하게 펼 수 없는 형태를 억지로 펴는 기능은 없습니다.
- Pack into Tile은 아일랜드의 경계 상자를 기준으로 배치하고 회전하지 않습니다. 복잡한 모양을 빈틈없이 끼워 넣으려면 Blender의 Pack Islands가 더 촘촘하게 배치합니다.
- Connected Edges는 Edit Mode의 면이 Face Limit(기본 1만 개)을 넘으면 표시를 건너뛰고, UV 에디터에 안내 문구를 띄웁니다.
- 패널의 버튼 이름은 영어입니다.

## 버그와 문의

궁금한 점, 버그, 바라는 기능은 [Issues](https://github.com/STmagi20/HamzziUVWs/issues)에 남겨 주세요. 버그라면 Blender 버전, 어떤 버튼을 눌렀을 때 일어났는지, 화면에 뜬 경고 문구를 함께 적어 주시면 확인하기 쉽습니다. 자세한 안내는 [사용 가이드](docs/GUIDE.md#버그와-문의)에 있습니다.

## 개발

애드온에 쓰이는 파일은 모두 `HamzziUVToolkit/` 폴더에 있습니다.

| 경로 | 내용 |
|---|---|
| `HamzziUVToolkit/__init__.py` | 등록·해제 |
| `HamzziUVToolkit/blender_manifest.toml` | 확장 정보와 버전 |
| `HamzziUVToolkit/info.py` | 이름, 제작자, 버전 |
| `HamzziUVToolkit/icons.py`, `HamzziUVToolkit/images/` | 패널 이름 앞의 작은 로고(`logo.png`)와 About의 전신 그림(`mascot.png`). 없어도 애드온은 동작합니다 |
| `HamzziUVToolkit/core.py` | UV 데이터 접근: 편집 오브젝트, 선택 판정, 아일랜드 |
| `HamzziUVToolkit/properties.py` | 패널에 보이는 설정값 |
| `HamzziUVToolkit/operators/` | 도구별 연산자 (`islands`, `density`, `elements`, `stitch`, `relax`) |
| `HamzziUVToolkit/overlay.py` | UV 에디터의 연결 엣지와 뒤집힌 면 표시 |
| `HamzziUVToolkit/ui.py` | 사이드바 패널 |
| `HamzziUVToolkit/menus.py` | UV 메뉴 항목과 Stitch, Detach의 빈 단축키 자리 |
| `README.en.md`, `README.ja.md` | 이 README의 영어판과 일본어판 |
| `docs/GUIDE.md`, `docs/GUIDE.en.md`, `docs/GUIDE.ja.md`, `docs/images/` | 사용 가이드와 그림 (설치용 zip에는 들어가지 않음) |
| `tests/` | 자동 테스트 (설치용 zip에는 들어가지 않음) |

버전은 `blender_manifest.toml`에만 적습니다. 패널에 보이는 버전은 이 파일에서 읽어 옵니다.

테스트는 백그라운드 Blender로 실행합니다. 모두 통과하면 종료 코드가 0입니다. 파일 이름 일부(예: `orient`)를 `--` 뒤에 적으면 그 테스트만 돌립니다.

```bash
blender --background --factory-startup --python tests/run_tests.py
```

백그라운드에는 UV 에디터가 없어서 Relax의 실제 동작과 화면 표시는 테스트가 확인하지 못합니다. 이 둘은 UV 에디터를 연 Blender에서 직접 확인하세요.

설치용 zip은 커밋한 뒤 아래 명령으로 만듭니다. zip 최상위에 `blender_manifest.toml`이 오도록 폴더 내용만 묶습니다.

```bash
git archive --format=zip -o HamzziUVToolkit.zip HEAD:HamzziUVToolkit
```

## 라이선스

GPL-3.0-or-later. 전문은 [LICENSE](LICENSE)에 있습니다.

Copyright (C) 2026 StudyingHamzzi
