module EvidenceTest exposing (tests)

import Array
import Evidence exposing (PointOrigin(..))
import Expect
import GeneratedFixtures
import Json.Decode as Decode
import Json.Encode as Encode
import Recording exposing (Integer(..))
import Test exposing (Test, describe, test)


tests : Test
tests =
    describe "recorded evidence"
        [ test "SPRT points retain actual originating samples and local counts" <|
            \_ ->
                withFixture "sprt.jsonl" <|
                    \recording report ->
                        Expect.all
                            [ \_ -> report.traces |> List.concatMap .points |> List.map (\point -> ( ( point.index, point.llr ), ( point.nObserved, point.decision, point.origin ) )) |> Expect.equal [ ( ( Safe 0, 1.5 ), ( Safe 1, "continue", SampleOrigin 1 ) ), ( ( Safe 1, 3 ), ( Safe 2, "accept_h1", SampleOrigin 2 ) ) ]
                            , \_ -> originatingRaw recording report |> Expect.equal [ Just "first", Just "second" ]
                            , \_ -> report.traces |> List.concatMap .points |> List.map .connected |> Expect.equal [ False, True ]
                            ]
                            ()
        , test "missing end does not promote the latest criterion to a run decision" <|
            \_ ->
                withFixture "incomplete.jsonl" <|
                    \_ report ->
                        Expect.equal ( ( "incomplete", Nothing ), ( Nothing, 1 ) ) ( ( report.status, report.decision ), ( report.reportedCount, report.sampleCount ) )
        , test "error ending retains a separate terminal decision and error type" <|
            \_ ->
                withFixture "terminal-error.jsonl" <|
                    \_ report ->
                        Expect.equal ( "error", Just "accept_h0", Just "builtins.KeyError" ) ( report.status, report.decision, report.endErrorType )
        , test "nested retry keeps distinct attempts without repeating stopped evidence" <|
            \_ ->
                withFixture "nested-retry.jsonl" <|
                    \_ report ->
                        Expect.all
                            [ \_ -> List.map (\attempt -> ( attempt.position, attempt.index )) report.attempts |> Expect.equal [ ( 1, Safe 0 ), ( 2, Safe 0 ), ( 3, Safe 1 ) ]
                            , \_ -> report.errorCount |> Expect.equal 1
                            , \_ -> traceAt [ "nested", "quick" ] report |> List.map .origin |> Expect.equal [ SampleOrigin 2 ]
                            , \_ -> traceAt [ "nested", "slow" ] report |> List.map .llr |> Expect.equal [ 1.5, 3 ]
                            , \_ -> traceAt [ "skipped" ] report |> Expect.equal []
                            , \_ -> List.member [ "skipped" ] report.hierarchy |> Expect.equal True
                            ]
                            ()
        , test "missing sample exposes one isolated retained terminal snapshot" <|
            \_ ->
                withFixture "missing-sample.jsonl" <|
                    \recording report ->
                        Expect.all
                            [ \_ -> report.missingEvidence |> Expect.equal True
                            , \_ -> ( report.sampleCount, report.reportedCount ) |> Expect.equal ( 2, Just (Safe 3) )
                            , \_ -> traceAt [ "child" ] report |> List.map (\point -> ( point.index, point.origin, point.connected )) |> Expect.equal [ ( Safe 0, SampleOrigin 1, False ), ( Safe 1, RetainedOrigin, False ) ]
                            , \_ -> Array.get 2 recording.eventJson |> Maybe.map (String.contains "9007199254740993") |> Expect.equal (Just True)
                            ]
                            ()
        , test "unsafe integer evidence remains source-only, never rounded text" <|
            \_ ->
                let
                    source =
                        fixtureSource "sprt.jsonl" |> String.replace "\"n_observed\":2" "\"n_observed\":9007199254740993"
                in
                withSource source <|
                    \_ report ->
                        report.traces |> List.concatMap .points |> List.reverse |> List.head |> Maybe.map (Recording.integerText << .nObserved) |> Expect.equal (Just "Evidence outside JavaScript numeric range")
        , test "unsafe attempt indices suppress otherwise safe criterion points" <|
            \_ ->
                let
                    source =
                        fixtureSource "sprt.jsonl" |> String.lines |> List.take 2 |> String.join "\n" |> String.replace "\"type\":\"sample\",\"index\":0" "\"type\":\"sample\",\"index\":9007199254740993"
                in
                withSource source <|
                    \_ report ->
                        report.traces |> List.concatMap .points |> List.map .numericSafe |> Expect.equal [ False ]
        , test "successful-event gaps break the trace" <|
            \_ ->
                let
                    source =
                        fixtureSource "sprt.jsonl" |> String.replace "\"index\":1" "\"index\":2"
                in
                withSource source <|
                    \_ report ->
                        Expect.equal ( True, [ False, False ] ) ( report.missingEvidence, report.traces |> List.concatMap .points |> List.map .connected )
        , test "an error attempt between samples breaks the trace" <|
            \_ ->
                let
                    lines =
                        fixtureSource "sprt.jsonl" |> String.lines |> List.filter (not << String.isEmpty)

                    retry =
                        fixtureSource "nested-retry.jsonl" |> String.lines |> List.drop 1 |> List.head |> Maybe.withDefault "" |> String.replace "\"index\":0" "\"index\":1"

                    source =
                        String.join "\n" (List.take 2 lines ++ [ retry ] ++ List.drop 2 lines)
                in
                withSource source <|
                    \_ report ->
                        Expect.equal ( 1, [ False, False ] ) ( report.errorCount, report.traces |> List.concatMap .points |> List.map .connected )
        , test "retained nested composites do not invent source samples" <|
            \_ ->
                let
                    lines =
                        fixtureSource "nested-retry.jsonl" |> String.lines |> List.filter (not << String.isEmpty)

                    source =
                        String.join "\n" (List.take 1 lines ++ List.drop 3 lines)
                in
                withSource source <|
                    \_ report ->
                        traceAt [ "nested", "quick" ] report |> List.map .origin |> Expect.equal [ RetainedOrigin ]
        , test "path labels escape keys and distinguish slash keys from nested paths" <|
            \_ ->
                Expect.all
                    [ \_ -> Evidence.hierarchyLabel [ "a/b" ] == Evidence.hierarchyLabel [ "a", "b" ] |> Expect.equal False
                    , \_ -> Evidence.hierarchyLabel [ "quote\"key", "line\nkey" ] |> Decode.decodeString (Decode.list Decode.string) |> Expect.equal (Ok [ "quote\"key", "line\nkey" ])
                    ]
                    ()
        , test "start-only recording is incomplete with no statistical trace" <|
            \_ ->
                withSource (fixtureSource "sprt.jsonl" |> String.lines |> List.take 1 |> String.join "\n") <|
                    \_ report ->
                        Expect.equal ( "incomplete", Nothing, [] ) ( report.status, report.decision, report.traces )
        , test "custom observation results retain their recorded decision without a trace" <|
            \_ ->
                let
                    source =
                        "{\"type\":\"run_start\",\"schema_version\":1,\"run_id\":\"custom\",\"metadata\":{}}\n{\"type\":\"sample\",\"index\":0,\"raw\":1,\"observed\":1,\"metadata\":{},\"result\":{\"kind\":\"observation\",\"index\":0,\"decision\":\"accept_h0\"}}"
                in
                withSource source <|
                    \_ report ->
                        Expect.equal ( [], Just "accept_h0" ) ( report.traces, report.criteria |> List.head |> Maybe.map .decision )
        , test "null current child evidence breaks a later returning path" <|
            \_ ->
                let
                    start =
                        fixtureSource "sprt.jsonl" |> String.lines |> List.head |> Maybe.withDefault ""

                    child index =
                        "{\"kind\":\"sprt\",\"index\":" ++ String.fromInt index ++ ",\"decision\":\"continue\",\"cumulative_llr\":1.5,\"lower_bound\":-2.25,\"upper_bound\":2.89,\"n_observed\":1}"

                    sample index result =
                        "{\"type\":\"sample\",\"index\":" ++ String.fromInt index ++ ",\"raw\":null,\"observed\":null,\"metadata\":{},\"result\":{\"kind\":\"composite\",\"index\":" ++ String.fromInt index ++ ",\"decision\":\"continue\",\"n_decided\":0,\"n_total\":1,\"results\":{\"child\":" ++ result ++ "},\"terminal_results\":{}}}"

                    source =
                        String.join "\n" [ start, sample 0 (child 0), sample 1 "null", sample 2 (child 2) ]
                in
                withSource source <|
                    \_ report ->
                        traceAt [ "child" ] report |> List.map .connected |> Expect.equal [ False, False ]
        , test "shared domain retains earlier criterion indices rather than only the latest" <|
            \_ ->
                let
                    source =
                        fixtureSource "sprt.jsonl" |> String.replace "\"kind\":\"sprt\",\"index\":0" "\"kind\":\"sprt\",\"index\":42"
                in
                withSource source <|
                    \_ report ->
                        report.resultRange |> Expect.equal (Just ( 1, 42 ))
        , test "decoder rejects invalid fields, counters, lifecycle, and event order" <|
            \_ ->
                let
                    sprt =
                        fixtureSource "sprt.jsonl"

                    lines =
                        String.lines sprt |> List.filter (not << String.isEmpty)

                    invalid =
                        [ String.replace "\"schema_version\":1" "\"schema_version\":2" sprt
                        , String.replace "\"index\":0" "\"index\":false" sprt
                        , String.replace "\"n_observed\":1" "\"n_observed\":true" sprt
                        , String.replace "\"decision\":\"accept_h1\"" "\"decision\":\"unknown\"" sprt
                        , String.replace "\"metadata\":{}" "\"metadata\":[]" sprt
                        , String.replace "\"status\":\"terminal\"" "\"status\":\"error\"" sprt
                        , String.replace "\"error_type\":null" "\"error_type\":\"bad\"" sprt
                        , String.join "\n" (lines ++ List.take 1 lines)
                        , String.join "\n" (List.take 2 lines ++ List.drop 1 lines)
                        , fixtureSource "nested-retry.jsonl" |> String.replace "\"quick\":{\"kind\":\"sprt\"" "\"quick\":{\"kind\":\"unknown\""
                        ]
                in
                List.map decodeSource invalid
                    |> List.all
                        (\result ->
                            case result of
                                Err _ ->
                                    True

                                Ok _ ->
                                    False
                        )
                    |> Expect.equal True
        , test "unequal flag arrays fail inside decoder" <|
            \_ -> Decode.decodeString Decode.value "{\"events\":[],\"event_json\":[\"extra\"]}" |> Result.andThen Recording.decode |> Result.map (\_ -> ()) |> isError |> Expect.equal True
        ]


traceAt : List String -> Evidence.Report -> List Evidence.EvidencePoint
traceAt path report =
    List.filter (\trace -> trace.path == path) report.traces |> List.head |> Maybe.map .points |> Maybe.withDefault []


originatingRaw : Recording.Recording -> Evidence.Report -> List (Maybe String)
originatingRaw recording report =
    report.traces
        |> List.concatMap .points
        |> List.map
            (\point ->
                case point.origin of
                    SampleOrigin position ->
                        Array.get position recording.sources |> Maybe.andThen (\source -> Decode.decodeValue (Decode.field "raw" Decode.string) source |> Result.toMaybe)

                    RetainedOrigin ->
                        Nothing
            )


fixtureSource : String -> String
fixtureSource name =
    GeneratedFixtures.files |> List.filter (\( file, _ ) -> file == name) |> List.head |> Maybe.map Tuple.second |> Maybe.withDefault ""


withFixture : String -> (Recording.Recording -> Evidence.Report -> Expect.Expectation) -> Expect.Expectation
withFixture name assertion =
    let
        source =
            fixtureSource name

        formatted =
            GeneratedFixtures.eventJson |> List.filter (\( file, _ ) -> file == name) |> List.head |> Maybe.map Tuple.second |> Maybe.withDefault []
    in
    applyAssertion (decodeWithJson source formatted) assertion


withSource : String -> (Recording.Recording -> Evidence.Report -> Expect.Expectation) -> Expect.Expectation
withSource source assertion =
    applyAssertion (decodeSource source) assertion


applyAssertion : Result Decode.Error Recording.Recording -> (Recording.Recording -> Evidence.Report -> Expect.Expectation) -> Expect.Expectation
applyAssertion result assertion =
    case result of
        Ok recording ->
            assertion recording (Evidence.project recording)

        Err error ->
            Expect.fail (Decode.errorToString error)


decodeSource : String -> Result Decode.Error Recording.Recording
decodeSource source =
    decodeWithJson source (String.lines source |> List.filter (not << String.isEmpty))


decodeWithJson : String -> List String -> Result Decode.Error Recording.Recording
decodeWithJson source sourceJson =
    let
        lines =
            String.lines source |> List.filter (not << String.isEmpty)

        flags =
            "{\"events\":[" ++ String.join "," lines ++ "],\"event_json\":" ++ Encode.encode 0 (Encode.list Encode.string sourceJson) ++ "}"
    in
    Decode.decodeString Decode.value flags |> Result.andThen Recording.decode


isError : Result error value -> Bool
isError result =
    case result of
        Err _ ->
            True

        Ok _ ->
            False
