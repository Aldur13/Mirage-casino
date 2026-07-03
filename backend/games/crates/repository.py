import uuid
from datetime import datetime, timezone

from database import get_session

# Default catalog — a placeholder until the admin dashboard (later phase)
# can add/edit crates and items. Seeded idempotently (MERGE on id) so
# re-running startup never duplicates them.
_DEFAULT_CRATES = [
    {
        "id": "crate-starter",
        "name": "Starter Crate",
        "price_cents": 500,
        "description": "A cheap crate with modest odds at something rare.",
        # Sell-value expectation is tuned to ~1% house edge (weighted sum of
        # sell_value_cents ~= 99% of price_cents) — rarity odds (drop_weight)
        # and the value/sell_value ratio per item are unchanged, only the
        # scale of the payouts.
        "items": [
            {"id": "starter-common-coin", "name": "Copper Trinket", "rarity": "common",
             "value_cents": 170, "sell_value_cents": 127, "image_url": "🪙",
             "description": "Barely worth melting down.", "drop_weight": 600},
            {"id": "starter-uncommon-charm", "name": "Silver Charm", "rarity": "uncommon",
             "value_cents": 509, "sell_value_cents": 381, "image_url": "🔮",
             "description": "A minor good-luck charm.", "drop_weight": 280},
            {"id": "starter-rare-ring", "name": "Sapphire Ring", "rarity": "rare",
             "value_cents": 2119, "sell_value_cents": 1526, "image_url": "💍",
             "description": "Catches the light nicely.", "drop_weight": 100},
            {"id": "starter-epic-crown", "name": "Jeweled Crown", "rarity": "epic",
             "value_cents": 6781, "sell_value_cents": 5086, "image_url": "👑",
             "description": "Fit for minor royalty.", "drop_weight": 18},
            {"id": "starter-legendary-gem", "name": "Mirage Heartstone", "rarity": "legendary",
             "value_cents": 42380, "sell_value_cents": 33904, "image_url": "💎",
             "description": "Legend says it's never the same color twice.", "drop_weight": 2},
        ],
    },
    {
        "id": "crate-high-roller",
        "name": "High Roller Crate",
        "price_cents": 5000,
        "description": "Expensive, but the floor and ceiling are both much higher.",
        "items": [
            {"id": "hr-common-watch", "name": "Steel Watch", "rarity": "common",
             "value_cents": 1418, "sell_value_cents": 1040, "image_url": "⌚",
             "description": "Keeps decent time.", "drop_weight": 500},
            {"id": "hr-uncommon-vase", "name": "Porcelain Vase", "rarity": "uncommon",
             "value_cents": 2835, "sell_value_cents": 2127, "image_url": "🏺",
             "description": "Older than it looks.", "drop_weight": 300},
            {"id": "hr-rare-statue", "name": "Golden Statue", "rarity": "rare",
             "value_cents": 9451, "sell_value_cents": 7088, "image_url": "🗿",
             "description": "Surprisingly heavy.", "drop_weight": 130},
            {"id": "hr-epic-chalice", "name": "Ancient Chalice", "rarity": "epic",
             "value_cents": 28353, "sell_value_cents": 21265, "image_url": "🏆",
             "description": "Museums have asked about this one.", "drop_weight": 55},
            {"id": "hr-legendary-orb", "name": "Mirage Eternity Orb", "rarity": "legendary",
             "value_cents": 141765, "sell_value_cents": 113412, "image_url": "🔱",
             "description": "The rarest pull in the game.", "drop_weight": 15},
        ],
    },
]


def seed_default_crates() -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_session() as session:
        for crate in _DEFAULT_CRATES:
            session.run(
                """
                MERGE (c:Crate {id: $id})
                ON CREATE SET c.created_at = $now
                SET c.name = $name, c.price_cents = $price_cents,
                    c.description = $description, c.active = true
                """,
                id=crate["id"], name=crate["name"], price_cents=crate["price_cents"],
                description=crate["description"], now=now,
            )
            for item in crate["items"]:
                session.run(
                    """
                    MATCH (c:Crate {id: $crate_id})
                    MERGE (i:CrateItem {id: $id})
                    SET i.crate_id = $crate_id, i.name = $name, i.rarity = $rarity,
                        i.value_cents = $value_cents, i.sell_value_cents = $sell_value_cents,
                        i.image_url = $image_url, i.description = $description,
                        i.drop_weight = $drop_weight
                    MERGE (c)-[:CONTAINS]->(i)
                    """,
                    crate_id=crate["id"], **item,
                )


def list_crates() -> list[dict]:
    with get_session() as session:
        records = session.run(
            "MATCH (c:Crate {active: true}) RETURN c.id AS id, c.name AS name, "
            "c.price_cents AS price_cents, c.description AS description ORDER BY c.price_cents"
        ).data()
    return records


def get_crate_with_items(crate_id: str) -> dict | None:
    with get_session() as session:
        crate = session.run(
            "MATCH (c:Crate {id: $id, active: true}) RETURN c.id AS id, c.name AS name, "
            "c.price_cents AS price_cents, c.description AS description",
            id=crate_id,
        ).single()
        if crate is None:
            return None
        items = session.run(
            """
            MATCH (:Crate {id: $id})-[:CONTAINS]->(i:CrateItem)
            RETURN i.id AS id, i.name AS name, i.rarity AS rarity, i.value_cents AS value_cents,
                   i.sell_value_cents AS sell_value_cents, i.image_url AS image_url,
                   i.description AS description, i.drop_weight AS drop_weight
            """,
            id=crate_id,
        ).data()
    result = dict(crate)
    result["items"] = items
    return result


def create_inventory_item(user_id: str, crate_item: dict, opened_at: str) -> dict:
    inventory_id = str(uuid.uuid4())
    with get_session() as session:
        session.run(
            """
            MATCH (u:User {id: $user_id})
            CREATE (inv:InventoryItem {
                id: $inventory_id, user_id: $user_id, crate_item_id: $crate_item_id,
                name: $name, rarity: $rarity, value_cents: $value_cents,
                sell_value_cents: $sell_value_cents, image_url: $image_url,
                obtained_at: $obtained_at, status: 'owned'
            })
            CREATE (u)-[:OWNS_ITEM]->(inv)
            """,
            user_id=user_id, inventory_id=inventory_id, crate_item_id=crate_item["id"],
            name=crate_item["name"], rarity=crate_item["rarity"], value_cents=crate_item["value_cents"],
            sell_value_cents=crate_item["sell_value_cents"], image_url=crate_item["image_url"],
            obtained_at=opened_at,
        )
    return get_inventory_item(inventory_id, user_id)


def get_inventory_item(item_id: str, user_id: str) -> dict | None:
    with get_session() as session:
        result = session.run(
            "MATCH (i:InventoryItem {id: $id, user_id: $user_id}) RETURN i",
            id=item_id, user_id=user_id,
        ).single()
    return dict(result["i"]) if result else None


def get_inventory(user_id: str, status: str | None = None) -> list[dict]:
    query = "MATCH (u:User {id: $user_id})-[:OWNS_ITEM]->(i:InventoryItem)"
    if status:
        query += " WHERE i.status = $status"
    query += " RETURN i ORDER BY i.obtained_at DESC"
    with get_session() as session:
        records = session.run(query, user_id=user_id, status=status).data()
    return [dict(r["i"]) for r in records]


def mark_item_sold(item_id: str, sold_at: str) -> None:
    with get_session() as session:
        session.run(
            "MATCH (i:InventoryItem {id: $id}) SET i.status = 'sold', i.sold_at = $sold_at",
            id=item_id, sold_at=sold_at,
        )
