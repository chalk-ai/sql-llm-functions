"""The demo's fictional data: support tickets and product reviews for Thistle & Pine, a made-up
online home-goods store. Every name, order number and email address here is invented.

`tables_cte()` renders both tables as a SQL WITH clause, so each query reads them like any other
table without needing a warehouse behind the demo.
"""

from __future__ import annotations

TICKETS: list[tuple[int, str, str, str, str]] = [
    # (id, customer, plan, channel, body)
    (
        101,
        "Maya R.",
        "pro",
        "email",
        "I was charged twice for order TP-48213. Please refund the duplicate charge of $86.40.",
    ),
    (
        102,
        "Dev P.",
        "free",
        "chat",
        "The checkout page spins forever when I try to pay with a gift card. Tried two browsers.",
    ),
    (
        103,
        "Hannah K.",
        "pro",
        "email",
        "My linen duvet cover from order TP-47790 arrived torn along the seam. I want a replacement, not store credit.",
    ),
    (
        104,
        "Owen T.",
        "pro",
        "chat",
        "Honestly this is the third late delivery this month. If order TP-48301 isn't here by Friday I'm cancelling my membership.",
    ),
    (
        105,
        "Priya S.",
        "free",
        "email",
        "Can you add a way to save items to a wishlist without making an account?",
    ),
    (
        106,
        "Luis G.",
        "pro",
        "phone",
        "I reset my password and now the app says my account doesn't exist. I have orders on it!",
    ),
    (
        107,
        "Amara N.",
        "free",
        "email",
        "Where is my order TP-48177? Tracking hasn't updated in six days.",
    ),
    (
        108,
        "Sam W.",
        "pro",
        "chat",
        "The ceramic planter set (order TP-48022) was lovely, but one pot was chipped. Small thing, a single replacement pot is fine.",
    ),
    (
        109,
        "Grace L.",
        "pro",
        "email",
        "Your app logs me out every time I switch tabs. It's been like this since the last update and it is driving me up the wall.",
    ),
    (
        110,
        "Ben A.",
        "free",
        "chat",
        "Do you ship to Canada? I couldn't find it in the FAQ.",
    ),
    (
        111,
        "Chloe M.",
        "pro",
        "email",
        "I returned the oak side table two weeks ago (TP-47512) and still haven't seen the refund. This is unacceptable.",
    ),
    (
        112,
        "Noah B.",
        "pro",
        "phone",
        "Please cancel my Pro membership at the end of this billing cycle. Nothing wrong, I'm just moving abroad.",
    ),
    (
        113,
        "Isla F.",
        "free",
        "email",
        "The discount code SPRING15 says it's expired but your banner says it runs until Sunday.",
    ),
    (
        114,
        "Ravi K.",
        "pro",
        "chat",
        "It would be great to filter rugs by pile height. Right now I have to open every product page.",
    ),
    (
        115,
        "Zoe H.",
        "pro",
        "email",
        "Order TP-48345 was delivered to the wrong address. The driver's photo shows a house I've never seen.",
    ),
    (
        116,
        "Leo V.",
        "free",
        "chat",
        "Two-factor codes never arrive by SMS, so I can't log in at all.",
    ),
    (
        117,
        "Mina J.",
        "pro",
        "email",
        "I love the throw blankets, but I was billed $14.99 for shipping on a Pro order, which should ship free. Order TP-48410.",
    ),
    (
        118,
        "Ethan C.",
        "pro",
        "chat",
        "Fourth time asking. Nobody has answered about my broken lamp from order TP-47901. I'm done with this company.",
    ),
]

REVIEWS: list[tuple[int, str, int, str]] = [
    # (id, product, stars, body)
    (
        1,
        "Linen duvet cover",
        5,
        "Softest bedding I've owned. It gets better with every wash and the oat color is exactly like the photos.",
    ),
    (
        2,
        "Linen duvet cover",
        2,
        "Beautiful fabric, but the buttons came off after two washes and the seams are already fraying.",
    ),
    (
        3,
        "Ceramic planter set",
        4,
        "Gorgeous glaze and good drainage. Knocked off a star because the smallest pot is tinier than I expected.",
    ),
    (
        4,
        "Oak side table",
        1,
        "Arrived wobbly with a cracked leg. Assembly instructions were missing a whole step. Returned it.",
    ),
    (
        5,
        "Oak side table",
        5,
        "Solid, heavy, and the finish is lovely. Took ten minutes to put together. Worth every penny.",
    ),
    (
        6,
        "Wool throw blanket",
        5,
        "Warm without being itchy. My cat has claimed it permanently, which is the highest praise in this house.",
    ),
    (
        7,
        "Wool throw blanket",
        3,
        "Nice weight, but it shed a lot for the first week and the color is greyer than pictured.",
    ),
    (
        8,
        "Brass table lamp",
        2,
        "Looks expensive, but the switch stopped working within a month. Customer service took forever to reply.",
    ),
    (
        9,
        "Jute area rug",
        4,
        "Great texture and it anchors the room. It does smell earthy for a few days, so air it out first.",
    ),
    (
        10,
        "Jute area rug",
        5,
        "Held up to two dogs and a toddler. Vacuum it once a week and it looks brand new.",
    ),
    (
        11,
        "Stoneware dinner set",
        3,
        "Pretty plates, but two of the bowls arrived chipped and the replacement took three weeks.",
    ),
    (
        12,
        "Stoneware dinner set",
        5,
        "Microwave and dishwasher safe, stacks neatly, and the speckled glaze hides scratches. Ordered a second set.",
    ),
]


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def tables_cte() -> str:
    tickets = ",\n    ".join(
        f"({i}, {_quote(c)}, {_quote(p)}, {_quote(ch)}, {_quote(b)})"
        for i, c, p, ch, b in TICKETS
    )
    reviews = ",\n    ".join(
        f"({i}, {_quote(p)}, {s}, {_quote(b)})" for i, p, s, b in REVIEWS
    )
    return (
        "WITH tickets AS (\n  SELECT * FROM (VALUES\n    "
        + tickets
        + "\n  ) AS t(id, customer, plan, channel, body)\n),\n"
        + "reviews AS (\n  SELECT * FROM (VALUES\n    "
        + reviews
        + "\n  ) AS r(id, product, stars, body)\n)\n"
    )
