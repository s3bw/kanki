import heapq
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile

from rich.console import Console, Group
from rich.prompt import Prompt

# from rich.group import Group
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.markdown import Markdown
from vim_edit import editor

import models
import queues
from models import Deck, FlashOptions, Card


console = Console()


def display_options(options):
    """Display a list of options using rich and return user's selection."""
    for i, option in enumerate(options, start=1):
        console.print(f"({i}) {option}")
    choice = Prompt.ask(
        "Select an option", choices=[str(i) for i in range(1, len(options) + 1)]
    )
    return int(choice) - 1


def main_menu():
    """Main menu with Play, Extend, Create options."""
    console.clear()
    options = ["Play", "Extend", "Edit", "Create"]
    choice = display_options(options)

    if options[choice] == "Play":
        deck = select_deck()
        play_flashcard(deck)
    elif options[choice] == "Extend":
        deck = select_deck()
        extend_deck(deck)
    elif options[choice] == "Edit":
        deck = select_deck()
        edit_deck(deck)
    elif options[choice] == "Create":
        create_deck()


def select_deck() -> Deck:
    """Let user select a deck and then show the flash card panel."""
    console.clear()
    decks = Deck.select()
    if not decks:
        console.print("[bold red]No deck has been created[/bold red]")
        exit()
    console.print("[bold underline]Select a deck:[/bold underline]")
    deck_choice = display_options([d.name for d in decks])
    return decks[deck_choice]


def edit_deck(deck: Deck):
    cards = Card.select().where(Card.deck == deck).order_by(Card.id)
    table = Table(title=deck.name, box=box.HEAVY_HEAD)
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Queue")
    table.add_column("Question", justify="left")
    table.add_column("Answer", justify="left")

    for card in cards:
        table.add_row(str(card.id), str(card.queue), card.question, card.answer)

    console.print(table)
    select = console.input("[bold yellow]Enter ID of card to edit[/bold yellow]")

    card = Card.get_by_id(select)

    with NamedTemporaryFile(mode="r+", suffix=".tmp") as file:
        file.write(card.answer)
        editor.open(file)
        content = file.read()

    card.answer = content
    card.save()


def extend_deck(deck):
    """Allow the user to create a new flashcard."""

    i = 0
    while True:
        console.clear()
        console.print(Panel(f"Flashcards added [bold green]{i}[/bold green]"))
        console.print(f"[bold underline]Adding to {deck.name}[/bold underline]\n")

        question = Prompt.ask("Question")
        if not question:
            console.print("Done!")
            break
        answer = Prompt.ask("Answer")
        if not answer:
            console.print("Done!")
            break
        topics_str = Prompt.ask("topics (comma-separated)")
        topics = [topic.strip() for topic in topics_str.split(",")]

        models.create_card(deck, question, answer, topics)
        i += 1


def create_deck():
    console.print("[bold underline]Creating a new deck[/bold underline]")
    name = Prompt.ask("Name")
    # This isn't checking for an existing deck of the same name.
    deck = Deck.create(name=name)
    deck.save()
    console.print(f"[green] New deck created: {deck.id} {deck.name}")


def play_flashcard(deck):
    """Simulate showing a flashcard with options."""
    cards = queues.start_session(deck)
    if not cards:
        console.print(f"[bold red]Deck {deck.id} {deck.name} is empty[/bold red]")
        exit()

    def noop():
        return

    info = noop

    while cards:
        total = len(cards)
        (_, _, card) = heapq.heappop(cards)

        show_answer = False
        while True:
            console.clear()
            info()
            question = (
                f"[bold cyan]Deck: {deck.name}[/bold cyan]\n"
                f"[bold]Remain:[/bold] {total}\n"
                f"[bold]Question:[/bold] {card.question}\n\n"
            )
            answer = Markdown(card.answer)
            content = (
                Group(question, "[bold]Answer:[/bold]", answer)
                if show_answer
                else Group(question)
            )
            console.print(Panel(content))

            choice = FlashOptions(
                Prompt.ask(
                    "\[r]eveal [yellow]\[a]gain [1]hard[/yellow] [green][2]good [3]easy[/green] [red]\[d]elete[/red]",
                    choices=[m.value for m in FlashOptions],
                )
            )

            if choice == FlashOptions.REVEAL:
                show_answer = True
                info = noop
            elif choice == FlashOptions.EXIT:
                exit()
            elif choice == FlashOptions.DELETE:
                models.delete_card(card.id)

                def delete():
                    console.print(f"[red]Flashcard {card.id} deleted![/red]")

                info = delete
                break
            else:
                olddue = card.due
                card.handle(choice)
                if card.due < (datetime.now() + timedelta(hours=1)).timestamp():
                    heapq.heappush(
                        cards, (queues.QUEUE_PRIORITY[card.queue], -card.due, card)
                    )

                def handle():
                    console.print(f"old {olddue}, new {card.due}")
                    console.print(f"[blue]Flashcard marked as {choice}[/blue]")

                info = handle
                break


if __name__ == "__main__":
    main_menu()
