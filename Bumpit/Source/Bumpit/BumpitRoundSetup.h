#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BumpitRoundSetup.generated.h"

class UBlueprint;
class UFont;
class UFontFace;

// Editor tool: wires the round rules into BP_BumpitHUD.
UCLASS()
class UBumpitRoundSetup : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    // Returns how many links were made. Compile and save the Blueprint afterwards.
    UFUNCTION(BlueprintCallable, Category="Bumpit") static int32 ApplyRoundSystem(UBlueprint* Blueprint);

    // Adds the bumper slot list and wheel selection to the table screen. Returns links made.
    UFUNCTION(BlueprintCallable, Category="Bumpit") static int32 ApplyBumperSlots(UBlueprint* Blueprint);

    // Makes Font a runtime font backed by Face, sized for the HUD's Label scale.
    UFUNCTION(BlueprintCallable, Category="Bumpit") static void ConfigureUiFont(UFont* Font, UFontFace* Face, int32 Size);

    // Recolors every HUD color literal to the workshop palette and sets the Label font.
    // Returns how many color pins changed.
    UFUNCTION(BlueprintCallable, Category="Bumpit") static int32 ApplyUiStyle(UBlueprint* Blueprint, UFont* Font);
};
