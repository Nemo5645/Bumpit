#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BumpitLampFlicker.generated.h"

class UPointLightComponent;

// Makes a named lamp hum and occasionally stutter. Place one in the level.
UCLASS()
class ABumpitLampFlicker : public AActor
{
    GENERATED_BODY()
public:
    ABumpitLampFlicker();
    virtual void Tick(float DeltaSeconds) override;

    UPROPERTY(EditAnywhere, Category="Mood") FString LampName = TEXT("TableLamp");
    UPROPERTY(EditAnywhere, Category="Mood") float MinQuietSeconds = 3.5f;
    UPROPERTY(EditAnywhere, Category="Mood") float MaxQuietSeconds = 10.f;

private:
    void FindLamp();
    TWeakObjectPtr<UPointLightComponent> Lamp;
    float BaseIntensity = 0;
    float NextSearch = 0, NextStutter = 0, StutterEnd = 0;
};
