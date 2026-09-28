import subprocess
from google.cloud import firestore
from google.oauth2.credentials import Credentials

FIRESTORE_PROJECT_ID = "qwiklabs-gcp-01-8d42beb94564"


def get_firestore_client():
    try:
        token = (
            subprocess.check_output(["gcloud", "auth", "print-access-token"])
            .decode()
            .strip()
        )
        creds = Credentials(token)
        return firestore.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
    except Exception:
        return firestore.Client(project=FIRESTORE_PROJECT_ID)


def seed_database():
    print(f"Connecting to Firestore for project: {FIRESTORE_PROJECT_ID}...")
    db = get_firestore_client()

    # Seed pantry collection
    pantry_items = [
        {
            "id": "pantry_1",
            "name": "Tomatoes",
            "quantity": "4 items",
            "category": "Produce",
            "expiry": "2026-10-05",
        },
        {
            "id": "pantry_2",
            "name": "Pasta",
            "quantity": "500g",
            "category": "Pantry",
            "expiry": "2027-01-01",
        },
        {
            "id": "pantry_3",
            "name": "Olive Oil",
            "quantity": "1 bottle",
            "category": "Pantry",
            "expiry": "2027-06-01",
        },
        {
            "id": "pantry_4",
            "name": "Garlic",
            "quantity": "1 bulb",
            "category": "Produce",
            "expiry": "2026-10-12",
        },
    ]

    for item in pantry_items:
        doc_ref = db.collection("pantry").document(item["id"])
        doc_ref.set(item)
        print(f"Seeded pantry item: {item['name']}")

    # Seed recipes collection
    recipes = [
        {
            "id": "recipe_1",
            "title": "Garlic Tomato Pasta",
            "ingredients": ["Tomatoes", "Pasta", "Olive Oil", "Garlic"],
            "prep_time": "20 mins",
            "instructions": "Boil pasta. Sauté garlic and tomatoes in olive oil. Combine and serve warm.",
        },
        {
            "id": "recipe_2",
            "title": "Fresh Tomato Salad",
            "ingredients": ["Tomatoes", "Olive Oil"],
            "prep_time": "5 mins",
            "instructions": "Slice fresh tomatoes, drizzle with olive oil, season with salt and pepper.",
        },
    ]

    for recipe in recipes:
        doc_ref = db.collection("recipes").document(recipe["id"])
        doc_ref.set(recipe)
        print(f"Seeded recipe: {recipe['title']}")

    print("Firestore database seeding completed successfully!")


if __name__ == "__main__":
    seed_database()
