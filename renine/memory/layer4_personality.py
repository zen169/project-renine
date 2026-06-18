"""Layer 4 memory: personality profiles.

Dual-storage engine utilizing SQLite for relational storage of person profiles
and ChromaDB for semantic search of personality data.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from renine.core.config import get_memory_config
from renine.databases.models.personality import Person
from renine.databases.session import get_session
from renine.memory.retrieval import (
    add_to_vector_store,
    delete_from_vector_store,
    search_vector_store,
)

logger = logging.getLogger("renine.memory.layer4_personality")


def _get_collection_name() -> str:
    """Get the ChromaDB collection name for personality."""
    config = get_memory_config()
    return (
        config.get("memory", {})
        .get("layer4", {})
        .get("chroma_collection", "personality")
    )


def _build_profile_text(
    name: str,
    relationship: str,
    notes: str,
    hobbies: list[str],
    food_preferences: list[str],
) -> str:
    """Build a comprehensive profile string for embedding."""
    hobbies_str = ", ".join(hobbies) if hobbies else "None"
    food_str = ", ".join(food_preferences) if food_preferences else "None"
    return (
        f"Name: {name}. "
        f"Relationship: {relationship}. "
        f"Hobbies: {hobbies_str}. "
        f"Food Preferences: {food_str}. "
        f"Notes: {notes}"
    )


def store_person(
    name: str,
    relationship: str,
    age: int | None = None,
    birthday: str | None = None,
    food_preferences: list[str] | None = None,
    hobbies: list[str] | None = None,
    personality_traits: list[str] | None = None,
    goals: list[str] | None = None,
    habits: list[str] | None = None,
    notes: str = "",
) -> Person:
    """Store or update a person profile in SQLite and ChromaDB.

    Args:
        name: Name of the person (unique).
        relationship: Relationship description.
        age: Current age (optional).
        birthday: Birthday (optional).
        food_preferences: Food preferences list (optional).
        hobbies: Hobbies list (optional).
        personality_traits: Personality traits list (optional).
        goals: Current goals list (optional).
        habits: Habits list (optional).
        notes: Free-form notes.

    Returns:
        The stored Person ORM model.
    """
    db = get_session("personality_db")
    try:
        stmt = select(Person).where(Person.name == name)
        person = db.scalars(stmt).first()

        food = food_preferences or []
        hobs = hobbies or []
        traits = personality_traits or []
        gls = goals or []
        hbts = habits or []

        if person:
            person.relationship = relationship
            person.age = age
            person.birthday = birthday
            person.food_preferences = food
            person.hobbies = hobs
            person.personality_traits = traits
            person.goals = gls
            person.habits = hbts
            person.notes = notes
        else:
            person = Person(
                name=name,
                relationship=relationship,
                age=age,
                birthday=birthday,
                food_preferences=food,
                hobbies=hobs,
                personality_traits=traits,
                goals=gls,
                habits=hbts,
                notes=notes,
            )
            db.add(person)

        db.commit()
        db.refresh(person)

        collection = _get_collection_name()
        chroma_id = f"person:{name}"
        profile_text = _build_profile_text(
            name, relationship, notes, hobs, food,
        )
        add_to_vector_store(
            collection_name=collection,
            id_=chroma_id,
            text=profile_text,
            metadata={"name": name},
        )
        logger.info("Stored person profile for '%s'", name)
        return person
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_person(name: str) -> Person | None:
    """Retrieve a person profile by name.

    Args:
        name: The person's name.

    Returns:
        The Person model or None.
    """
    db = get_session("personality_db")
    try:
        stmt = select(Person).where(Person.name == name)
        return db.scalars(stmt).first()
    finally:
        db.close()


def delete_person(name: str) -> bool:
    """Delete a person profile by name from both SQLite and ChromaDB.

    Args:
        name: The person's name.

    Returns:
        True if deleted, False if not found.
    """
    db = get_session("personality_db")
    try:
        stmt = select(Person).where(Person.name == name)
        person = db.scalars(stmt).first()
        if not person:
            return False

        db.delete(person)
        db.commit()

        collection = _get_collection_name()
        chroma_id = f"person:{name}"
        delete_from_vector_store(collection, chroma_id)

        logger.info("Deleted person profile for '%s'", name)
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_people() -> list[Person]:
    """List all people profiles.

    Returns:
        List of Person models.
    """
    db = get_session("personality_db")
    try:
        stmt = select(Person)
        return list(db.scalars(stmt).all())
    finally:
        db.close()


def search_people(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Semantically search people profiles using ChromaDB notes search.

    Args:
        query: Semantic search query.
        limit: Max results.

    Returns:
        List of dicts containing the matching profiles.
    """
    collection = _get_collection_name()
    chroma_results = search_vector_store(collection, query, limit)

    out = []
    db = get_session("personality_db")
    try:
        for res in chroma_results:
            name = res["metadata"].get("name")
            stmt = select(Person).where(Person.name == name)
            person = db.scalars(stmt).first()
            if person:
                out.append({
                    "name": person.name,
                    "relationship": person.relationship,
                    "age": person.age,
                    "birthday": person.birthday,
                    "food_preferences": person.food_preferences,
                    "hobbies": person.hobbies,
                    "personality_traits": person.personality_traits,
                    "goals": person.goals,
                    "habits": person.habits,
                    "notes": person.notes,
                    "distance": res["distance"],
                })
        return out
    finally:
        db.close()
