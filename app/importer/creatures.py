from app.importer.traits import NEEDED_KEYS
import os
import csv
import re

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from app.config import ROOT_DIR
from app.orm.base import slug_default, to_slug
from app.orm.base import Session
from app.orm.creature import CreatureOrm
from app.orm.klass import KlassOrm
from app.orm.race import RaceOrm
from app.orm.source import SourceOrm
from app.orm.trait import TraitOrm
from .icons import load_icon_to_base64

BIO_NEW_LINE_REGEX = re.compile(r'([^\n])\n')

BIO_KEYS = [
    "name",
    "bio",
]

NEEDED_KEYS = [
    "name",
    "health",
    "attack",
    "intelligence",
    "defense",
    "speed",
    "klass",
    "race",
    "sources",
    "trait",
    "battle_sprite",
]
BATTLE_SPRITES_PATH = os.path.join(ROOT_DIR, "data", "battle_sprites")


def creatures_importer():
    with Session.begin() as session:
        values = list()

        klasses = session.execute(select(KlassOrm)).scalars().all()
        slug_to_klasses = {klass.slug: klass for klass in klasses}

        races = session.execute(select(RaceOrm)).scalars().all()
        slug_to_races = {race.slug: race for race in races}

        sources = session.execute(select(SourceOrm)).scalars().all()
        slug_to_sources = {source.slug: source for source in sources}

        traits = session.execute(select(TraitOrm)).scalars().all()
        slug_to_traits = {trait.slug: trait for trait in traits}

        creature_to_bio = {}

        with open(os.path.join(ROOT_DIR, "data", "bios.csv")) as csvfile:
            for row in csv.DictReader(csvfile):
                creature_to_bio[row["name"]] = BIO_NEW_LINE_REGEX.sub(r'\1 ', row["bio"])

        with open(os.path.join(ROOT_DIR, "data", "creatures.csv")) as csvfile:
            for row in csv.DictReader(csvfile):
                value = {key: row[key] for key in NEEDED_KEYS}
                slug_default("name", value)

                klass = value.pop("klass")
                race = value.pop("race")
                trait = value.pop("trait")
                sources = value.pop("sources").split(",")

                value["klass_id"] = slug_to_klasses[to_slug(klass)].id
                value["race_id"] = slug_to_races[to_slug(race)].id
                value["trait_id"] = slug_to_traits[to_slug(trait)].id
                value["source_ids"] = [
                    slug_to_sources[to_slug(source)].id for source in sources
                ]

                battle_sprite = value.pop("battle_sprite")
                battle_sprite_file = os.path.join(
                    BATTLE_SPRITES_PATH, battle_sprite
                )
                value["battle_sprite"] = load_icon_to_base64(
                    battle_sprite_file
                )

                value["description"] = creature_to_bio.get(value["name"], "")

                values.append(value)

        stmt = insert(CreatureOrm).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={
                "name": stmt.excluded.name,
                "description": stmt.excluded.description,
                "battle_sprite": stmt.excluded.battle_sprite,
                "health": stmt.excluded.health,
                "attack": stmt.excluded.attack,
                "intelligence": stmt.excluded.intelligence,
                "defense": stmt.excluded.defense,
                "speed": stmt.excluded.speed,
                "klass_id": stmt.excluded.klass_id,
                "race_id": stmt.excluded.race_id,
                "trait_id": stmt.excluded.trait_id,
                "source_ids": stmt.excluded.source_ids,
                "updated_at": text("now()"),
            },
        )
        session.execute(stmt)
