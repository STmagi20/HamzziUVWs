# tests

애드온 개발용 자동 테스트입니다. 애드온을 쓰는 데는 필요 없고, 설치용 zip에도 들어 있지 않습니다.
코드를 고친 뒤 기존 기능이 그대로 동작하는지 확인하는 용도입니다.

*Automated tests for developing the add-on. You do not need them to use it, and they are not in the install zip. They check that existing features still work after a code change.*

## 실행

백그라운드 Blender로 실행합니다. 모두 통과하면 종료 코드가 0입니다.

```bash
blender --background --factory-startup --python tests/run_tests.py
```

`--` 뒤에 파일 이름 일부를 적으면 그 테스트만 돌립니다. `orient`는 `test_orient.py`를 뜻합니다.

```bash
blender --background --factory-startup --python tests/run_tests.py -- orient flipped
```

## 구성

| 파일 | 확인하는 것 |
|---|---|
| `test_align.py`, `test_distribute.py`, `test_sort.py` | 아일랜드 정렬, 분배, 나열 |
| `test_tile.py`, `test_pack.py` | 타일 이동과 Pack into Tile |
| `test_transform.py`, `test_orient.py`, `test_flipped.py` | 회전·뒤집기, 방향 맞춤, 뒤집힌 면 |
| `test_density.py` | 텍셀 밀도 |
| `test_stitch.py`, `test_detach.py`, `test_straighten.py` | Stitch, Detach, Straighten |
| `test_relax.py` | Unstretch (UV 에디터가 필요 없는 부분만) |
| `test_overlay.py` | 연결 엣지와 뒤집힌 면 표시 |
| `test_menus.py`, `test_panel_values.py`, `test_no_uv.py` | UV 메뉴와 단축키 자리, 패널 값, UV가 없는 메시 |
| `helpers.py`, `run_tests.py` | 테스트용 공통 함수와 실행기 |

## 한계

백그라운드 Blender에는 UV 에디터가 없어서 Relax의 실제 동작과 화면에 그려지는 모습은 확인하지 못합니다.
이 둘은 UV 에디터를 연 Blender에서 직접 확인하세요.
