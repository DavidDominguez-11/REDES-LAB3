import pytest

from router.transport.ndjson import LineBuffer, encode_line


def test_single_chunk_single_line():
    buf = LineBuffer()
    lines = buf.feed(b'{"a":1}\n')
    assert lines == [b'{"a":1}']
    assert buf.pending_bytes() == 0


def test_message_split_across_chunks():
    """Simula TCP entregando un mensaje partido en varios recv()."""
    buf = LineBuffer()
    assert buf.feed(b'{"a":1') == []
    assert buf.feed(b',"b":2}') == []
    assert buf.feed(b'\n') == [b'{"a":1,"b":2}']


def test_multiple_messages_in_one_chunk():
    """Simula TCP entregando varios mensajes juntos en un solo recv()."""
    buf = LineBuffer()
    lines = buf.feed(b'{"a":1}\n{"a":2}\n{"a":3}\n')
    assert lines == [b'{"a":1}', b'{"a":2}', b'{"a":3}']


def test_partial_last_line_stays_buffered():
    buf = LineBuffer()
    lines = buf.feed(b'{"a":1}\n{"a":2')
    assert lines == [b'{"a":1}']
    assert buf.pending_bytes() > 0
    lines2 = buf.feed(b'}\n')
    assert lines2 == [b'{"a":2}']


def test_encode_line_rejects_embedded_newline():
    with pytest.raises(ValueError):
        encode_line("linea\ncon salto")


def test_encode_line_appends_single_newline():
    encoded = encode_line('{"a":1}')
    assert encoded == b'{"a":1}\n'
