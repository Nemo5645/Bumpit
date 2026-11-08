#pragma once

#include "CoreMinimal.h"
#include "Camera/CameraModifier.h"
#include "BumpitTiltView.generated.h"

// What a tilt does to the player's view: a shake with a burst of blur, and a black circle
// that closes in over everything with every tilt used. Nothing here touches the ball.
UCLASS()
class UBumpitTiltView : public UCameraModifier
{
    GENERATED_BODY()
public:
    // Call after the tilt is counted: the burst of blur grows with the tilts used.
    static void Shake(const UWorld* World);

    // Draws over the HUD: the circle, then black at the given strength, then the game over
    // text, which comes up line by line once BlackSeconds passes zero. A tilt-out shows 0 points first.
    static void DrawOverlay(const class AHUD* Hud, class UCanvas* Canvas, float Black, float BlackSeconds, bool bTilted);

    // Seconds of full black before the restart line shows.
    static float RestartDelay(bool bTilted);

protected:
    using UCameraModifier::ModifyCamera;
    virtual void ModifyCamera(float DeltaTime, FVector ViewLocation, FRotator ViewRotation, float FOV,
        FVector& NewViewLocation, FRotator& NewViewRotation, float& NewFOV) override;
    virtual void ModifyPostProcess(float DeltaTime, float& PostProcessBlendWeight, FPostProcessSettings& PostProcessSettings) override;

private:
    void DrawCircle(class UCanvas* Canvas);

    float ShakeLeft = 0;
    float ShakeLength = 0;
    float ShakeSize = 0;
    float ShakeClock = 0;
    float Blur = 0;
    float Radius = 2;
    UPROPERTY() TObjectPtr<class UMaterialInstanceDynamic> Circle;
};
