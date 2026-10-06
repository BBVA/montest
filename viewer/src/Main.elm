module Main exposing (main)

import Array
import Browser
import Evidence exposing (CriterionEvidence, EvidencePoint, PointOrigin(..), Report)
import Html exposing (Html, button, div, h1, h2, h3, label, option, pre, select, span, text)
import Html.Attributes as A
import Html.Events exposing (onClick, onInput)
import Html.Lazy as Lazy
import Json.Decode as Decode
import Recording exposing (Attempt, Event(..), Integer(..), Recording)
import Wald


main : Program Decode.Value Model Msg
main =
    Browser.element { init = init, update = update, subscriptions = \_ -> Sub.none, view = view }


type alias Model =
    { result : Result Decode.Error ( Recording, Report )
    , metadataOpen : Bool
    , selection : Maybe Selection
    , hover : Maybe EvidencePoint
    , focus : Maybe EvidencePoint
    , horizontal : ( Float, Float )
    }


type Selection
    = AttemptSelection Int
    | RetainedSelection EvidencePoint


type Msg
    = ToggleMetadata
    | SelectAttempt String
    | SelectPoint EvidencePoint
    | HoverPoint (Maybe EvidencePoint)
    | FocusPoint (Maybe EvidencePoint)


init : Decode.Value -> ( Model, Cmd Msg )
init flags =
    let
        result =
            Recording.decode flags |> Result.map (\recording -> ( recording, Evidence.project recording ))

        firstAttempt report =
            case List.head (List.filter (\attempt -> attempt.result /= Nothing) report.attempts) of
                Just attempt ->
                    Just attempt

                Nothing ->
                    List.head report.attempts

        initialSelection =
            result |> Result.toMaybe |> Maybe.andThen (\( _, report ) -> firstAttempt report |> Maybe.map (AttemptSelection << .position))

        horizontal =
            result |> Result.toMaybe |> Maybe.map (horizontalDomain << Tuple.second) |> Maybe.withDefault ( 0, 1 )
    in
    ( { result = result, metadataOpen = False, selection = initialSelection, hover = Nothing, focus = Nothing, horizontal = horizontal }, Cmd.none )


update : Msg -> Model -> ( Model, Cmd Msg )
update message model =
    case message of
        ToggleMetadata ->
            ( { model | metadataOpen = not model.metadataOpen }, Cmd.none )

        SelectAttempt position ->
            ( { model | selection = String.toInt position |> Maybe.map AttemptSelection }, Cmd.none )

        SelectPoint point ->
            let
                selection =
                    case point.origin of
                        SampleOrigin source ->
                            AttemptSelection source

                        RetainedOrigin ->
                            RetainedSelection point
            in
            ( { model | selection = Just selection, hover = Just point }, Cmd.none )

        HoverPoint point ->
            ( { model | hover = point }, Cmd.none )

        FocusPoint point ->
            ( { model | focus = point }, Cmd.none )


view : Model -> Html Msg
view model =
    case model.result of
        Err error ->
            div [ A.class "report invalid" ] [ h1 [] [ text "Invalid report data" ], pre [ A.class "source-json" ] [ text (Decode.errorToString error) ] ]

        Ok ( recording, report ) ->
            div [ A.class "report" ]
                [ header report
                , summary recording report
                , metadataPanel model recording report
                , hierarchy recording report
                , plots model recording report
                , inspector model recording report
                ]


header : Report -> Html Msg
header report =
    let
        testId =
            report.metadata |> Maybe.andThen (\metadata -> Decode.decodeValue (Decode.field "test_id" Decode.string) metadata |> Result.toMaybe)
    in
    div [ A.class "run-header" ]
        [ h1 [] [ text report.runId ]
        , span [ A.class "test-id" ] [ text (Maybe.withDefault "" testId) ]
        , div [ A.class "badges" ]
            [ span [ A.class "badge status" ] [ text report.status ]
            , span [ A.class "badge decision" ] [ text (Maybe.withDefault "No run decision" report.decision) ]
            ]
        , maybeNotice "Run error: " report.endErrorType
        , maybeNotice "Lifecycle reason: " report.endReason
        ]


maybeNotice : String -> Maybe String -> Html msg
maybeNotice prefix contents =
    case contents of
        Just value ->
            div [ A.class "notice" ] [ text (prefix ++ value) ]

        Nothing ->
            text ""


summary : Recording -> Report -> Html Msg
summary recording report =
    div [ A.class "summary" ]
        ([ metric "Recorded samples" (String.fromInt report.sampleCount)
         , metric "Observation errors" (String.fromInt report.errorCount)
         ]
            ++ (case report.reportedCount of
                    Nothing ->
                        []

                    Just count ->
                        if Recording.isSafe count then
                            [ metric "Reported count" (Recording.integerText count) ]

                        else
                            [ div [ A.class "notice warning" ] [ text "Evidence outside JavaScript numeric range", sourceAt (Array.length recording.eventJson - 1) recording ] ]
               )
            ++ (if report.status == "incomplete" && report.reportedCount == Nothing then
                    [ div [ A.class "notice" ] [ text "Incomplete: no run_end record" ] ]

                else
                    []
               )
            ++ (if report.missingEvidence then
                    [ div [ A.class "notice warning" ] [ text "Missing evidence: recorded samples or reported count contain gaps." ] ]

                else
                    []
               )
        )


metric : String -> String -> Html msg
metric title contents =
    div [ A.class "metric" ] [ span [ A.class "metric-label" ] [ text title ], Html.strong [] [ text contents ] ]


metadataPanel : Model -> Recording -> Report -> Html Msg
metadataPanel model recording report =
    div [ A.class "metadata-panel" ]
        [ button
            [ onClick ToggleMetadata
            , A.class "metadata-toggle"
            , A.attribute "aria-expanded"
                (if model.metadataOpen then
                    "true"

                 else
                    "false"
                )
            , A.attribute "aria-controls" "run-metadata"
            ]
            [ text
                (if model.metadataOpen then
                    "Hide metadata"

                 else
                    "Show metadata"
                )
            ]
        , if model.metadataOpen then
            div [ A.id "run-metadata" ] [ h2 [] [ text "Run metadata" ], sourceAt (Maybe.withDefault 0 report.startPosition) recording ]

          else
            text ""
        ]


hierarchy : Recording -> Report -> Html Msg
hierarchy recording report =
    div [ A.class "hierarchy" ]
        [ h2 [] [ text "Criterion hierarchy" ]
        , div [ A.attribute "role" "list" ] (List.map (hierarchyEntry recording report.criteria) report.hierarchy)
        ]


hierarchyEntry : Recording -> List CriterionEvidence -> List String -> Html Msg
hierarchyEntry recording criteria path =
    let
        evidence =
            List.filter (\criterion -> criterion.path == path) criteria |> List.head

        detail =
            case evidence of
                Nothing ->
                    [ span [ A.class "criterion-detail" ] [ text "No recorded child evidence" ] ]

                Just criterion ->
                    if criterion.numericSafe then
                        [ span [ A.class "criterion-detail" ] [ text (criterion.kind ++ ": " ++ criterion.decision ++ ", index " ++ Recording.integerText criterion.index) ] ]

                    else
                        [ div [ A.class "notice warning" ] [ text "Evidence outside JavaScript numeric range", sourceAt criterion.sourcePosition recording ] ]
    in
    div [ A.class "hierarchy-item", A.attribute "role" "listitem", A.style "padding-left" (String.fromInt (List.length path * 16) ++ "px") ]
        (span [ A.class "criterion-name" ] [ text (Evidence.hierarchyLabel path) ] :: detail)


plots : Model -> Recording -> Report -> Html Msg
plots model recording report =
    div [ A.class "plots" ] (List.map (plotCard model recording model.horizontal) report.traces)


horizontalDomain : Report -> ( Float, Float )
horizontalDomain report =
    let
        safeValue integer =
            case integer of
                Safe number ->
                    Just number

                Unsafe _ ->
                    Nothing

        indices =
            List.filterMap (safeValue << .index) report.attempts
                ++ (case report.resultRange of
                        Just ( low, high ) ->
                            [ low, high ]

                        Nothing ->
                            []
                   )
                ++ (case report.reportedCount of
                        Just (Safe count) ->
                            [ count - 1 ]

                        _ ->
                            []
                   )

        left =
            Maybe.withDefault 0 (List.minimum indices)

        right =
            Maybe.withDefault 1 (List.maximum indices)
    in
    if left == right then
        ( left - 1, right + 1 )

    else
        ( left, right )


plotCard : Model -> Recording -> ( Float, Float ) -> Evidence.Trace -> Html Msg
plotCard model recording horizontal trace =
    let
        terminal =
            List.filter (\point -> point.decision /= "continue") trace.points |> List.reverse |> List.head

        tooltip =
            case
                if model.hover /= Nothing then
                    model.hover

                else
                    model.focus
            of
                Just point ->
                    if point.path == trace.path then
                        pointDetails point

                    else
                        text "Hover or focus a point to inspect its evidence."

                Nothing ->
                    text "Hover or focus a point to inspect its evidence."

        unsafeSources =
            trace.points |> List.filter (\point -> not point.numericSafe || List.any (\number -> isNaN number || isInfinite number) [ point.llr, point.lower, point.upper ]) |> List.map (\point -> sourceAt point.sourcePosition recording)

        terminalLabel =
            case terminal of
                Nothing ->
                    "No terminal criterion decision recorded"

                Just point ->
                    if point.numericSafe then
                        point.decision ++ " at recorded index " ++ Recording.integerText point.index ++ ", local n_observed " ++ Recording.integerText point.nObserved

                    else
                        point.decision ++ ": Evidence outside JavaScript numeric range"
    in
    div [ A.class "plot-card", A.attribute "data-criterion" (Evidence.hierarchyLabel trace.path) ]
        ([ h3 [] [ text (Evidence.hierarchyLabel trace.path) ]
         , Lazy.lazy5 Wald.render horizontal SelectPoint HoverPoint FocusPoint trace
         , div [ A.class "chart-tooltip", A.attribute "aria-live" "polite" ] [ tooltip ]
         , div [ A.class "terminal-label" ] [ text terminalLabel ]
         ]
            ++ unsafeSources
        )


pointDetails : EvidencePoint -> Html msg
pointDetails point =
    div [] [ text ("Criterion index " ++ Recording.integerText point.index ++ ", LLR " ++ String.fromFloat point.llr ++ ", local count " ++ Recording.integerText point.nObserved ++ ", decision " ++ point.decision) ]


inspector : Model -> Recording -> Report -> Html Msg
inspector model recording report =
    let
        selectedValue =
            case model.selection of
                Just (AttemptSelection position) ->
                    String.fromInt position

                _ ->
                    ""

        placeholder =
            case model.selection of
                Just (RetainedSelection _) ->
                    [ option [ A.value "", A.disabled True, A.selected True ] [ text "Retained terminal evidence" ] ]

                _ ->
                    []
    in
    div [ A.class "inspector" ]
        [ h2 [] [ text "Sample inspector" ]
        , label [ A.for "sample-selector" ] [ text "Recorded sample or observation-error attempt" ]
        , select [ A.id "sample-selector", onInput SelectAttempt, A.value selectedValue ] (placeholder ++ List.map (attemptOption selectedValue) report.attempts)
        , selectedInspector model recording
        ]


attemptOption : String -> Attempt -> Html msg
attemptOption selectedValue attempt =
    let
        kind =
            if attempt.result == Nothing then
                "observation_error"

            else
                "sample"

        index =
            if Recording.isSafe attempt.index then
                Recording.integerText attempt.index

            else
                "Evidence outside JavaScript numeric range"
    in
    option [ A.value (String.fromInt attempt.position), A.selected (selectedValue == String.fromInt attempt.position) ] [ text ("Source event " ++ String.fromInt attempt.position ++ ": " ++ kind ++ ", index " ++ index) ]


selectedInspector : Model -> Recording -> Html Msg
selectedInspector model recording =
    case model.selection of
        Just (RetainedSelection point) ->
            div [ A.class "retained-evidence" ]
                [ div [ A.class "notice" ] [ text "Retained terminal evidence. No originating sample result is recorded for this point." ]
                , pointDetails point
                , div [] [ text "Containing event JSON. Its raw value is not an originating sample for this point." ]
                , sourceAt point.sourcePosition recording
                ]

        Just (AttemptSelection position) ->
            case Array.get position recording.events of
                Just event ->
                    div [] (div [ A.class "event-kind" ] [ text (eventLabel event) ] :: rawBlocks event ++ [ sourceAt position recording ])

                Nothing ->
                    emptyInspector

        Nothing ->
            emptyInspector


emptyInspector : Html msg
emptyInspector =
    div [ A.class "empty" ] [ text "No samples or observation errors were recorded." ]


sourceAt : Int -> Recording -> Html msg
sourceAt position recording =
    pre [ A.class "source-json" ] [ text (Maybe.withDefault "" (Array.get position recording.eventJson)) ]


eventLabel : Event -> String
eventLabel event =
    let
        attemptLabel kind attempt =
            if Recording.isSafe attempt.index then
                kind ++ ", index " ++ Recording.integerText attempt.index

            else
                kind ++ ": Evidence outside JavaScript numeric range"
    in
    case event of
        Sample attempt ->
            attemptLabel "sample" attempt

        ObservationError attempt ->
            attemptLabel "observation_error" attempt ++ ", " ++ Maybe.withDefault "" attempt.errorType

        RunStart _ ->
            "run_start"

        RunEnd _ ->
            "run_end"


rawBlocks : Event -> List (Html msg)
rawBlocks event =
    let
        attempt =
            case event of
                Sample value ->
                    Just value

                ObservationError value ->
                    Just value

                _ ->
                    Nothing

        plain title value =
            case Decode.decodeValue Decode.string value of
                Ok contents ->
                    [ div [ A.class "plain-value" ] [ h3 [] [ text title ], pre [] [ text contents ] ] ]

                Err _ ->
                    []
    in
    case attempt of
        Just value ->
            plain "Raw text" value.raw ++ plain "Observed text" value.observed

        Nothing ->
            []
