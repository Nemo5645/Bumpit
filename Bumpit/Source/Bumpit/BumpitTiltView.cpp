#include "BumpitTiltView.h"
#include "BumpitRound.h"
#include "Camera/PlayerCameraManager.h"
#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/World.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

namespace
{
constexpr float ShakeSeconds = .55f, ShakeDegrees = 1.6f, LastShakeSeconds = 1.1f, LastShakeDegrees = 5, ShakeRate = 42;
// A tilt bursts the blur up to the tilt level, then it eases down to RestBlur of that level.
// The f-stop sets the strength at full level; a lower one is blurrier.
constexpr float BlurEase = 2.5f, RestBlur = .035f, FullBlurFstop = 2.5f, BlurFocusDistance = 10, FullBlurFringe = 4;
// The black circle's radius in screen heights: off the screen with no tilts used, around the
// pinball board at the last tilt level before the end, then shut.
constexpr float OpenRadius = 1.1f, BoardRadius = .5f, BoardLevel = .8f, ShutRadius = -.25f, RadiusEase = 3;
// When each game over line appears, in seconds after the screen is fully black.
constexpr float ScoreLineDelay = .3f, GameOverLineDelay = 1.2f, RestartLineDelay = 2;
constexpr float HudHeight = 740;
const FLinearColor GameOverColor(1.f,.66f,.19f), RestartColor(.49f,.62f,.68f);

UBumpitTiltView* FindView(const APlayerController* Player)
{
    APlayerCameraManager* Camera = Player ? Player->PlayerCameraManager : nullptr;
    return Camera ? Cast<UBumpitTiltView>(Camera->FindCameraModifierByClass(UBumpitTiltView::StaticClass())) : nullptr;
}
}

void UBumpitTiltView::Shake(const UWorld* World)
{
    const APlayerController* Player = World ? World->GetFirstPlayerController() : nullptr;
    if (!Player || !Player->PlayerCameraManager) return;
    UBumpitTiltView* View = FindView(Player);
    if (!View) View = Cast<UBumpitTiltView>(Player->PlayerCameraManager->AddNewCameraModifier(StaticClass()));
    if (!View) return;
    const float Level = UBumpitRound::TiltLevel(World);
    const bool bLast = Level >= 1;
    View->ShakeLength = bLast ? LastShakeSeconds : ShakeSeconds;
    View->ShakeSize = bLast ? LastShakeDegrees : ShakeDegrees;
    View->ShakeLeft = View->ShakeLength;
    View->Blur = Level;
}

void UBumpitTiltView::ModifyCamera(float DeltaTime, FVector ViewLocation, FRotator ViewRotation, float FOV,
    FVector& NewViewLocation, FRotator& NewViewRotation, float& NewFOV)
{
    Super::ModifyCamera(DeltaTime,ViewLocation,ViewRotation,FOV,NewViewLocation,NewViewRotation,NewFOV);
    if (ShakeLeft <= 0) return;
    ShakeLeft = FMath::Max(0.f,ShakeLeft-DeltaTime);
    ShakeClock += DeltaTime;
    const float Amount = ShakeSize*ShakeLeft/ShakeLength;
    NewViewRotation += FRotator(FMath::Sin(ShakeClock*ShakeRate)*Amount,FMath::Sin(ShakeClock*ShakeRate*1.3f+1)*Amount,
        FMath::Sin(ShakeClock*ShakeRate*.7f)*Amount*.6f);
}

void UBumpitTiltView::ModifyPostProcess(float DeltaTime, float& PostProcessBlendWeight, FPostProcessSettings& PostProcessSettings)
{
    const float Level = UBumpitRound::TiltLevel(this);
    const float Target = Level >= 1 ? ShutRadius : FMath::Lerp(OpenRadius,BoardRadius,Level/BoardLevel);
    Radius = FMath::FInterpTo(Radius,Target,DeltaTime,RadiusEase);
    Blur = FMath::FInterpTo(Blur,Level*RestBlur,DeltaTime,BlurEase);
    if (Blur < .002f) return;
    PostProcessBlendWeight = 1;
    PostProcessSettings.bOverride_DepthOfFieldFocalDistance = true;
    PostProcessSettings.DepthOfFieldFocalDistance = BlurFocusDistance;
    PostProcessSettings.bOverride_DepthOfFieldFstop = true;
    PostProcessSettings.DepthOfFieldFstop = FullBlurFstop/Blur;
    PostProcessSettings.bOverride_SceneFringeIntensity = true;
    PostProcessSettings.SceneFringeIntensity = FullBlurFringe*Blur;
}

void UBumpitTiltView::DrawCircle(UCanvas* Canvas)
{
    if (Radius > OpenRadius-.01f) return;
    if (!Circle)
    {
        UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Bumpit/Materials/M_UI_BumpitTunnel.M_UI_BumpitTunnel"));
        Circle = UMaterialInstanceDynamic::Create(Material,this);
    }
    if (!Circle) return;
    Circle->SetScalarParameterValue(TEXT("Radius"),Radius);
    Circle->SetScalarParameterValue(TEXT("Aspect"),Canvas->ClipX/Canvas->ClipY);
    FCanvasTileItem Tile(FVector2D::ZeroVector,Circle->GetRenderProxy(),FVector2D(Canvas->ClipX,Canvas->ClipY));
    Canvas->DrawItem(Tile);
}

float UBumpitTiltView::RestartDelay()
{
    return RestartLineDelay;
}

void UBumpitTiltView::DrawOverlay(const AHUD* Hud, UCanvas* Canvas, float Black, float BlackSeconds)
{
    if (!Hud || !Canvas) return;
    if (UBumpitTiltView* View = FindView(Hud->GetOwningPlayerController())) View->DrawCircle(Canvas);
    if (Black <= 0) return;
    FCanvasTileItem Cover(FVector2D::ZeroVector,FVector2D(Canvas->ClipX,Canvas->ClipY),FLinearColor(0,0,0,Black));
    Cover.BlendMode = SE_BLEND_Translucent;
    Canvas->DrawItem(Cover);
    const UFont* Font = GEngine->GetMediumFont();
    const float Scale = Canvas->ClipY/HudHeight;
    const auto Line = [&](float Delay, const TCHAR* Text, float OffsetY, float Size, const FLinearColor& Color)
    {
        if (BlackSeconds < Delay) return;
        FCanvasTextItem Label(FVector2D::ZeroVector,FText::FromString(Text),Font,Color);
        Label.Scale = FVector2D(Size*Scale);
        Label.bCentreX = true;
        Label.bCentreY = true;
        Canvas->DrawItem(Label,FVector2D(Canvas->ClipX/2,Canvas->ClipY/2+OffsetY*Scale));
    };
    Line(ScoreLineDelay,TEXT("0점"),-80,4.5f,GameOverColor);
    Line(GameOverLineDelay,TEXT("GAME OVER"),20,3.2f,GameOverColor);
    Line(RestartLineDelay,TEXT("다시  [SPACE]"),110,1.3f,RestartColor);
}
