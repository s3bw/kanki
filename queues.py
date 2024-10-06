from datetime import datetime
from heapq import heapify

from models import Card, Deck, Queue


SESSION_LIMIT = 150
REVIEW_LIMIT = 25

QUEUE_PRIORITY = {
    Queue.NEW.value: 1,
    Queue.LEARNING.value: 0,
    Queue.REVIEW.value: 2,
}


def start_session(deck: Deck):
    today = datetime.now().timestamp()

    query = Card.select().where(
        (Card.deck == deck)
        & (Card.due < today)
        & (Card.queue == Queue.LEARNING.value)
    ).limit(SESSION_LIMIT)

    learning = list(query)

    query = Card.select().where(
        (Card.deck == deck)
        & (Card.due < today)
        & (Card.queue == Queue.REVIEW.value)
    ).limit(REVIEW_LIMIT)

    reviewing = list(query)
    total_cards = len(learning) + len(reviewing)
    new_limit = max(int(total_cards * 0.2), 15)

    query = Card.select().where(
        (Card.deck == deck)
        & (Card.due < today)
        & (Card.queue == Queue.NEW.value)
    ).limit(new_limit)

    new_cards = list(query)

    heap = []
    for card in learning:
        heap.append((0, card.due, card))

    for card in new_cards:
        heap.append((1, card.due, card))

    for card in reviewing:
        heap.append((2, card.due, card))

    heapify(heap)
    return heap


if __name__ == "__main__":
    deck = Deck.select().where(Deck.name == "Maths")
    start_session(deck)
