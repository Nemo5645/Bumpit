#include "BumpitKeyRepair.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "InputCoreTypes.h"

#if WITH_EDITOR
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "Kismet/KismetMathLibrary.h"

namespace
{
UEdGraph* FindFunctionGraph(UBlueprint* Blueprint, const TCHAR* Name)
{
    for (UEdGraph* Graph : Blueprint->FunctionGraphs)
        if (Graph && Graph->GetName() == Name) return Graph;
    return nullptr;
}

UEdGraphNode* FindNode(UEdGraph* Graph, const TCHAR* Name)
{
    for (UEdGraphNode* Node : Graph->Nodes)
        if (Node && Node->GetName() == Name) return Node;
    return nullptr;
}

UK2Node_CallFunction* AddMathCall(UEdGraph* Graph, FName Function, int32 X, int32 Y)
{
    FGraphNodeCreator<UK2Node_CallFunction> Creator(*Graph);
    UK2Node_CallFunction* Node = Creator.CreateNode();
    Node->SetFromFunction(UKismetMathLibrary::StaticClass()->FindFunctionByName(Function));
    Node->NodePosX = X;
    Node->NodePosY = Y;
    Creator.Finalize();
    return Node;
}
}
#endif

int32 UBumpitKeyRepair::RepairHudKeys(UBlueprint* Blueprint)
{
    int32 Repaired = 0;
#if WITH_EDITOR
    UEdGraph* Graph = Blueprint ? FindFunctionGraph(Blueprint,TEXT("UpdateBoard")) : nullptr;
    if (!Graph) return 0;
    // Node name -> key, matching ABumpitBoard::Tick in the original C++ board.
    const TMap<FString, FString> Keys = {
        {TEXT("K2Node_CallFunction_3"), TEXT("R")},
        {TEXT("K2Node_CallFunction_10"), TEXT("LeftMouseButton")},
        {TEXT("K2Node_CallFunction_15"), TEXT("W")},
        {TEXT("K2Node_CallFunction_19"), TEXT("S")},
        {TEXT("K2Node_CallFunction_23"), TEXT("D")},
        {TEXT("K2Node_CallFunction_27"), TEXT("A")},
        {TEXT("K2Node_CallFunction_37"), TEXT("Tab")},
        {TEXT("K2Node_CallFunction_40"), TEXT("One")},
        {TEXT("K2Node_CallFunction_43"), TEXT("Two")},
        {TEXT("K2Node_CallFunction_46"), TEXT("Three")},
        {TEXT("K2Node_CallFunction_51"), TEXT("SpaceBar")},
        {TEXT("K2Node_CallFunction_57"), TEXT("SpaceBar")},
        {TEXT("K2Node_CallFunction_60"), TEXT("SpaceBar")},
        {TEXT("K2Node_CallFunction_63"), TEXT("LeftMouseButton")},
        {TEXT("K2Node_CallFunction_65"), TEXT("RightMouseButton")},
    };
    for (UEdGraphNode* Node : Graph->Nodes)
    {
        const FString* Key = Node ? Keys.Find(Node->GetName()) : nullptr;
        UEdGraphPin* Pin = Key ? Node->FindPin(TEXT("Key")) : nullptr;
        if (!Pin) continue;
        check(FKey(**Key).IsValid());
        Node->Modify();
        Pin->DefaultValue = *Key;
        ++Repaired;
    }
    if (Repaired) Blueprint->Modify();
#endif
    return Repaired;
}

int32 UBumpitKeyRepair::RepairHexCenter(UBlueprint* Blueprint)
{
    int32 Links = 0;
#if WITH_EDITOR
    UEdGraph* Graph = Blueprint ? FindFunctionGraph(Blueprint,TEXT("HexCenter")) : nullptr;
    if (!Graph) return 0;
    UEdGraphNode* FloatRow = FindNode(Graph,TEXT("K2Node_PromotableOperator_0"));
    UEdGraphNode* Entry = FindNode(Graph,TEXT("K2Node_FunctionEntry_0"));
    UEdGraphNode* Eight = FindNode(Graph,TEXT("K2Node_CallFunction_0"));
    UEdGraphNode* ColumnStep = FindNode(Graph,TEXT("K2Node_PromotableOperator_1"));
    UEdGraphNode* HalfRow = FindNode(Graph,TEXT("K2Node_PromotableOperator_3"));
    UEdGraphNode* RowParity = FindNode(Graph,TEXT("K2Node_PromotableOperator_5"));
    UEdGraphNode* RowOffset = FindNode(Graph,TEXT("K2Node_PromotableOperator_6"));
    if (!FloatRow || !Entry || !Eight || !ColumnStep || !HalfRow || !RowParity || !RowOffset) return 0;

    Graph->Modify();
    const int32 X = FloatRow->NodePosX, Y = FloatRow->NodePosY;
    FloatRow->BreakAllNodeLinks();
    Graph->RemoveNode(FloatRow);
    UK2Node_CallFunction* Row = AddMathCall(Graph,TEXT("Divide_IntInt"),X,Y);
    UK2Node_CallFunction* RowAsDouble = AddMathCall(Graph,TEXT("Conv_IntToDouble"),X+220,Y);

    const UEdGraphSchema* Schema = Graph->GetSchema();
    const auto Connect = [&](UEdGraphNode* From, const TCHAR* Output, UEdGraphNode* To, const TCHAR* Input)
    {
        UEdGraphPin* A = From->FindPin(Output);
        UEdGraphPin* B = To->FindPin(Input);
        if (A && B && Schema->TryCreateConnection(A,B)) ++Links;
        else UE_LOG(LogTemp,Error,TEXT("HexCenter link failed: %s.%s -> %s.%s"),*From->GetName(),Output,*To->GetName(),Input);
    };
    Connect(Entry,TEXT("Index"),Row,TEXT("A"));
    Connect(Eight,TEXT("ReturnValue"),Row,TEXT("B"));
    Connect(Row,TEXT("ReturnValue"),ColumnStep,TEXT("A"));
    Connect(Row,TEXT("ReturnValue"),HalfRow,TEXT("A"));
    Connect(Row,TEXT("ReturnValue"),RowParity,TEXT("A"));
    Connect(Row,TEXT("ReturnValue"),RowAsDouble,TEXT("InInt"));
    Connect(RowAsDouble,TEXT("ReturnValue"),RowOffset,TEXT("B"));
    Blueprint->Modify();
#endif
    return Links;
}
