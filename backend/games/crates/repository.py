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
    {
        "id": "crate-pocket",
        "name": "Pocket Crate",
        "price_cents": 100,
        "description": "Spare-change stakes. A cheap way to see the odds in action.",
        "items": [
            {"id": "pocket-common-penny", "name": "Bent Penny", "rarity": "common",
             "value_cents": 34, "sell_value_cents": 25, "image_url": "🪙",
             "description": "Won't buy you much, but it's yours.", "drop_weight": 600},
            {"id": "pocket-uncommon-button", "name": "Lucky Button", "rarity": "uncommon",
             "value_cents": 100, "sell_value_cents": 75, "image_url": "🔘",
             "description": "Rubbed smooth by nervous fingers.", "drop_weight": 280},
            {"id": "pocket-rare-locket", "name": "Tarnished Locket", "rarity": "rare",
             "value_cents": 400, "sell_value_cents": 300, "image_url": "📿",
             "description": "The photo inside has faded away.", "drop_weight": 100},
            {"id": "pocket-epic-key", "name": "Antique Key", "rarity": "epic",
             "value_cents": 1350, "sell_value_cents": 1000, "image_url": "🗝️",
             "description": "Opens a door that no longer exists.", "drop_weight": 18},
            {"id": "pocket-legendary-coin", "name": "Wishing Coin", "rarity": "legendary",
             "value_cents": 9350, "sell_value_cents": 7000, "image_url": "✨",
             "description": "Said to grant one honest wish.", "drop_weight": 2},
        ],
    },
    {
        "id": "crate-classic",
        "name": "Classic Crate",
        "price_cents": 1500,
        "description": "A step up from Pocket — vintage jewelry, better odds at real value.",
        "items": [
            {"id": "classic-common-coin", "name": "Tarnished Coin", "rarity": "common",
             "value_cents": 400, "sell_value_cents": 300, "image_url": "🥉",
             "description": "Currency from a country that no longer exists.", "drop_weight": 620},
            {"id": "classic-uncommon-locket", "name": "Antique Locket", "rarity": "uncommon",
             "value_cents": 1600, "sell_value_cents": 1200, "image_url": "🧿",
             "description": "Still ticks, somehow.", "drop_weight": 260},
            {"id": "classic-rare-brooch", "name": "Emerald Brooch", "rarity": "rare",
             "value_cents": 6000, "sell_value_cents": 4500, "image_url": "💚",
             "description": "Once pinned to a duchess's collar.", "drop_weight": 100},
            {"id": "classic-epic-medallion", "name": "Platinum Medallion", "rarity": "epic",
             "value_cents": 30000, "sell_value_cents": 22500, "image_url": "🏅",
             "description": "Engraved with initials no one remembers.", "drop_weight": 18},
            {"id": "classic-legendary-feather", "name": "Mirage Phoenix Feather", "rarity": "legendary",
             "value_cents": 90000, "sell_value_cents": 67500, "image_url": "🪶",
             "description": "Warm to the touch, always.", "drop_weight": 2},
        ],
    },
    {
        "id": "crate-premium",
        "name": "Premium Crate",
        "price_cents": 10000,
        "description": "Luxury accessories. The floor is comfortable; the ceiling isn't.",
        "items": [
            {"id": "premium-common-cufflink", "name": "Chrome Cufflink", "rarity": "common",
             "value_cents": 2400, "sell_value_cents": 1800, "image_url": "🔗",
             "description": "Missing its pair.", "drop_weight": 600},
            {"id": "premium-uncommon-pen", "name": "Silver Fountain Pen", "rarity": "uncommon",
             "value_cents": 10000, "sell_value_cents": 7500, "image_url": "🖋️",
             "description": "Signed one contract, then vanished into a drawer.", "drop_weight": 280},
            {"id": "premium-rare-cufflinks", "name": "Diamond Cufflinks", "rarity": "rare",
             "value_cents": 40000, "sell_value_cents": 30000, "image_url": "💠",
             "description": "A matching, complete set this time.", "drop_weight": 100},
            {"id": "premium-epic-watch", "name": "Gilded Pocket Watch", "rarity": "epic",
             "value_cents": 213350, "sell_value_cents": 160000, "image_url": "⏱️",
             "description": "Keeps perfect time, for a price.", "drop_weight": 18},
            {"id": "premium-legendary-crown", "name": "Mirage Sovereign Crown", "rarity": "legendary",
             "value_cents": 600000, "sell_value_cents": 450000, "image_url": "👑",
             "description": "Unclaimed by any known royal house.", "drop_weight": 2},
        ],
    },
    {
        "id": "crate-vip",
        "name": "VIP Crate",
        "price_cents": 25000,
        "description": "Precious stones for the high-stakes regulars.",
        "items": [
            {"id": "vip-common-quartz", "name": "Polished Quartz", "rarity": "common",
             "value_cents": 6000, "sell_value_cents": 4500, "image_url": "⚪",
             "description": "Catches light, nothing more.", "drop_weight": 600},
            {"id": "vip-uncommon-amethyst", "name": "Amethyst Pendant", "rarity": "uncommon",
             "value_cents": 25000, "sell_value_cents": 18750, "image_url": "🟣",
             "description": "Cut by a patient hand.", "drop_weight": 280},
            {"id": "vip-rare-ruby", "name": "Ruby Signet Ring", "rarity": "rare",
             "value_cents": 100000, "sell_value_cents": 75000, "image_url": "🔴",
             "description": "Bears a crest belonging to no one in particular.", "drop_weight": 100},
            {"id": "vip-epic-sapphire", "name": "Sapphire Tiara", "rarity": "epic",
             "value_cents": 533350, "sell_value_cents": 400000, "image_url": "🔵",
             "description": "Fit for a very minor pageant.", "drop_weight": 18},
            {"id": "vip-legendary-star", "name": "Mirage Star of Eternity", "rarity": "legendary",
             "value_cents": 1500000, "sell_value_cents": 1125000, "image_url": "⭐",
             "description": "The single rarest stone in the vault.", "drop_weight": 2},
        ],
    },
    {
        "id": "crate-whale",
        "name": "Whale Crate",
        "price_cents": 100000,
        "description": "The top shelf. Only opened by the house's biggest players.",
        "items": [
            {"id": "whale-common-compass", "name": "Gilded Compass", "rarity": "common",
             "value_cents": 24000, "sell_value_cents": 18000, "image_url": "🧭",
             "description": "Always points somewhere expensive.", "drop_weight": 600},
            {"id": "whale-uncommon-chess", "name": "Ivory Chess Piece", "rarity": "uncommon",
             "value_cents": 100000, "sell_value_cents": 75000, "image_url": "♟️",
             "description": "Missing the rest of the set.", "drop_weight": 280},
            {"id": "whale-rare-bust", "name": "Platinum Bust", "rarity": "rare",
             "value_cents": 400000, "sell_value_cents": 300000, "image_url": "🏛️",
             "description": "Nobody's sure who it depicts.", "drop_weight": 100},
            {"id": "whale-epic-skull", "name": "Diamond-Encrusted Skull", "rarity": "epic",
             "value_cents": 2133350, "sell_value_cents": 1600000, "image_url": "💀",
             "description": "Memento mori, but make it luxury.", "drop_weight": 18},
            {"id": "whale-legendary-jewel", "name": "Mirage Crown Jewel", "rarity": "legendary",
             "value_cents": 6000000, "sell_value_cents": 4500000, "image_url": "👑",
             "description": "The single most valuable pull in the game.", "drop_weight": 2},
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
