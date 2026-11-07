#include "BumpitRound.h"
#include "BumpitTiltView.h"
#include "Components/PrimitiveComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"

namespace
{
// Tuning: balls per round, the first target, and how fast targets grow.
constexpr int32 MaxBalls = 4;
constexpr double FirstTarget = 600.;
constexpr double TargetGrowth = 1.5;
constexpr int32 TargetStep = 50;
// Credit multiplier for balls fired after the target has been reached.
constexpr double ClearedCreditRate = 1.5;
// The 6x8 board splits into three 2x8 sections; each loses half its bumpers.
constexpr int32 SectionCells = 16;
// Lane multipliers; each round shuffles this same set across the nine lanes.
constexpr int32 LaneSet[] = {1,2,5,2,10,2,5,2,1};
// Engraved labels, in the table's local space on the goal cells.
constexpr double LaneLabelX = -312, LaneLabelFirstY = -256, LaneLabelStepY = 64, LaneLabelZ = 8, LaneLabelSize = 32;
// A ball that stays inside StillRadius for StallSeconds gets kicked back up the table.
// Every stall uses a tilt; the last tilt blacks out the view and ends the run on 0 points.
constexpr float StallSeconds = 5;
constexpr int32 MaxTilts = 5;
// Long enough for the last shake to be seen before the screen is fully black.
constexpr float BlackoutFade = 1.1f;
constexpr double StillRadius = 6, StallKickUp = 750, StallKickSide = 220, StallKickHop = 120;
// A ball stopped on the launch rail is not the player's stall: it goes back out at a launch speed, free.
constexpr double LaunchRailY = 288, RailKick = 1100;
// Table-space point below the lost-ball line, where the last tilted ball goes.
const FVector VoidedBallSpot(0,0,-200);
// The HUD takes Space only in SettlePhase. A tilted-out run sits in EndingPhase until the restart line is up.
constexpr int32 SettlePhase = 2, EndingPhase = 3;
// Matches RoundScore in BP_BumpitHUD, before the lane multiplier.
constexpr int32 BaseBallScore = 100, ScorePerHit = 25;
constexpr double PulseSeconds = .18;

template<class TProperty>
TProperty* FindVariable(const UObject* Owner, FName Name)
{
    return Owner ? FindFProperty<TProperty>(Owner->GetClass(),Name) : nullptr;
}

UPrimitiveComponent* BallOf(const AActor* Table)
{
    const FObjectProperty* Property = FindVariable<FObjectProperty>(Table,TEXT("Ball"));
    return Property ? Cast<UPrimitiveComponent>(Property->GetObjectPropertyValue_InContainer(Table)) : nullptr;
}

AHUD* HudOf(const UWorld* World)
{
    const APlayerController* Player = World ? World->GetFirstPlayerController() : nullptr;
    return Player ? Player->GetHUD() : nullptr;
}

void SetPhase(const UWorld* World, int32 Phase)
{
    AHUD* Hud = HudOf(World);
    if (const FIntProperty* Property = FindVariable<FIntProperty>(Hud,TEXT("Phase")))
        Property->SetPropertyValue_InContainer(Hud,Phase);
}

int32 HitsOf(const AActor* Table)
{
    const FIntProperty* Property = FindVariable<FIntProperty>(Table,TEXT("Hits"));
    return Property ? Property->GetPropertyValue_InContainer(Table) : 0;
}
}

TStatId UBumpitRound::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UBumpitRound,STATGROUP_Tickables);
}

void UBumpitRound::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    PostRenderHandle = AHUD::OnHUDPostRender.AddUObject(this,&UBumpitRound::DrawOverlay);
}

void UBumpitRound::Deinitialize()
{
    AHUD::OnHUDPostRender.Remove(PostRenderHandle);
    Super::Deinitialize();
}

void UBumpitRound::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (BlackoutSeconds >= 0)
    {
        TickBlackout(DeltaTime);
        return;
    }
    const AActor* Table = TableActor.Get();
    UPrimitiveComponent* Ball = BallOf(Table);
    if (!Ball || !Ball->IsSimulatingPhysics())
    {
        StillSeconds = 0;
        StallKicks = 0;
        bVoided = false;
        return;
    }
    const FVector Position = Ball->GetComponentLocation();
    if (FVector::Dist(Position,StillAnchor) > StillRadius)
    {
        StillAnchor = Position;
        StillSeconds = 0;
        return;
    }
    StillSeconds += DeltaTime;
    if (StillSeconds < StallSeconds) return;
    StillSeconds = 0;
    const FTransform TableSpace = Table->GetActorTransform();
    if (TableSpace.InverseTransformPosition(Position).Y >= LaunchRailY)
    {
        Ball->SetPhysicsLinearVelocity(TableSpace.TransformVectorNoScale(FVector(RailKick,0,0)));
        return;
    }
    ++StallKicks;
    UBumpitTiltView::Shake(GetWorld());
    if (StallKicks >= MaxTilts)
    {
        BlackoutSeconds = 0;
        return;
    }
    const FVector Kick(StallKickUp,FMath::FRandRange(-StallKickSide,StallKickSide),StallKickHop);
    Ball->SetPhysicsLinearVelocity(TableSpace.TransformVectorNoScale(Kick));
}

void UBumpitRound::TickBlackout(float DeltaTime)
{
    const bool bWasFading = BlackoutSeconds < BlackoutFade;
    BlackoutSeconds += DeltaTime;
    if (bWasFading && BlackoutSeconds >= BlackoutFade) VoidBall();
    if (State == EState::GameOver && BlackoutSeconds >= BlackoutFade+UBumpitTiltView::RestartDelay())
        SetPhase(GetWorld(),SettlePhase);
}

// Settles the ball out of sight; the screen stays black until Space restarts the run.
void UBumpitRound::VoidBall()
{
    const AActor* Table = TableActor.Get();
    UPrimitiveComponent* Ball = BallOf(Table);
    if (!Ball) return;
    bVoided = true;
    Ball->SetWorldLocation(Table->GetActorTransform().TransformPosition(VoidedBallSpot),false,nullptr,ETeleportType::TeleportPhysics);
}

void UBumpitRound::DrawOverlay(AHUD* Hud, UCanvas* Canvas)
{
    if (!Hud || Hud->GetWorld() != GetWorld()) return;
    const float Fade = FMath::Clamp(BlackoutSeconds/BlackoutFade,0.f,1.f);
    UBumpitTiltView::DrawOverlay(Hud,Canvas,Fade*Fade,BlackoutSeconds-BlackoutFade);
}

int32 UBumpitRound::TiltsLeft(const UObject* Context)
{
    const UBumpitRound* Rules = Get(Context);
    return Rules ? MaxTilts-Rules->StallKicks : MaxTilts;
}

float UBumpitRound::TiltLevel(const UObject* Context)
{
    const UBumpitRound* Rules = Get(Context);
    return Rules ? float(Rules->StallKicks)/MaxTilts : 0;
}

int32 UBumpitRound::LiveBallScore(const UObject* Context, float& OutPulse)
{
    OutPulse = 0;
    UBumpitRound* Rules = Get(Context);
    if (!Rules) return BaseBallScore;
    const int32 Hits = HitsOf(Rules->TableActor.Get());
    const double Now = Rules->GetWorld()->GetTimeSeconds();
    if (Hits > Rules->LastHits) Rules->PulseStart = Now;
    Rules->LastHits = Hits;
    if (Rules->PulseStart >= 0 && Now-Rules->PulseStart < PulseSeconds)
        OutPulse = float(1-(Now-Rules->PulseStart)/PulseSeconds);
    return BaseBallScore+ScorePerHit*Hits;
}

UBumpitRound* UBumpitRound::Get(const UObject* Context)
{
    const UWorld* World = GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::LogAndReturnNull);
    return World ? World->GetSubsystem<UBumpitRound>() : nullptr;
}

int32 UBumpitRound::TargetFor(int32 Round)
{
    const double Target = FirstTarget*FMath::Pow(TargetGrowth,double(Round-1));
    return FMath::RoundToInt(Target/TargetStep)*TargetStep;
}

FString UBumpitRound::RecordBall(const UObject* Context, int32 Points)
{
    UBumpitRound* Rules = Get(Context);
    if (!Rules) return FString();
    const int32 Target = TargetFor(Rules->Round);
    const bool bAlreadyReached = Rules->RoundPoints >= Target;
    ++Rules->BallsUsed;
    Rules->RoundPoints += Points;
    const bool bReached = Rules->RoundPoints >= Target;
    const int32 BallsLeft = MaxBalls-Rules->BallsUsed;
    if (Rules->bVoided)
    {
        Rules->State = EState::GameOver;
        SetPhase(Rules->GetWorld(),EndingPhase);
        return TEXT("틸트를 모두 사용했습니다.");
    }
    if (BallsLeft <= 0)
    {
        Rules->State = bReached ? EState::Cleared : EState::GameOver;
        return bReached ? FString::Printf(TEXT("라운드 클리어! 다음 목표 %d"),TargetFor(Rules->Round+1))
                        : FString::Printf(TEXT("게임 오버 · 목표까지 %d점 부족"),Target-Rules->RoundPoints);
    }
    if (bAlreadyReached) return FString::Printf(TEXT("보너스 크레딧 지급 · 남은 구슬 %d개"),BallsLeft);
    if (bReached) return FString::Printf(TEXT("목표 달성! 이제 크레딧 보너스 · 남은 구슬 %d개"),BallsLeft);
    return FString::Printf(TEXT("이번 공 +%d점 · 남은 구슬 %d개"),Points,BallsLeft);
}

int32 UBumpitRound::AdjustCredits(const UObject* Context, int32 Base)
{
    const UBumpitRound* Rules = Get(Context);
    if (Rules && Rules->bVoided) return 0;
    if (!Rules || Rules->RoundPoints < TargetFor(Rules->Round)) return Base;
    return FMath::CeilToInt(Base*ClearedCreditRate);
}

bool UBumpitRound::IsGameOver(const UObject* Context)
{
    const UBumpitRound* Rules = Get(Context);
    return Rules && Rules->State == EState::GameOver;
}

bool UBumpitRound::IsBoardLocked(const UObject* Context)
{
    const UBumpitRound* Rules = Get(Context);
    return Rules && Rules->BallsUsed > 0;
}

int32 UBumpitRound::BreakBumpers(AActor* Table, TArray<int32>& Cells)
{
    struct { int32 Index; int32 Type; } Params;
    UFunction* SetObstacle = Table ? Table->FindFunction(TEXT("SetObstacle")) : nullptr;
    if (!SetObstacle || SetObstacle->ParmsSize != sizeof(Params))
    {
        UE_LOG(LogTemp,Error,TEXT("BreakBumpers: SetObstacle(Index, Type) not found on the table"));
        return 0;
    }
    int32 Broken = 0;
    for (int32 First=0; First<Cells.Num(); First+=SectionCells)
    {
        TArray<int32> Placed;
        for (int32 Cell=First; Cell<FMath::Min(First+SectionCells,Cells.Num()); ++Cell)
            if (Cells[Cell] > 0) Placed.Add(Cell);
        for (int32 I=Placed.Num()-1; I>0; --I)
            Placed.Swap(I,FMath::RandRange(0,I));
        // Half of the section goes; an odd leftover is a coin flip, so each bumper has a 50% chance.
        const int32 Count = Placed.Num()/2 + (Placed.Num()%2 && FMath::RandBool() ? 1 : 0);
        for (int32 I=0; I<Count; ++I)
        {
            Params = {Placed[I],0};
            Cells[Placed[I]] = 0;
            Table->ProcessEvent(SetObstacle,&Params);
            ++Broken;
        }
    }
    return Broken;
}

void UBumpitRound::AdvanceRound(const UObject* Context, AActor* Table, TArray<int32>& Cells)
{
    UBumpitRound* Rules = Get(Context);
    if (!Rules || Rules->State != EState::Cleared) return;
    Rules->LastBroken = BreakBumpers(Table,Cells);
    Rules->FixedCells.Reset();
    for (int32 Cell=0; Cell<Cells.Num(); ++Cell)
        if (Cells[Cell] > 0) Rules->FixedCells.Add(Cell);
    ++Rules->Round;
    Rules->BallsUsed = 0;
    Rules->RoundPoints = 0;
    Rules->State = EState::Playing;
    Rules->ShuffleLanes(Table);
}

void UBumpitRound::StartRun(const UObject* Context, AActor* Table)
{
    if (UBumpitRound* Rules = Get(Context))
    {
        Rules->TableActor = Table;
        Rules->ShuffleLanes(Table);
    }
}

void UBumpitRound::ShuffleLanes(AActor* Table)
{
    Multipliers = TArray<int32>(LaneSet,UE_ARRAY_COUNT(LaneSet));
    for (int32 I=Multipliers.Num()-1; I>0; --I)
        Multipliers.Swap(I,FMath::RandRange(0,I));
    if (!Table) return;
    if (LaneLabels.IsEmpty())
    {
        for (int32 Lane=0; Lane<Multipliers.Num(); ++Lane)
        {
            auto* Label = NewObject<UTextRenderComponent>(Table);
            Table->AddInstanceComponent(Label);
            Label->SetupAttachment(Table->GetRootComponent());
            Label->SetHorizontalAlignment(EHTA_Center);
            Label->SetVerticalAlignment(EVRTA_TextCenter);
            Label->SetWorldSize(LaneLabelSize);
            Label->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            Label->RegisterComponent();
            // Lies flat on the goal cell, reading upright from the table camera.
            Label->SetRelativeLocationAndRotation(
                FVector(LaneLabelX,LaneLabelFirstY+LaneLabelStepY*Lane,LaneLabelZ),FRotator(90.,180.,0.));
            LaneLabels.Add(Label);
        }
    }
    for (int32 Lane=0; Lane<LaneLabels.Num(); ++Lane)
        LaneLabels[Lane]->SetText(FText::FromString(FString::Printf(TEXT("×%d"),Multipliers[Lane])));
}

int32 UBumpitRound::LaneMultiplier(const UObject* Context, int32 Lane)
{
    const UBumpitRound* Rules = Get(Context);
    return Rules && Rules->Multipliers.IsValidIndex(Lane) ? Rules->Multipliers[Lane] : 1;
}

bool UBumpitRound::IsCellLocked(const UObject* Context, int32 Cell)
{
    const UBumpitRound* Rules = Get(Context);
    return Rules && Cell >= 0 && (Rules->BallsUsed > 0 || Rules->FixedCells.Contains(Cell));
}

FString UBumpitRound::CellLockMessage(const UObject* Context, int32 Cell)
{
    const UBumpitRound* Rules = Get(Context);
    if (Rules && Rules->BallsUsed == 0) return TEXT("살아남은 범퍼는 고정되어 옮길 수 없습니다.");
    return TEXT("구슬을 모두 쓸 때까지 판과 상점이 잠겨 있습니다.");
}

void UBumpitRound::RestartGame(const UObject* Context)
{
    UGameplayStatics::OpenLevel(Context,FName(*UGameplayStatics::GetCurrentLevelName(Context)));
}

FString UBumpitRound::StatusLine(const UObject* Context)
{
    const UBumpitRound* Rules = Get(Context);
    if (!Rules) return FString();
    const int32 Target = TargetFor(Rules->Round);
    return FString::Printf(TEXT("라운드 %d   ·   점수 %d / %d%s   ·   구슬 %d개"),Rules->Round,Rules->RoundPoints,
        Target,Rules->RoundPoints >= Target ? TEXT(" 달성") : TEXT(""),MaxBalls-Rules->BallsUsed);
}

FString UBumpitRound::ContinueLabel(const UObject* Context)
{
    const UBumpitRound* Rules = Get(Context);
    if (!Rules) return FString();
    switch (Rules->State)
    {
    case EState::Cleared: return TEXT("다음 라운드  [SPACE]");
    case EState::GameOver: return TEXT("다시 시작  [SPACE]");
    default: return TEXT("다음 구슬  [SPACE]");
    }
}

FString UBumpitRound::ReadyMessage(const UObject* Context)
{
    const UBumpitRound* Rules = Get(Context);
    if (!Rules) return FString();
    if (Rules->BallsUsed > 0)
        return FString::Printf(TEXT("판이 잠겼습니다 · 남은 구슬 %d개"),MaxBalls-Rules->BallsUsed);
    return FString::Printf(TEXT("범퍼 %d개가 부서졌습니다. 남은 범퍼는 고정, 배율이 바뀌었습니다."),Rules->LastBroken);
}

int32 UBumpitRound::NextStation(const UObject* Context)
{
    return IsBoardLocked(Context) ? 1 : 2;
}
