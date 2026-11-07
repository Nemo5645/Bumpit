#include "BumpitLampFlicker.h"
#include "Components/PointLightComponent.h"
#include "EngineUtils.h"

ABumpitLampFlicker::ABumpitLampFlicker()
{
    PrimaryActorTick.bCanEverTick = true;
    SetActorHiddenInGame(true);
}

void ABumpitLampFlicker::FindLamp()
{
    // The HUD spawns the lighting actor at runtime, so the lamp may not exist on the first tick.
    for (TActorIterator<AActor> Actor(GetWorld()); Actor; ++Actor)
    {
        TInlineComponentArray<UPointLightComponent*> Lights(*Actor);
        for (UPointLightComponent* Light : Lights)
        {
            if (Light->GetName().Contains(LampName) && !Light->bHiddenInGame)
            {
                Lamp = Light;
                BaseIntensity = Light->Intensity;
                NextStutter = GetWorld()->GetTimeSeconds() + MinQuietSeconds;
                return;
            }
        }
    }
}

void ABumpitLampFlicker::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    const float Now = GetWorld()->GetTimeSeconds();
    if (!Lamp.IsValid())
    {
        if (Now >= NextSearch) { NextSearch = Now + .5f; FindLamp(); }
        return;
    }
    if (Now >= NextStutter)
    {
        StutterEnd = Now + FMath::FRandRange(.08f,.45f);
        NextStutter = StutterEnd + FMath::FRandRange(MinQuietSeconds,MaxQuietSeconds);
    }
    float Level = .94f + .04f*FMath::Sin(Now*7.3f) + .02f*FMath::Sin(Now*23.f);
    if (Now < StutterEnd) Level *= FMath::FRandRange(.08f,.6f);
    Lamp->SetIntensity(BaseIntensity*Level);
}
