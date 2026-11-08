#include "BumpitRoundSetup.h"
#include "BumpitBoardUi.h"
#include "BumpitRound.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "Engine/Font.h"
#include "Engine/FontFace.h"

#if WITH_EDITOR
#include "K2Node_CallFunction.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "Kismet/KismetMathLibrary.h"

namespace
{
UEdGraph* FindGraph(UBlueprint* Blueprint, const TCHAR* Name)
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

UK2Node_CallFunction* AddCall(UEdGraph* Graph, UFunction* Function, int32 X, int32 Y)
{
    FGraphNodeCreator<UK2Node_CallFunction> Creator(*Graph);
    UK2Node_CallFunction* Node = Creator.CreateNode();
    Node->SetFromFunction(Function);
    Node->NodePosX = X;
    Node->NodePosY = Y;
    Creator.Finalize();
    return Node;
}

UK2Node_CallFunction* AddRule(UEdGraph* Graph, const TCHAR* Function, int32 X, int32 Y)
{
    return AddCall(Graph,UBumpitRound::StaticClass()->FindFunctionByName(Function),X,Y);
}

UK2Node_VariableGet* AddSelfGet(UEdGraph* Graph, FName Variable, int32 X, int32 Y)
{
    FGraphNodeCreator<UK2Node_VariableGet> Creator(*Graph);
    UK2Node_VariableGet* Node = Creator.CreateNode();
    Node->VariableReference.SetSelfMember(Variable);
    Node->NodePosX = X;
    Node->NodePosY = Y;
    Creator.Finalize();
    return Node;
}

UK2Node_VariableSet* AddSelfSet(UEdGraph* Graph, FName Variable, int32 X, int32 Y)
{
    FGraphNodeCreator<UK2Node_VariableSet> Creator(*Graph);
    UK2Node_VariableSet* Node = Creator.CreateNode();
    Node->VariableReference.SetSelfMember(Variable);
    Node->NodePosX = X;
    Node->NodePosY = Y;
    Creator.Finalize();
    return Node;
}

UK2Node_IfThenElse* AddBranch(UEdGraph* Graph, int32 X, int32 Y)
{
    FGraphNodeCreator<UK2Node_IfThenElse> Creator(*Graph);
    UK2Node_IfThenElse* Node = Creator.CreateNode();
    Node->NodePosX = X;
    Node->NodePosY = Y;
    Creator.Finalize();
    return Node;
}
}
#endif

int32 UBumpitRoundSetup::ApplyRoundSystem(UBlueprint* Blueprint)
{
    int32 Links = 0;
#if WITH_EDITOR
    if (!Blueprint || !Blueprint->SkeletonGeneratedClass) return 0;
    UEdGraph* Settle = FindGraph(Blueprint,TEXT("Settle"));
    UEdGraph* NextStage = FindGraph(Blueprint,TEXT("NextStage"));
    UEdGraph* Render = FindGraph(Blueprint,TEXT("RenderBoard"));
    UEdGraph* Terminal = FindGraph(Blueprint,TEXT("DrawTerminal"));
    UEdGraph* Board = FindGraph(Blueprint,TEXT("UpdateBoard"));
    UEdGraph* Pointer = FindGraph(Blueprint,TEXT("PointerInput"));
    UEdGraph* EditCell = FindGraph(Blueprint,TEXT("EditCell"));
    UEdGraph* Purchase = FindGraph(Blueprint,TEXT("Purchase"));
    UEdGraph* Initialize = FindGraph(Blueprint,TEXT("InitializeBoard"));
    if (!Settle || !NextStage || !Render || !Terminal || !Board || !Pointer || !EditCell || !Purchase || !Initialize) return 0;

    UEdGraphNode* Score = FindNode(Settle,TEXT("K2Node_CallFunction_4"));
    UEdGraphNode* Reward = FindNode(Settle,TEXT("K2Node_CallFunction_5"));
    UEdGraphNode* AddCredits = FindNode(Settle,TEXT("K2Node_PromotableOperator_2"));
    UEdGraphNode* SetStation = FindNode(Settle,TEXT("K2Node_VariableSet_4"));
    UEdGraphNode* SetMessage = FindNode(Settle,TEXT("K2Node_VariableSet_5"));
    UEdGraphNode* PhaseCheck = FindNode(NextStage,TEXT("K2Node_IfThenElse_0"));
    UEdGraphNode* SetStage = FindNode(NextStage,TEXT("K2Node_VariableSet_0"));
    UEdGraphNode* SetNextStation = FindNode(NextStage,TEXT("K2Node_VariableSet_2"));
    UEdGraphNode* SetReadyMessage = FindNode(NextStage,TEXT("K2Node_VariableSet_3"));
    UEdGraphNode* BoardVisit = FindNode(Board,TEXT("K2Node_CallFunction_53"));
    UEdGraphNode* PointerVisit = FindNode(Pointer,TEXT("K2Node_CallFunction_15"));
    UEdGraphNode* EditGuard = FindNode(EditCell,TEXT("K2Node_IfThenElse_0"));
    UEdGraphNode* EditBlocked = FindNode(EditCell,TEXT("K2Node_CommutativeAssociativeBinaryOperator_1"));
    UEdGraphNode* BuyGuard = FindNode(Purchase,TEXT("K2Node_IfThenElse_0"));
    UEdGraphNode* BuyBlocked = FindNode(Purchase,TEXT("K2Node_CommutativeAssociativeBinaryOperator_1"));
    UEdGraphNode* SettleEntry = FindNode(Settle,TEXT("K2Node_FunctionEntry_0"));
    UEdGraphNode* EditEntry = FindNode(EditCell,TEXT("K2Node_FunctionEntry_0"));
    UEdGraphNode* SetTable = FindNode(Initialize,TEXT("K2Node_VariableSet_9"));
    UEdGraphNode* SpawnCamera = FindNode(Initialize,TEXT("K2Node_SpawnActorFromClass_3"));
    UEdGraphNode* HintLabel = FindNode(Render,TEXT("K2Node_CallFunction_7"));
    UEdGraphNode* AfterHint = FindNode(Render,TEXT("K2Node_IfThenElse_0"));
    UEdGraphNode* ContinueButton = FindNode(Terminal,TEXT("K2Node_CallFunction_10"));
    UFunction* Panel = Blueprint->SkeletonGeneratedClass->FindFunctionByName(TEXT("Panel"));
    UFunction* Label = Blueprint->SkeletonGeneratedClass->FindFunctionByName(TEXT("Label"));
    if (!Score || !Reward || !AddCredits || !SetStation || !SetMessage || !PhaseCheck || !SetStage
        || !SetNextStation || !SetReadyMessage || !BoardVisit || !PointerVisit || !EditGuard || !EditBlocked
        || !BuyGuard || !BuyBlocked || !SettleEntry || !EditEntry || !SetTable || !SpawnCamera
        || !HintLabel || !AfterHint || !ContinueButton || !Panel || !Label) return 0;

    const UEdGraphSchema* Schema = Settle->GetSchema();
    const auto Connect = [&](UEdGraphNode* From, const TCHAR* Output, UEdGraphNode* To, const TCHAR* Input)
    {
        UEdGraphPin* A = From->FindPin(Output);
        UEdGraphPin* B = To->FindPin(Input);
        if (A && B && Schema->TryCreateConnection(A,B)) ++Links;
        else UE_LOG(LogTemp,Error,TEXT("Round link failed: %s.%s -> %s.%s"),*From->GetName(),Output,*To->GetName(),Input);
    };

    // Settle: count the ball, use the rule's message, and apply the post-target credit rate.
    Settle->Modify();
    UK2Node_CallFunction* Record = AddRule(Settle,TEXT("RecordBall"),SetStation->NodePosX+200,SetStation->NodePosY+200);
    UK2Node_CallFunction* Adjust = AddRule(Settle,TEXT("AdjustCredits"),Reward->NodePosX+220,Reward->NodePosY+180);
    SetStation->FindPin(TEXT("then"))->BreakLinkTo(SetMessage->FindPin(TEXT("execute")));
    Connect(SetStation,TEXT("then"),Record,TEXT("execute"));
    Connect(Record,TEXT("then"),SetMessage,TEXT("execute"));
    Connect(Score,TEXT("Points"),Record,TEXT("Points"));
    Connect(Record,TEXT("ReturnValue"),SetMessage,TEXT("Message"));
    Connect(Reward,TEXT("Credits"),Adjust,TEXT("Base"));
    Connect(Adjust,TEXT("ReturnValue"),AddCredits,TEXT("B"));

    // Settle: score with this round's shuffled multiplier for the lane.
    UK2Node_CallFunction* LaneRate = AddRule(Settle,TEXT("LaneMultiplier"),Score->NodePosX-240,Score->NodePosY+220);
    Connect(SettleEntry,TEXT("Lane"),LaneRate,TEXT("Lane"));
    Connect(LaneRate,TEXT("ReturnValue"),Score,TEXT("Multiplier"));

    // InitializeBoard: roll the first multipliers as soon as the table exists.
    Initialize->Modify();
    UK2Node_CallFunction* StartRun = AddRule(Initialize,TEXT("StartRun"),SetTable->NodePosX+220,SetTable->NodePosY+200);
    UK2Node_VariableGet* NewTable = AddSelfGet(Initialize,TEXT("Table"),SetTable->NodePosX,SetTable->NodePosY+260);
    SetTable->FindPin(TEXT("then"))->BreakLinkTo(SpawnCamera->FindPin(TEXT("execute")));
    Connect(SetTable,TEXT("then"),StartRun,TEXT("execute"));
    Connect(StartRun,TEXT("then"),SpawnCamera,TEXT("execute"));
    Connect(NewTable,TEXT("Table"),StartRun,TEXT("Table"));

    // NextStage: restart after a game over, otherwise roll into the next round if cleared.
    NextStage->Modify();
    const int32 NX = PhaseCheck->NodePosX, NY = PhaseCheck->NodePosY + 260;
    UK2Node_CallFunction* IsOver = AddRule(NextStage,TEXT("IsGameOver"),NX,NY);
    UK2Node_IfThenElse* Branch = AddBranch(NextStage,NX+220,NY);
    UK2Node_CallFunction* Restart = AddRule(NextStage,TEXT("RestartGame"),NX+440,NY-120);
    UK2Node_CallFunction* Advance = AddRule(NextStage,TEXT("AdvanceRound"),NX+440,NY+120);
    UK2Node_VariableGet* Table = AddSelfGet(NextStage,TEXT("Table"),NX+220,NY+240);
    UK2Node_VariableGet* Cells = AddSelfGet(NextStage,TEXT("CellTypes"),NX+220,NY+340);
    PhaseCheck->FindPin(TEXT("else"))->BreakLinkTo(SetStage->FindPin(TEXT("execute")));
    Connect(IsOver,TEXT("ReturnValue"),Branch,TEXT("Condition"));
    Connect(PhaseCheck,TEXT("else"),Branch,TEXT("execute"));
    Connect(Branch,TEXT("then"),Restart,TEXT("execute"));
    Connect(Branch,TEXT("else"),Advance,TEXT("execute"));
    Connect(Advance,TEXT("then"),SetStage,TEXT("execute"));
    Connect(Table,TEXT("Table"),Advance,TEXT("Table"));
    Connect(Cells,TEXT("CellTypes"),Advance,TEXT("Cells"));

    // Back to the table while balls remain; the shop opens only for a new round.
    UK2Node_CallFunction* Ready = AddRule(NextStage,TEXT("ReadyMessage"),NX+660,NY+240);
    UK2Node_CallFunction* StationAfter = AddRule(NextStage,TEXT("NextStation"),NX+660,NY+120);
    Connect(Ready,TEXT("ReturnValue"),SetReadyMessage,TEXT("Message"));
    Connect(StationAfter,TEXT("ReturnValue"),SetNextStation,TEXT("Station"));
    Board->Modify();
    Pointer->Modify();
    UK2Node_CallFunction* BoardStation = AddRule(Board,TEXT("NextStation"),BoardVisit->NodePosX-240,BoardVisit->NodePosY+160);
    UK2Node_CallFunction* PointerStation = AddRule(Pointer,TEXT("NextStation"),PointerVisit->NodePosX-240,PointerVisit->NodePosY+160);
    Connect(BoardStation,TEXT("ReturnValue"),BoardVisit,TEXT("NewStation"));
    Connect(PointerStation,TEXT("ReturnValue"),PointerVisit,TEXT("NewStation"));

    // EditCell and Purchase: a locked board refuses changes and says why.
    UFunction* BooleanOr = UKismetMathLibrary::StaticClass()->FindFunctionByName(TEXT("BooleanOR"));
    const auto LockGuard = [&](UEdGraph* Graph, UEdGraphNode* Guard, UEdGraphNode* Blocked, UEdGraphNode* CellEntry)
    {
        Graph->Modify();
        const int32 GX = Guard->NodePosX, GY = Guard->NodePosY + 260;
        UK2Node_CallFunction* Locked = AddRule(Graph,CellEntry ? TEXT("IsCellLocked") : TEXT("IsBoardLocked"),GX-440,GY);
        UK2Node_CallFunction* Refuse = AddCall(Graph,BooleanOr,GX-220,GY);
        UK2Node_IfThenElse* Notice = AddBranch(Graph,GX+240,GY);
        UK2Node_VariableSet* Message = AddSelfSet(Graph,TEXT("Message"),GX+460,GY);
        Message->FindPin(TEXT("Message"))->DefaultValue = TEXT("구슬을 모두 쓸 때까지 판과 상점이 잠겨 있습니다.");
        if (CellEntry)
        {
            UK2Node_CallFunction* Reason = AddRule(Graph,TEXT("CellLockMessage"),GX+240,GY+160);
            Connect(CellEntry,TEXT("Index"),Locked,TEXT("Cell"));
            Connect(CellEntry,TEXT("Index"),Reason,TEXT("Cell"));
            Connect(Reason,TEXT("ReturnValue"),Message,TEXT("Message"));
        }
        Guard->FindPin(TEXT("Condition"))->BreakAllPinLinks();
        Connect(Blocked,TEXT("ReturnValue"),Refuse,TEXT("A"));
        Connect(Locked,TEXT("ReturnValue"),Refuse,TEXT("B"));
        Connect(Refuse,TEXT("ReturnValue"),Guard,TEXT("Condition"));
        Connect(Guard,TEXT("then"),Notice,TEXT("execute"));
        Connect(Locked,TEXT("ReturnValue"),Notice,TEXT("Condition"));
        Connect(Notice,TEXT("then"),Message,TEXT("execute"));
    };
    LockGuard(EditCell,EditGuard,EditBlocked,EditEntry);
    LockGuard(Purchase,BuyGuard,BuyBlocked,nullptr);

    // RenderBoard: always show round, score, and balls above the control hint.
    Render->Modify();
    const int32 RX = HintLabel->NodePosX, RY = HintLabel->NodePosY - 300;
    UK2Node_CallFunction* StatusPanel = AddCall(Render,Panel,RX,RY);
    UK2Node_CallFunction* StatusLabel = AddCall(Render,Label,RX+240,RY);
    UK2Node_CallFunction* Status = AddRule(Render,TEXT("StatusLine"),RX,RY-160);
    StatusPanel->FindPin(TEXT("X"))->DefaultValue = TEXT("32");
    StatusPanel->FindPin(TEXT("Y"))->DefaultValue = TEXT("44");
    StatusPanel->FindPin(TEXT("W"))->DefaultValue = TEXT("428");
    StatusPanel->FindPin(TEXT("H"))->DefaultValue = TEXT("34");
    StatusPanel->FindPin(TEXT("Tint"))->DefaultValue = TEXT("(R=0.012,G=0.022,B=0.037,A=1)");
    StatusLabel->FindPin(TEXT("X"))->DefaultValue = TEXT("43");
    StatusLabel->FindPin(TEXT("Y"))->DefaultValue = TEXT("48");
    StatusLabel->FindPin(TEXT("Size"))->DefaultValue = TEXT("1");
    StatusLabel->FindPin(TEXT("Tint"))->DefaultValue = TEXT("(R=1,G=0.66,B=0.19,A=1)");
    HintLabel->FindPin(TEXT("then"))->BreakLinkTo(AfterHint->FindPin(TEXT("execute")));
    Connect(HintLabel,TEXT("then"),StatusPanel,TEXT("execute"));
    Connect(StatusPanel,TEXT("then"),StatusLabel,TEXT("execute"));
    Connect(StatusLabel,TEXT("then"),AfterHint,TEXT("execute"));
    Connect(Status,TEXT("ReturnValue"),StatusLabel,TEXT("Caption"));

    // DrawTerminal: the continue button names what Space will do.
    Terminal->Modify();
    UK2Node_CallFunction* Continue = AddRule(Terminal,TEXT("ContinueLabel"),ContinueButton->NodePosX-260,ContinueButton->NodePosY+160);
    Connect(Continue,TEXT("ReturnValue"),ContinueButton,TEXT("Caption"));
    Blueprint->Modify();
#endif
    return Links;
}

void UBumpitRoundSetup::ConfigureUiFont(UFont* Font, UFontFace* Face, int32 Size)
{
#if WITH_EDITOR
    if (!Font || !Face) return;
    Font->Modify();
    Font->FontCacheType = EFontCacheType::Runtime;
    Font->LegacyFontSize = Size;
    FTypeface& Typeface = Font->GetMutableInternalCompositeFont().DefaultTypeface;
    Typeface.Fonts.Reset();
    FTypefaceEntry& Entry = Typeface.Fonts.AddDefaulted_GetRef();
    Entry.Name = TEXT("Regular");
    Entry.Font = FFontData(Face);
    Font->PostEditChange();
#endif
}

int32 UBumpitRoundSetup::ApplyUiStyle(UBlueprint* Blueprint, UFont* Font)
{
    int32 Changed = 0;
#if WITH_EDITOR
    if (!Blueprint || !Font) return 0;
    const TMap<FString, FString> Palette = {
        {TEXT("(R=0.012,G=0.022,B=0.037,A=1)"), TEXT("(R=0.016,G=0.01,B=0.008,A=0.86)")},  // panels: burnt black
        {TEXT("(R=0.032,G=0.055,B=0.08,A=1)"), TEXT("(R=0.05,G=0.026,B=0.018,A=0.9)")},    // inner panels
        {TEXT("(R=0.065,G=0.105,B=0.145,A=1)"), TEXT("(R=0.12,G=0.06,B=0.035,A=1)")},      // bars and buttons: rust
        {TEXT("(R=0.9,G=0.94,B=0.96,A=1)"), TEXT("(R=0.86,G=0.79,B=0.66,A=1)")},           // text: old bone
        {TEXT("(R=0.49,G=0.62,B=0.68,A=1)"), TEXT("(R=0.56,G=0.46,B=0.36,A=1)")},          // muted text
        {TEXT("(R=0.2,G=0.94,B=0.69,A=1)"), TEXT("(R=0.95,G=0.36,B=0.16,A=1)")},           // accent: ember
        {TEXT("(R=1,G=0.66,B=0.19,A=1)"), TEXT("(R=0.92,G=0.62,B=0.22,A=1)")},             // numbers: tarnished brass
        {TEXT("(R=0.98,G=0.37,B=0.3,A=1)"), TEXT("(R=0.8,G=0.12,B=0.08,A=1)")},            // warnings: dried red
    };
    for (UEdGraph* Graph : Blueprint->FunctionGraphs)
    {
        if (!Graph) continue;
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            if (!Node) continue;
            for (UEdGraphPin* Pin : Node->Pins)
            {
                const FString* Color = Pin ? Palette.Find(Pin->DefaultValue) : nullptr;
                if (!Color) continue;
                Node->Modify();
                Pin->DefaultValue = *Color;
                ++Changed;
            }
        }
    }
    UEdGraph* LabelGraph = FindGraph(Blueprint,TEXT("Label"));
    UEdGraphNode* DrawText = LabelGraph ? FindNode(LabelGraph,TEXT("K2Node_CallFunction_0")) : nullptr;
    UEdGraphPin* FontPin = DrawText ? DrawText->FindPin(TEXT("Font")) : nullptr;
    if (!FontPin) return 0;
    DrawText->Modify();
    FontPin->DefaultObject = Font;
    Blueprint->Modify();
#endif
    return Changed;
}

int32 UBumpitRoundSetup::ApplyShopArrow(UBlueprint* Blueprint)
{
    int32 Links = 0;
#if WITH_EDITOR
    UEdGraph* Board = Blueprint ? FindGraph(Blueprint,TEXT("UpdateBoard")) : nullptr;
    UEdGraphNode* UpdateView = Board ? FindNode(Board,TEXT("K2Node_CallFunction_0")) : nullptr;
    UEdGraphPin* ViewEntry = UpdateView ? UpdateView->FindPin(TEXT("execute")) : nullptr;
    UFunction* Clicked = UBumpitBoardUi::StaticClass()->FindFunctionByName(TEXT("ShopArrowClicked"));
    UFunction* Visit = Blueprint && Blueprint->SkeletonGeneratedClass
        ? Blueprint->SkeletonGeneratedClass->FindFunctionByName(TEXT("Visit")) : nullptr;
    if (!ViewEntry || ViewEntry->LinkedTo.Num() != 1 || !Clicked || !Visit) return 0;

    UEdGraphPin* Previous = ViewEntry->LinkedTo[0];
    const UEdGraphSchema* Schema = Board->GetSchema();
    const auto Link = [&](UEdGraphPin* A, UEdGraphPin* B)
    {
        if (A && B && Schema->TryCreateConnection(A,B)) ++Links;
        else UE_LOG(LogTemp,Error,TEXT("Shop arrow link failed"));
    };
    Board->Modify();
    const int32 X = UpdateView->NodePosX, Y = UpdateView->NodePosY - 700;
    UK2Node_VariableGet* Station = AddSelfGet(Board,TEXT("Station"),X-440,Y);
    UK2Node_CallFunction* Arrow = AddCall(Board,Clicked,X-220,Y);
    UK2Node_IfThenElse* Branch = AddBranch(Board,X,Y);
    UK2Node_CallFunction* GoShop = AddCall(Board,Visit,X+220,Y);
    GoShop->FindPin(TEXT("NewStation"))->DefaultValue = TEXT("2");
    Previous->BreakLinkTo(ViewEntry);
    Link(Station->FindPin(TEXT("Station")),Arrow->FindPin(TEXT("Station")));
    Link(Arrow->FindPin(TEXT("ReturnValue")),Branch->FindPin(TEXT("Condition")));
    Link(Previous,Branch->FindPin(TEXT("execute")));
    Link(Branch->FindPin(TEXT("then")),GoShop->FindPin(TEXT("execute")));
    Link(Branch->FindPin(TEXT("else")),ViewEntry);
    Link(GoShop->FindPin(TEXT("then")),ViewEntry);
    Blueprint->Modify();
#endif
    return Links;
}

int32 UBumpitRoundSetup::ApplyShopReturn(UBlueprint* Blueprint)
{
    int32 Links = 0;
#if WITH_EDITOR
    UEdGraph* Shop = Blueprint ? FindGraph(Blueprint,TEXT("DrawShop")) : nullptr;
    UEdGraph* Board = Blueprint ? FindGraph(Blueprint,TEXT("UpdateBoard")) : nullptr;
    UEdGraphNode* LastLabel = Shop ? FindNode(Shop,TEXT("K2Node_CallFunction_32")) : nullptr;
    UFunction* DrawArrow = UBumpitBoardUi::StaticClass()->FindFunctionByName(TEXT("DrawTableArrow"));
    UFunction* ArrowStation = UBumpitBoardUi::StaticClass()->FindFunctionByName(TEXT("ArrowStation"));
    if (!Board || !LastLabel || !DrawArrow || !ArrowStation) return 0;

    // UpdateBoard: follow the existing arrow branch to the Visit call it fires.
    UEdGraphPin* NewStation = nullptr;
    for (UEdGraphNode* Node : Board->Nodes)
    {
        const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node);
        if (!Call || Call->GetFunctionName() != TEXT("ShopArrowClicked")) continue;
        UEdGraphPin* Clicked = Node->FindPin(TEXT("ReturnValue"));
        UEdGraphNode* Branch = Clicked && Clicked->LinkedTo.Num() == 1 ? Clicked->LinkedTo[0]->GetOwningNode() : nullptr;
        UEdGraphPin* Then = Branch ? Branch->FindPin(TEXT("then")) : nullptr;
        NewStation = Then && Then->LinkedTo.Num() == 1 ? Then->LinkedTo[0]->GetOwningNode()->FindPin(TEXT("NewStation")) : nullptr;
    }
    if (!NewStation) return 0;

    const UEdGraphSchema* Schema = Shop->GetSchema();
    const auto Link = [&](UEdGraphPin* A, UEdGraphPin* B)
    {
        if (A && B && Schema->TryCreateConnection(A,B)) ++Links;
        else UE_LOG(LogTemp,Error,TEXT("Shop return link failed"));
    };
    Shop->Modify();
    Board->Modify();
    const int32 X = LastLabel->NodePosX, Y = LastLabel->NodePosY + 260;
    UK2Node_CallFunction* Arrow = AddCall(Shop,DrawArrow,X+240,Y);
    UK2Node_VariableGet* Scale = AddSelfGet(Shop,TEXT("ScaleHUD"),X,Y);
    UK2Node_VariableGet* OffsetX = AddSelfGet(Shop,TEXT("OffsetX"),X,Y+80);
    UK2Node_VariableGet* OffsetY = AddSelfGet(Shop,TEXT("OffsetY"),X,Y+160);
    Link(LastLabel->FindPin(TEXT("then")),Arrow->FindPin(TEXT("execute")));
    Link(Scale->FindPin(TEXT("ScaleHUD")),Arrow->FindPin(TEXT("Scale")));
    Link(OffsetX->FindPin(TEXT("OffsetX")),Arrow->FindPin(TEXT("OffsetX")));
    Link(OffsetY->FindPin(TEXT("OffsetY")),Arrow->FindPin(TEXT("OffsetY")));
    const UEdGraphNode* Visit = NewStation->GetOwningNode();
    UK2Node_VariableGet* Station = AddSelfGet(Board,TEXT("Station"),Visit->NodePosX-440,Visit->NodePosY+160);
    UK2Node_CallFunction* Destination = AddCall(Board,ArrowStation,Visit->NodePosX-220,Visit->NodePosY+160);
    Link(Station->FindPin(TEXT("Station")),Destination->FindPin(TEXT("Station")));
    Link(Destination->FindPin(TEXT("ReturnValue")),NewStation);
    Blueprint->Modify();
#endif
    return Links;
}

int32 UBumpitRoundSetup::ApplyRoomViews(UBlueprint* Blueprint)
{
    int32 Changes = 0;
#if WITH_EDITOR
    if (!Blueprint) return 0;
    const auto SetPin = [&](const TCHAR* GraphName, const TCHAR* NodeName, const TCHAR* PinName, double Value)
    {
        UEdGraph* Graph = FindGraph(Blueprint,GraphName);
        UEdGraphNode* Node = Graph ? FindNode(Graph,NodeName) : nullptr;
        UEdGraphPin* Pin = Node ? Node->FindPin(PinName) : nullptr;
        if (!Pin)
        {
            UE_LOG(LogTemp,Error,TEXT("Room view pin missing: %s.%s.%s"),GraphName,NodeName,PinName);
            return;
        }
        Node->Modify();
        Pin->DefaultValue = FString::SanitizeFloat(Value);
        ++Changes;
    };
    const auto SetVector = [&](const TCHAR* GraphName, const TCHAR* NodeName, double X, double Y, double Z)
    {
        SetPin(GraphName,NodeName,TEXT("X"),X);
        SetPin(GraphName,NodeName,TEXT("Y"),Y);
        SetPin(GraphName,NodeName,TEXT("Z"),Z);
    };
    // The opening view stands inside the new walls.
    SetVector(TEXT("Visit"),TEXT("K2Node_CallFunction_4"),-900,-340,160);
    // Settlement looks up at the score screen instead of the terminal behind the wall.
    SetVector(TEXT("Visit"),TEXT("K2Node_CallFunction_12"),-280,0,175);
    SetVector(TEXT("Visit"),TEXT("K2Node_CallFunction_13"),431,0,345);
    // Walking away from it lands in front of the machine, not behind the wall.
    SetVector(TEXT("Walk"),TEXT("K2Node_CallFunction_11"),-532,0,160);
    SetVector(TEXT("Walk"),TEXT("K2Node_CallFunction_12"),100,0,20);
    // The floor now ends at the side walls.
    SetPin(TEXT("ClearFloor"),TEXT("K2Node_CallFunction_5"),TEXT("Value"),375);
    // The terminal is walled off, so looking its way must not click it. Its box moves out of reach.
    SetVector(TEXT("Focus"),TEXT("K2Node_CallFunction_8"),9000,9000,9000);
    SetPin(TEXT("Focus"),TEXT("K2Node_CallFunction_9"),TEXT("X"),9100);
    SetPin(TEXT("Focus"),TEXT("K2Node_CallFunction_9"),TEXT("Y"),9100);
    SetPin(TEXT("Focus"),TEXT("K2Node_CallFunction_9"),TEXT("Z"),9100);

    // DrawTerminal: only the settlement prompt remains; the score is on the screen in the room.
    UEdGraph* Terminal = FindGraph(Blueprint,TEXT("DrawTerminal"));
    UEdGraphNode* Entry = Terminal ? FindNode(Terminal,TEXT("K2Node_FunctionEntry_0")) : nullptr;
    UFunction* Draw = UBumpitBoardUi::StaticClass()->FindFunctionByName(TEXT("DrawSettlement"));
    if (!Entry || !Draw) return 0;
    const UEdGraphSchema* Schema = Terminal->GetSchema();
    const auto Link = [&](UEdGraphPin* A, UEdGraphPin* B)
    {
        if (A && B && Schema->TryCreateConnection(A,B)) ++Changes;
        else UE_LOG(LogTemp,Error,TEXT("Settlement link failed"));
    };
    Terminal->Modify();
    const int32 X = Entry->NodePosX, Y = Entry->NodePosY-400;
    UK2Node_CallFunction* Prompt = AddCall(Terminal,Draw,X+240,Y);
    UK2Node_VariableGet* Scale = AddSelfGet(Terminal,TEXT("ScaleHUD"),X,Y);
    UK2Node_VariableGet* OffsetX = AddSelfGet(Terminal,TEXT("OffsetX"),X,Y+80);
    UK2Node_VariableGet* OffsetY = AddSelfGet(Terminal,TEXT("OffsetY"),X,Y+160);
    UEdGraphPin* Then = Entry->FindPin(TEXT("then"));
    Then->BreakAllPinLinks();
    Link(Then,Prompt->FindPin(TEXT("execute")));
    Link(Scale->FindPin(TEXT("ScaleHUD")),Prompt->FindPin(TEXT("Scale")));
    Link(OffsetX->FindPin(TEXT("OffsetX")),Prompt->FindPin(TEXT("OffsetX")));
    Link(OffsetY->FindPin(TEXT("OffsetY")),Prompt->FindPin(TEXT("OffsetY")));
    Blueprint->Modify();
#endif
    return Changes;
}

int32 UBumpitRoundSetup::ApplyWordText(UBlueprint* Blueprint)
{
    int32 Changed = 0;
#if WITH_EDITOR
    if (!Blueprint) return 0;
    const TMap<FString, FString> Lines = {
        {TEXT("작업실   /   개조 핀볼 머신 및 정산 단말기"), TEXT("CELL 08")},
        {TEXT("가운데 +를 기계에 맞추고 클릭해 가까이 보세요."), TEXT("기계 조준 · 클릭")},
        {TEXT("기계를 클릭해 가까이 보세요. 시선을 돌리려면 R을 누르세요."), TEXT("기계 조준 · 클릭")},
        {TEXT("구매 후 [1] 핀볼대로 이동"), TEXT("[1] 기계")},
        {TEXT("Space를 눌렀다 떼면 발사"), TEXT("Space  충전 · 발사")},
        {TEXT("좌클릭 배치 / 이동   ·   우클릭 회수"), TEXT("좌클릭 배치   ·   우클릭 회수")},
        {TEXT("장애물을 보관함에 회수했습니다."), TEXT("회수")},
        {TEXT("옮길 빈 칸을 클릭하세요."), TEXT("빈 칸 선택")},
        {TEXT("상점에서 장애물을 먼저 구매하세요."), TEXT("재고 없음")},
        {TEXT("배치 완료. 준비되면 발사하세요."), TEXT("배치 완료")},
        {TEXT("상점에서 첫 장애물을 구매하세요."), TEXT("범퍼 구매")},
        {TEXT("선택한 부품을 빈 칸에 배치하세요."), TEXT("빈 칸 선택")},
        {TEXT("크레딧이 부족합니다."), TEXT("크레딧 부족")},
        {TEXT("빈 칸을 클릭해 배치하세요."), TEXT("빈 칸 선택")},
        {TEXT("구슬을 모두 쓸 때까지 판과 상점이 잠겨 있습니다."), TEXT("판 잠김")},
        {TEXT("공이 이동하고 있습니다."), TEXT("구슬 이동")},
        // The earlier sentence-style text, for HUDs that already went through it.
        {TEXT("기계를 조준하고 눌러라."), TEXT("기계 조준 · 클릭")},
        {TEXT("[1] 기계로"), TEXT("[1] 기계")},
        {TEXT("Space. 놓으면 쏜다."), TEXT("Space  충전 · 발사")},
        {TEXT("회수."), TEXT("회수")},
        {TEXT("놓을 칸."), TEXT("빈 칸 선택")},
        {TEXT("재고 없음."), TEXT("재고 없음")},
        {TEXT("놓았다."), TEXT("배치 완료")},
        {TEXT("범퍼를 사라."), TEXT("범퍼 구매")},
        {TEXT("돈이 없다."), TEXT("크레딧 부족")},
        {TEXT("구슬을 다 쓸 때까지 못 건드린다."), TEXT("판 잠김")},
        {TEXT("굴러간다."), TEXT("구슬 이동")},
    };
    for (UEdGraph* Graph : Blueprint->FunctionGraphs)
    {
        if (!Graph) continue;
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            if (!Node) continue;
            for (UEdGraphPin* Pin : Node->Pins)
            {
                const FString* Line = Pin ? Lines.Find(Pin->DefaultValue) : nullptr;
                if (!Line) continue;
                Node->Modify();
                Pin->DefaultValue = *Line;
                ++Changed;
            }
        }
    }
    if (Changed) Blueprint->Modify();
#endif
    return Changed;
}

int32 UBumpitRoundSetup::ApplyBumperSlots(UBlueprint* Blueprint)
{
    int32 Links = 0;
#if WITH_EDITOR
    if (!Blueprint) return 0;
    UEdGraph* Board = FindGraph(Blueprint,TEXT("UpdateBoard"));
    UEdGraph* Table = FindGraph(Blueprint,TEXT("DrawTable"));
    if (!Board || !Table) return 0;
    UEdGraphNode* Entry = FindNode(Board,TEXT("K2Node_FunctionEntry_0"));
    UEdGraphNode* UpdateView = FindNode(Board,TEXT("K2Node_CallFunction_0"));
    UEdGraphNode* LastLabel = FindNode(Table,TEXT("K2Node_CallFunction_9"));
    UEdGraphNode* LaneLoop = FindNode(Table,TEXT("K2Node_MacroInstance_0"));
    UFunction* NextSelection = UBumpitBoardUi::StaticClass()->FindFunctionByName(TEXT("NextSelection"));
    UFunction* DrawSlots = UBumpitBoardUi::StaticClass()->FindFunctionByName(TEXT("DrawBumperSlots"));
    if (!Entry || !UpdateView || !LastLabel || !LaneLoop || !NextSelection || !DrawSlots) return 0;

    const UEdGraphSchema* Schema = Board->GetSchema();
    const auto Connect = [&](UEdGraphNode* From, const TCHAR* Output, UEdGraphNode* To, const TCHAR* Input)
    {
        UEdGraphPin* A = From->FindPin(Output);
        UEdGraphPin* B = To->FindPin(Input);
        if (A && B && Schema->TryCreateConnection(A,B)) ++Links;
        else UE_LOG(LogTemp,Error,TEXT("Slot link failed: %s.%s -> %s.%s"),*From->GetName(),Output,*To->GetName(),Input);
    };

    // UpdateBoard: apply the wheel before anything else reads the selection.
    Board->Modify();
    const int32 BX = Entry->NodePosX, BY = Entry->NodePosY - 300;
    UK2Node_VariableGet* Station = AddSelfGet(Board,TEXT("Station"),BX,BY);
    UK2Node_VariableGet* Selected = AddSelfGet(Board,TEXT("Selected"),BX,BY+100);
    UK2Node_CallFunction* Wheel = AddCall(Board,NextSelection,BX+220,BY);
    UK2Node_VariableSet* SetSelected = AddSelfSet(Board,TEXT("Selected"),BX+480,BY);
    Entry->FindPin(TEXT("then"))->BreakLinkTo(UpdateView->FindPin(TEXT("execute")));
    Connect(Entry,TEXT("then"),SetSelected,TEXT("execute"));
    Connect(SetSelected,TEXT("then"),UpdateView,TEXT("execute"));
    Connect(Station,TEXT("Station"),Wheel,TEXT("Station"));
    Connect(Selected,TEXT("Selected"),Wheel,TEXT("Selected"));
    Connect(Wheel,TEXT("ReturnValue"),SetSelected,TEXT("Selected"));

    // DrawTable: draw the slots and drop the old screen-space lane labels,
    // which are now engraved on the table itself.
    Table->Modify();
    const int32 TX = LastLabel->NodePosX, TY = LastLabel->NodePosY + 260;
    UK2Node_CallFunction* Slots = AddCall(Table,DrawSlots,TX+240,TY);
    UK2Node_VariableGet* TableSelected = AddSelfGet(Table,TEXT("Selected"),TX,TY);
    UK2Node_VariableGet* Stock = AddSelfGet(Table,TEXT("Stock"),TX,TY+80);
    UK2Node_VariableGet* Scale = AddSelfGet(Table,TEXT("ScaleHUD"),TX,TY+160);
    UK2Node_VariableGet* OffsetX = AddSelfGet(Table,TEXT("OffsetX"),TX,TY+240);
    UK2Node_VariableGet* OffsetY = AddSelfGet(Table,TEXT("OffsetY"),TX,TY+320);
    LastLabel->FindPin(TEXT("then"))->BreakLinkTo(LaneLoop->FindPin(TEXT("execute")));
    Connect(LastLabel,TEXT("then"),Slots,TEXT("execute"));
    Connect(TableSelected,TEXT("Selected"),Slots,TEXT("Selected"));
    Connect(Stock,TEXT("Stock"),Slots,TEXT("Stock"));
    Connect(Scale,TEXT("ScaleHUD"),Slots,TEXT("Scale"));
    Connect(OffsetX,TEXT("OffsetX"),Slots,TEXT("OffsetX"));
    Connect(OffsetY,TEXT("OffsetY"),Slots,TEXT("OffsetY"));
    Blueprint->Modify();
#endif
    return Links;
}
