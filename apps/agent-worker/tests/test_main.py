import json

from graph import build_graph
from main import handle_event


class RecordingNotifier:
    def __init__(self) -> None:
        self.classify_calls: list[dict] = []
        self.draft_calls: list[dict] = []

    def send_classify(self, state):
        self.classify_calls.append(dict(state))

    def send_draft(self, state):
        self.draft_calls.append(dict(state))


def test_handle_event_full_pipeline_pushes_classify_and_draft():
    graph = build_graph()
    notifier = RecordingNotifier()
    raw = json.dumps({"ticket_id": "t1", "type": "created", "title": "how do I set up sso"})

    handle_event(graph, notifier, raw)

    assert len(notifier.classify_calls) == 1
    assert notifier.classify_calls[0]["ticket_id"] == "t1"
    assert len(notifier.draft_calls) == 1


def test_handle_event_low_confidence_only_pushes_classify():
    graph = build_graph()
    notifier = RecordingNotifier()
    raw = json.dumps({"ticket_id": "t2", "type": "created", "title": "zzz asdkjasd"})

    handle_event(graph, notifier, raw)

    assert len(notifier.classify_calls) == 1
    assert len(notifier.draft_calls) == 0


def test_handle_event_ignores_malformed_json():
    graph = build_graph()
    notifier = RecordingNotifier()
    handle_event(graph, notifier, "{not json")
    assert notifier.classify_calls == []


def test_handle_event_ignores_missing_ticket_id():
    graph = build_graph()
    notifier = RecordingNotifier()
    handle_event(graph, notifier, json.dumps({"type": "created", "title": "no id"}))
    assert notifier.classify_calls == []


def test_handle_event_swallows_notifier_errors():
    graph = build_graph()

    class FailingNotifier:
        def send_classify(self, state):
            raise ConnectionError("notifier unreachable")

        def send_draft(self, state):  # pragma: no cover - never reached, satisfies Notifier shape
            raise AssertionError("should not be called")

    raw = json.dumps({"ticket_id": "t3", "type": "created", "title": "sso setup"})
    handle_event(graph, FailingNotifier(), raw)  # must not raise
