from agent_registry.llm_eval import (
    answer_relevance,
    context_precision,
    context_recall,
    faithfulness,
)


def test_faithfulness_grounded():
    assert faithfulness("the sky is blue", "the sky is blue today") == 1.0


def test_faithfulness_ungrounded():
    assert faithfulness("aliens landed", "the sky is blue") == 0.0


def test_answer_relevance_on_topic():
    assert answer_relevance("what is the sky color", "the sky is blue") > 0


def test_answer_relevance_off_topic():
    assert answer_relevance("what is the sky color", "bananas are yellow") == 0.0


def test_context_precision():
    assert context_precision("sky blue today", "sky blue") == round(2 / 3, 4)


def test_context_recall():
    assert context_recall("sky blue", "sky blue today") == round(2 / 3, 4)


def test_empty_answer_faithfulness():
    assert faithfulness("", "anything") == 1.0


def test_empty_question_relevance():
    assert answer_relevance("", "answer") == 0.0
