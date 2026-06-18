"""Pet agent for managing pet profiles, feeding schedules, and medications.

Orchestrates pet profiles in the database and schedules feeding reminders
using APScheduler, triggering event bus alerts when reminders fire.
"""
from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select

from renine.agents.base_agent import AgentManifest, BaseAgent, MemoryAccessLevel
from renine.core.events import event_bus
from renine.core.logging_config import get_logger
from renine.databases.models.pets import Pet
from renine.databases.session import get_session
from renine.memory.expiration import get_scheduler
from renine.tools.permissions import PermissionLevel

logger = get_logger(__name__)


def _fire_feeding_reminder(pet_name: str, time_str: str, amount: str) -> None:
    """Callback function triggered by APScheduler when a feeding reminder is due.

    Args:
        pet_name: Name of the pet.
        time_str: Scheduled time (HH:MM).
        amount: Scheduled amount.
    """
    payload = {
        "pet_name": pet_name,
        "time": time_str,
        "amount": amount,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    event_bus.publish("pet.feeding_reminder", payload)
    logger.info(
        "pet_feeding_reminder_fired",
        pet=pet_name,
        time=time_str,
        amount=amount,
    )


class PetAgent(BaseAgent):
    """Agent that manages pet profiles, schedules reminders, and tracks medicine."""

    def __init__(self) -> None:
        """Initialize the PetAgent and synchronize database schedules."""
        super().__init__()
        try:
            self.sync_all_reminders()
        except Exception as e:
            logger.warning("Failed to sync pet reminders on init: %s", e)

    def get_manifest(self) -> AgentManifest:
        """Return the capability manifest for the PetAgent."""
        return AgentManifest(
            name="pets",
            description="Manages pet profiles, feeding schedules, and medications",
            required_tools=[],
            memory_access_level=MemoryAccessLevel.FULL_ACCESS,
            permission_level=PermissionLevel.STANDARD,
            active_phase=3,
        )

    def process(
        self,
        user_input: str,
        context: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process pet-related queries.

        Args:
            user_input: The user's query text.
            context: Optional conversation context.
            metadata: Optional additional metadata.

        Returns:
            Response dict with 'content', 'success', and source.
        """
        try:
            query = user_input.lower().strip()
            if "list pets" in query or "show pets" in query:
                pets = self.list_pets()
                if not pets:
                    content = "No pet profiles found."
                else:
                    content = "Pet Profiles:\n" + "\n".join(
                        f"- {pet.name} ({pet.species}): "
                        f"feeding schedule: {pet.feeding_schedule}"
                        for pet in pets
                    )
                return {
                    "content": content,
                    "success": True,
                    "pets": [{"name": p.name, "species": p.species} for p in pets],
                    "source_agent": "pets",
                }

            if "feed " in query:
                # Simple parsing for "feed [pet]"
                pet_name = user_input.split("feed ")[-1].strip().strip("!.")
                success = self.feed_pet(pet_name)
                if success:
                    content = f"I've recorded that you fed {pet_name} just now."
                else:
                    content = f"Could not find a pet named {pet_name}."
                return {
                    "content": content,
                    "success": success,
                    "source_agent": "pets",
                }

            return {
                "content": "I can help you manage your pets, feeding schedules, and medicine.",
                "success": True,
                "source_agent": "pets",
            }

        except Exception as e:
            logger.exception("Error in PetAgent processing")
            return {
                "content": "",
                "success": False,
                "error": str(e),
                "source_agent": "pets",
            }

    def add_pet(
        self,
        name: str,
        species: str,
        breed: str | None = None,
        age: float | None = None,
        birthday: str | None = None,
        weight: float | None = None,
        feeding_schedule: list[dict[str, Any]] | None = None,
        medical_conditions: list[str] | None = None,
        medications: list[dict[str, Any]] | None = None,
    ) -> Pet:
        """Add a new pet profile and schedule its feeding reminders.

        Args:
            name: Name of the pet.
            species: Species (e.g. dog, cat).
            breed: Optional breed.
            age: Optional age.
            birthday: Optional birthday.
            weight: Optional weight in kg.
            feeding_schedule: Optional list of daily feeding schedules.
            medical_conditions: Optional list of conditions.
            medications: Optional list of medications.

        Returns:
            The created Pet ORM object.
        """
        db = get_session("mind_db")
        try:
            stmt = select(Pet).where(Pet.name == name)
            pet = db.scalars(stmt).first()
            if pet:
                pet.species = species
                pet.breed = breed
                pet.age = age
                pet.birthday = birthday
                pet.weight = weight
                if feeding_schedule is not None:
                    pet.feeding_schedule = feeding_schedule
                if medical_conditions is not None:
                    pet.medical_conditions = medical_conditions
                if medications is not None:
                    pet.medications = medications
            else:
                pet = Pet(
                    name=name,
                    species=species,
                    breed=breed,
                    age=age,
                    birthday=birthday,
                    weight=weight,
                    feeding_schedule=feeding_schedule or [],
                    medical_conditions=medical_conditions or [],
                    medications=medications or [],
                )
                db.add(pet)
            db.commit()
            db.refresh(pet)

            self.unschedule_reminders(pet.name)
            self.schedule_reminders(pet)

            logger.info("Added/Updated pet profile: %s", name)
            return pet
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_pet(self, name: str) -> Pet | None:
        """Retrieve a pet profile by name.

        Args:
            name: Name of the pet.

        Returns:
            The Pet ORM object or None if not found.
        """
        db = get_session("mind_db")
        try:
            stmt = select(Pet).where(Pet.name == name)
            return db.scalars(stmt).first()
        finally:
            db.close()

    def update_pet(
        self,
        name: str,
        species: str | None = None,
        breed: str | None = None,
        age: float | None = None,
        birthday: str | None = None,
        weight: float | None = None,
        feeding_schedule: list[dict[str, Any]] | None = None,
        medical_conditions: list[str] | None = None,
        medications: list[dict[str, Any]] | None = None,
    ) -> Pet | None:
        """Update an existing pet profile and reschedule reminders.

        Args:
            name: Name of the pet.
            species: Optional species.
            breed: Optional breed.
            age: Optional age.
            birthday: Optional birthday.
            weight: Optional weight.
            feeding_schedule: Optional new feeding schedule.
            medical_conditions: Optional new medical conditions.
            medications: Optional new medications.

        Returns:
            The updated Pet ORM object or None if not found.
        """
        db = get_session("mind_db")
        try:
            stmt = select(Pet).where(Pet.name == name)
            pet = db.scalars(stmt).first()
            if not pet:
                return None

            if species is not None:
                pet.species = species
            if breed is not None:
                pet.breed = breed
            if age is not None:
                pet.age = age
            if birthday is not None:
                pet.birthday = birthday
            if weight is not None:
                pet.weight = weight
            if feeding_schedule is not None:
                pet.feeding_schedule = feeding_schedule
            if medical_conditions is not None:
                pet.medical_conditions = medical_conditions
            if medications is not None:
                pet.medications = medications

            db.commit()
            db.refresh(pet)

            self.unschedule_reminders(pet.name)
            self.schedule_reminders(pet)

            logger.info("Updated pet profile: %s", name)
            return pet
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_pet(self, name: str) -> bool:
        """Delete a pet profile by name and unschedule its reminders.

        Args:
            name: Name of the pet to delete.

        Returns:
            True if deleted, False if not found.
        """
        db = get_session("mind_db")
        try:
            stmt = select(Pet).where(Pet.name == name)
            pet = db.scalars(stmt).first()
            if not pet:
                return False
            db.delete(pet)
            db.commit()

            self.unschedule_reminders(name)
            logger.info("Deleted pet profile: %s", name)
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_pets(self) -> list[Pet]:
        """List all pet profiles.

        Returns:
            List of Pet ORM objects.
        """
        db = get_session("mind_db")
        try:
            stmt = select(Pet)
            return list(db.scalars(stmt).all())
        finally:
            db.close()

    def feed_pet(self, name: str) -> bool:
        """Record a feeding event for the pet.

        Args:
            name: Name of the pet.

        Returns:
            True if pet was found and feeding was updated.
        """
        db = get_session("mind_db")
        try:
            stmt = select(Pet).where(Pet.name == name)
            pet = db.scalars(stmt).first()
            if not pet:
                return False
            pet.last_fed = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
            logger.info("Pet %s recorded as fed.", name)
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def schedule_reminders(self, pet: Pet) -> None:
        """Schedule feeding reminders in APScheduler based on pet's schedule.

        Args:
            pet: The Pet ORM object.
        """
        scheduler = get_scheduler()
        if not scheduler.running:
            scheduler.start()

        for idx, entry in enumerate(pet.feeding_schedule):
            time_str = entry.get("time")
            amount = entry.get("amount", "standard amount")
            if not time_str:
                continue

            try:
                hour, minute = map(int, time_str.split(":"))
                job_id = f"pet_feed_{pet.name}_{idx}"
                scheduler.add_job(
                    _fire_feeding_reminder,
                    "cron",
                    hour=hour,
                    minute=minute,
                    args=[pet.name, time_str, amount],
                    id=job_id,
                    replace_existing=True,
                )
                logger.info(
                    "Scheduled feeding job '%s' for %s at %02d:%02d",
                    job_id,
                    pet.name,
                    hour,
                    minute,
                )
            except Exception as e:
                logger.error(
                    "Failed to schedule feeding job for %s at %s: %s",
                    pet.name,
                    time_str,
                    e,
                )

    def unschedule_reminders(self, pet_name: str) -> None:
        """Remove all scheduled feeding reminders for a specific pet.

        Args:
            pet_name: Name of the pet.
        """
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        prefix = f"pet_feed_{pet_name}_"
        for job in jobs:
            if job.id.startswith(prefix):
                try:
                    scheduler.remove_job(job.id)
                    logger.info("Removed scheduled job '%s'", job.id)
                except Exception as e:
                    logger.error("Failed to remove job %s: %s", job.id, e)

    def sync_all_reminders(self) -> None:
        """Synchronize all pet feeding schedules from the database to APScheduler."""
        db = get_session("mind_db")
        try:
            stmt = select(Pet)
            pets = db.scalars(stmt).all()
            for pet in pets:
                self.unschedule_reminders(pet.name)
                self.schedule_reminders(pet)
            logger.info("Synchronized feeding reminders for all pets.")
        finally:
            db.close()
