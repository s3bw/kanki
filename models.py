from enum import Enum
from datetime import datetime, timedelta

from peewee import Model, CharField, IntegerField, ForeignKeyField, SqliteDatabase, ManyToManyField, FloatField


MAX_TRAINING_REPS = 5


class ModelComparitorMixin:

    def __lt__(self, other):
        return self.id < other.id

    def __le__(self, other):
        return self.id <= other.id

    def __gt__(self, other):
        return self.id > other.id

    def __ge__(self, other):
        return self.id >= other.id

    def __eq__(self, other):
        return self.id == other.id


class Queue(Enum):
    NEW = 0
    LEARNING = 1
    REVIEW = 2


class QueueType(Enum):

    NEW = 0
    LEARNING = 1
    REVIEW = 2
    RELEARNING = 3


class FlashOptions(Enum):
    REVEAL = "r"
    AGAIN = "a"
    HARD = "1"
    GOOD = "2"
    EASY = "3"
    DELETE = "d"
    EXIT = "q"


db = SqliteDatabase('kanki-beta.db')


class Deck(Model):
    id = IntegerField(primary_key=True)
    name = CharField(null=False)

    class Meta:
        database = db


class Topic(Model):
    """
    new_card.topic.add("network")
    """
    id = IntegerField(primary_key=True)
    name = CharField(null=False, unique=True)

    class Meta:
        database = db


def compute_due(**kwargs):
    return (datetime.now() + timedelta(**kwargs)).timestamp()


class Card(Model, ModelComparitorMixin):
    id = IntegerField(primary_key=True)
    question = CharField(null=False)
    answer = CharField(null=False)
    deck = ForeignKeyField(Deck, backref='cards', on_delete='CASCADE')
    queue = IntegerField(null=False)
    type = IntegerField(null=False)
    due = FloatField(null=False)
    left = IntegerField(null=False)
    reps = IntegerField(null=False)
    ivl = IntegerField(null=False)
    factor = IntegerField(null=False)

    topics = ManyToManyField(Topic, backref="cards", on_delete="CASCADE")

    class Meta:

        database = db

    def handle(self, choice):
        self.reps += 1
        match self.queue:
            case Queue.NEW.value:
                self.handle_new(choice)
            case Queue.LEARNING.value:
                self.handle_learning(choice)
            case Queue.REVIEW.value:
                self.handle_review(choice)
            case _:
                pass
        self.save()

    def handle_new(self, choice):
        self.queue = Queue.LEARNING.value
        match choice:
            case FlashOptions.AGAIN:
                self.left = MAX_TRAINING_REPS
            case FlashOptions.HARD:
                self.left -= 1
                self.due = compute_due(minutes=1)
            case FlashOptions.GOOD:
                self.left -= 1
                self.due = compute_due(minutes=5)
            case FlashOptions.EASY:
                self.left -= 1
                self.due = compute_due(days=1)
            case _:
                pass

    def handle_learning(self, choice):
        match choice:
            case FlashOptions.AGAIN:
                self.left = MAX_TRAINING_REPS
            case FlashOptions.HARD:
                self.left -= 1
                self.due = compute_due(minutes=1)
            case FlashOptions.GOOD:
                self.left -= 1
                self.due = compute_due(minutes=5)
            case FlashOptions.EASY:
                self.left -= 1
                self.due = compute_due(days=1)
            case _:
                pass

        if self.left != 0:
            return
        self.queue = Queue.REVIEW.value

    def handle_review(self, choice):
        match choice:
            case FlashOptions.AGAIN:
                self.left = MAX_TRAINING_REPS
                self.queue = Queue.LEARNING.value
                self.type = QueueType.RELEARNING.value
            case FlashOptions.HARD:
                self.factor = int(self.factor * 0.85)
                self.ivl = int((self.factor / 1000) * self.ivl)
                self.due = compute_due(days=self.ivl)
            case FlashOptions.GOOD:
                self.ivl = int((self.factor / 1000) * self.ivl)
                self.due = compute_due(days=self.ivl)
            case FlashOptions.EASY:
                self.factor = int(self.factor * 1.15)
                self.ivl = int((self.factor / 1000) * self.ivl)
                self.due = compute_due(days=self.ivl)
            case _:
                pass



class CardTopicThrough(Model):
    card = ForeignKeyField(Card, backref='topics')
    topic = ForeignKeyField(Topic, backref='cards')

    class Meta:

        database = db


def create_card(deck: Deck, question: str, answer: str, topics: list) -> Card:
    card = Card.create(
        deck=deck,
        question=question,
        answer=answer,
        queue=Queue.NEW.value,
        type=QueueType.NEW.value,
        due=0,
        left=MAX_TRAINING_REPS,
        reps=0,
        ivl=1,
        factor=2500,
    )
    for topic in topics:
        topic, created = Topic.get_or_create(name=topic)
        CardTopicThrough.create(card=card, topic=topic)
    card.save()
    return card


def delete_card(card_id):
    """Delete a card by its ID, including its relationships in the through table."""

    card = Card.get_by_id(card_id)
    CardTopicThrough.delete().where(CardTopicThrough.card == card).execute()
    card.delete_instance()


if __name__ == "__main__":
    # Jank database migrations
    db.connect()
    db.create_tables([Deck, Card, Topic, CardTopicThrough])
    db.close()
