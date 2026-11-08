#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BumpitShow.generated.h"

// The room's show pieces: the score screen above the machine, and the coins that
// pour out under it when a round is cleared. The coins are only a show; credits are paid elsewhere.
UCLASS()
class ABumpitShow : public AActor
{
    GENERATED_BODY()
public:
    ABumpitShow();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;

    void ShowScore(int32 BallPoints, int32 Target, int32 RoundPoints);

    // One big line in place of the score, on green or on the usual red, until the next ShowScore.
    void ShowBanner(const FString& Text, bool bGreen);

    // Pours this many coins over the same stretch of time, however many there are.
    void PourCoins(int32 Count);
    void ClearCoins();

private:
    struct FCoin
    {
        FVector Position;
        FVector Velocity;
        FRotator Rotation;
        FRotator Spin;
        float StartSeconds;
    };

    UFUNCTION() void DrawScreen(class UCanvas* Canvas, int32 Width, int32 Height);

    UPROPERTY() TObjectPtr<class UStaticMeshComponent> Frame;
    UPROPERTY() TObjectPtr<class UStaticMeshComponent> Screen;
    UPROPERTY() TObjectPtr<class UInstancedStaticMeshComponent> Coins;
    UPROPERTY() TObjectPtr<class UCanvasRenderTarget2D> ScreenImage;
    TArray<FCoin> Pour;
    TArray<FTransform> PourTransforms;
    float PourSeconds = 0;
    int32 ShownBall = 0, ShownTarget = 0, ShownRound = 0;
    FString Banner;
    bool bBannerGreen = false;
};
