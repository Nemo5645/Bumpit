#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "BumpitBoard.generated.h"

UCLASS()
class ABumpitGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ABumpitGameMode();
};

UCLASS()
class ABumpitBoard : public AHUD
{
    GENERATED_BODY()
public:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void DrawHUD() override;

private:
    friend class FBumpitPlaytest;
    friend class FBumpitWaitForCatch;
    enum class EPhase { Build, Flight, Result };
    enum class EStation { Room, Table, Shop, Terminal };
    EStation Station = EStation::Room;
    UPROPERTY() TObjectPtr<class ACameraActor> ViewCamera;
    bool Charging = false;
    float Power = 0;
    void Visit(EStation NewStation);
    void SetLooking(bool Enabled);
    void RotateView(float MouseX, float MouseY);
    void FocusView(const FVector& Eye, const FVector& Direction);
    void MoveCamera(FVector Eye, FVector Target, float Fov);
    void UpdateCamera(float DeltaSeconds);
    void Walk(FVector2D Input, float DeltaSeconds);
    FTransform BlendFrom, BlendTo;
    float FromFov = 53, ToFov = 53, BlendTime = 0;
    bool Blending = false;
    FVector ViewPivot;
    bool Looking = false;
    EPhase Phase = EPhase::Build;
    int32 Cells[48]{};
    int32 Stock[3]{};
    int32 Selected = 0, Stage = 1, Credits = 12, Hits = 0, Lane = 0, Earned = 0;
    int64 Total = 0;
    UPROPERTY() TObjectPtr<class APinballTable> Table;
    FVector2D Origin, Pointer;
    float Scale = 1;
    FString Message;
    void Buy(int32 Type);
    void Edit(int32 Index, bool Remove);
    void Advance();
    void Settle(bool Scored);
    void Rect(float X,float Y,float W,float H,FLinearColor Color);
    void Label(const FString& Text,float X,float Y,float Size,FLinearColor Color);
};
