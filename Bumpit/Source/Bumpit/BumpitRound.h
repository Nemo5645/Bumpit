#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "BumpitRound.generated.h"

// Round rules: build the board, fire every ball, and reach the target or the run ends.
// State lives with the world, so reloading the level starts a fresh run.
UCLASS()
class UBumpitRound : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    // Counts one finished ball and returns the settlement message.
    UFUNCTION(BlueprintCallable, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static FString RecordBall(const UObject* Context, int32 Points);

    // Raises a ball's credit reward once the target has already been reached.
    UFUNCTION(BlueprintPure, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static int32 AdjustCredits(const UObject* Context, int32 Base);

    UFUNCTION(BlueprintPure, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static bool IsGameOver(const UObject* Context);

    // True from the first ball of a round until the next round starts.
    UFUNCTION(BlueprintPure, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static bool IsBoardLocked(const UObject* Context);

    // After a cleared round: breaks bumpers, then opens the next round.
    UFUNCTION(BlueprintCallable, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static void AdvanceRound(const UObject* Context, AActor* Table, UPARAM(ref) TArray<int32>& Cells);

    UFUNCTION(BlueprintCallable, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static void RestartGame(const UObject* Context);

    UFUNCTION(BlueprintPure, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static FString StatusLine(const UObject* Context);

    UFUNCTION(BlueprintPure, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static FString ContinueLabel(const UObject* Context);

    // Message shown after leaving the settlement screen.
    UFUNCTION(BlueprintPure, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static FString ReadyMessage(const UObject* Context);

    // Shop while the board is open, otherwise straight back to the table.
    UFUNCTION(BlueprintPure, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static int32 NextStation(const UObject* Context);

    // Rolls the first round's multipliers and engraves them on the table.
    UFUNCTION(BlueprintCallable, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static void StartRun(const UObject* Context, AActor* Table);

    UFUNCTION(BlueprintPure, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static int32 LaneMultiplier(const UObject* Context, int32 Lane);

    // True while the board is locked, or for a bumper that survived a previous round.
    UFUNCTION(BlueprintPure, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static bool IsCellLocked(const UObject* Context, int32 Cell);

    UFUNCTION(BlueprintPure, Category="Bumpit|Round", meta=(WorldContext="Context"))
    static FString CellLockMessage(const UObject* Context, int32 Cell);

private:
    enum class EState { Playing, Cleared, GameOver };
    static UBumpitRound* Get(const UObject* Context);
    static int32 TargetFor(int32 Round);
    static int32 BreakBumpers(AActor* Table, TArray<int32>& Cells);
    void ShuffleLanes(AActor* Table);

    EState State = EState::Playing;
    int32 Round = 1;
    int32 BallsUsed = 0;
    int32 RoundPoints = 0;
    int32 LastBroken = 0;
    TArray<int32> Multipliers;
    TSet<int32> FixedCells;
    UPROPERTY() TArray<TObjectPtr<class UTextRenderComponent>> LaneLabels;
};
