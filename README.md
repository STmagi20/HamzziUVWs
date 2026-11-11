# UV Edit Toolkit (HamzziUVWs)

이미 펼친 UV를 편집하는 Blender 애드온입니다. 3ds Max Unwrap UVW에서 쓰던 정렬, Stitch, 연결 엣지 표시 같은 기능을 Blender에서 쓸 수 있게 합니다.

- Blender 4.2 이상 (5.2에서 테스트)
- 제작: StudyingHamzzi

## 설치

1. [Releases](https://github.com/STmagi20/HamzziUVWs/releases)에서 최신 `uv_edit_toolkit.zip`을 받습니다. 압축은 풀지 않습니다.
2. Blender에서 Edit → Preferences → Get Extensions를 엽니다.
3. 오른쪽 위 화살표 메뉴에서 Install from Disk를 고르고 받은 zip을 선택합니다.

GitHub의 "Code → Download ZIP"으로 받은 파일은 설치되지 않습니다. 반드시 Releases의 zip을 쓰세요.

## 사용

메시를 Edit Mode로 두면 3D 뷰포트와 UV 에디터 사이드바(N 키)의 **UV Edit** 탭에 패널이 나타납니다. 각 패널은 제목을 눌러 접을 수 있습니다. 아무것도 선택하지 않으면 보이는 아일랜드 전체에 적용됩니다.

| 패널 | 기능 |
|---|---|
| Align Islands | 아일랜드를 좌·우·상·하·중앙으로 정렬 (선택 영역 또는 0–1 타일 기준) |
| Distribute / Tile | 간격 균등·고정 분배, UDIM 타일 이동 |
| Rotate / Flip / Orient | 90°·180°·임의 각도 회전, 뒤집기, 자동 방향 맞춤, 선택 엣지를 축에 맞춤 |
| Texel Density | 밀도 측정, 목표값 적용, 평균으로 통일, 활성 면 기준 맞춤 |
| Scale Islands | 아일랜드별 U·V 배율 스케일 |
| UV Vertices | 선택한 UV 정점 정렬(엣지 펴기)과 균등 분배 |
| Stitch | 선택한 UV 엣지를 이웃 아일랜드의 짝 엣지에 붙임 (Bias, Align, Scale) |
| Unstretch | 선택한 UV만 다시 풀어 왜곡 해소, 스트레치 오버레이 토글 |
| Connected Edges | 선택한 점·선·면이 다른 아일랜드의 어디로 이어지는지 파란색으로 표시 |

### 텍셀 밀도

- **Texture Size**는 px/m 단위 환산에만 쓰이며 UV를 움직이지 않습니다.
- 스포이드 버튼은 현재 밀도를 측정해 Target에 채웁니다.
- **Equalize**는 선택한 아일랜드를 평균 밀도로 통일합니다.
- 아일랜드는 제자리에서 크기만 바뀌므로 서로 겹칠 수 있습니다.

## 알려진 한계

- Stitch는 엣지 단위만 지원하며 정점 용접은 하지 않습니다.
- Unstretch는 브러시가 아니라 선택 영역에 한 번에 적용됩니다.
- Connected Edges는 Edit Mode의 면이 Face Limit(기본 5만 개)을 넘으면 표시를 건너뜁니다.

## 개발

설치용 zip은 저장소에 포함하지 않습니다. 직접 만들려면:

```bash
python build_zip.py
```
