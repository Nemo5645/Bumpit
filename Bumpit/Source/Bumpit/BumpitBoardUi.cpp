#include "BumpitBoardUi.h"
#include "BumpitRound.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"

namespace
{
constexpr int32 SlotCount = 3;
constexpr int32 TableStation = 1;
constexpr int32 BuildPhase = 0, FlightPhase = 1;
// Layout in the HUD's 1200x740 space, directly below LAUNCH CONTROL.
constexpr double HudWidth = 1200, HudHeight = 740;
constexpr double SlotX = 886, SlotW = 295, SlotTop = 290, SlotH = 122, SlotGap = 8, IconSize = 86;
constexpr double ArrowX = 34, ArrowY = 300, ArrowW = 92, ArrowH = 130;
constexpr double ScoreCenterX = 600, ScoreTop = 22, ScoreW = 220, ScoreH = 72;

const FLinearColor PanelColor(.012f,.022f,.037f), FrameColor(.05f,.28f,.42f), SelectedColor(.95f,.06f,.05f);
const FLinearColor TextColor(.9f,.94f,.96f), MutedColor(.49f,.62f,.68f), ScoreColor(1.f,.66f,.19f), HitColor(.2f,.94f,.69f);
const FLinearColor IconColors[SlotCount] = {{.05f,.85f,.65f},{1.f,.54f,.08f},{.96f,.19f,.11f}};
const TCHAR* const SlotNames[SlotCount] = {TEXT("원형 범퍼"),TEXT("왼쪽 반사판"),TEXT("오른쪽 반사판")};

int32 PhaseOf(const AHUD* Hud)
{
    const FIntProperty* Property = Hud ? FindFProperty<FIntProperty>(Hud->GetClass(),TEXT("Phase")) : nullptr;
    return Property ? Property->GetPropertyValue_InContainer(Hud) : BuildPhase;
}

bool ArrowVisible(const AHUD* Hud)
{
    return PhaseOf(Hud) == BuildPhase && !UBumpitRound::IsBoardLocked(Hud);
}

// The cursor in HUD space on the frame of a left click, if the cursor is showing.
bool ClickedAt(const APlayerController* Player, FVector2D& OutPoint)
{
    if (!Player || !Player->bShowMouseCursor || !Player->WasInputKeyJustPressed(EKeys::LeftMouseButton)) return false;
    float X, Y;
    int32 Width, Height;
    if (!Player->GetMousePosition(X,Y)) return false;
    Player->GetViewportSize(Width,Height);
    const double Scale = FMath::Min(Width/HudWidth,Height/HudHeight);
    if (Scale <= 0) return false;
    OutPoint = FVector2D((X-(Width-HudWidth*Scale)*.5)/Scale,(Y-(Height-HudHeight*Scale)*.5)/Scale);
    return true;
}

bool Inside(const FVector2D& Point, double X, double Y, double W, double H)
{
    return Point.X >= X && Point.X < X+W && Point.Y >= Y && Point.Y < Y+H;
}
}

void UBumpitBoardUi::DrawBumperSlots(AHUD* Hud, int32 Selected, const TArray<int32>& Stock,
    double Scale, double OffsetX, double OffsetY)
{
    if (!Hud) return;
    UFont* Font = GEngine->GetMediumFont();
    const auto Rect = [&](double X, double Y, double W, double H, const FLinearColor& Color)
    {
        Hud->DrawRect(Color,float(OffsetX+X*Scale),float(OffsetY+Y*Scale),float(W*Scale),float(H*Scale));
    };
    const auto Label = [&](const FString& Text, double X, double Y, double Size, const FLinearColor& Color)
    {
        Hud->DrawText(Text,Color,float(OffsetX+X*Scale),float(OffsetY+Y*Scale),Font,float(Size*Scale));
    };
    const auto Centered = [&](const FString& Text, double CenterX, double Y, double Size, const FLinearColor& Color)
    {
        float Width, Height;
        Hud->GetTextSize(Text,Width,Height,Font,float(Size*Scale));
        Hud->DrawText(Text,Color,float(OffsetX+CenterX*Scale-Width/2),float(OffsetY+Y*Scale),Font,float(Size*Scale));
    };
    const auto Frame = [&](double X, double Y, double W, double H, double Line, const FLinearColor& Color)
    {
        Rect(X,Y,W,Line,Color);
        Rect(X,Y+H-Line,W,Line,Color);
        Rect(X,Y,Line,H,Color);
        Rect(X+W-Line,Y,Line,H,Color);
    };

    for (int32 Slot=0; Slot<SlotCount; ++Slot)
    {
        const double Y = SlotTop + Slot*(SlotH+SlotGap);
        const bool bSelected = Slot == Selected;
        Rect(SlotX,Y,SlotW,SlotH,PanelColor);
        Frame(SlotX,Y,SlotW,SlotH,bSelected ? 4 : 2,bSelected ? SelectedColor : FrameColor);
        Rect(SlotX+16,Y+(SlotH-IconSize)/2,IconSize,IconSize,IconColors[Slot]);
        Label(SlotNames[Slot],SlotX+116,Y+30,1.12,TextColor);
        const int32 Count = Stock.IsValidIndex(Slot) ? Stock[Slot] : 0;
        Label(FString::Printf(TEXT("보관함: %d개"),Count),SlotX+116,Y+68,1,MutedColor);
    }

    if (ArrowVisible(Hud))
    {
        Rect(ArrowX,ArrowY,ArrowW,ArrowH,PanelColor);
        Frame(ArrowX,ArrowY,ArrowW,ArrowH,2,FrameColor);
        Centered(TEXT("<"),ArrowX+ArrowW/2,ArrowY+18,3.4,HitColor);
        Centered(TEXT("상점"),ArrowX+ArrowW/2,ArrowY+90,1,TextColor);
    }

    if (PhaseOf(Hud) == FlightPhase)
    {
        float Pulse;
        const int32 Score = UBumpitRound::LiveBallScore(Hud,Pulse);
        Rect(ScoreCenterX-ScoreW/2,ScoreTop,ScoreW,ScoreH,PanelColor);
        Frame(ScoreCenterX-ScoreW/2,ScoreTop,ScoreW,ScoreH,2,FrameColor);
        Centered(FString::FromInt(Score),ScoreCenterX,ScoreTop+12-Pulse*5,3+Pulse*.9,
            FMath::Lerp(ScoreColor,HitColor,Pulse));
    }
}

int32 UBumpitBoardUi::NextSelection(const UObject* Context, int32 Station, int32 Selected)
{
    if (Station != TableStation) return Selected;
    const APlayerController* Player = UGameplayStatics::GetPlayerController(Context,0);
    if (!Player) return Selected;
    FVector2D Point;
    if (ClickedAt(Player,Point))
    {
        for (int32 Slot=0; Slot<SlotCount; ++Slot)
            if (Inside(Point,SlotX,SlotTop+Slot*(SlotH+SlotGap),SlotW,SlotH)) return Slot;
    }
    const int32 Step = Player->WasInputKeyJustPressed(EKeys::MouseScrollDown) ? 1
        : Player->WasInputKeyJustPressed(EKeys::MouseScrollUp) ? -1 : 0;
    return (Selected+Step+SlotCount)%SlotCount;
}

bool UBumpitBoardUi::ShopArrowClicked(const UObject* Context, int32 Station)
{
    if (Station != TableStation) return false;
    const APlayerController* Player = UGameplayStatics::GetPlayerController(Context,0);
    FVector2D Point;
    return Player && ArrowVisible(Player->GetHUD()) && ClickedAt(Player,Point)
        && Inside(Point,ArrowX,ArrowY,ArrowW,ArrowH);
}
