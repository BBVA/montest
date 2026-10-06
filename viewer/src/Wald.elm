module Wald exposing (render)

import Evidence exposing (EvidencePoint, PointOrigin(..), Trace)
import Html exposing (Html, div, text)
import Html.Attributes as HA
import Json.Decode as Decode
import Recording exposing (Integer(..), integerText, isSafe)
import Svg exposing (Svg, circle, line, path, polygon, rect, svg, text_)
import Svg.Attributes as A
import Svg.Events as Events


render : ( Float, Float ) -> (EvidencePoint -> msg) -> (Maybe EvidencePoint -> msg) -> (Maybe EvidencePoint -> msg) -> Trace -> Html msg
render horizontal select hover focus trace =
    let
        safePoints =
            plottable trace.points

        outside =
            List.length safePoints /= List.length trace.points

        domain =
            domains horizontal safePoints
    in
    div [ HA.class "wald-chart" ]
        [ if outside then
            div [ HA.class "notice warning" ] [ text "Evidence outside JavaScript numeric range" ]

          else
            text ""
        , if List.isEmpty safePoints then
            text ""

          else
            svg [ A.viewBox "0 0 720 390", A.class "wald-svg", HA.attribute "role" "img", HA.attribute "aria-label" "Recorded Wald evidence" ]
                (regions domain safePoints ++ axes domain ++ tracePath domain safePoints ++ List.map (pointMark select hover focus domain) safePoints)
        ]


plottable : List EvidencePoint -> List EvidencePoint
plottable points =
    let
        step point ( previousSafe, reversed ) =
            if safePoint point then
                ( True, { point | connected = point.connected && previousSafe } :: reversed )

            else
                ( False, reversed )
    in
    List.foldl step ( False, [] ) points |> Tuple.second |> List.reverse


safePoint : EvidencePoint -> Bool
safePoint point =
    point.numericSafe && List.all finite [ point.llr, point.lower, point.upper ]


finite : Float -> Bool
finite number =
    not (isNaN number || isInfinite number)


type alias Domain =
    { left : Float, right : Float, bottom : Float, top : Float }


domains : ( Float, Float ) -> List EvidencePoint -> Domain
domains ( left, right ) points =
    let
        values =
            0 :: List.concatMap (\point -> [ point.llr, point.lower, point.upper ]) points

        minimum =
            Maybe.withDefault -1 (List.minimum values)

        maximum =
            Maybe.withDefault 1 (List.maximum values)

        span =
            if minimum == maximum then
                1

            else
                maximum - minimum
    in
    { left = left, right = right, bottom = minimum - 0.1 * span, top = maximum + 0.1 * span }


pointIndex : EvidencePoint -> Float
pointIndex point =
    case point.index of
        Safe value ->
            value

        Unsafe _ ->
            0


scaleX : Domain -> Float -> Float
scaleX domain value =
    72 + (value - domain.left) / (domain.right - domain.left) * 610


scaleY : Domain -> Float -> Float
scaleY domain value =
    310 - (value - domain.bottom) / (domain.top - domain.bottom) * 260


axes : Domain -> List (Svg msg)
axes domain =
    [ line [ A.x1 "72", A.y1 "310", A.x2 "682", A.y2 "310", A.stroke "#374151" ] []
    , line [ A.x1 "72", A.y1 "50", A.x2 "72", A.y2 "310", A.stroke "#374151" ] []
    , line [ A.x1 "72", A.y1 (float (scaleY domain 0)), A.x2 "682", A.y2 (float (scaleY domain 0)), A.stroke "#6b7280", A.strokeDasharray "4 4" ] []
    , text_ [ A.x "377", A.y "373", A.textAnchor "middle", A.class "axis-label" ] [ text "Recorded criterion index (zero-based)" ]
    , text_ [ A.x "72", A.y "26", A.class "axis-label" ] [ text "Cumulative log-likelihood ratio" ]
    , text_ [ A.x "72", A.y "333", A.textAnchor "middle", A.class "tick-label" ] [ text (float domain.left) ]
    , text_ [ A.x "682", A.y "333", A.textAnchor "middle", A.class "tick-label" ] [ text (float domain.right) ]
    , text_ [ A.x "64", A.y (float (scaleY domain 0 + 4)), A.textAnchor "end", A.class "tick-label" ] [ text "0" ]
    , text_ [ A.x "64", A.y "54", A.textAnchor "end", A.class "tick-label" ] [ text (tick domain.top) ]
    , text_ [ A.x "64", A.y "310", A.textAnchor "end", A.class "tick-label" ] [ text (tick domain.bottom) ]
    ]


regions : Domain -> List EvidencePoint -> List (Svg msg)
regions domain points =
    let
        valid =
            List.all (\point -> point.lower < point.upper) points

        constant =
            case points of
                first :: rest ->
                    List.all (\point -> point.lower == first.lower && point.upper == first.upper) rest

                [] ->
                    False

        labels =
            [ text_ [ A.x "80", A.y "65", A.class "region-label" ] [ text "H1 boundary region" ]
            , text_ [ A.x "80", A.y "301", A.class "region-label" ] [ text "H0 boundary region" ]
            ]
    in
    if not valid then
        text_ [ A.x "90", A.y "78", A.class "bounds-warning" ] [ text "Invalid recorded bounds" ] :: varyingSegments False domain points

    else if constant then
        case points of
            first :: _ ->
                let
                    upperY =
                        scaleY domain first.upper

                    lowerY =
                        scaleY domain first.lower
                in
                [ rect [ A.x "72", A.y "50", A.width "610", A.height (float (upperY - 50)), A.fill "#fed7aa", A.class "boundary-region" ] []
                , rect [ A.x "72", A.y (float lowerY), A.width "610", A.height (float (310 - lowerY)), A.fill "#bfdbfe", A.class "boundary-region" ] []
                , boundLine "#b45309" 72 upperY 682 upperY
                , boundLine "#2563eb" 72 lowerY 682 lowerY
                ]
                    ++ labels

            [] ->
                []

    else
        varyingSegments True domain points ++ labels


varyingSegments : Bool -> Domain -> List EvidencePoint -> List (Svg msg)
varyingSegments shade domain points =
    case points of
        left :: right :: rest ->
            let
                xLeft =
                    scaleX domain (pointIndex left)

                xRight =
                    scaleX domain (pointIndex right)

                upperLeft =
                    scaleY domain left.upper

                upperRight =
                    scaleY domain right.upper

                lowerLeft =
                    scaleY domain left.lower

                lowerRight =
                    scaleY domain right.lower

                segment =
                    if right.connected then
                        (if shade then
                            [ polygon [ A.points (coordinates [ ( xLeft, 50 ), ( xRight, 50 ), ( xRight, upperRight ), ( xLeft, upperLeft ) ]), A.fill "#fed7aa", A.class "boundary-region" ] []
                            , polygon [ A.points (coordinates [ ( xLeft, lowerLeft ), ( xRight, lowerRight ), ( xRight, 310 ), ( xLeft, 310 ) ]), A.fill "#bfdbfe", A.class "boundary-region" ] []
                            ]

                         else
                            []
                        )
                            ++ [ boundLine "#b45309" xLeft upperLeft xRight upperRight, boundLine "#2563eb" xLeft lowerLeft xRight lowerRight ]

                    else
                        []
            in
            segment ++ varyingSegments shade domain (right :: rest)

        _ ->
            []


boundLine : String -> Float -> Float -> Float -> Float -> Svg msg
boundLine color left top right bottom =
    line [ A.x1 (float left), A.y1 (float top), A.x2 (float right), A.y2 (float bottom), A.stroke color, A.strokeDasharray "7 5", A.strokeWidth "1.5" ] []


coordinates : List ( Float, Float ) -> String
coordinates points =
    String.join " " (List.map (\( x, y ) -> float x ++ "," ++ float y) points)


tracePath : Domain -> List EvidencePoint -> List (Svg msg)
tracePath domain points =
    let
        command point =
            float (scaleX domain (pointIndex point)) ++ " " ++ float (scaleY domain point.llr)

        build point ( previous, reversed ) =
            ( Just point
            , ((if point.connected && previous /= Nothing then
                    " L "

                else
                    " M "
               )
                ++ command point
              )
                :: reversed
            )

        ( _, commands ) =
            List.foldl build ( Nothing, [] ) points
    in
    [ path [ A.d (String.concat (List.reverse commands)), A.fill "none", A.stroke "#1f2937", A.strokeWidth "2.5", A.class "llr-trace" ] [] ]


pointMark : (EvidencePoint -> msg) -> (Maybe EvidencePoint -> msg) -> (Maybe EvidencePoint -> msg) -> Domain -> EvidencePoint -> Svg msg
pointMark select hover focus domain point =
    let
        label =
            "Criterion index " ++ integerText point.index ++ ", LLR " ++ float point.llr ++ ", local count " ++ integerText point.nObserved ++ ", decision " ++ point.decision

        hollow =
            case point.origin of
                RetainedOrigin ->
                    "#ffffff"

                SampleOrigin _ ->
                    "#1f2937"

        enter =
            Decode.field "key" Decode.string
                |> Decode.andThen
                    (\key ->
                        if key == "Enter" then
                            Decode.succeed (select point)

                        else
                            Decode.fail "not Enter"
                    )
    in
    circle
        [ A.cx (float (scaleX domain (pointIndex point)))
        , A.cy (float (scaleY domain point.llr))
        , A.r "5"
        , A.fill hollow
        , A.stroke "#111827"
        , A.strokeWidth "2"
        , HA.attribute "tabindex" "0"
        , A.class "evidence-point"
        , HA.attribute "aria-label" label
        , HA.attribute "role" "button"
        , Events.onClick (select point)
        , Events.on "keydown" enter
        , Events.on "mouseenter" (Decode.succeed (hover (Just point)))
        , Events.on "focus" (Decode.succeed (focus (Just point)))
        , Events.on "mouseleave" (Decode.succeed (hover Nothing))
        , Events.on "blur" (Decode.succeed (focus Nothing))
        ]
        []


float : Float -> String
float =
    String.fromFloat


tick : Float -> String
tick number =
    String.fromFloat (toFloat (round (number * 100)) / 100)
