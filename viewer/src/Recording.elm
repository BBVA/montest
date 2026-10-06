module Recording exposing (Attempt, CriterionResult(..), Event(..), Integer(..), Recording, decode, integerText, isSafe)

import Array exposing (Array)
import Dict
import Json.Decode as Decode exposing (Decoder)


type Integer
    = Safe Float
    | Unsafe Float


type alias Recording =
    { events : Array Event
    , eventJson : Array String
    , sources : Array Decode.Value
    }


type Event
    = RunStart { runId : String, metadata : Decode.Value }
    | Sample Attempt
    | ObservationError Attempt
    | RunEnd { status : String, decision : Maybe String, nObserved : Integer, reason : Maybe String, errorType : Maybe String }


type alias Attempt =
    { position : Int
    , index : Integer
    , raw : Decode.Value
    , observed : Decode.Value
    , metadata : Decode.Value
    , result : Maybe CriterionResult
    , errorType : Maybe String
    }


type CriterionResult
    = Observation { index : Integer, decision : String }
    | Sprt { index : Integer, decision : String, llr : Float, lower : Float, upper : Float, nObserved : Integer }
    | Composite { index : Integer, decision : String, results : List ( String, Maybe CriterionResult ), terminalResults : List ( String, CriterionResult ), nDecided : Integer, nTotal : Integer }


maxSafe : Float
maxSafe =
    9007199254740991


isSafe : Integer -> Bool
isSafe value =
    case value of
        Safe _ ->
            True

        Unsafe _ ->
            False


integerText : Integer -> String
integerText value =
    case value of
        Safe number ->
            formatInteger number

        Unsafe _ ->
            "Evidence outside JavaScript numeric range"


formatInteger : Float -> String
formatInteger number =
    let
        text =
            String.fromFloat number
    in
    if String.endsWith ".0" text then
        String.dropRight 2 text

    else
        text


decode : Decode.Value -> Result Decode.Error Recording
decode value =
    Decode.decodeValue flagsDecoder value


flagsDecoder : Decoder Recording
flagsDecoder =
    Decode.map3 (\events json sources -> ( events, json, sources ))
        (Decode.field "events" (Decode.list eventDecoder))
        (Decode.field "event_json" (Decode.list Decode.string))
        (Decode.field "events" (Decode.list Decode.value))
        |> Decode.andThen
            (\( events, json, sources ) ->
                if List.length events /= List.length json then
                    Decode.fail "events and event_json must have equal lengths"

                else if validOrder events then
                    Decode.succeed (makeRecording events json sources)

                else
                    Decode.fail "invalid run event order"
            )


makeRecording : List Event -> List String -> List Decode.Value -> Recording
makeRecording events json sources =
    { events = events |> List.indexedMap attachPosition |> Array.fromList
    , eventJson = Array.fromList json
    , sources = Array.fromList sources
    }


attachPosition : Int -> Event -> Event
attachPosition position event =
    case event of
        Sample attempt ->
            Sample { attempt | position = position }

        ObservationError attempt ->
            ObservationError { attempt | position = position }

        _ ->
            event


validOrder : List Event -> Bool
validOrder events =
    case events of
        (RunStart _) :: rest ->
            validAfterStart False -1 -1 rest

        _ ->
            False


validAfterStart : Bool -> Float -> Float -> List Event -> Bool
validAfterStart ended lastAttempt lastSample events =
    case events of
        [] ->
            True

        event :: rest ->
            case event of
                RunStart _ ->
                    False

                RunEnd _ ->
                    not ended && validAfterStart True lastAttempt lastSample rest

                Sample attempt ->
                    not ended && integerNumber attempt.index >= lastAttempt && integerNumber attempt.index > lastSample && validAfterStart ended (integerNumber attempt.index) (integerNumber attempt.index) rest

                ObservationError attempt ->
                    not ended && integerNumber attempt.index >= lastAttempt && validAfterStart ended (integerNumber attempt.index) lastSample rest


eventDecoder : Decoder Event
eventDecoder =
    Decode.field "type" Decode.string |> Decode.andThen eventForType


eventForType : String -> Decoder Event
eventForType kind =
    case kind of
        "run_start" ->
            Decode.map3 (\schema runId metadata -> RunStart { runId = runId, metadata = metadata })
                (Decode.field "schema_version" versionDecoder)
                (Decode.field "run_id" Decode.string)
                (Decode.field "metadata" objectValue)

        "sample" ->
            Decode.map Sample attemptDecoder

        "observation_error" ->
            Decode.map ObservationError errorAttemptDecoder

        "run_end" ->
            Decode.map5 (\status decision nObserved reason errorType -> RunEnd { status = status, decision = decision, nObserved = nObserved, reason = reason, errorType = errorType })
                (Decode.field "status" Decode.string)
                (Decode.field "decision" (Decode.nullable terminalDecisionDecoder))
                (Decode.field "n_observed" nonnegativeInteger)
                (Decode.field "reason" (Decode.nullable Decode.string))
                (Decode.field "error_type" (Decode.nullable Decode.string))
                |> Decode.andThen validateEnd

        _ ->
            Decode.fail "unsupported event type"


validateEnd : Event -> Decoder Event
validateEnd event =
    case event of
        RunEnd ending ->
            let
                valid =
                    case ending.status of
                        "terminal" ->
                            ending.decision /= Nothing && ending.reason == Nothing && ending.errorType == Nothing

                        "incomplete" ->
                            List.member ending.reason [ Just "unobserved_sample", Just "no_terminal_decision" ] && ending.errorType == Nothing

                        "error" ->
                            ending.errorType /= Nothing && ending.reason == Nothing

                        _ ->
                            False
            in
            if valid then
                Decode.succeed event

            else
                Decode.fail "invalid run_end lifecycle fields"

        _ ->
            Decode.fail "expected run_end"


integerNumber : Integer -> Float
integerNumber value =
    case value of
        Safe number ->
            number

        Unsafe number ->
            number


attemptDecoder : Decoder Attempt
attemptDecoder =
    Decode.map5 (\index raw observed metadata result -> { position = -1, index = index, raw = raw, observed = observed, metadata = metadata, result = Just result, errorType = Nothing })
        (Decode.field "index" nonnegativeInteger)
        (Decode.field "raw" Decode.value)
        (Decode.field "observed" Decode.value)
        (Decode.field "metadata" objectValue)
        (Decode.field "result" resultDecoder)


errorAttemptDecoder : Decoder Attempt
errorAttemptDecoder =
    Decode.map5 (\index raw observed metadata errorType -> { position = -1, index = index, raw = raw, observed = observed, metadata = metadata, result = Nothing, errorType = Just errorType })
        (Decode.field "index" nonnegativeInteger)
        (Decode.field "raw" Decode.value)
        (Decode.field "observed" Decode.value)
        (Decode.field "metadata" objectValue)
        (Decode.field "error_type" Decode.string)


resultDecoder : Decoder CriterionResult
resultDecoder =
    Decode.field "kind" Decode.string |> Decode.andThen resultForKind


resultForKind : String -> Decoder CriterionResult
resultForKind kind =
    case kind of
        "observation" ->
            Decode.map2 (\index decision -> Observation { index = index, decision = decision })
                (Decode.field "index" integer)
                (Decode.field "decision" decisionDecoder)

        "sprt" ->
            Decode.map6 (\index decision llr lower upper nObserved -> Sprt { index = index, decision = decision, llr = llr, lower = lower, upper = upper, nObserved = nObserved })
                (Decode.field "index" integer)
                (Decode.field "decision" decisionDecoder)
                (Decode.field "cumulative_llr" Decode.float)
                (Decode.field "lower_bound" Decode.float)
                (Decode.field "upper_bound" Decode.float)
                (Decode.field "n_observed" integer)

        "composite" ->
            Decode.map6 (\index decision results terminalResults nDecided nTotal -> Composite { index = index, decision = decision, results = results, terminalResults = terminalResults, nDecided = nDecided, nTotal = nTotal })
                (Decode.field "index" integer)
                (Decode.field "decision" decisionDecoder)
                (Decode.field "results" childrenDecoder)
                (Decode.field "terminal_results" terminalChildrenDecoder)
                (Decode.field "n_decided" integer)
                (Decode.field "n_total" integer)

        _ ->
            Decode.fail "unsupported result kind"


childrenDecoder : Decoder (List ( String, Maybe CriterionResult ))
childrenDecoder =
    Decode.dict (Decode.nullable resultDecoder) |> Decode.map Dict.toList


terminalChildrenDecoder : Decoder (List ( String, CriterionResult ))
terminalChildrenDecoder =
    Decode.dict resultDecoder |> Decode.map Dict.toList


objectValue : Decoder Decode.Value
objectValue =
    Decode.map2 (\value _ -> value) Decode.value (Decode.dict Decode.value)


decisionDecoder : Decoder String
decisionDecoder =
    Decode.string
        |> Decode.andThen
            (\decision ->
                if List.member decision [ "continue", "accept_h0", "accept_h1", "inconclusive" ] then
                    Decode.succeed decision

                else
                    Decode.fail "unknown decision"
            )


terminalDecisionDecoder : Decoder String
terminalDecisionDecoder =
    decisionDecoder
        |> Decode.andThen
            (\decision ->
                if decision == "continue" then
                    Decode.fail "terminal decision cannot continue"

                else
                    Decode.succeed decision
            )


versionDecoder : Decoder Integer
versionDecoder =
    integer
        |> Decode.andThen
            (\version ->
                case version of
                    Safe number ->
                        if number == 1 then
                            Decode.succeed version

                        else
                            Decode.fail "unsupported schema version"

                    _ ->
                        Decode.fail "unsupported schema version"
            )


integer : Decoder Integer
integer =
    Decode.float
        |> Decode.andThen
            (\number ->
                if isNaN number then
                    Decode.fail "expected integer"

                else if isInfinite number then
                    Decode.succeed (Unsafe number)

                else if toFloat (round number) == number then
                    Decode.succeed
                        (if abs number <= maxSafe then
                            Safe number

                         else
                            Unsafe number
                        )

                else
                    Decode.fail "expected integer"
            )


nonnegativeInteger : Decoder Integer
nonnegativeInteger =
    integer
        |> Decode.andThen
            (\value ->
                case value of
                    Safe number ->
                        if number >= 0 then
                            Decode.succeed value

                        else
                            Decode.fail "expected nonnegative integer"

                    Unsafe number ->
                        if number >= 0 then
                            Decode.succeed value

                        else
                            Decode.fail "expected nonnegative integer"
            )
