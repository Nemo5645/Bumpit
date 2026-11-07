#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BumpitBoardUi.generated.h"

class AHUD;

// Table screen helpers: the bumper slot list and mouse wheel selection.
UCLASS()
class UBumpitBoardUi : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    // Draws one slot per bumper type with its stock; the selected slot gets a red frame.
    UFUNCTION(BlueprintCallable, Category="Bumpit|UI", meta=(DefaultToSelf="Hud"))
    static void DrawBumperSlots(AHUD* Hud, int32 Selected, const TArray<int32>& Stock,
        double Scale, double OffsetX, double OffsetY);

    // Moves the selection with the mouse wheel while the table is open.
    UFUNCTION(BlueprintPure, Category="Bumpit|UI", meta=(WorldContext="Context"))
    static int32 NextSelection(const UObject* Context, int32 Station, int32 Selected);
};
