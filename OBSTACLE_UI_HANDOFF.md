# 장애물 선택 / 보유 기물 UI

사용자 제공 `장애물 선택 예시.png`, `보유 기물 예시.png`에 맞춘 Canvas HUD 변경.

## 동작

- 상점은 기존대로 구슬만 구매한다.
- 구슬을 구매하고 테이블에 들어오면 매 라운드 중앙에 무작위 장애물 카드 3장을 표시한다. 하나를 무료로 선택한다.
- 카드에는 종류별 도형, 이름, 효과 설명, 무료 선택 버튼이 있다.
- 선택 시 보관함에 1개 추가되고 창이 닫힌다. 같은 클릭으로 맵에 배치되지 않는다.
- 오른쪽 보관함은 보유 기물 1개당 육각 슬롯 1개를 표시한다. 같은 종류를 여러 개 보유하면 각각 표시한다.
- 슬롯 선택 후 맵의 빈 칸을 클릭하면 기존 EditCell 로직으로 배치 및 수량 차감을 처리한다.
- 페이지당 12개, 이전/다음 버튼 또는 보관함 위에서 휠로 페이지를 이동한다.
- 비행 중에는 기물 선택을 변경할 수 없다. 보관함 영역의 클릭은 맵으로 전달하지 않는다.
- 공 구매 전에는 선택 모달을 띄우지 않아 상점으로 이동할 수 있다.

## 구현 위치

- `/Game/Bumpit/Blueprints/BP_BumpitHUD`
- `DrawBumperSlots`: 기존 우측 세로 카드 대신 보관함과 중앙 모달 렌더링.
- `InventoryPieces`: Stock을 개별 기물 목록으로 펼친 표시용 배열. 재고 원본은 Stock이다.
- `RebuildObstacleInventory`, `FocusObstacleStock`: 목록과 선택/페이지 갱신.
- `HandleObstacleUI`: 중앙 카드 및 육각형의 입력 처리. PointerInput 앞에서 호출하여 소비된 클릭 차단.
- `ObstacleModalOpen`: 준비 단계 + ChoicePending + 남은 구매 구슬 조건.
- `ObstacleUILine`, `ObstacleStroke`, `ObstacleHex`, `ObstacleIcon*`: 기존 HUD 스케일/원점에 맞춘 도형.
- `apply_obstacle_ui.py`: 에디터에서 실행하는 재현 스크립트. 런타임 Python 의존성 없음.
- `obstacle_ui_playtest.py`: 실제 PIE에서 지급/선택/차감/중복/페이지/다음 라운드 검증. 테스트 전용 함수는 저장하지 않는다.

## 백업

`Bumpit/Saved/Backups/before_obstacle_ui_20261125/BP_BumpitHUD.uasset`

에디터가 같은 프로젝트를 여러 창에서 열고 있다면, 오래된 메모리 상태의 HUD를 저장하여 덮어쓰지 않도록 최신 에셋을 다시 로드한다.
