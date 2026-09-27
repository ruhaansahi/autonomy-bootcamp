"""
TODO(bootcamper): write the tests for ``src/waypoint_utils.py`` in here.

The example below covers files that parse fine: with and without ``home``,
and files with comments and blank lines in them. The rest is yours:

- Bad data: a file whose top level isn't a mapping, waypoints missing
  ``lat``, ``lon``, or ``alt``, values that aren't numbers, YAML that
  doesn't parse, and a file that isn't there.
- Out of range: latitudes past +/-90 and longitudes past +/-180 get
  rejected.
- Nothing to work with: an empty file, an empty ``waypoints`` list, and
  ``sort_clockwise_sweep`` given a list of 0 or 1 waypoints.
- ``east_north_coordinate_offset_m``: offsets you worked out yourself,
  compared with ``pytest.approx``. Never use ``==`` on meters.
- Ordering: with no ``home``, ``sort_clockwise_sweep`` goes clockwise
  starting from north.
- With a ``home``: the order starts in home's direction instead, and goes
  back to starting at north if home is right on top of the centroid.
- Two waypoints in the same direction: the closer one comes first.
- Parsing gives you frozen ``Coordinate`` objects that can't be changed.

Graded by ``warg run utils grade-tests``: pass on the real code, 90% branch
coverage, and fail on every broken copy in ``grader/mutants/``.
"""
import dataclasses

import pytest

from src.types import Coordinate
from src.waypoint_utils import (
    east_north_coordinate_offset_m,
    parse_waypoints_file,
    sort_clockwise_sweep,
)

# The helper and the test below are given to you.


def write_to_tmp_waypoints_file(tmp_path, text):
    """Write ``text`` to a YAML file and hand back its path.

    ``tmp_path`` is a pytest fixture: a fresh empty directory per test.
    """
    path = tmp_path / "waypoints.yaml"
    path.write_text(text)
    return path


# One test, three files. ``parametrize`` runs the test body once per
# ``(text, expected)`` pair, and ``ids`` names each run so a failure tells you
# which file broke.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            """
            home: {lat: 1, lon: 2, alt: 3}
            waypoints:
              - {lat: 4, lon: 5, alt: 6}
            """,
            (Coordinate(1, 2, 3), [Coordinate(4, 5, 6)]),
        ),
        (
            """
            waypoints:
              - {lat: 4, lon: 5, alt: 6}
              - {lat: 7, lon: 8, alt: 9}
            """,
            (None, [Coordinate(4, 5, 6), Coordinate(7, 8, 9)]),
        ),
        (
            """
            # a lap

            home: {lat: 1, lon: 2, alt: 3}

            waypoints:
              # first leg
              - {lat: 4, lon: 5, alt: 6}
            """,
            (Coordinate(1, 2, 3), [Coordinate(4, 5, 6)]),
        ),
    ],
    ids=["home-and-waypoints", "no-home", "comments-and-blank-lines"],
)
def test_parse_waypoints_file_success(tmp_path, text, expected):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(path) == expected


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[1, 2, 3]", "expected a mapping"),
        ("waypoints: [", "invalid YAML"),
        ("waypoints: 5", "must be a list"),
        ("home: 5", "home must be a mapping"),
        ("waypoints: [5]", "waypoint 1 must be a mapping"),
        ("home: {lat: 1, lon: 2}", "home is missing key"),
        ("waypoints: [{lon: 2, alt: 3}]", "waypoint 1 is missing key"),
        ("waypoints: [{lat: 1, alt: 3}]", "waypoint 1 is missing key"),
        ("waypoints: [{lat: 1, lon: 2}]", "waypoint 1 is missing key"),
        ("waypoints: [{lat: one, lon: 2, alt: 3}]", "non-numeric"),
        ("waypoints: [{lat: [1], lon: 2, alt: 3}]", "non-numeric"),
    ],
    ids=[
        "top-level-not-mapping",
        "invalid-yaml",
        "waypoints-not-list",
        "home-not-mapping",
        "waypoint-not-mapping",
        "home-missing-key",
        "waypoint-missing-key-lat",
        "waypoint-missing-key-lon",
        "waypoint-missing-key-alt",
        "waypoint-non-numeric-lat",
        "waypoint-non-numeric-lat-list",
    ], 
)
def test_parse_waypoints_file_bad_data(tmp_path, text, message):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError, match=message):
        parse_waypoints_file(path)


def test_parse_waypoints_file_missing_file_raises(tmp_path):
    with pytest.raises(OSError):
        parse_waypoints_file(tmp_path / "does_not_exist.yaml")


@pytest.mark.parametrize(
    ("lat", "lon"),
    [(90.1, 0), (-90.1, 0), (0, 180.1), (0, -180.1)],
    ids=["lat-too-high", "lat-too-low", "lon-too-high", "lon-too-low"],
)
def test_parse_waypoints_file_out_of_range_raises(tmp_path, lat, lon):
    text = f"waypoints: [{{lat: {lat}, lon: {lon}, alt: 0}}]"
    path = write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError, match="out of range"):
        parse_waypoints_file(path)


@pytest.mark.parametrize(
    ("lat", "lon"),
    [(90, 0), (-90, 0), (0, 180), (0, -180)],
    ids=["lat-max", "lat-min", "lon-max", "lon-min"],
)
def test_parse_waypoints_file_edge_of_range_accepted(tmp_path, lat, lon):
    text = f"waypoints: [{{lat: {lat}, lon: {lon}, alt: 0}}]"
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(path) == (None, [Coordinate(lat, lon, 0)])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", (None, [])),
        ("waypoints: []", (None, [])),
        ("waypoints:", (None, [])),
        ("home: {lat: 1, lon: 2, alt: 3}", (Coordinate(1, 2, 3), [])),
    ],
    ids=["empty-file", "empty-list", "waypoints-no-value", "home-only"],
)
def test_parse_waypoints_file_nothing_to_parse(tmp_path, text, expected):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(path) == expected


@pytest.mark.parametrize(
    "waypoints",
    [[], [Coordinate(1, 2, 3)]],
    ids=["no-waypoints", "one-waypoint"],
)
def test_sort_clockwise_sweep_zero_or_one_waypoint(waypoints):
    result = sort_clockwise_sweep(waypoints)
    assert result == waypoints
    assert result is not waypoints


@pytest.mark.parametrize(
    ("from_lat", "from_lon", "to_lat", "to_lon", "east", "north"),
    [
        (43.47, -80.54, 43.47, -80.54, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0, 0.0, 111195.08),
        (0.0, 0.0, -1.0, 0.0, 0.0, -111195.08),
        (0.0, 0.0, 0.0, 1.0, 111195.08, 0.0),
        (0.0, 0.0, 0.0, -1.0, -111195.08, 0.0),
        (60.0, 0.0, 60.0, 1.0, 55597.54, 0.0),
        (0.0, 0.0, 60.0, 1.0, 96297.76, 6671704.8),
    ],
    ids=[
        "same-point",
        "one-degree-north",
        "one-degree-south",
        "one-degree-east",
        "one-degree-west",
        "east-at-60-north",
        "uses-average-latitude",
    ],
)
def test_east_north_coordinate_offset_m(
    from_lat, from_lon, to_lat, to_lon, east, north
):
    result = east_north_coordinate_offset_m(from_lat, from_lon, to_lat, to_lon)
    assert result == pytest.approx((east, north), abs=1.0)


def test_sort_clockwise_sweep_starts_north_and_goes_clockwise():
    north = Coordinate(1, 0, 0)
    east = Coordinate(0, 1, 0)
    south = Coordinate(-1, 0, 0)
    west = Coordinate(0, -1, 0)

    result = sort_clockwise_sweep([south, west, north, east])

    assert result == [north, east, south, west]


def test_sort_clockwise_sweep_starts_in_home_direction():
    north = Coordinate(1, 0, 0)
    east = Coordinate(0, 1, 0)
    south = Coordinate(-1, 0, 0)
    west = Coordinate(0, -1, 0)
    home = Coordinate(-5, 0, 0)

    result = sort_clockwise_sweep([north, east, south, west], home)

    assert result == [south, west, north, east]


@pytest.mark.parametrize(
    "home",
    [Coordinate(0, 0, 0), Coordinate(-1e-15, 0, 0)],
    ids=["exactly-on-centroid", "a-hair-south-of-centroid"],
)
def test_sort_clockwise_sweep_home_on_centroid_starts_north(home):
    north = Coordinate(1, 0, 0)
    east = Coordinate(0, 1, 0)
    south = Coordinate(-1, 0, 0)
    west = Coordinate(0, -1, 0)

    result = sort_clockwise_sweep([south, west, north, east], home)

    assert result == [north, east, south, west]


def test_sort_clockwise_sweep_same_direction_closer_first():
    near_north = Coordinate(1, 0, 0)
    far_north = Coordinate(2, 0, 0)
    near_south = Coordinate(-1, 0, 0)
    far_south = Coordinate(-2, 0, 0)

    result = sort_clockwise_sweep([far_south, far_north, near_south, near_north])

    assert result == [near_north, far_north, near_south, far_south]


def test_parse_waypoints_file_gives_frozen_coordinates(tmp_path):
    text = "home: {lat: 1, lon: 2, alt: 3}\nwaypoints: [{lat: 4, lon: 5, alt: 6}]"
    path = write_to_tmp_waypoints_file(tmp_path, text)
    home, waypoints = parse_waypoints_file(path)

    with pytest.raises(dataclasses.FrozenInstanceError):
        home.lat = 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        waypoints[0].lat = 0
