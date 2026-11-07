#include "BumpitBoardUi.h"
#include "Engine/Font.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"

namespace
{
constexpr int32 SlotCount = 3;
constexpr int32 TableStation = 1;
// Layout in the HUD's 1200x740 space, directly below LAUNCH CONTROL.
constexpr double SlotX = 886, SlotW = 295, SlotTop = 290, SlotH = 122, SlotGap = 8, IconSize = 86;

const FLinearColor PanelColor(.016f,.010f,.008f,.86f), FrameColor(.30f,.15f,.07f), SelectedColor(.95f,.06f,.05f);
const FLinearColor TextColor(.86f,.79f,.66f), MutedColor(.56f,.46f,.36f);
const FLinearColor IconColors[SlotCount] = {{.64f,.52f,.11f},{.85f,.29f,.03f},{.62f,.025f,.022f}};
const TCHAR* const SlotNames[SlotCount] = {TEXT("원형 범퍼"),TEXT("왼쪽 반사판"),TEXT("오른쪽 반사판")};
}

void UBumpitBoardUi::DrawBumperSlots(AHUD* Hud, int32 Selected, const TArray<int32>& Stock,
    double Scale, double OffsetX, double OffsetY)
{
    if (!Hud) return;
    UFont* Font = LoadObject<UFont>(nullptr,TEXT("/Game/Bumpit/UI/F_Galmuri.F_Galmuri"));
    const auto Rect =[&](double X, double Y, double W, double H, const FLinearColor& Color)
    {
        Hud->DrawRect(Color,float(OffsetX+X*Scale),float(OffsetY+Y*Scale),float(W*Scale),float(H*Scale));
    };
    const auto Label = [&](const FString& Text, double X, double Y, double Size, const FLinearColor& Color)
    {
        Hud->DrawText(Text,Color,float(OffsetX+X*Scale),float(OffsetY+Y*Scale),Font,float(Size*Scale));
    };
    for (int32 Slot=0; Slot<SlotCount; ++Slot)
    {
        const double Y = SlotTop + Slot*(SlotH+SlotGap);
        const bool bSelected = Slot == Selected;
        const FLinearColor& Frame = bSelected ? SelectedColor : FrameColor;
        const double Line = bSelected ? 4 : 2;
        Rect(SlotX,Y,SlotW,SlotH,PanelColor);
        Rect(SlotX,Y,SlotW,Line,Frame);
        Rect(SlotX,Y+SlotH-Line,SlotW,Line,Frame);
        Rect(SlotX,Y,Line,SlotH,Frame);
        Rect(SlotX+SlotW-Line,Y,Line,SlotH,Frame);
        Rect(SlotX+16,Y+(SlotH-IconSize)/2,IconSize,IconSize,IconColors[Slot]);
        Label(SlotNames[Slot],SlotX+116,Y+30,1.12,TextColor);
        const int32 Count = Stock.IsValidIndex(Slot) ? Stock[Slot] : 0;
        Label(FString::Printf(TEXT("보관함: %d개"),Count),SlotX+116,Y+68,1,MutedColor);
    }
}

int32 UBumpitBoardUi::NextSelection(const UObject* Context, int32 Station, int32 Selected)
{
    if (Station != TableStation) return Selected;
    const APlayerController* Player = UGameplayStatics::GetPlayerController(Context,0);
    if (!Player) return Selected;
    const int32 Step = Player->WasInputKeyJustPressed(EKeys::MouseScrollDown) ? 1
        : Player->WasInputKeyJustPressed(EKeys::MouseScrollUp) ? -1 : 0;
    return (Selected+Step+SlotCount)%SlotCount;
}
