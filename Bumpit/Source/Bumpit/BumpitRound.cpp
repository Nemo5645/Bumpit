#include "BumpitRound.h"
#include "Components/PrimitiveComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
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
constexpr float StallSeconds = 5;
constexpr double StillRadius = 6, StallKickUp = 750, StallKickSide = 220, StallKickHop = 120;
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

void UBumpitRound::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    const AActor* Table = TableActor.Get();
    UPrimitiveComponent* Ball = BallOf(Table);
    if (!Ball || !Ball->IsSimulatingPhysics())
    {
        StillSeconds = 0;
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
    const FVector Kick(StallKickUp,FMath::FRandRange(-StallKickSide,StallKickSide),StallKickHop);
    Ball->SetPhysicsLinearVelocity(Table->GetActorTransform().TransformVectorNoScale(Kick));
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
    if (BallsLeft <= 0)
    {
        Rules->State = bReached ? EState::Cleared : EState::GameOver;
        return bReached ? FString::Printf(TEXT("통과. 다음은 %d."),TargetFor(Rules->Round+1))
                        : FString::Printf(TEXT("끝났다. %d점 모자랐다."),Target-Rules->RoundPoints);
    }
    if (bAlreadyReached) return FString::Printf(TEXT("+%d. 더 쳐줬다. 구슬 %d."),Points,BallsLeft);
    if (bReached) return FString::Printf(TEXT("목표 넘김. 이제 더 준다. 구슬 %d."),BallsLeft);
    return FString::Printf(TEXT("+%d. 구슬 %d."),Points,BallsLeft);
}

int32 UBumpitRound::AdjustCredits(const UObject* Context, int32 Base)
{
    const UBumpitRound* Rules = Get(Context);
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
    if (Rules && Rules->BallsUsed == 0) return TEXT("그건 못 옮긴다.");
    return TEXT("구슬을 다 쓸 때까지 못 건드린다.");
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
    case EState::GameOver: return TEXT("다시  [SPACE]");
    default: return TEXT("다음 구슬  [SPACE]");
    }
}

FString UBumpitRound::ReadyMessage(const UObject* Context)
{
    const UBumpitRound* Rules = Get(Context);
    if (!Rules) return FString();
    if (Rules->BallsUsed > 0)
        return FString::Printf(TEXT("판 잠김. 구슬 %d."),MaxBalls-Rules->BallsUsed);
    return FString::Printf(TEXT("범퍼 %d개 박살. 남은 건 못 건드린다."),Rules->LastBroken);
}

int32 UBumpitRound::NextStation(const UObject* Context)
{
    return IsBoardLocked(Context) ? 1 : 2;
}
