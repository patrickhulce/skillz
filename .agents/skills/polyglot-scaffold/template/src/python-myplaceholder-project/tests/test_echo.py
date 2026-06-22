from myplaceholder_project import echo


def test_echo_roundtrip() -> None:
    assert echo(b"hello") == b"hello"
