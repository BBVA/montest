module Evidence exposing (CriterionEvidence, EvidencePoint, PointOrigin(..), Report, Trace, hierarchyLabel, project)

import Array
import Dict exposing (Dict)
import Json.Decode
import Json.Encode
import Recording exposing (Attempt, CriterionResult(..), Event(..), Integer(..), Recording)


type PointOrigin
    = SampleOrigin Int
    | RetainedOrigin


type alias EvidencePoint =
    { path : List String
    , index : Integer
    , llr : Float
    , lower : Float
    , upper : Float
    , nObserved : Integer
    , decision : String
    , origin : PointOrigin
    , sourcePosition : Int
    , connected : Bool
    , numericSafe : Bool
    }


type alias Trace =
    { path : List String, points : List EvidencePoint }


type alias CriterionEvidence =
    { path : List String, index : Integer, decision : String, kind : String, sourcePosition : Int, numericSafe : Bool }


type alias Report =
    { runId : String
    , metadata : Maybe Json.Decode.Value
    , startPosition : Maybe Int
    , status : String
    , decision : Maybe String
    , reportedCount : Maybe Integer
    , endReason : Maybe String
    , endErrorType : Maybe String
    , errorCount : Int
    , sampleCount : Int
    , attempts : List Attempt
    , hierarchy : List (List String)
    , traces : List Trace
    , criteria : List CriterionEvidence
    , missingEvidence : Bool
    , resultRange : Maybe ( Float, Float )
    }


type alias State =
    { runId : String
    , metadata : Maybe Json.Decode.Value
    , startPosition : Maybe Int
    , status : String
    , decision : Maybe String
    , reportedCount : Maybe Integer
    , endReason : Maybe String
    , endErrorType : Maybe String
    , errorCount : Int
    , sampleCount : Int
    , attempts : List Attempt
    , hierarchy : Dict (List String) ()
    , traces : Dict (List String) Trace
    , criteria : Dict (List String) CriterionEvidence
    , previousSample : Maybe Attempt
    , missing : Bool
    , resultRange : Maybe ( Float, Float )
    }


project : Recording -> Report
project recording =
    let
        state =
            Array.foldl step initial recording.events

        reportedGap =
            case state.reportedCount of
                Just (Safe count) ->
                    count > toFloat state.sampleCount

                Just (Unsafe _) ->
                    True

                Nothing ->
                    False
    in
    { runId = state.runId
    , metadata = state.metadata
    , startPosition = state.startPosition
    , status = state.status
    , decision = state.decision
    , reportedCount = state.reportedCount
    , endReason = state.endReason
    , endErrorType = state.endErrorType
    , errorCount = state.errorCount
    , sampleCount = state.sampleCount
    , attempts = List.reverse state.attempts
    , hierarchy = Dict.keys state.hierarchy
    , traces = Dict.values state.traces |> List.map (\trace -> { trace | points = List.reverse trace.points })
    , criteria = Dict.values state.criteria
    , missingEvidence = state.missing || reportedGap
    , resultRange = state.resultRange
    }


initial : State
initial =
    { runId = ""
    , metadata = Nothing
    , startPosition = Just 0
    , status = "incomplete"
    , decision = Nothing
    , reportedCount = Nothing
    , endReason = Nothing
    , endErrorType = Nothing
    , errorCount = 0
    , sampleCount = 0
    , attempts = []
    , hierarchy = Dict.singleton [] ()
    , traces = Dict.empty
    , criteria = Dict.empty
    , previousSample = Nothing
    , missing = False
    , resultRange = Nothing
    }


step : Event -> State -> State
step event state =
    case event of
        RunStart start ->
            { state | runId = start.runId, metadata = Just start.metadata }

        ObservationError attempt ->
            { state | errorCount = state.errorCount + 1, attempts = attempt :: state.attempts, missing = state.missing || revealsGap attempt state }

        Sample attempt ->
            let
                next =
                    { state | sampleCount = state.sampleCount + 1, attempts = attempt :: state.attempts, missing = state.missing || revealsGap attempt state }

                collected =
                    case attempt.result of
                        Just result ->
                            collectResult False [] attempt result next

                        Nothing ->
                            next
            in
            { collected | previousSample = Just attempt }

        RunEnd ending ->
            { state | status = ending.status, decision = ending.decision, reportedCount = Just ending.nObserved, endReason = ending.reason, endErrorType = ending.errorType }


revealsGap : Attempt -> State -> Bool
revealsGap attempt state =
    case attempt.index of
        Safe index ->
            index > toFloat state.sampleCount

        Unsafe _ ->
            True


collectResult : Bool -> List String -> Attempt -> CriterionResult -> State -> State
collectResult retained path attempt result state =
    let
        withCriterion =
            addCriterion retained path attempt.position result state
    in
    case result of
        Observation _ ->
            withCriterion

        Sprt evidence ->
            if retained && (evidence.decision == "continue" || terminalRecorded path evidence.index withCriterion) then
                withCriterion

            else
                let
                    previousPoint =
                        Dict.get path state.traces |> Maybe.andThen (List.head << .points)

                    consecutive =
                        case ( state.previousSample, previousPoint ) of
                            ( Just previous, Just previousEvidence ) ->
                                previous.position
                                    + 1
                                    == attempt.position
                                    && consecutiveIndices previous.index attempt.index
                                    && previousEvidence.origin
                                    == SampleOrigin previous.position

                            _ ->
                                False

                    point =
                        { path = path
                        , index = evidence.index
                        , llr = evidence.llr
                        , lower = evidence.lower
                        , upper = evidence.upper
                        , nObserved = evidence.nObserved
                        , decision = evidence.decision
                        , origin =
                            if retained then
                                RetainedOrigin

                            else
                                SampleOrigin attempt.position
                        , sourcePosition = attempt.position
                        , connected = not retained && consecutive
                        , numericSafe = Recording.isSafe evidence.index && Recording.isSafe evidence.nObserved && (retained || Recording.isSafe attempt.index)
                        }

                    trace =
                        Dict.get path withCriterion.traces |> Maybe.withDefault { path = path, points = [] }
                in
                { withCriterion | traces = Dict.insert path { trace | points = point :: trace.points } withCriterion.traces }

        Composite composite ->
            let
                current =
                    List.foldl (collectChild retained path attempt) withCriterion composite.results
            in
            List.foldl (\( key, child ) -> collectResult True (path ++ [ key ]) attempt child) current composite.terminalResults


collectChild : Bool -> List String -> Attempt -> ( String, Maybe CriterionResult ) -> State -> State
collectChild retained path attempt ( key, maybeResult ) state =
    let
        childPath =
            path ++ [ key ]

        withPath =
            { state | hierarchy = Dict.insert childPath () state.hierarchy }
    in
    case maybeResult of
        Nothing ->
            withPath

        Just result ->
            collectResult retained childPath attempt result withPath


addCriterion : Bool -> List String -> Int -> CriterionResult -> State -> State
addCriterion retained path source result state =
    let
        info index decision kind counters =
            { path = path, index = index, decision = decision, kind = kind, sourcePosition = source, numericSafe = List.all Recording.isSafe (index :: counters) }

        criterion =
            case result of
                Observation evidence ->
                    info evidence.index evidence.decision "observation" []

                Sprt evidence ->
                    info evidence.index evidence.decision "sprt" [ evidence.nObserved ]

                Composite evidence ->
                    info evidence.index evidence.decision "composite" [ evidence.nDecided, evidence.nTotal ]

        keepExisting =
            retained && (Dict.get path state.criteria |> Maybe.map (\existing -> existing.decision /= "continue" || criterion.decision == "continue") |> Maybe.withDefault False)

        criteria =
            if keepExisting then
                state.criteria

            else
                Dict.insert path criterion state.criteria

        range =
            case criterion.index of
                Unsafe _ ->
                    state.resultRange

                Safe index ->
                    case state.resultRange of
                        Nothing ->
                            Just ( index, index )

                        Just ( low, high ) ->
                            Just ( min low index, max high index )
    in
    { state | hierarchy = Dict.insert path () state.hierarchy, criteria = criteria, resultRange = range }


consecutiveIndices : Integer -> Integer -> Bool
consecutiveIndices left right =
    case ( left, right ) of
        ( Safe a, Safe b ) ->
            b == a + 1

        _ ->
            False


terminalRecorded : List String -> Integer -> State -> Bool
terminalRecorded path index state =
    Dict.get path state.traces
        |> Maybe.map (\trace -> List.any (\point -> point.index == index && point.decision /= "continue") trace.points)
        |> Maybe.withDefault False


hierarchyLabel : List String -> String
hierarchyLabel path =
    if List.isEmpty path then
        "Run criterion"

    else
        Json.Encode.encode 0 (Json.Encode.list Json.Encode.string path)
