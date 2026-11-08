#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BumpitBoardUi.generated.h"

class AHUD;

// Table screen helpers: bumper slots, shop arrow, and the live ball score.
UCLASS()
class UBumpitBoardUi : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    // Draws the slots, the shop arrow, and the live score while a ball is moving.
    UFUNCTION(BlueprintCallable, Category="Bumpit|UI", meta=(DefaultToSelf="Hud"))
    static void DrawBumperSlots(AHUD* Hud, int32 Selected, const TArray<int32>& Stock,
        double Scale, double OffsetX, double OffsetY);

    // Draws the settlement prompt over the score screen view.
    UFUNCTION(BlueprintCallable, Category="Bumpit|UI", meta=(DefaultToSelf="Hud"))
    static void DrawSettlement(AHUD* Hud, double Scale, double OffsetX, double OffsetY);

    // Moves the selection with the mouse wheel or a click on a slot while the table is open.
    UFUNCTION(BlueprintPure, Category="Bumpit|UI", meta=(WorldContext="Context"))
    static int32 NextSelection(const UObject* Context, int32 Station, int32 Selected);

    // Draws the arrow back to the table on the shop screen.
    UFUNCTION(BlueprintCallable, Category="Bumpit|UI", meta=(DefaultToSelf="Hud"))
    static void DrawTableArrow(AHUD* Hud, double Scale, double OffsetX, double OffsetY);

    // True on the frame the side arrow is clicked, on the table or in the shop.
    UFUNCTION(BlueprintPure, Category="Bumpit|UI", meta=(WorldContext="Context"))
    static bool ShopArrowClicked(const UObject* Context, int32 Station);

    // Where the side arrow leads from this station: the table and the shop lead to each other.
    UFUNCTION(BlueprintPure, Category="Bumpit|UI")
    static int32 ArrowStation(int32 Station);
};
