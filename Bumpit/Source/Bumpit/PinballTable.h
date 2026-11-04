#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PinballTable.generated.h"

class UPhysicalMaterial;
class UStaticMeshComponent;
class UMaterialInterface;

UCLASS()
class APinballTable : public AActor
{
    GENERATED_BODY()
public:
    APinballTable();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    void SetObstacle(int32 Index, int32 Type);
    int32 PickCell(const FVector& RayOrigin, const FVector& RayDirection) const;
    FVector GoalLabel(int32 Lane) const;
    void ResetBall();
    UFUNCTION(BlueprintCallable, CallInEditor, Category="Table") void BuildGeometry();
    void Launch(float Power);
    // Returns the catch lane, -1 in flight, or -2 for a lost ball.
    int32 CheckBall() const;
    void StopBall();
    int32 Hits = 0;

private:
    friend class FRoundBumperTest;
    friend class FCheckRoundBounce;
    FVector IncomingVelocity = FVector::ZeroVector;
    UPROPERTY() TObjectPtr<UStaticMesh> Cube;
    UPROPERTY() TObjectPtr<UStaticMesh> Cylinder;
    UPROPERTY() TObjectPtr<UStaticMesh> Sphere;
    UPROPERTY() TObjectPtr<UMaterialInterface> Surface;
    UPROPERTY() TObjectPtr<UPhysicalMaterial> Rubber;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Ball;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> LaunchGate;
    void SetLaunchGateClosed(bool Closed);
    UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Obstacles;
    void BuildRoom();
    UStaticMeshComponent* Piece(UStaticMesh* Mesh, FVector Position, FVector Dimensions,
        FLinearColor Color, bool Solid = true, float Yaw = 0);
    UFUNCTION() void OnBallHit(UPrimitiveComponent* HitComponent, AActor* OtherActor,
        UPrimitiveComponent* OtherComponent, FVector NormalImpulse, const FHitResult& Hit);
};

