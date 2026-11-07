#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BumpitKeyRepair.generated.h"

class UBlueprint;

// Editor tools for damage left by the C++ to Blueprint port.
UCLASS()
class UBumpitKeyRepair : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    // Restores literal keys on BP_BumpitHUD's UpdateBoard input nodes. Returns pins set.
    UFUNCTION(BlueprintCallable, Category="Bumpit") static int32 RepairHudKeys(UBlueprint* Blueprint);

    // Rebuilds Row = Index / 8 in BP_PinballTable's HexCenter as an integer. Returns links made.
    UFUNCTION(BlueprintCallable, Category="Bumpit") static int32 RepairHexCenter(UBlueprint* Blueprint);
};
