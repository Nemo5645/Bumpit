# Bumpit

UE 5.8 Blueprint pinball prototype. Open `Bumpit/Bumpit.uproject` and play
`/Game/Bumpit/Maps/BumpitCell`.

## 스테이지 진행

- 첫 발사 전에 상점에서 구슬을 구매합니다. 종류를 합쳐 최대 5개이며 구매 순서대로 발사합니다.
- 일반공: 3크레딧. 범퍼 강화공: 5크레딧, 범퍼 충돌 점수만 2배.
- 무거운 공: 4크레딧, 질량 2배·발사 속도 85%. 가벼운 공: 4크레딧, 질량 0.5배·발사 속도 115%. 기본 크기와 점수 규칙은 동일합니다.
- 상점의 5칸은 독립 추첨하며 같은 공이 중복 등장할 수 있습니다. 무료 리롤은 남은 상품만 바꾸며 **구매한 칸은 빈칸으로 유지**됩니다. 다음 스테이지에서만 모든 칸을 다시 채웁니다.
- 분열공: 5크레딧. 발사 레일을 벗어난 뒤 첫 벽/범퍼 반사에서 두 공으로 분열합니다. 바닥 접촉은 제외하며 추가 분열은 없습니다.
- 매 라운드 시작 전 장애물 카드 3개 중 하나를 무료로 선택합니다. 선택한 장애물은 빈 육각 칸에 배치하며, 남은 보관함 재고는 유지됩니다.
- 구슬 1개 구매 = 라운드 1회. 분열된 두 공은 하나의 라운드이며, 두 공의 결과를 합산한 후 종료합니다.
- 구매한 구슬을 전부 사용하면 기존 목표 점수 규칙으로 클리어/실패를 판정합니다.
- 스테이지 클리어 시 철거권 2개를 지급합니다. 미사용 철거권은 누적되며 다음 스테이지 첫 발사 전에만 사용합니다.
- 장애물 위에서 우클릭하면 철거권 1개를 사용해 제거합니다. 철거 시 장애물 재고는 돌려주지 않습니다.
- 첫 발사 이후 해당 스테이지에서는 추가 구매와 수동 철거가 잠깁니다. 장애물은 스테이지 전환 시 자동 파괴되지 않습니다.

SPACE: 충전/발사 및 결과 확인. 1: 테이블, 2: 상점. 기존 WASD 이동과 카메라 조작을 유지합니다.

## 검증

`Bumpit/Tests/ball_progression_playtest.py`는 실제 맵의 PIE GameMode/HUD로
구매 한도, 라운드 선택, 철거권, 특수공 점수 및 실제 충돌 분열을 검증합니다.
에디터를 닫고 `UnrealEditor.exe <project> -ExecutePythonScript=<test> -unattended`
로 실행하면 `Bumpit/Saved/Tests/ball_progression.json`에 결과를 기록하고 종료합니다.

`Bumpit/Tests/weighted_shop_playtest.py`는 중복 등장, 빈칸 유지, 스테이지 재입고,
구매 한도와 질량·발사 속도를 검사하고 `Saved/Tests/weighted_shop.json`에 기록합니다.

`Bumpit/Tools/apply_ball_progression.py`, `apply_special_balls.py`,
`apply_split_and_bumper_balls.py`, `finalize_ball_progression.py`는 movement_fix 원본에
순서대로 적용한 일회성 마이그레이션입니다. 현재 자산에는 이미 반영되어 있으므로
게임 실행 시 이 스크립트를 실행할 필요가 없습니다.
`apply_weighted_ball_shop.py`는 그 이후 적용한 무게 구슬 및 랜덤 상점 마이그레이션입니다.
